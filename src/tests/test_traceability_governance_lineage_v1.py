"""AGH v1 Patch 3 — api_governance_lineage_for_registry_entry contract tests.

Replay / Traceability must be able to reconstruct the four-link chain
(proposal -> decision -> applied -> spectrum_refresh) for any registered
governed ``registry_entry_artifact_promotion`` apply. The packets live in a
harness store and are joined via ``cited_proposal_packet_id`` /
``cited_applied_packet_id``. This test exercises:

    * newest-first ordering by ``created_at_utc``
    * horizon filter (cross-horizon proposals excluded)
    * summary counts and ``latest_applied_needs_db_rebuild`` picking up the
      refresh carry-over flag
    * horizon_provenance proposals with a matching registry_entry_id in
      ``target_scope`` also appear in the chain (Patch 2 interop)
"""

from __future__ import annotations

from phase47_runtime.traceability_replay import (
    api_governance_lineage_for_registry_entry,
)
from agentic_harness.store import FixtureHarnessStore


def _proposal(
    *,
    packet_id: str,
    registry_entry_id: str,
    horizon: str,
    created_at_utc: str,
    target: str = "registry_entry_artifact_promotion",
) -> dict:
    return {
        "packet_id": packet_id,
        "packet_type": "RegistryUpdateProposalV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "promotion_arbiter_agent",
        "created_at_utc": created_at_utc,
        "target_scope": {
            "registry_entry_id": registry_entry_id,
            "horizon": horizon,
        },
        "provenance_refs": ["packet:pkt_evidence"],
        "confidence": 0.9,
        "status": "applied" if target == "registry_entry_artifact_promotion" else "done",
        "payload": {
            "target": target,
            "registry_entry_id": registry_entry_id,
            "horizon": horizon,
            "from_active_artifact_id": "art_active_v0",
            "to_active_artifact_id": "art_challenger_v0",
            "from_challenger_artifact_ids": ["art_challenger_v0"],
            "to_challenger_artifact_ids": ["art_active_v0"],
            "evidence_refs": ["packet:pkt_evidence"],
        }
        if target == "registry_entry_artifact_promotion"
        else {
            "target": "horizon_provenance",
            "horizon": horizon,
            "from_source": "seed_fixture",
            "to_source": "real_derived",
            "evidence_refs": ["packet:pkt_evidence"],
        },
    }


def _decision(*, packet_id: str, proposal_id: str, created_at_utc: str) -> dict:
    return {
        "packet_id": packet_id,
        "packet_type": "RegistryDecisionPacketV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "operator:test",
        "created_at_utc": created_at_utc,
        "target_scope": {
            "proposal_packet_id": proposal_id,
            "action": "approve",
        },
        "provenance_refs": [f"packet:{proposal_id}"],
        "confidence": 1.0,
        "status": "done",
        "payload": {
            "action": "approve",
            "actor": "test",
            "reason": "approve for lineage test",
            "decision_at_utc": created_at_utc,
            "cited_proposal_packet_id": proposal_id,
        },
    }


def _applied(
    *,
    packet_id: str,
    proposal_id: str,
    decision_id: str,
    registry_entry_id: str,
    horizon: str,
    created_at_utc: str,
) -> dict:
    return {
        "packet_id": packet_id,
        "packet_type": "RegistryPatchAppliedPacketV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "registry_patch_executor",
        "created_at_utc": created_at_utc,
        "target_scope": {"proposal_packet_id": proposal_id},
        "provenance_refs": [f"packet:{proposal_id}", f"packet:{decision_id}"],
        "confidence": 1.0,
        "status": "done",
        "payload": {
            "target": "registry_entry_artifact_promotion",
            "registry_entry_id": registry_entry_id,
            "horizon": horizon,
            "outcome": "applied",
            "cited_proposal_packet_id": proposal_id,
            "cited_decision_packet_id": decision_id,
            "applied_at_utc": created_at_utc,
            "bundle_path": "/tmp/bundle.json",
            "bundle_write_mode": "atomic_replace",
            "before_snapshot": {},
            "after_snapshot": {},
        },
    }


def _refresh(
    *,
    packet_id: str,
    applied_id: str,
    proposal_id: str,
    decision_id: str,
    registry_entry_id: str,
    horizon: str,
    created_at_utc: str,
    outcome: str = "carry_over_fixture_fallback",
    needs_db_rebuild: bool = True,
) -> dict:
    return {
        "packet_id": packet_id,
        "packet_type": "SpectrumRefreshRecordV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "registry_patch_executor",
        "created_at_utc": created_at_utc,
        "target_scope": {"applied_packet_id": applied_id},
        "provenance_refs": [f"packet:{applied_id}"],
        "confidence": 1.0,
        "status": "done",
        "payload": {
            "horizon": horizon,
            "registry_entry_id": registry_entry_id,
            "outcome": outcome,
            "refresh_mode": "fixture_fallback" if needs_db_rebuild else "full_recompute_from_validation",
            "needs_db_rebuild": needs_db_rebuild,
            "cited_applied_packet_id": applied_id,
            "cited_proposal_packet_id": proposal_id,
            "cited_decision_packet_id": decision_id,
            "refreshed_at_utc": created_at_utc,
            "bundle_path": "/tmp/bundle.json",
            "before_row_count": 3,
            "after_row_count": 3,
            "before_row_asset_ids_sample": ["A", "B", "C"],
            "after_row_asset_ids_sample": ["A", "B", "C"],
            "blocking_reasons": [],
        },
    }


