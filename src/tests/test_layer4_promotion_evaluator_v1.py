"""AGH v1 Patch 4 — validation -> governance promotion evaluator tests.

Covers the core invariants of
``agentic_harness.agents.layer4_promotion_evaluator_v1``:

    * Promote happy path with added_challenger mutation + emitted
      RegistryUpdateProposalV1 + ValidationPromotionEvaluationV1 +
      governance_queue job.
    * Block-by-gate path (PIT certified=False) never mutates the bundle, never
      emits a proposal, and records ``pit_failed`` in ``blocking_reasons``.
    * Missing evidence path (no summary row) records
      ``outcome='blocked_missing_evidence'`` without touching the bundle.
    * ``already_active`` + verdict=promote -> ``blocked_same_as_active``
      (refreshes ``validation_pointer`` on the existing active artifact but
      never emits a proposal).
    * ``derive_artifact_id`` is deterministic in (factor, universe,
      horizon_type, return_basis, validation_run_id).
    * Horizon mismatch (requested bundle horizon ≠ mapping of
      ``horizon_type``) is an honest block, not a silent coerce.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_harness.agents.layer4_promotion_evaluator_v1 import (
    derive_artifact_id,
    evaluate_registry_entries,
    evaluate_validation_for_promotion,
)
from agentic_harness.store import FixtureHarnessStore


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
    horizon: str = "short",
) -> dict:
    bundle = {
        "schema_version": 1,
        "as_of_utc": "2026-04-19T00:00:00+00:00",
        "price_layer_note": "",
        "artifacts": [_artifact(active_id, horizon)],
        "promotion_gates": [_gate(active_id)],
        "registry_entries": [
            {
                "registry_entry_id": "reg_short_demo_v0",
                "horizon": horizon,
                "active_model_family_name": "shallow_value_blend_v0",
                "active_artifact_id": active_id,
                "challenger_artifact_ids": [],
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
            horizon: [_row(aid, 0.1 + 0.15 * i) for i, aid in enumerate(("AAA", "BBB", "CCC"))],
        },
        "horizon_provenance": {horizon: {"source": "real_derived"}},
    }
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return bundle


def _promote_summary_row(
    *,
    run_id: str = "run_fvr_promote_1",
    factor: str = "demo_factor",
    universe: str = "large_cap_research_slice_demo_v0",
    htype: str = "next_month",
    basis: str = "raw",
    pit_certified: bool = True,
) -> dict:
    return {
        "run_id": run_id,
        "factor_name": factor,
        "universe_name": universe,
        "horizon_type": htype,
        "return_basis": basis,
        "sample_count": 400,
        "valid_factor_count": 300,
        "spearman_rank_corr": 0.21,
        "summary_json": {"pit_certified": pit_certified, "pit_rule": "no_lookahead_v0"},
    }


def _quantiles_promote(n: int = 5) -> list[dict]:
    return [
        {
            "quantile_index": i,
            "avg_raw_return": 0.001 * (i - 2),
            "avg_excess_return": 0.0005 * (i - 2),
        }
        for i in range(n)
    ]


@pytest.fixture
def bundle_path(tmp_path, monkeypatch):
    p = tmp_path / "metis_brain_bundle_v0.json"
    _write_bundle(p)
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(p))
    monkeypatch.setenv("METIS_REPO_ROOT", str(tmp_path))
    return p


def _fetchers(
    *,
    summary_row: dict | None,
    quantile_rows: list[dict],
    run_id: str = "run_fvr_promote_1",
):
    def _fetch_summary(client, spec):
        if summary_row is None:
            return None, []
        return run_id, [dict(summary_row)]

    def _fetch_quant(client, spec):
        return [dict(q) for q in quantile_rows]

    return _fetch_summary, _fetch_quant


def test_derive_artifact_id_is_deterministic_and_distinct_per_tuple():
    a1 = derive_artifact_id(
        factor_name="f",
        universe_name="u",
        horizon_type="next_month",
        return_basis="raw",
        validation_run_id="run_X",
    )
    a2 = derive_artifact_id(
        factor_name="f",
        universe_name="u",
        horizon_type="next_month",
        return_basis="raw",
        validation_run_id="run_X",
    )
    assert a1 == a2
    assert a1.startswith("art_f_u_next_month_raw_")

    different_run = derive_artifact_id(
        factor_name="f",
        universe_name="u",
        horizon_type="next_month",
        return_basis="raw",
        validation_run_id="run_Y",
    )
    different_basis = derive_artifact_id(
        factor_name="f",
        universe_name="u",
        horizon_type="next_month",
        return_basis="excess",
        validation_run_id="run_X",
    )
    assert different_run != a1
    assert different_basis != a1


def test_derive_artifact_id_rejects_empty_inputs():
    with pytest.raises(ValueError):
        derive_artifact_id(
            factor_name="",
            universe_name="u",
            horizon_type="next_month",
            return_basis="raw",
            validation_run_id="r",
        )
    with pytest.raises(ValueError):
        derive_artifact_id(
            factor_name="f",
            universe_name="u",
            horizon_type="next_month",
            return_basis="raw",
            validation_run_id="",
        )


def test_evaluator_promote_happy_path_emits_proposal_and_evaluation(bundle_path):
    store = FixtureHarnessStore()
    summary = _promote_summary_row()
    fetch_summary, fetch_quant = _fetchers(
        summary_row=summary, quantile_rows=_quantiles_promote()
    )

    bundle_dict = json.loads(bundle_path.read_text(encoding="utf-8"))
    res = evaluate_validation_for_promotion(
        store=store,
        bundle_path=bundle_path,
        bundle_dict=bundle_dict,
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        factor_name="demo_factor",
        universe_name="large_cap_research_slice_demo_v0",
        horizon_type="next_month",
        return_basis="raw",
        now_iso="2026-04-19T10:00:00+00:00",
        fetch_validation_summary=fetch_summary,
        fetch_quantiles=fetch_quant,
    )

    assert res["ok"] is True
    assert res["outcome"] == "proposal_emitted"
    assert res["gate_verdict"] == "promote"
    assert res["artifact_action"] == "added_challenger"
    assert res["derived_artifact_id"].startswith(
        "art_demo_factor_large_cap_research_slice_demo_v0_next_month_raw_"
    )
    assert res["emitted_proposal_packet_id"]

    # Bundle mutated: new challenger + new artifact slot + new promotion_gate.
    written = json.loads(bundle_path.read_text(encoding="utf-8"))
    entry = written["registry_entries"][0]
    assert entry["active_artifact_id"] == "art_active_v0"
    assert res["derived_artifact_id"] in entry["challenger_artifact_ids"]
    assert any(
        a["artifact_id"] == res["derived_artifact_id"]
        for a in written["artifacts"]
    )
    assert any(
        g["artifact_id"] == res["derived_artifact_id"]
        for g in written["promotion_gates"]
    )

    evals = store.list_packets(packet_type="ValidationPromotionEvaluationV1")
    assert len(evals) == 1
    ev_payload = evals[0]["payload"]
    assert ev_payload["outcome"] == "proposal_emitted"
    assert ev_payload["gate_verdict"] == "promote"
    assert ev_payload["artifact_action"] == "added_challenger"
    assert ev_payload["emitted_proposal_packet_id"] == res["emitted_proposal_packet_id"]
    assert ev_payload["validation_run_id"] == "run_fvr_promote_1"
    assert ev_payload["gate_metrics"]["pit_pass"] is True

    proposals = store.list_packets(packet_type="RegistryUpdateProposalV1")
    assert len(proposals) == 1
    prop_payload = proposals[0]["payload"]
    assert prop_payload["target"] == "registry_entry_artifact_promotion"
    assert prop_payload["registry_entry_id"] == "reg_short_demo_v0"
    assert prop_payload["horizon"] == "short"
    assert prop_payload["from_active_artifact_id"] == "art_active_v0"
    assert prop_payload["to_active_artifact_id"] == res["derived_artifact_id"]
    assert res["derived_artifact_id"] in prop_payload["from_challenger_artifact_ids"]
    assert res["derived_artifact_id"] not in prop_payload["to_challenger_artifact_ids"]
    assert "art_active_v0" in prop_payload["to_challenger_artifact_ids"]

    # A governance_queue job was enqueued pointing at the new proposal.
    jobs = store.list_jobs(queue_class="governance_queue")
    assert any(
        str(j.get("packet_id") or "") == proposals[0]["packet_id"] for j in jobs
    )


def test_evaluator_block_by_gate_pit_failed_never_writes_proposal(bundle_path):
    store = FixtureHarnessStore()
    summary = _promote_summary_row(pit_certified=False)
    fetch_summary, fetch_quant = _fetchers(
        summary_row=summary, quantile_rows=_quantiles_promote()
    )

    before = json.loads(bundle_path.read_text(encoding="utf-8"))
    res = evaluate_validation_for_promotion(
        store=store,
        bundle_path=bundle_path,
        bundle_dict=json.loads(bundle_path.read_text(encoding="utf-8")),
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        factor_name="demo_factor",
        universe_name="large_cap_research_slice_demo_v0",
        horizon_type="next_month",
        return_basis="raw",
        now_iso="2026-04-19T10:00:00+00:00",
        fetch_validation_summary=fetch_summary,
        fetch_quantiles=fetch_quant,
    )

    assert res["outcome"] == "blocked_by_gate"
    assert res["gate_verdict"] == "reject"
    assert "pit_failed" in res["blocking_reasons"]
    assert res["emitted_proposal_packet_id"] is None
    assert store.list_packets(packet_type="RegistryUpdateProposalV1") == []

    # Bundle unchanged on disk (artifacts/registry_entries identical).
    after = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert after["registry_entries"] == before["registry_entries"]
    assert after["artifacts"] == before["artifacts"]

    evals = store.list_packets(packet_type="ValidationPromotionEvaluationV1")
    assert len(evals) == 1
    assert evals[0]["payload"]["outcome"] == "blocked_by_gate"
    assert evals[0]["payload"]["gate_verdict"] == "reject"
    # Honest provenance_refs: no emitted proposal packet id.
    assert evals[0]["payload"]["emitted_proposal_packet_id"] in (None, "")


def test_evaluator_missing_evidence_blocks_and_does_not_write(bundle_path):
    store = FixtureHarnessStore()
    fetch_summary, fetch_quant = _fetchers(summary_row=None, quantile_rows=[])

    before = json.loads(bundle_path.read_text(encoding="utf-8"))
    res = evaluate_validation_for_promotion(
        store=store,
        bundle_path=bundle_path,
        bundle_dict=json.loads(bundle_path.read_text(encoding="utf-8")),
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        factor_name="demo_factor",
        universe_name="large_cap_research_slice_demo_v0",
        horizon_type="next_month",
        return_basis="raw",
        now_iso="2026-04-19T10:00:00+00:00",
        fetch_validation_summary=fetch_summary,
        fetch_quantiles=fetch_quant,
    )

    assert res["outcome"] == "blocked_missing_evidence"
    assert res["emitted_proposal_packet_id"] is None
    assert store.list_packets(packet_type="RegistryUpdateProposalV1") == []
    assert json.loads(bundle_path.read_text(encoding="utf-8")) == before
    evals = store.list_packets(packet_type="ValidationPromotionEvaluationV1")
    assert len(evals) == 1
    assert evals[0]["payload"]["outcome"] == "blocked_missing_evidence"
    assert any(
        "no_completed_factor_validation_summary" in r
        for r in evals[0].get("blocking_reasons") or []
    )


def test_evaluator_already_active_blocks_same_as_active(bundle_path, tmp_path):
    """The active artifact already matches the deterministic id -> no proposal,
    no challenger mutation, but a fresh evaluation packet is still emitted."""

    store = FixtureHarnessStore()
    summary = _promote_summary_row()
    active_id = derive_artifact_id(
        factor_name="demo_factor",
        universe_name="large_cap_research_slice_demo_v0",
        horizon_type="next_month",
        return_basis="raw",
        validation_run_id="run_fvr_promote_1",
    )
    # Rewrite bundle so active_artifact_id == derived.
    _write_bundle(bundle_path, active_id=active_id)

    fetch_summary, fetch_quant = _fetchers(
        summary_row=summary, quantile_rows=_quantiles_promote()
    )

    res = evaluate_validation_for_promotion(
        store=store,
        bundle_path=bundle_path,
        bundle_dict=json.loads(bundle_path.read_text(encoding="utf-8")),
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        factor_name="demo_factor",
        universe_name="large_cap_research_slice_demo_v0",
        horizon_type="next_month",
        return_basis="raw",
        now_iso="2026-04-19T10:00:00+00:00",
        fetch_validation_summary=fetch_summary,
        fetch_quantiles=fetch_quant,
    )

    assert res["outcome"] == "blocked_same_as_active"
    assert res["artifact_action"] == "already_active"
    assert res["emitted_proposal_packet_id"] is None
    assert store.list_packets(packet_type="RegistryUpdateProposalV1") == []

    after = json.loads(bundle_path.read_text(encoding="utf-8"))
    entry = after["registry_entries"][0]
    assert entry["active_artifact_id"] == active_id
    # No challenger added; active pointer should be refreshed to the new run id
    # (canonical pointer sync path) but structural identity is preserved.
    active_art = next(a for a in after["artifacts"] if a["artifact_id"] == active_id)
    assert active_art["validation_pointer"] == "factor_validation_run:run_fvr_promote_1"

    evals = store.list_packets(packet_type="ValidationPromotionEvaluationV1")
    assert len(evals) == 1
    assert evals[0]["payload"]["outcome"] == "blocked_same_as_active"
    assert evals[0]["payload"]["artifact_action"] == "already_active"


def test_evaluator_horizon_mismatch_blocks(bundle_path):
    """Requested bundle horizon doesn't match the mapping of ``horizon_type``."""

    store = FixtureHarnessStore()
    summary = _promote_summary_row(htype="next_year")  # maps to "long", not "short"
    fetch_summary, fetch_quant = _fetchers(
        summary_row=summary, quantile_rows=_quantiles_promote()
    )

    res = evaluate_validation_for_promotion(
        store=store,
        bundle_path=bundle_path,
        bundle_dict=json.loads(bundle_path.read_text(encoding="utf-8")),
        registry_entry_id="reg_short_demo_v0",
        horizon="short",  # mismatch with next_year->long
        factor_name="demo_factor",
        universe_name="large_cap_research_slice_demo_v0",
        horizon_type="next_year",
        return_basis="raw",
        now_iso="2026-04-19T10:00:00+00:00",
        fetch_validation_summary=fetch_summary,
        fetch_quantiles=fetch_quant,
    )

    assert res["outcome"] == "blocked_missing_evidence"
    assert any(
        r.startswith("horizon_mismatch:") for r in res["blocking_reasons"]
    )
    assert store.list_packets(packet_type="RegistryUpdateProposalV1") == []


