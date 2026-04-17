"""Unit tests for ``metis_brain.bundle_full_from_validation_v1`` (mocked DB)."""

from __future__ import annotations

from pathlib import Path

import pytest

from metis_brain.bundle_full_from_validation_v1 import (
    build_bundle_full_from_validation_v1,
)
from metis_brain.bundle_promotion_merge_v0 import load_bundle_json


def _repo() -> Path:
    return Path(__file__).resolve().parents[2]


def _template() -> dict:
    return load_bundle_json(_repo() / "data/mvp/metis_brain_bundle_v0.json")


def _passing_gate(artifact_id: str, run_id: str = "run_1") -> dict:
    return {
        "artifact_id": artifact_id,
        "evaluation_run_id": run_id,
        "pit_pass": True,
        "coverage_pass": True,
        "monotonicity_pass": True,
        "regime_notes": "test",
        "sector_override_notes": "",
        "challenger_or_active": "active",
        "approved_by_rule": "unit_test_rule",
        "approved_at": "2026-04-01T00:00:00+00:00",
        "supersedes_registry_entry": "",
        "reasons": "test_pass",
        "expiry_or_recheck_rule": "test",
    }


def _make_fetchers(
    *,
    gate: dict,
    summary_row: dict | None = None,
    joined_rows: list[dict] | None = None,
    run_id: str = "run_1",
    gate_ok: bool = True,
    joined_ok: bool = True,
):
    def fetch_gate(_c, _spec):
        if not gate_ok:
            return {"ok": False, "error": "stub_gate_fail"}
        return {"ok": True, "promotion_gate": gate}

    def fetch_joined(_c, spec):
        if not joined_ok:
            return {"ok": False, "error": "stub_joined_fail"}
        factor = spec["factor_name"]
        sr = summary_row if summary_row is not None else {
            "sample_count": 120,
            "valid_factor_count": 96,
            "spearman_rank_corr": -0.2,
        }
        jr = joined_rows if joined_rows is not None else [
            {
                "symbol": "AAA", factor: 0.01,
                "fiscal_year": 2024, "fiscal_period": "Q4", "accession_no": "a1",
            },
            {
                "symbol": "BBB", factor: 0.05,
                "fiscal_year": 2024, "fiscal_period": "Q4", "accession_no": "a2",
            },
            {
                "symbol": "CCC", factor: 0.10,
                "fiscal_year": 2024, "fiscal_period": "Q4", "accession_no": "a3",
            },
        ]
        return {
            "ok": True,
            "run_id": run_id,
            "summary_row": sr,
            "quantile_rows": [{"quantile_index": i} for i in range(5)],
            "joined_rows": jr,
        }

    return fetch_gate, fetch_joined


def test_full_builder_happy_path_replaces_artifact_and_sets_spectrum_rows() -> None:
    spec = {
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "return_basis": "raw",
        "artifact_id": "art_short_demo_v0",
    }
    fg, fj = _make_fetchers(gate=_passing_gate("art_short_demo_v0"))
    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=[spec],
        fetch_gate=fg,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
    )
    assert merged is not None, report
    assert report["integrity_ok"] is True
    art = next(a for a in merged["artifacts"] if a["artifact_id"] == "art_short_demo_v0")
    assert art["feature_set"] == "factor:accruals"
    assert art["created_by"] == "artifact_from_validation_v1"
    assert art["validation_pointer"].startswith("factor_validation_run:")
    rows = merged["spectrum_rows_by_horizon"]["short"]
    assert len(rows) == 3
    assert {r["asset_id"] for r in rows} == {"AAA", "BBB", "CCC"}


def test_full_builder_aborts_when_gate_export_fails() -> None:
    spec = {
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "return_basis": "raw",
        "artifact_id": "art_short_demo_v0",
    }
    fg, fj = _make_fetchers(gate=_passing_gate("x"), gate_ok=False)
    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=[spec],
        fetch_gate=fg,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
    )
    assert merged is None
    assert report["aborted_reason"] == "gate_export_failed"


def test_full_builder_aborts_when_no_spectrum_rows_synthesized() -> None:
    spec = {
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "return_basis": "raw",
        "artifact_id": "art_short_demo_v0",
    }
    fg, fj = _make_fetchers(
        gate=_passing_gate("art_short_demo_v0"),
        joined_rows=[],
    )
    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=[spec],
        fetch_gate=fg,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
    )
    assert merged is None
    assert report["aborted_reason"] == "no_spectrum_rows"


def test_full_builder_preserves_other_horizons_in_template() -> None:
    spec = {
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "return_basis": "raw",
        "artifact_id": "art_short_demo_v0",
    }
    fg, fj = _make_fetchers(gate=_passing_gate("art_short_demo_v0"))
    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=[spec],
        fetch_gate=fg,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
    )
    assert merged is not None, report
    assert "medium" in merged["spectrum_rows_by_horizon"]
    assert "long" in merged["spectrum_rows_by_horizon"]
    assert len(merged["spectrum_rows_by_horizon"]["medium"]) >= 1