def _seed_full_chain(
    store,
    *,
    registry_entry_id: str,
    horizon: str,
    nonce: str,
    created_at_utc: str,
    needs_db_rebuild: bool = True,
    outcome: str = "carry_over_fixture_fallback",
) -> tuple[str, str, str, str]:
    pid = f"pkt_prop_{nonce}"
    did = f"pkt_dec_{nonce}"
    aid = f"pkt_app_{nonce}"
    rid = f"pkt_ref_{nonce}"
    store.upsert_packet(
        _proposal(
            packet_id=pid,
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            created_at_utc=created_at_utc,
        )
    )
    store.upsert_packet(_decision(packet_id=did, proposal_id=pid, created_at_utc=created_at_utc))
    store.upsert_packet(
        _applied(
            packet_id=aid,
            proposal_id=pid,
            decision_id=did,
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            created_at_utc=created_at_utc,
        )
    )
    store.upsert_packet(
        _refresh(
            packet_id=rid,
            applied_id=aid,
            proposal_id=pid,
            decision_id=did,
            registry_entry_id=registry_entry_id,
            horizon=horizon,
            created_at_utc=created_at_utc,
            outcome=outcome,
            needs_db_rebuild=needs_db_rebuild,
        )
    )
    return pid, did, aid, rid


def test_governance_lineage_builds_full_chain_newest_first():
    store = FixtureHarnessStore()
    _seed_full_chain(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        nonce="a",
        created_at_utc="2026-04-18T08:00:00+00:00",
    )
    # Latest apply: recomputed (needs_db_rebuild=False).
    _seed_full_chain(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        nonce="b",
        created_at_utc="2026-04-19T09:00:00+00:00",
        needs_db_rebuild=False,
        outcome="recomputed",
    )

    res = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
    )

    assert res["ok"] is True
    chain = res["chain"]
    assert len(chain) == 2
    assert chain[0]["proposal"]["packet_id"] == "pkt_prop_b"  # newest first
    assert chain[1]["proposal"]["packet_id"] == "pkt_prop_a"
    for link in chain:
        assert link["decision"] is not None
        assert link["applied"] is not None
        assert link["spectrum_refresh"] is not None

    summary = res["summary"]
    assert summary["total_proposals"] == 2
    assert summary["total_applied"] == 2
    assert summary["total_spectrum_refreshed"] == 2
    assert summary["latest_applied_packet_id"] == "pkt_app_b"
    assert summary["latest_applied_needs_db_rebuild"] is False


def test_governance_lineage_filters_by_horizon_and_registry_entry():
    store = FixtureHarnessStore()
    _seed_full_chain(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        nonce="short1",
        created_at_utc="2026-04-19T00:00:00+00:00",
    )
    _seed_full_chain(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="medium",
        nonce="medium1",
        created_at_utc="2026-04-19T01:00:00+00:00",
    )
    _seed_full_chain(
        store,
        registry_entry_id="reg_long_other_v0",
        horizon="short",
        nonce="other1",
        created_at_utc="2026-04-19T02:00:00+00:00",
    )

    res = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
    )

    assert res["ok"] is True
    assert len(res["chain"]) == 1
    assert (
        res["chain"][0]["proposal"]["payload"]["registry_entry_id"]
        == "reg_short_demo_v0"
    )
    assert res["chain"][0]["proposal"]["payload"]["horizon"] == "short"


def test_governance_lineage_includes_horizon_provenance_proposals():
    store = FixtureHarnessStore()
    # horizon_provenance proposal — older Patch 2 target.
    prov_pid = "pkt_prop_prov_1"
    store.upsert_packet(
        _proposal(
            packet_id=prov_pid,
            registry_entry_id="reg_short_demo_v0",
            horizon="short",
            created_at_utc="2026-04-17T00:00:00+00:00",
            target="horizon_provenance",
        )
    )
    store.upsert_packet(
        _decision(
            packet_id="pkt_dec_prov_1",
            proposal_id=prov_pid,
            created_at_utc="2026-04-17T00:05:00+00:00",
        )
    )

    # Artifact promotion proposal — Patch 3 target.
    _seed_full_chain(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        nonce="art1",
        created_at_utc="2026-04-19T00:00:00+00:00",
    )

    res = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
    )

    assert res["ok"] is True
    assert len(res["chain"]) == 2
    # newest first: artifact promotion then horizon_provenance.
    targets = [c["proposal"]["payload"]["target"] for c in res["chain"]]
    assert targets == [
        "registry_entry_artifact_promotion",
        "horizon_provenance",
    ]
    # horizon_provenance has no applied/refresh packet in this test.
    assert res["chain"][1]["applied"] is None
    assert res["chain"][1]["spectrum_refresh"] is None