def test_evaluate_registry_entries_reloads_bundle_between_specs(bundle_path):
    """Two specs against the same registry entry must compose: the second call
    should see the challenger added by the first call."""

    store = FixtureHarnessStore()

    def make_fetchers(run_id: str, basis: str):
        return _fetchers(
            summary_row=_promote_summary_row(run_id=run_id, basis=basis),
            quantile_rows=_quantiles_promote(),
            run_id=run_id,
        )

    # We need a fetcher that dispatches based on the requested spec so both
    # specs behave independently. Build a small dispatcher.
    summaries = {
        ("demo_factor", "next_month", "raw"): (
            "run_fvr_A",
            _promote_summary_row(run_id="run_fvr_A", basis="raw"),
        ),
        ("demo_factor", "next_month", "excess"): (
            "run_fvr_B",
            _promote_summary_row(run_id="run_fvr_B", basis="excess"),
        ),
    }

    def fetch_summary(client, spec):
        key = (spec["factor_name"], spec["horizon_type"], "raw")
        # Choose summary by matching the previously active basis.  The walker
        # iterates specs in order, so we key off the factor/horizon_type and
        # let the basis filter in the evaluator pick the right row.
        rid, row = summaries[key]
        # Return *both* rows so row_by_basis picks based on spec.return_basis.
        return rid, [
            {**_promote_summary_row(run_id=rid, basis="raw")},
            {**_promote_summary_row(run_id=rid, basis="excess")},
        ]

    def fetch_quant(client, spec):
        return _quantiles_promote()

    specs = [
        {
            "registry_entry_id": "reg_short_demo_v0",
            "horizon": "short",
            "factor_name": "demo_factor",
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "return_basis": "raw",
        },
        {
            "registry_entry_id": "reg_short_demo_v0",
            "horizon": "short",
            "factor_name": "demo_factor",
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "return_basis": "excess",
        },
    ]

    results = evaluate_registry_entries(
        store=store,
        bundle_path=bundle_path,
        specs=specs,
        now_iso="2026-04-19T10:00:00+00:00",
        fetch_validation_summary=fetch_summary,
        fetch_quantiles=fetch_quant,
    )

    assert len(results) == 2
    assert all(r["outcome"] == "proposal_emitted" for r in results)
    # Two distinct challenger artifacts must be in the bundle after both runs.
    final = json.loads(bundle_path.read_text(encoding="utf-8"))
    challenger_ids = final["registry_entries"][0]["challenger_artifact_ids"]
    assert results[0]["derived_artifact_id"] in challenger_ids
    assert results[1]["derived_artifact_id"] in challenger_ids
    assert results[0]["derived_artifact_id"] != results[1]["derived_artifact_id"]


