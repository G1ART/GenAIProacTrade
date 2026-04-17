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


# ---------------------------------------------------------------------------
# Real Bundle Generalization v1 — auto-degrade + horizon_provenance + aliases
# ---------------------------------------------------------------------------


def _gate_with_reasons(artifact_id: str, *, pit_rule: str = "accepted_at_signal_date_pit_rule_v0") -> dict:
    g = _passing_gate(artifact_id)
    g["reasons"] = f"mapped_from_factor_validation;pit=certified;pit_rule={pit_rule}"
    return g


def test_horizon_provenance_records_real_derived_entry_with_pit_rule() -> None:
    spec = {
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "return_basis": "raw",
        "artifact_id": "art_short_demo_v0",
    }
    fg, fj = _make_fetchers(gate=_gate_with_reasons("art_short_demo_v0"))
    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=[spec],
        fetch_gate=fg,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
    )
    assert merged is not None, report
    hp = merged.get("horizon_provenance") or {}
    assert "short" in hp
    entry = hp["short"]
    assert entry["source"] == "real_derived"
    assert entry["pit_pass"] is True
    assert entry["pit_rule"] == "accepted_at_signal_date_pit_rule_v0"
    assert entry["spectrum_row_count"] == 3
    assert entry["factor_name"] == "accruals"
    assert entry["artifact_id"] == "art_short_demo_v0"
    assert isinstance(entry["contributing_gates"], list) and len(entry["contributing_gates"]) == 1


def test_horizon_provenance_fallback_labels_emitted_without_real_data() -> None:
    spec = {
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "return_basis": "raw",
        "artifact_id": "art_short_demo_v0",
    }
    fg, fj = _make_fetchers(gate=_gate_with_reasons("art_short_demo_v0"))
    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=[spec],
        fetch_gate=fg,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
        horizon_fallback_labels={
            "medium_long": {
                "reason": "forward_returns_horizon_not_yet_emitted_for_next_half_year",
                "display_family_name_ko": "중장기 (샘플 전용)",
                "display_family_name_en": "Medium-long (sample only)",
            },
            "long": {
                "reason": "forward_returns_horizon_not_yet_emitted_for_next_year",
                "display_family_name_ko": "장기 (샘플 전용)",
                "display_family_name_en": "Long (sample only)",
            },
        },
    )
    assert merged is not None, report
    hp = merged["horizon_provenance"]
    assert hp["medium_long"]["source"] == "template_fallback"
    assert hp["medium_long"]["reason"].startswith("forward_returns_horizon_not_yet_emitted")
    assert hp["long"]["source"] == "template_fallback"
    assert hp["medium_long"]["display_family_name_ko"] == "중장기 (샘플 전용)"


def test_auto_degrade_optional_gate_does_not_abort_build() -> None:
    specs = [
        {
            "factor_name": "accruals",
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
            "return_basis": "raw",
            "artifact_id": "art_short_demo_v0",
        },
        {
            "factor_name": "gross_profitability",
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
            "return_basis": "raw",
            "artifact_id": "art_short_challenger_momentum_v0",
        },
    ]

    def fetch_gate(_c, spec):
        if spec["factor_name"] == "gross_profitability":
            return {"ok": False, "error": "stub_optional_missing"}
        return {"ok": True, "promotion_gate": _gate_with_reasons(spec["artifact_id"])}

    _ignored, fj = _make_fetchers(gate=_gate_with_reasons("art_short_demo_v0"))

    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=specs,
        fetch_gate=fetch_gate,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
        auto_degrade_optional_gates=["gross_profitability:next_month"],
    )
    assert merged is not None, report
    # The failing optional spec did NOT abort; it became a degraded entry.
    hp = merged["horizon_provenance"]
    assert hp["short"]["source"] in {"real_derived", "real_derived_with_degraded_challenger"}
    degraded = [g for g in hp["short"]["contributing_gates"] if g.get("degraded")]
    assert len(degraded) == 1
    assert degraded[0]["factor_name"] == "gross_profitability"
    assert degraded[0]["degraded_reason"].startswith("gate_export_failed")
    # And the corresponding step records the optional-degraded outcome.
    assert any(
        s.get("degraded") and s["spec"]["factor_name"] == "gross_profitability"
        for s in report["steps"]
    )


def test_auto_degrade_on_failing_gate_criteria_marks_degraded_not_abort() -> None:
    failing_gate = _gate_with_reasons("art_short_challenger_momentum_v0")
    failing_gate["monotonicity_pass"] = False  # non-passing challenger
    passing_gate = _gate_with_reasons("art_short_demo_v0")

    def fetch_gate(_c, spec):
        if spec["factor_name"] == "gross_profitability":
            return {"ok": True, "promotion_gate": failing_gate}
        return {"ok": True, "promotion_gate": passing_gate}

    _ignored, fj = _make_fetchers(gate=passing_gate)
    specs = [
        {
            "factor_name": "accruals",
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
            "return_basis": "raw",
            "artifact_id": "art_short_demo_v0",
        },
        {
            "factor_name": "gross_profitability",
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
            "return_basis": "raw",
            "artifact_id": "art_short_challenger_momentum_v0",
        },
    ]
    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=specs,
        fetch_gate=fetch_gate,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
        auto_degrade_optional_gates=["gross_profitability:next_month"],
    )
    assert merged is not None, report
    hp = merged["horizon_provenance"]
    degraded = [g for g in hp["short"]["contributing_gates"] if g.get("degraded")]
    assert any(
        str(d.get("degraded_reason") or "").startswith("optional_gate_not_passing")
        for d in degraded
    )


def test_display_aliases_overlay_applied_to_artifact_and_provenance() -> None:
    spec = {
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "return_basis": "raw",
        "artifact_id": "art_short_demo_v0",
    }
    fg, fj = _make_fetchers(gate=_gate_with_reasons("art_short_demo_v0"))
    aliases = {
        "artifacts": {
            "art_short_demo_v0": {
                "display_id": "art_short_value_accruals_v1",
                "display_family_name_ko": "단기 가치(발생액)",
                "display_family_name_en": "Short value — accruals",
            }
        },
        "registry_entries": {
            "reg_short_demo_v0": {
                "display_id": "reg_short_value_v1",
                "display_family_name_ko": "단기 가치",
                "display_family_name_en": "Short value",
            }
        },
    }
    merged, report = build_bundle_full_from_validation_v1(
        template_bundle=_template(),
        gate_specs=[spec],
        fetch_gate=fg,
        fetch_joined=fj,
        client=None,
        sync_artifact_validation_pointer=True,
        display_aliases=aliases,
    )
    assert merged is not None, report
    art = next(a for a in merged["artifacts"] if a["artifact_id"] == "art_short_demo_v0")
    assert art.get("display_id") == "art_short_value_accruals_v1"
    assert art.get("display_family_name_ko") == "단기 가치(발생액)"
    reg = next(
        e for e in merged["registry_entries"] if e["registry_entry_id"] == "reg_short_demo_v0"
    )
    assert reg.get("display_id") == "reg_short_value_v1"
    assert merged["horizon_provenance"]["short"]["display_id"] == "art_short_value_accruals_v1"
    assert merged["horizon_provenance"]["short"]["display_family_name_ko"] == "단기 가치(발생액)"