def test_governance_lineage_rejects_missing_registry_entry_id():
    store = FixtureHarnessStore()
    res = api_governance_lineage_for_registry_entry(
        store, registry_entry_id="", horizon="short"
    )
    assert res["ok"] is False
    assert "registry_entry_id" in (res.get("error") or "")


# ---------------------------------------------------------------------------
# AGH v1 Patch 4 - validation -> governance evaluator chain extension
# ---------------------------------------------------------------------------


def _evaluation_packet(
    *,
    packet_id: str,
    registry_entry_id: str,
    horizon: str,
    outcome: str,
    created_at_utc: str,
    emitted_proposal_packet_id: str | None = None,
    blocking_reasons: list[str] | None = None,
    gate_verdict: str = "promote",
    artifact_action: str = "added_challenger",
) -> dict:
    payload = {
        "evaluation_id": f"eval_{packet_id}",
        "factor_name": "demo_factor",
        "universe_name": "large_cap_research_slice_demo_v0",
        "horizon_type": "next_month",
        "return_basis": "raw",
        "validation_run_id": f"run_{packet_id}",
        "validation_pointer": f"factor_validation_run:run_{packet_id}",
        "registry_entry_id": registry_entry_id,
        "horizon": horizon,
        "derived_artifact_id": f"art_derived_{packet_id}",
        "artifact_action": artifact_action,
        "gate_verdict": gate_verdict,
        "gate_metrics": {
            "pit_pass": True,
            "coverage_pass": True,
            "monotonicity_pass": True,
        },
        "outcome": outcome,
        "evidence_refs": [f"factor_validation_run:run_{packet_id}"],
        "emitted_proposal_packet_id": emitted_proposal_packet_id,
    }
    return {
        "packet_id": packet_id,
        "packet_type": "ValidationPromotionEvaluationV1",
        "target_layer": "layer4_governance",
        "created_by_agent": "promotion_evaluator_v1",
        "created_at_utc": created_at_utc,
        "target_scope": {
            "evaluation_id": f"eval_{packet_id}",
            "registry_entry_id": registry_entry_id,
            "horizon": horizon,
        },
        "provenance_refs": [f"factor_validation_run:run_{packet_id}"],
        "confidence": 0.9,
        "blocking_reasons": list(blocking_reasons or []),
        "status": "done",
        "payload": payload,
    }


def test_governance_lineage_includes_validation_promotion_evaluations():
    store = FixtureHarnessStore()
    pid, did, aid, rid = _seed_full_chain(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        nonce="p4a",
        created_at_utc="2026-04-19T10:00:00+00:00",
    )
    # Evaluator emitted its audit packet that cites the proposal just seeded.
    store.upsert_packet(
        _evaluation_packet(
            packet_id="pkt_eval_p4a",
            registry_entry_id="reg_short_demo_v0",
            horizon="short",
            outcome="proposal_emitted",
            created_at_utc="2026-04-19T09:59:00+00:00",
            emitted_proposal_packet_id=pid,
        )
    )
    # An older blocked evaluation (no proposal) - must still surface in the
    # validation_promotion_evaluations flat list.
    store.upsert_packet(
        _evaluation_packet(
            packet_id="pkt_eval_blocked",
            registry_entry_id="reg_short_demo_v0",
            horizon="short",
            outcome="blocked_by_gate",
            gate_verdict="reject",
            artifact_action="no_change",
            created_at_utc="2026-04-18T09:00:00+00:00",
            emitted_proposal_packet_id=None,
            blocking_reasons=["pit_failed"],
        )
    )

    res = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
    )

    assert res["ok"] is True
    assert len(res["chain"]) == 1
    link = res["chain"][0]
    assert link["validation_promotion_evaluation"] is not None
    assert link["validation_promotion_evaluation"]["packet_id"] == "pkt_eval_p4a"

    assert len(res["validation_promotion_evaluations"]) == 2
    # Newest first.
    assert res["validation_promotion_evaluations"][0]["packet_id"] == "pkt_eval_p4a"
    assert (
        res["validation_promotion_evaluations"][1]["packet_id"] == "pkt_eval_blocked"
    )
    assert res["summary"]["total_evaluations"] == 2
    assert res["summary"]["total_emitted_from_evaluator"] == 1