def test_evaluator_dry_run_does_not_persist_or_mutate(bundle_path):
    store = FixtureHarnessStore()
    summary = _promote_summary_row()
    fetch_summary, fetch_quant = _fetchers(
        summary_row=summary, quantile_rows=_quantiles_promote()
    )
    before = json.loads(bundle_path.read_text(encoding="utf-8"))

    res = evaluate_validation_for_promotion(
        store=store,
        bundle_path=bundle_path,
        bundle_dict=json.loads(bundle_path.read_text(encoding="utf-8")),
        registry_entry_id="reg_short_demo_v0",
        horizon="short",
        factor_name="demo_factor",
        universe_name="large_cap_research_slice_demo_v0",
        horizon_type="next_month",
        return_basis="raw",
        now_iso="2026-04-19T10:00:00+00:00",
        fetch_validation_summary=fetch_summary,
        fetch_quantiles=fetch_quant,
        dry_run=True,
    )

    assert res["outcome"] == "proposal_emitted"
    assert res["dry_run"] is True
    # Dry run never surfaces a real proposal packet id.
    assert res["emitted_proposal_packet_id"] is None
    assert res["dry_run_preview"]["would_emit_proposal"] is True
    assert store.list_packets(packet_type="RegistryUpdateProposalV1") == []
    assert store.list_packets(packet_type="ValidationPromotionEvaluationV1") == []
    assert json.loads(bundle_path.read_text(encoding="utf-8")) == before
