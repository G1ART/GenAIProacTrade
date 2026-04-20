"""AGH v1 Patch 4 - validation -> governance bridge closure runbook.

Exercises the five operator-visible upstream evaluator paths against a tmp
brain bundle via the in-process ``FixtureHarnessStore``. Captures before/after
snapshots as the Patch 4 "h-runbook" evidence:

    1. promote                 verdict=promote; artifact_action=added_challenger;
                               outcome=proposal_emitted; governance_queue+1.
    2. blocked_by_gate         verdict=reject (pit_failed); no proposal;
                               bundle unchanged; ValidationPromotionEvaluationV1
                               records ``blocking_reasons=['pit_failed']``.
    3. blocked_missing_evidence  fetch returns no summary; outcome=blocked_missing_evidence;
                                 no proposal; no bundle mutation.
    4. blocked_same_as_active   derived artifact_id already == active_artifact_id;
                                outcome=blocked_same_as_active; artifact_action=already_active;
                                validation_pointer refreshed but active state untouched.
    5. dry_run                  same promote-shaped input but dry_run=True; no packets persisted;
                                no bundle write; res.dry_run_preview.would_emit_proposal=True.

Writes the payload to
``data/mvp/evidence/agentic_operating_harness_v1_milestone_15_validation_to_governance_runbook_evidence.json``.
This is not a unit test; it is an operator-auditable dry run that proves the
validation -> governance bridge closes end-to-end without touching the
production brain bundle or any Supabase rows.

Invariants (work-order METIS_Patch_4 §2, §3):
    * No direct active-state mutation. ``active_artifact_id`` stays gated
      behind ``harness-decide approve`` + Patch 3 apply.
    * Bundle writes go only through ``validate_merged_bundle_dict`` +
      ``write_bundle_json_atomic`` and only when (a) adding a challenger on
      verdict=promote or (b) refreshing ``validation_pointer`` for an
      existing challenger / active artifact.
    * Every evaluation - promote or blocked - persists a
      ``ValidationPromotionEvaluationV1`` packet so replay can reconstruct
      the upstream audit trail (except dry_run, which is stdout-only).
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


from agentic_harness.agents.layer4_promotion_evaluator_v1 import (  # noqa: E402
    derive_artifact_id,
    evaluate_validation_for_promotion,
)
from agentic_harness.store import FixtureHarnessStore  # noqa: E402
from agentic_harness.store.protocol import now_utc_iso  # noqa: E402


_REGISTRY_ENTRY_ID = "reg_short_demo_v0"
_HORIZON = "short"
_FACTOR = "demo_factor"
_UNIVERSE = "large_cap_research_slice_demo_v0"
_HORIZON_TYPE = "next_month"
_RETURN_BASIS = "raw"


def _artifact(aid: str, *, horizon: str = _HORIZON) -> dict[str, Any]:
    return {
        "artifact_id": aid,
        "created_at": "2026-04-19T00:00:00+00:00",
        "created_by": "artifact_from_validation_v1",
        "horizon": horizon,
        "universe": _UNIVERSE,
        "sector_scope": "multi_sector_v0",
        "thesis_family": f"factor_{_FACTOR}_v0",
        "feature_set": f"factor:{_FACTOR}",
        "feature_transforms": "identity_v0",
        "weighting_rule": "equal_weight:v0",
        "score_formula": "rank_position_from_spearman_and_quantile:v0",
        "banding_rule": "quintile_from_factor_rank:v0",
        "ranking_direction": "higher_more_stretched:v0",
        "invalidation_conditions": "pit_or_coverage_or_monotonicity_fail:v0",
        "expected_holding_horizon": horizon,
        "confidence_rule": "band_from_valid_rows:v0",
        "evidence_requirements": "validation_pointer_required:v0",
        "validation_pointer": f"factor_validation_run:run_{aid}:{_FACTOR}:{_RETURN_BASIS}",
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


def _write_bundle(path: Path, *, active_id: str = "art_active_v0") -> None:
    bundle = {
        "schema_version": 1,
        "as_of_utc": "2026-04-19T00:00:00+00:00",
        "price_layer_note": "",
        "artifacts": [_artifact(active_id)],
        "promotion_gates": [_gate(active_id)],
        "registry_entries": [
            {
                "registry_entry_id": _REGISTRY_ENTRY_ID,
                "horizon": _HORIZON,
                "active_model_family_name": "shallow_value_blend_v0",
                "active_artifact_id": active_id,
                "challenger_artifact_ids": [],
                "universe": _UNIVERSE,
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
            _HORIZON: [
                {"asset_id": "AAA", "spectrum_position": 0.1},
                {"asset_id": "BBB", "spectrum_position": 0.4},
                {"asset_id": "CCC", "spectrum_position": 0.7},
            ]
        },
        "horizon_provenance": {_HORIZON: {"source": "real_derived"}},
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
            }
    return {}


def _artifacts_view(bundle: dict[str, Any]) -> list[str]:
    return [a.get("artifact_id") for a in bundle.get("artifacts") or []]


def _promote_summary_row(
    *,
    run_id: str,
    pit_certified: bool = True,
    return_basis: str = _RETURN_BASIS,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "factor_name": _FACTOR,
        "universe_name": _UNIVERSE,
        "horizon_type": _HORIZON_TYPE,
        "return_basis": return_basis,
        "sample_count": 400,
        "valid_factor_count": 300,
        "spearman_rank_corr": 0.21,
        "summary_json": {
            "pit_certified": pit_certified,
            "pit_rule": "no_lookahead_v0",
        },
    }


def _quantiles_promote(n: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "quantile_index": i,
            "avg_raw_return": 0.001 * (i - 2),
            "avg_excess_return": 0.0005 * (i - 2),
        }
        for i in range(n)
    ]


def _fetchers(
    *, summary_row: dict[str, Any] | None, run_id: str
):
    def _fetch_summary(_client, _spec):
        if summary_row is None:
            return None, []
        return run_id, [dict(summary_row)]

    def _fetch_quant(_client, _spec):
        return _quantiles_promote()

    return _fetch_summary, _fetch_quant


def _run(base: Path, *, name: str, build_bundle, run_id: str, summary_row, dry_run: bool = False):
    bundle_path = base / f"{name}_bundle.json"
    build_bundle(bundle_path)
    store = FixtureHarnessStore()
    before_bundle = _read_bundle(bundle_path)
    fetch_summary, fetch_quant = _fetchers(summary_row=summary_row, run_id=run_id)

    res = evaluate_validation_for_promotion(
        store=store,
        bundle_path=bundle_path,
        bundle_dict=copy.deepcopy(before_bundle),
        registry_entry_id=_REGISTRY_ENTRY_ID,
        horizon=_HORIZON,
        factor_name=_FACTOR,
        universe_name=_UNIVERSE,
        horizon_type=_HORIZON_TYPE,
        return_basis=_RETURN_BASIS,
        now_iso=now_utc_iso(),
        fetch_validation_summary=fetch_summary,
        fetch_quantiles=fetch_quant,
        dry_run=dry_run,
    )
    after_bundle = _read_bundle(bundle_path)
    evals = store.list_packets(packet_type="ValidationPromotionEvaluationV1")
    proposals = store.list_packets(packet_type="RegistryUpdateProposalV1")
    jobs = store.list_jobs(queue_class="governance_queue")
    return {
        "before_registry_entry": _registry_entry_view(before_bundle),
        "after_registry_entry": _registry_entry_view(after_bundle),
        "before_artifacts": _artifacts_view(before_bundle),
        "after_artifacts": _artifacts_view(after_bundle),
        "result": {
            k: res.get(k)
            for k in (
                "outcome",
                "gate_verdict",
                "artifact_action",
                "derived_artifact_id",
                "emitted_proposal_packet_id",
                "blocking_reasons",
                "dry_run",
                "dry_run_preview",
            )
        },
        "evaluation_packet_count": len(evals),
        "latest_evaluation_outcome": (evals[-1]["payload"].get("outcome") if evals else None),
        "latest_evaluation_blocking_reasons": (
            list(evals[-1].get("blocking_reasons") or []) if evals else []
        ),
        "proposal_packet_count": len(proposals),
        "governance_queue_job_count": sum(
            1 for j in jobs if str(j.get("queue_class")) == "governance_queue"
        ),
    }


def _scenario_promote(base: Path) -> dict[str, Any]:
    out = _run(
        base,
        name="promote",
        build_bundle=_write_bundle,
        run_id="run_fvr_promote_1",
        summary_row=_promote_summary_row(run_id="run_fvr_promote_1"),
    )
    return {
        "scenario": "promote",
        "expectation": (
            "verdict=promote; artifact_action=added_challenger; "
            "outcome=proposal_emitted; evaluation + proposal packets emitted; "
            "governance_queue job+1."
        ),
        **out,
    }


def _scenario_blocked_by_gate(base: Path) -> dict[str, Any]:
    out = _run(
        base,
        name="blocked_by_gate",
        build_bundle=_write_bundle,
        run_id="run_fvr_blocked_1",
        summary_row=_promote_summary_row(
            run_id="run_fvr_blocked_1", pit_certified=False
        ),
    )
    return {
        "scenario": "blocked_by_gate",
        "expectation": (
            "pit_certified=False -> verdict=reject; outcome=blocked_by_gate; "
            "no proposal; bundle unchanged; evaluation packet emitted with "
            "blocking_reasons=['pit_failed']."
        ),
        **out,
    }


def _scenario_blocked_missing_evidence(base: Path) -> dict[str, Any]:
    out = _run(
        base,
        name="blocked_missing",
        build_bundle=_write_bundle,
        run_id="run_fvr_missing_1",
        summary_row=None,
    )
    return {
        "scenario": "blocked_missing_evidence",
        "expectation": (
            "no completed factor_validation summary -> outcome=blocked_missing_evidence; "
            "no proposal; bundle unchanged; evaluation packet emitted with "
            "no_completed_factor_validation_summary blocking reason."
        ),
        **out,
    }


def _scenario_blocked_same_as_active(base: Path) -> dict[str, Any]:
    # Seed the bundle so ``active_artifact_id`` matches the deterministic id.
    active_id = derive_artifact_id(
        factor_name=_FACTOR,
        universe_name=_UNIVERSE,
        horizon_type=_HORIZON_TYPE,
        return_basis=_RETURN_BASIS,
        validation_run_id="run_fvr_promote_1",
    )

    def _build_bundle(path: Path) -> None:
        _write_bundle(path, active_id=active_id)

    out = _run(
        base,
        name="blocked_same_as_active",
        build_bundle=_build_bundle,
        run_id="run_fvr_promote_1",
        summary_row=_promote_summary_row(run_id="run_fvr_promote_1"),
    )
    return {
        "scenario": "blocked_same_as_active",
        "expectation": (
            "derived artifact_id == active_artifact_id -> artifact_action=already_active; "
            "outcome=blocked_same_as_active; no proposal; active state untouched; "
            "validation_pointer may be refreshed on the existing active artifact."
        ),
        **out,
    }


def _scenario_dry_run(base: Path) -> dict[str, Any]:
    out = _run(
        base,
        name="dry_run",
        build_bundle=_write_bundle,
        run_id="run_fvr_dry_1",
        summary_row=_promote_summary_row(run_id="run_fvr_dry_1"),
        dry_run=True,
    )
    return {
        "scenario": "dry_run",
        "expectation": (
            "dry_run=True: verdict/artifact_action/derived_artifact_id "
            "reported but no packets persisted, no bundle write, "
            "dry_run_preview.would_emit_proposal=True."
        ),
        **out,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="agh_v1_patch4_runbook_") as tdir:
        base = Path(tdir)
        scenarios = [
            _scenario_promote(base),
            _scenario_blocked_by_gate(base),
            _scenario_blocked_missing_evidence(base),
            _scenario_blocked_same_as_active(base),
            _scenario_dry_run(base),
        ]

    out = {
        "contract": "METIS_AGH_V1_PATCH_4_VALIDATION_TO_GOVERNANCE_RUNBOOK_V1",
        "captured_at_utc": now_utc_iso(),
        "target_scope": {
            "registry_entry_id": _REGISTRY_ENTRY_ID,
            "horizon": _HORIZON,
            "factor_name": _FACTOR,
            "universe_name": _UNIVERSE,
            "horizon_type": _HORIZON_TYPE,
            "return_basis": _RETURN_BASIS,
        },
        "scenarios": scenarios,
        "invariants_exercised": [
            "promote: added_challenger + proposal_emitted + governance_queue job",
            "blocked_by_gate: pit_certified=False -> no proposal, bundle unchanged, blocking_reasons include pit_failed",
            "blocked_missing_evidence: summary missing -> no proposal, bundle unchanged, audit packet still emitted",
            "blocked_same_as_active: derived == active -> no proposal, active state untouched",
            "dry_run: full pipeline runs without persistence; preview reports would_emit_proposal=True",
            "no direct active-state mutation: every scenario leaves active_artifact_id unchanged (active-state changes require harness-decide + Patch 3 apply)",
            "ValidationPromotionEvaluationV1 is emitted for every non-dry-run path (promote + 3 blocked); dry_run persists zero packets",
        ],
    }

    evidence_path = (
        REPO_ROOT
        / "data"
        / "mvp"
        / "evidence"
        / "agentic_operating_harness_v1_milestone_15_validation_to_governance_runbook_evidence.json"
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
