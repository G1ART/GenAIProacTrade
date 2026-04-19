"""AGH v1 Patch 3 — registry_patch_executor artifact_promotion path tests.

Covers the operator-approved registry_entry active<->challenger swap:

    * approve happy path with ``supabase_client=None`` (carry-over refresh +
      stale-flag on rows + recent_governed_applies append + applied packet +
      SpectrumRefreshRecordV1 + proposal -> applied)
    * approve happy path with monkey-patched fetch_joined/build_spectrum_rows
      (refresh outcome=recomputed, rows fully replaced, needs_db_rebuild=False)
    * active_artifact_id mismatch -> conflict_skip, bundle unchanged
    * challenger set mismatch -> conflict_skip, bundle unchanged
    * to_active_artifact_id missing -> retryable=False DLQ, no mutation
    * to_active_artifact_id horizon mismatch -> retryable=False DLQ
    * recent_governed_applies FIFO cap (cap=20; 21st apply evicts oldest)
    * bundle integrity failure -> retryable=False DLQ, no bundle write,
      no applied / refresh packet
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agentic_harness.agents.layer4_registry_patch_executor import (
    RECENT_GOVERNED_APPLIES_CAP,
    registry_patch_executor,
)
from agentic_harness.contracts.packets_v1 import (
    RegistryDecisionPacketV1,
    RegistryUpdateProposalV1,
    deterministic_packet_id,
)
from agentic_harness.store import FixtureHarnessStore
from agentic_harness.store.protocol import now_utc_iso


def _artifact(aid: str, horizon: str = "short") -> dict:
    return {
        "artifact_id": aid,
        "created_at": "2026-04-19T00:00:00+00:00",
        "created_by": "artifact_from_validation_v1",
        "horizon": horizon,
        "universe": "large_cap_research_slice_demo_v0",
        "sector_scope": "multi_sector_v0",
        "thesis_family": f"factor_demo_{aid}_v0",
        "feature_set": "factor:demo_factor",
        "feature_transforms": "identity_v0",
        "weighting_rule": "equal_weight:v0",
        "score_formula": "rank_position_from_spearman_and_quantile:v0",
        "banding_rule": "quintile_from_factor_rank:v0",
        "ranking_direction": "higher_more_stretched:v0",
        "invalidation_conditions": "pit_or_coverage_or_monotonicity_fail:v0",
        "expected_holding_horizon": horizon,
        "confidence_rule": "band_from_valid_rows:v0",
        "evidence_requirements": "validation_pointer_required:v0",
        "validation_pointer": f"factor_validation_run:run_{aid}:demo_factor:raw",
        "replay_eligibility": "eligible_when_lineage_present:v0",
        "notes_for_message_layer": f"aid={aid};horizon={horizon}",
    }


def _gate(aid: str, *, challenger: bool = False) -> dict:
    return {
        "artifact_id": aid,
        "evaluation_run_id": f"eval_{aid}",
        "pit_pass": True,
        "coverage_pass": True,
        "monotonicity_pass": True,
        "regime_notes": "",
        "sector_override_notes": "",
        "challenger_or_active": "challenger" if challenger else "active",
        "approved_by_rule": "governed_test_gate",
        "approved_at": "2026-04-19T00:00:00+00:00",
        "supersedes_registry_entry": "",
        "reasons": "",
        "expiry_or_recheck_rule": "recheck_on_next_artifact_drop:v0",
    }


def _row(aid: str, pos: float) -> dict:
    return {
        "asset_id": aid,
        "spectrum_position": pos,
        "valuation_tension": "compressed" if pos < 0.5 else "stretched",
        "rationale_summary": {"ko": "테스트", "en": "test"},
        "confidence_band": "medium",
    }


def _write_bundle(
    path: Path,
    *,
    active_id: str = "art_active_v0",
    challenger_id: str = "art_challenger_v0",
    horizon: str = "short",
    row_asset_ids: tuple[str, ...] = ("AAA", "BBB", "CCC"),
) -> dict:
    bundle = {
        "schema_version": 1,
        "as_of_utc": "2026-04-19T00:00:00+00:00",
        "price_layer_note": "",
        "artifacts": [
            _artifact(active_id, horizon),
            _artifact(challenger_id, horizon),
        ],
        "promotion_gates": [
            _gate(active_id),
            _gate(challenger_id, challenger=True),
        ],
        "registry_entries": [
            {
                "registry_entry_id": "reg_short_demo_v0",
                "horizon": horizon,
                "active_model_family_name": "shallow_value_blend_v0",
                "active_artifact_id": active_id,
                "challenger_artifact_ids": [challenger_id],
                "universe": "large_cap_research_slice_demo_v0",
                "sector_scope": "multi_sector_v0",
                "effective_from": "2026-04-01T00:00:00+00:00",
                "effective_to": "",
                "scoring_endpoint_contract": "inline_spectrum_rows_v0",
                "message_contract_version": "v1",
                "replay_lineage_pointer": "lineage:registry:short:demo_v0",
                "status": "active",
            }
        ],
        "spectrum_rows_by_horizon": {
            horizon: [
                _row(aid, 0.1 + 0.15 * i) for i, aid in enumerate(row_asset_ids)
            ],
        },
        "horizon_provenance": {horizon: {"source": "real_derived"}},
    }
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return bundle


@pytest.fixture
def bundle_path(tmp_path, monkeypatch):
    p = tmp_path / "bundle.json"
    _write_bundle(p)
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(p))
    monkeypatch.setenv("METIS_REPO_ROOT", str(tmp_path))
    return p


def _seed_proposal(
    store,
    *,
    registry_entry_id: str = "reg_short_demo_v0",
    horizon: str = "short",
    from_active: str = "art_active_v0",
    to_active: str = "art_challenger_v0",
    from_challengers: list | None = None,
    to_challengers: list | None = None,
) -> str:
    from_challengers = (
        [to_active] if from_challengers is None else list(from_challengers)
    )
    to_challengers = (
        [from_active] if to_challengers is None else list(to_challengers)
    )
    pid = deterministic_packet_id(
        packet_type="RegistryUpdateProposalV1",
        created_by_agent="promotion_arbiter_agent",
        target_scope={
            "registry_entry_id": registry_entry_id,
            "horizon": horizon,
            "from_active": from_active,
            "to_active": to_active,
        },
    )
    proposal = RegistryUpdateProposalV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "RegistryUpdateProposalV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_arbiter_agent",
            "target_scope": {
                "registry_entry_id": registry_entry_id,
                "horizon": horizon,
            },
            "provenance_refs": ["packet:pkt_gate_demo"],
            "confidence": 0.9,
            "status": "escalated",
            "payload": {
                "target": "registry_entry_artifact_promotion",
                "registry_entry_id": registry_entry_id,
                "horizon": horizon,
                "from_active_artifact_id": from_active,
                "to_active_artifact_id": to_active,
                "from_challenger_artifact_ids": from_challengers,
                "to_challenger_artifact_ids": to_challengers,
                "evidence_refs": ["packet:pkt_gate_demo"],
            },
        }
    )
    store.upsert_packet(proposal.model_dump())
    return proposal.packet_id


def _seed_approve_decision(store, proposal_id: str) -> str:
    did = deterministic_packet_id(
        packet_type="RegistryDecisionPacketV1",
        created_by_agent="operator:test",
        target_scope={"proposal_packet_id": proposal_id, "action": "approve"},
    )
    decision = RegistryDecisionPacketV1.model_validate(
        {
            "packet_id": did,
            "packet_type": "RegistryDecisionPacketV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "operator:test",
            "target_scope": {"proposal_packet_id": proposal_id, "action": "approve"},
            "provenance_refs": [f"packet:{proposal_id}"],
            "confidence": 1.0,
            "status": "done",
            "payload": {
                "action": "approve",
                "actor": "test",
                "reason": "governed approve for test",
                "decision_at_utc": now_utc_iso(),
                "cited_proposal_packet_id": proposal_id,
            },
        }
    )
    store.upsert_packet(decision.model_dump())
    return decision.packet_id


def test_artifact_promotion_approve_happy_fixture_carry_over(bundle_path):
    store = FixtureHarnessStore()
    pid = _seed_proposal(store)
    did = _seed_approve_decision(store, pid)

    res = registry_patch_executor(store, {"packet_id": pid})

    assert res["ok"] is True
    assert res["outcome"] == "applied"
    assert res["refresh_outcome"] == "carry_over_fixture_fallback"
    assert res["applied_packet_id"]
    assert res["refresh_record_id"]

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    ent = bundle["registry_entries"][0]
    assert ent["active_artifact_id"] == "art_challenger_v0"
    assert ent["challenger_artifact_ids"] == ["art_active_v0"]
    assert ent["last_governed_proposal_packet_id"] == pid
    assert ent["last_governed_decision_packet_id"] == did

    rows = bundle["spectrum_rows_by_horizon"]["short"]
    assert all(r.get("stale_after_active_swap") is True for r in rows)
    assert all(r.get("stale_since_utc") for r in rows)

    tail = bundle["recent_governed_applies"]
    assert len(tail) == 1
    assert tail[0]["target"] == "registry_entry_artifact_promotion"
    assert tail[0]["horizon"] == "short"
    assert tail[0]["from_active_artifact_id"] == "art_active_v0"
    assert tail[0]["to_active_artifact_id"] == "art_challenger_v0"
    assert tail[0]["spectrum_refresh_needs_db_rebuild"] is True

    applied_pkt = store.get_packet(res["applied_packet_id"])
    assert applied_pkt["payload"]["outcome"] == "applied"
    assert applied_pkt["payload"]["target"] == "registry_entry_artifact_promotion"
    assert applied_pkt["payload"]["after_snapshot"]["registry_entry"][
        "active_artifact_id"
    ] == "art_challenger_v0"

    refresh_pkt = store.get_packet(res["refresh_record_id"])
    assert refresh_pkt["payload"]["outcome"] == "carry_over_fixture_fallback"
    assert refresh_pkt["payload"]["needs_db_rebuild"] is True
    assert refresh_pkt["payload"]["cited_applied_packet_id"] == res["applied_packet_id"]
    assert refresh_pkt["payload"]["cited_proposal_packet_id"] == pid
    assert refresh_pkt["payload"]["cited_decision_packet_id"] == did

    assert store.get_packet(pid)["status"] == "applied"


def test_artifact_promotion_approve_happy_mocked_db_recompute(bundle_path, monkeypatch):
    """Monkey-patch fetch_joined + build_spectrum_rows via refresh helper injection."""

    new_rows = [
        {"asset_id": "NEW1", "spectrum_position": 0.2},
        {"asset_id": "NEW2", "spectrum_position": 0.5},
        {"asset_id": "NEW3", "spectrum_position": 0.8},
    ]

    def fake_fetch_joined(client, spec):
        return {
            "ok": True,
            "run_id": "run_mock_v1",
            "summary_row": {
                "spearman_rank_corr": 0.2,
                "sample_count": 100,
                "valid_factor_count": 80,
                "pit_pass": True,
            },
            "quantile_rows": [],
            "joined_rows": [],
        }

    def fake_build_rows(*, factor_name, horizon_type, summary_row, joined_rows, max_rows=None):
        return "short", [dict(r) for r in new_rows]

    import agentic_harness.agents.layer4_spectrum_refresh_v1 as srmod
    import agentic_harness.agents.layer4_registry_patch_executor as exmod

    real_refresh = srmod.refresh_spectrum_rows_for_horizon

    def patched_refresh(bundle_dict, **kwargs):
        kwargs["supabase_client"] = object()  # force DB branch
        kwargs["fetch_joined"] = fake_fetch_joined
        kwargs["build_spectrum_rows"] = fake_build_rows
        return real_refresh(bundle_dict, **kwargs)

    monkeypatch.setattr(exmod, "refresh_spectrum_rows_for_horizon", patched_refresh)

    store = FixtureHarnessStore()
    pid = _seed_proposal(store)
    _seed_approve_decision(store, pid)

    res = registry_patch_executor(store, {"packet_id": pid})

    assert res["ok"] is True
    assert res["outcome"] == "applied"
    assert res["refresh_outcome"] == "recomputed"

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    rows = bundle["spectrum_rows_by_horizon"]["short"]
    assert [r["asset_id"] for r in rows] == ["NEW1", "NEW2", "NEW3"]
    assert all("stale_after_active_swap" not in r for r in rows)

    refresh_pkt = store.get_packet(res["refresh_record_id"])
    assert refresh_pkt["payload"]["outcome"] == "recomputed"
    assert refresh_pkt["payload"]["refresh_mode"] == "full_recompute_from_validation"
    assert refresh_pkt["payload"]["needs_db_rebuild"] is False


def test_active_mismatch_yields_conflict_skip(bundle_path):
    store = FixtureHarnessStore()
    pid = _seed_proposal(
        store,
        from_active="art_unrelated_v0",
        to_active="art_challenger_v0",
        from_challengers=[],
        to_challengers=[],
    )
    _seed_approve_decision(store, pid)

    before_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    res = registry_patch_executor(store, {"packet_id": pid})

    assert res["ok"] is True
    assert res["outcome"] == "conflict_skip"
    after_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert after_bundle == before_bundle  # bundle must be unchanged

    applied_pkt = store.get_packet(res["applied_packet_id"])
    assert applied_pkt["payload"]["outcome"] == "conflict_skip"
    assert applied_pkt["payload"]["after_snapshot"] == {}
    assert any(
        "active_mismatch" in r
        for r in applied_pkt.get("blocking_reasons") or []
    )

    assert store.get_packet(pid)["status"] == "deferred"


def test_challenger_mismatch_yields_conflict_skip(bundle_path):
    store = FixtureHarnessStore()
    pid = _seed_proposal(
        store,
        from_challengers=["art_unrelated_v0"],
        to_challengers=["art_active_v0"],
    )
    _seed_approve_decision(store, pid)

    before_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    res = registry_patch_executor(store, {"packet_id": pid})

    assert res["outcome"] == "conflict_skip"
    assert json.loads(bundle_path.read_text(encoding="utf-8")) == before_bundle
    assert store.get_packet(pid)["status"] == "deferred"


def test_to_active_missing_in_bundle_artifacts_goes_dlq(bundle_path):
    store = FixtureHarnessStore()
    pid = _seed_proposal(
        store,
        to_active="art_not_in_bundle_v0",
        from_challengers=["art_challenger_v0"],
        to_challengers=[],
    )
    _seed_approve_decision(store, pid)

    before_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    res = registry_patch_executor(store, {"packet_id": pid})

    assert res["ok"] is False
    assert res["retryable"] is False
    assert "to_active_artifact_missing" in res["error"]
    assert json.loads(bundle_path.read_text(encoding="utf-8")) == before_bundle
    # proposal still escalated (not mutated by DLQ path).
    assert store.get_packet(pid)["status"] == "escalated"


def test_to_active_horizon_mismatch_goes_dlq(tmp_path, monkeypatch):
    p = tmp_path / "bundle.json"
    bundle = _write_bundle(p)
    # Add a long-horizon artifact and ask to promote to it on the short
    # registry entry; this should be rejected as horizon_mismatch.
    bundle["artifacts"].append(_artifact("art_long_v0", horizon="long"))
    bundle["promotion_gates"].append(_gate("art_long_v0", challenger=True))
    p.write_text(json.dumps(bundle), encoding="utf-8")
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(p))
    monkeypatch.setenv("METIS_REPO_ROOT", str(tmp_path))

    store = FixtureHarnessStore()
    pid = _seed_proposal(
        store,
        to_active="art_long_v0",
        from_challengers=["art_challenger_v0"],
        to_challengers=[],
    )
    _seed_approve_decision(store, pid)

    before = p.read_text(encoding="utf-8")
    res = registry_patch_executor(store, {"packet_id": pid})

    assert res["ok"] is False
    assert res["retryable"] is False
    assert "horizon_mismatch" in res["error"]
    assert p.read_text(encoding="utf-8") == before


def test_recent_governed_applies_fifo_cap(tmp_path, monkeypatch):
    p = tmp_path / "bundle.json"
    _write_bundle(p)
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(p))
    monkeypatch.setenv("METIS_REPO_ROOT", str(tmp_path))

    # Pre-seed the bundle with 20 governed apply events already.
    bundle = json.loads(p.read_text(encoding="utf-8"))
    bundle["recent_governed_applies"] = [
        {
            "target": "registry_entry_artifact_promotion",
            "horizon": "short",
            "registry_entry_id": "reg_short_demo_v0",
            "proposal_packet_id": f"pkt_prior_{i}",
            "decision_packet_id": f"dec_prior_{i}",
            "from_active_artifact_id": "art_active_v0",
            "to_active_artifact_id": "art_challenger_v0",
            "applied_at_utc": f"2026-04-18T0{i%10}:00:00+00:00",
            "spectrum_refresh_outcome": "carry_over_fixture_fallback",
            "spectrum_refresh_needs_db_rebuild": True,
        }
        for i in range(RECENT_GOVERNED_APPLIES_CAP)
    ]
    p.write_text(json.dumps(bundle), encoding="utf-8")

    store = FixtureHarnessStore()
    pid = _seed_proposal(store)
    _seed_approve_decision(store, pid)

    res = registry_patch_executor(store, {"packet_id": pid})
    assert res["outcome"] == "applied"

    after = json.loads(p.read_text(encoding="utf-8"))
    tail = after["recent_governed_applies"]
    assert len(tail) == RECENT_GOVERNED_APPLIES_CAP
    # Oldest (pkt_prior_0) was evicted.
    assert all(e.get("proposal_packet_id") != "pkt_prior_0" for e in tail)
    assert tail[-1]["proposal_packet_id"] == pid


def test_bundle_integrity_failure_prevents_write_and_packets(tmp_path, monkeypatch):
    p = tmp_path / "bundle.json"
    bundle = _write_bundle(p)
    # Break the challenger's promotion gate so validate_merged_bundle_dict
    # fails after the active/challenger swap.
    for g in bundle["promotion_gates"]:
        if g["artifact_id"] == "art_challenger_v0":
            g["pit_pass"] = False
            g["approved_by_rule"] = ""
    p.write_text(json.dumps(bundle), encoding="utf-8")
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(p))
    monkeypatch.setenv("METIS_REPO_ROOT", str(tmp_path))

    store = FixtureHarnessStore()
    pid = _seed_proposal(store)
    _seed_approve_decision(store, pid)

    before = p.read_text(encoding="utf-8")
    res = registry_patch_executor(store, {"packet_id": pid})

    assert res["ok"] is False
    assert res["retryable"] is False
    assert "bundle_integrity_failed" in res["error"]
    assert p.read_text(encoding="utf-8") == before  # no write
    # Neither applied nor refresh packet should exist.
    applied_rows = store.list_packets(
        packet_type="RegistryPatchAppliedPacketV1", limit=50
    )
    refresh_rows = store.list_packets(
        packet_type="SpectrumRefreshRecordV1", limit=50
    )
    assert applied_rows == []
    assert refresh_rows == []
    # Proposal remains escalated (not applied, not deferred).
    assert store.get_packet(pid)["status"] == "escalated"
