"""AGH v1 Patch 3 - artifact promotion bridge closure runbook.

Exercises the five operator-visible decision paths for the new
``registry_entry_artifact_promotion`` target, each against a tmp brain bundle
via the in-process ``FixtureHarnessStore``. Captures before/after snapshots as
the Patch 3 "g-runbook" evidence:

    1. approve(carry-over)   supabase_client=None -> carry_over_fixture_fallback
    2. approve(recompute)    monkey-patched fetch_joined + build_spectrum_rows
                             -> recomputed (rows swapped, needs_db_rebuild=False)
    3. reject                proposal.status=rejected, bundle unchanged
    4. defer                 proposal.status=deferred with next_revisit_hint_utc
    5. conflict_skip         from_active mismatch -> applied.outcome=conflict_skip

Writes the payload to
``data/mvp/evidence/agentic_operating_harness_v1_milestone_14_artifact_promotion_bridge_runbook_evidence.json``.
This is not a unit test; it is an operator-auditable dry run that proves the
artifact promotion bridge closes end-to-end without touching the production
brain bundle or any Supabase rows.

Invariants (work-order §2 / §3 / §6):
    * No direct bundle write outside the ``registry_patch_executor`` atomic path.
    * ``refresh_spectrum_rows_for_horizon`` is the only path that mutates
      ``spectrum_rows_by_horizon`` for a governed apply; it is called before
      the single atomic write.
    * ``recent_governed_applies`` is appended only on outcome=applied; its cap
      is 20 and today surfaces the top 5 per horizon.
    * Reject / defer / conflict_skip must leave the registry entry's
      ``active_artifact_id`` / ``challenger_artifact_ids`` untouched.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


from agentic_harness import runtime  # noqa: E402
from agentic_harness.agents.layer4_governance import record_registry_decision  # noqa: E402
from agentic_harness.contracts.packets_v1 import (  # noqa: E402
    RegistryUpdateProposalV1,
    deterministic_packet_id,
)
from agentic_harness.store import FixtureHarnessStore  # noqa: E402
from agentic_harness.store.protocol import now_utc_iso  # noqa: E402


_ACTIVE_ID = "art_active_v0"
_CHALLENGER_ID = "art_challenger_v0"
_REGISTRY_ENTRY_ID = "reg_short_demo_v0"
_HORIZON = "short"


def _artifact(aid: str, *, horizon: str = _HORIZON) -> dict[str, Any]:
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


def _gate(aid: str, *, challenger: bool = False) -> dict[str, Any]:
    return {
        "artifact_id": aid,
        "evaluation_run_id": f"eval_{aid}",
        "pit_pass": True,
        "coverage_pass": True,
        "monotonicity_pass": True,
        "regime_notes": "",
        "sector_override_notes": "",
        "challenger_or_active": "challenger" if challenger else "active",
        "approved_by_rule": "governed_runbook_gate",
        "approved_at": "2026-04-19T00:00:00+00:00",
        "supersedes_registry_entry": "",
        "reasons": "",
        "expiry_or_recheck_rule": "recheck_on_next_artifact_drop:v0",
    }


def _write_bundle(
    path: Path,
    *,
    active_id: str = _ACTIVE_ID,
    challenger_id: str = _CHALLENGER_ID,
    horizon: str = _HORIZON,
) -> None:
    bundle = {
        "schema_version": 1,
        "as_of_utc": "2026-04-19T00:00:00+00:00",
        "price_layer_note": "",
        "artifacts": [_artifact(active_id, horizon=horizon), _artifact(challenger_id, horizon=horizon)],
        "promotion_gates": [_gate(active_id), _gate(challenger_id, challenger=True)],
        "registry_entries": [
            {
                "registry_entry_id": _REGISTRY_ENTRY_ID,
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
                {"asset_id": "AAA", "spectrum_position": 0.1},
                {"asset_id": "BBB", "spectrum_position": 0.4},
                {"asset_id": "CCC", "spectrum_position": 0.7},
            ]
        },
        "horizon_provenance": {horizon: {"source": "real_derived"}},
    }
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry_entry_view(bundle: dict[str, Any]) -> dict[str, Any]:
    for ent in bundle.get("registry_entries") or []:
        if ent.get("registry_entry_id") == _REGISTRY_ENTRY_ID:
            return {
                "active_artifact_id": ent.get("active_artifact_id"),
                "challenger_artifact_ids": list(ent.get("challenger_artifact_ids") or []),
                "last_governed_proposal_packet_id": ent.get(
                    "last_governed_proposal_packet_id"
                ),
                "last_governed_decision_packet_id": ent.get(
                    "last_governed_decision_packet_id"
                ),
                "last_governed_apply_at_utc": ent.get("last_governed_apply_at_utc"),
            }
    return {}


def _spectrum_view(bundle: dict[str, Any]) -> dict[str, Any]:
    rows = list(bundle.get("spectrum_rows_by_horizon", {}).get(_HORIZON, []))
    return {
        "row_count": len(rows),
        "asset_ids": [r.get("asset_id") for r in rows],
        "stale_after_active_swap_count": sum(
            1 for r in rows if r.get("stale_after_active_swap") is True
        ),
    }


def _recent_view(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "proposal_packet_id": e.get("proposal_packet_id"),
            "applied_packet_id": e.get("applied_packet_id"),
            "from_active_artifact_id": e.get("from_active_artifact_id"),
            "to_active_artifact_id": e.get("to_active_artifact_id"),
            "spectrum_refresh_outcome": e.get("spectrum_refresh_outcome"),
            "spectrum_refresh_needs_db_rebuild": e.get(
                "spectrum_refresh_needs_db_rebuild"
            ),
        }
        for e in bundle.get("recent_governed_applies") or []
    ]


def _seed_proposal(
    store: FixtureHarnessStore,
    *,
    from_active: str = _ACTIVE_ID,
    to_active: str = _CHALLENGER_ID,
    from_challengers: list[str] | None = None,
    to_challengers: list[str] | None = None,
    salt: str = "base",
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
            "registry_entry_id": _REGISTRY_ENTRY_ID,
            "horizon": _HORIZON,
            "from_active": from_active,
            "to_active": to_active,
        },
        salt=salt,
    )
    proposal = RegistryUpdateProposalV1.model_validate(
        {
            "packet_id": pid,
            "packet_type": "RegistryUpdateProposalV1",
            "target_layer": "layer4_governance",
            "created_by_agent": "promotion_arbiter_agent",
            "target_scope": {
                "registry_entry_id": _REGISTRY_ENTRY_ID,
                "horizon": _HORIZON,
            },
            "provenance_refs": [
                f"governance://registry_entry:{_REGISTRY_ENTRY_ID}",
                "packet:pkt_gate_demo",
            ],
            "confidence": 0.9,
            "status": "escalated",
            "payload": {
                "target": "registry_entry_artifact_promotion",
                "registry_entry_id": _REGISTRY_ENTRY_ID,
                "horizon": _HORIZON,
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


def _reset_env(base_dir: Path, bundle_path: Path, store: FixtureHarnessStore) -> None:
    os.environ["METIS_BRAIN_BUNDLE"] = str(bundle_path)
    os.environ["METIS_REPO_ROOT"] = str(base_dir)
    runtime._FIXTURE_STORE = store


def _applied_and_refresh(store: FixtureHarnessStore) -> tuple[dict | None, dict | None]:
    applied = store.list_packets(packet_type="RegistryPatchAppliedPacketV1")
    refresh = store.list_packets(packet_type="SpectrumRefreshRecordV1")
    return (applied[0] if applied else None, refresh[0] if refresh else None)


def _scenario_approve_carry_over(base_dir: Path) -> dict[str, Any]:
    bundle_path = base_dir / "approve_carry_over_bundle.json"
    _write_bundle(bundle_path)
    store = FixtureHarnessStore()
    _reset_env(base_dir, bundle_path, store)
    proposal_id = _seed_proposal(store, salt="approve_carry_over")
    before_bundle = _read_bundle(bundle_path)

    decision_res = runtime.perform_decision(
        proposal_id=proposal_id,
        action="approve",
        actor="ops@example.com",
        reason="runbook-approve carry-over (supabase_client missing)",
        use_fixture=True,
    )
    tick_summary = runtime.perform_tick(use_fixture=True, max_jobs=5)
    after_bundle = _read_bundle(bundle_path)
    applied, refresh = _applied_and_refresh(store)
    proposal_final = store.get_packet(proposal_id)

    return {
        "scenario": "approve_carry_over",
        "expectation": (
            "active/challenger swap; spectrum rows carry-over with "
            "stale_after_active_swap=True; recent_governed_applies += 1; "
            "SpectrumRefreshRecordV1.outcome=carry_over_fixture_fallback; "
            "needs_db_rebuild=True; proposal.status=applied"
        ),
        "proposal_id": proposal_id,
        "decision_result": decision_res,
        "tick_summary_registry_apply_queue": tick_summary.get("queue_runs", {}).get(
            "registry_apply_queue"
        ),
        "before_registry_entry": _registry_entry_view(before_bundle),
        "after_registry_entry": _registry_entry_view(after_bundle),
        "before_spectrum": _spectrum_view(before_bundle),
        "after_spectrum": _spectrum_view(after_bundle),
        "before_recent_governed_applies": _recent_view(before_bundle),
        "after_recent_governed_applies": _recent_view(after_bundle),
        "applied_packet_outcome": (applied or {}).get("payload", {}).get("outcome"),
        "refresh_packet_outcome": (refresh or {}).get("payload", {}).get("outcome"),
        "refresh_packet_needs_db_rebuild": (refresh or {}).get("payload", {}).get(
            "needs_db_rebuild"
        ),
        "proposal_status_after": proposal_final.get("status"),
    }


def _scenario_approve_recompute(base_dir: Path) -> dict[str, Any]:
    bundle_path = base_dir / "approve_recompute_bundle.json"
    _write_bundle(bundle_path)
    store = FixtureHarnessStore()
    _reset_env(base_dir, bundle_path, store)
    proposal_id = _seed_proposal(store, salt="approve_recompute")
    before_bundle = _read_bundle(bundle_path)

    import agentic_harness.agents.layer4_registry_patch_executor as exmod
    import agentic_harness.agents.layer4_spectrum_refresh_v1 as srmod

    def fake_fetch_joined(_client, _spec):
        return {
            "ok": True,
            "run_id": "run_runbook_recompute_v1",
            "summary_row": {
                "spearman_rank_corr": 0.25,
                "sample_count": 120,
                "valid_factor_count": 98,
                "pit_pass": True,
            },
            "quantile_rows": [],
            "joined_rows": [],
        }

    def fake_build_rows(**_kwargs):
        return _HORIZON, [
            {"asset_id": "NEW_A", "spectrum_position": 0.15},
            {"asset_id": "NEW_B", "spectrum_position": 0.45},
            {"asset_id": "NEW_C", "spectrum_position": 0.85},
        ]

    real_refresh = srmod.refresh_spectrum_rows_for_horizon

    def patched_refresh(bundle_dict, **kwargs):
        kwargs["supabase_client"] = object()
        kwargs["fetch_joined"] = fake_fetch_joined
        kwargs["build_spectrum_rows"] = fake_build_rows
        return real_refresh(bundle_dict, **kwargs)

    prev = getattr(exmod, "refresh_spectrum_rows_for_horizon")
    exmod.refresh_spectrum_rows_for_horizon = patched_refresh
    try:
        decision_res = runtime.perform_decision(
            proposal_id=proposal_id,
            action="approve",
            actor="ops@example.com",
            reason="runbook-approve full recompute (mocked fetch_joined)",
            use_fixture=True,
        )
        tick_summary = runtime.perform_tick(use_fixture=True, max_jobs=5)
    finally:
        exmod.refresh_spectrum_rows_for_horizon = prev

    after_bundle = _read_bundle(bundle_path)
    applied, refresh = _applied_and_refresh(store)
    proposal_final = store.get_packet(proposal_id)

    return {
        "scenario": "approve_recompute",
        "expectation": (
            "active/challenger swap; spectrum rows fully recomputed "
            "(no stale_after_active_swap flags); "
            "SpectrumRefreshRecordV1.outcome=recomputed; needs_db_rebuild=False; "
            "proposal.status=applied"
        ),
        "proposal_id": proposal_id,
        "decision_result": decision_res,
        "tick_summary_registry_apply_queue": tick_summary.get("queue_runs", {}).get(
            "registry_apply_queue"
        ),
        "before_registry_entry": _registry_entry_view(before_bundle),
        "after_registry_entry": _registry_entry_view(after_bundle),
        "before_spectrum": _spectrum_view(before_bundle),
        "after_spectrum": _spectrum_view(after_bundle),
        "before_recent_governed_applies": _recent_view(before_bundle),
        "after_recent_governed_applies": _recent_view(after_bundle),
        "applied_packet_outcome": (applied or {}).get("payload", {}).get("outcome"),
        "refresh_packet_outcome": (refresh or {}).get("payload", {}).get("outcome"),
        "refresh_packet_needs_db_rebuild": (refresh or {}).get("payload", {}).get(
            "needs_db_rebuild"
        ),
        "proposal_status_after": proposal_final.get("status"),
    }


def _scenario_reject(base_dir: Path) -> dict[str, Any]:
    bundle_path = base_dir / "reject_bundle.json"
    _write_bundle(bundle_path)
    store = FixtureHarnessStore()
    _reset_env(base_dir, bundle_path, store)
    proposal_id = _seed_proposal(store, salt="reject")
    before_bundle = _read_bundle(bundle_path)

    decision_res = record_registry_decision(
        store,
        proposal_id=proposal_id,
        action="reject",
        actor="ops@example.com",
        reason="runbook-reject: challenger gate not yet robust enough",
        now_iso=now_utc_iso(),
    )
    after_bundle = _read_bundle(bundle_path)
    proposal_final = store.get_packet(proposal_id)

    return {
        "scenario": "reject",
        "expectation": (
            "bundle untouched; no apply job enqueued; proposal.status=rejected; "
            "no SpectrumRefreshRecordV1 emitted; recent_governed_applies unchanged"
        ),
        "proposal_id": proposal_id,
        "decision_result": decision_res,
        "queue_depth_registry_apply_queue": store.queue_depth().get(
            "registry_apply_queue", 0
        ),
        "before_registry_entry": _registry_entry_view(before_bundle),
        "after_registry_entry": _registry_entry_view(after_bundle),
        "before_spectrum": _spectrum_view(before_bundle),
        "after_spectrum": _spectrum_view(after_bundle),
        "before_recent_governed_applies": _recent_view(before_bundle),
        "after_recent_governed_applies": _recent_view(after_bundle),
        "applied_packet_count": len(
            store.list_packets(packet_type="RegistryPatchAppliedPacketV1")
        ),
        "refresh_packet_count": len(
            store.list_packets(packet_type="SpectrumRefreshRecordV1")
        ),
        "proposal_status_after": proposal_final.get("status"),
    }


def _scenario_defer(base_dir: Path) -> dict[str, Any]:
    bundle_path = base_dir / "defer_bundle.json"
    _write_bundle(bundle_path)
    store = FixtureHarnessStore()
    _reset_env(base_dir, bundle_path, store)
    proposal_id = _seed_proposal(store, salt="defer")
    before_bundle = _read_bundle(bundle_path)

    decision_res = record_registry_decision(
        store,
        proposal_id=proposal_id,
        action="defer",
        actor="ops@example.com",
        reason="runbook-defer: wait for next validation window",
        now_iso=now_utc_iso(),
        next_revisit_hint_utc="2026-04-26T00:00:00+00:00",
    )
    after_bundle = _read_bundle(bundle_path)
    proposal_final = store.get_packet(proposal_id)
    decisions = store.list_packets(packet_type="RegistryDecisionPacketV1")

    return {
        "scenario": "defer",
        "expectation": (
            "bundle untouched; proposal.status=deferred; decision packet carries "
            "next_revisit_hint_utc; no SpectrumRefreshRecordV1 emitted"
        ),
        "proposal_id": proposal_id,
        "decision_result": decision_res,
        "queue_depth_registry_apply_queue": store.queue_depth().get(
            "registry_apply_queue", 0
        ),
        "before_registry_entry": _registry_entry_view(before_bundle),
        "after_registry_entry": _registry_entry_view(after_bundle),
        "before_spectrum": _spectrum_view(before_bundle),
        "after_spectrum": _spectrum_view(after_bundle),
        "before_recent_governed_applies": _recent_view(before_bundle),
        "after_recent_governed_applies": _recent_view(after_bundle),
        "proposal_status_after": proposal_final.get("status"),
        "decision_next_revisit_hint_utc": (
            decisions[0]["payload"].get("next_revisit_hint_utc") if decisions else None
        ),
    }


def _scenario_conflict_skip(base_dir: Path) -> dict[str, Any]:
    bundle_path = base_dir / "conflict_skip_bundle.json"
    _write_bundle(bundle_path)
    store = FixtureHarnessStore()
    _reset_env(base_dir, bundle_path, store)

    # Propose a swap whose from_active_artifact_id no longer matches current bundle.
    proposal_id = _seed_proposal(
        store,
        from_active="art_unrelated_v0",
        to_active=_CHALLENGER_ID,
        from_challengers=[],
        to_challengers=[],
        salt="conflict_skip",
    )
    before_bundle = _read_bundle(bundle_path)

    decision_res = runtime.perform_decision(
        proposal_id=proposal_id,
        action="approve",
        actor="ops@example.com",
        reason="runbook-approve on stale from_active_artifact_id",
        use_fixture=True,
    )
    tick_summary = runtime.perform_tick(use_fixture=True, max_jobs=5)
    after_bundle = _read_bundle(bundle_path)
    applied, refresh = _applied_and_refresh(store)
    proposal_final = store.get_packet(proposal_id)

    return {
        "scenario": "conflict_skip",
        "expectation": (
            "from_active_artifact_id mismatch; bundle untouched; applied packet "
            "records outcome=conflict_skip with blocking_reason "
            "active_mismatch:<id>; no SpectrumRefreshRecordV1; "
            "proposal.status=deferred"
        ),
        "proposal_id": proposal_id,
        "decision_result": decision_res,
        "tick_summary_registry_apply_queue": tick_summary.get("queue_runs", {}).get(
            "registry_apply_queue"
        ),
        "before_registry_entry": _registry_entry_view(before_bundle),
        "after_registry_entry": _registry_entry_view(after_bundle),
        "before_spectrum": _spectrum_view(before_bundle),
        "after_spectrum": _spectrum_view(after_bundle),
        "before_recent_governed_applies": _recent_view(before_bundle),
        "after_recent_governed_applies": _recent_view(after_bundle),
        "applied_packet_outcome": (applied or {}).get("payload", {}).get("outcome"),
        "applied_packet_blocking_reasons": (applied or {}).get("blocking_reasons"),
        "refresh_packet_count": len(
            store.list_packets(packet_type="SpectrumRefreshRecordV1")
        ),
        "proposal_status_after": proposal_final.get("status"),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="agh_v1_patch3_runbook_") as tdir:
        base = Path(tdir)
        scenarios = [
            _scenario_approve_carry_over(base),
            _scenario_approve_recompute(base),
            _scenario_reject(base),
            _scenario_defer(base),
            _scenario_conflict_skip(base),
        ]

    out = {
        "contract": "METIS_AGH_V1_PATCH_3_ARTIFACT_PROMOTION_BRIDGE_RUNBOOK_V1",
        "captured_at_utc": now_utc_iso(),
        "target_scope": {
            "registry_entry_id": _REGISTRY_ENTRY_ID,
            "horizon": _HORIZON,
            "from_active_artifact_id": _ACTIVE_ID,
            "to_active_artifact_id": _CHALLENGER_ID,
        },
        "scenarios": scenarios,
        "invariants_exercised": [
            "approve(carry-over): active/challenger swap + spectrum rows carry-over with stale flags + needs_db_rebuild=True",
            "approve(recompute): active/challenger swap + spectrum rows fully recomputed + needs_db_rebuild=False",
            "reject: bundle unchanged + proposal.status=rejected + no apply job",
            "defer: bundle unchanged + proposal.status=deferred + next_revisit_hint_utc recorded",
            "conflict_skip: from_active_artifact_id mismatch -> bundle unchanged + applied.outcome=conflict_skip + proposal.status=deferred",
            "recent_governed_applies FIFO grows only on outcome=applied; reject/defer/conflict_skip never append",
            "SpectrumRefreshRecordV1 is emitted only on outcome=applied and always carries cited_proposal/decision/applied packet ids",
        ],
    }

    evidence_path = (
        REPO_ROOT
        / "data"
        / "mvp"
        / "evidence"
        / "agentic_operating_harness_v1_milestone_14_artifact_promotion_bridge_runbook_evidence.json"
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "ok": True,
                "evidence_path": str(evidence_path),
                "n_scenarios": len(scenarios),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
