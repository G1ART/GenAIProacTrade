"""Runtime health surface exposes per-horizon provenance + active artifact alias.

Real Bundle Generalization v1 — D. Runtime provenance visibility.
"""

from __future__ import annotations

import json
from pathlib import Path

from phase51_runtime.cockpit_health_surface import build_cockpit_runtime_health_payload


def _write_bundle_with_provenance(repo_root: Path) -> Path:
    src = Path(__file__).resolve().parents[2] / "data" / "mvp" / "metis_brain_bundle_v0.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    # Inject a passing gate for art_short_demo_v0 and art_medium_demo_v0 so the
    # bundle_ready_for_horizon checks hit True on short+medium.
    gate_short = {
        "artifact_id": "art_short_demo_v0",
        "evaluation_run_id": "run-short-test",
        "pit_pass": True,
        "coverage_pass": True,
        "monotonicity_pass": True,
        "regime_notes": "test",
        "sector_override_notes": "",
        "challenger_or_active": "active",
        "approved_by_rule": "test_rule",
        "approved_at": "2026-04-16T00:00:00+00:00",
        "supersedes_registry_entry": "",
        "reasons": "mapped_from_factor_validation;pit=certified;pit_rule=accepted_at_signal_date_pit_rule_v0",
        "expiry_or_recheck_rule": "test",
    }
    gate_medium = dict(gate_short)
    gate_medium["artifact_id"] = "art_medium_demo_v0"
    gate_medium["evaluation_run_id"] = "run-medium-test"
    # Keep the template's existing 4-horizon passing gates; append these two so
    # horizon_provenance stays consistent with a post-build-from-validation state.
    raw["promotion_gates"] = list(raw.get("promotion_gates") or []) + [gate_short, gate_medium]
    # Attach real-derived + fallback provenance.
    raw["horizon_provenance"] = {
        "short": {
            "source": "real_derived",
            "factor_name": "accruals",
            "validation_horizon_type": "next_month",
            "return_basis": "raw",
            "run_id": "run-short-test",
            "artifact_id": "art_short_demo_v0",
            "registry_entry_id": "reg_short_demo_v0",
            "pit_pass": True,
            "pit_rule": "accepted_at_signal_date_pit_rule_v0",
            "coverage_pass": True,
            "monotonicity_pass": True,
            "spectrum_row_count": 7,
            "display_id": "art_short_value_accruals_v1",
            "display_family_name_ko": "단기 가치 (발생액)",
            "display_family_name_en": "Short value — accruals",
            "contributing_gates": [],
        },
        "medium_long": {
            "source": "template_fallback",
            "reason": "forward_returns_horizon_not_yet_emitted_for_next_half_year",
            "artifact_id": "art_medium_long_demo_v0",
            "registry_entry_id": "reg_medium_long_demo_v0",
            "display_family_name_ko": "중장기 (샘플 전용)",
            "display_family_name_en": "Medium-long (sample only)",
            "contributing_gates": [],
        },
    }
    # Apply alias to the short active artifact so active_artifact_by_horizon picks up display.
    for a in raw["artifacts"]:
        if a["artifact_id"] == "art_short_demo_v0":
            a["display_id"] = "art_short_value_accruals_v1"
            a["display_family_name_ko"] = "단기 가치 (발생액)"
            a["display_family_name_en"] = "Short value — accruals"
    out = repo_root / "data" / "mvp" / "metis_brain_bundle_v0.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return out


def test_health_exposes_bundle_as_of_utc_horizon_provenance_and_active_artifact(tmp_path: Path) -> None:
    _write_bundle_with_provenance(tmp_path)
    payload = build_cockpit_runtime_health_payload(repo_root=tmp_path)
    gate = payload["mvp_brain_gate"]
    assert gate["contract"] == "MVP_RUNTIME_BRAIN_GATE_V1"
    assert gate["bundle_as_of_utc"]
    hp = gate["horizon_provenance"]
    assert hp["short"]["source"] == "real_derived"
    assert hp["short"]["pit_rule"] == "accepted_at_signal_date_pit_rule_v0"
    assert hp["medium_long"]["source"] == "template_fallback"
    abh = gate["active_artifact_by_horizon"]
    assert "short" in abh
    assert abh["short"]["active_artifact_id"] == "art_short_demo_v0"
    assert abh["short"]["display_id"] == "art_short_value_accruals_v1"
    assert abh["short"]["display_family_name_ko"] == "단기 가치 (발생액)"


def test_health_payload_when_bundle_missing_has_empty_provenance(tmp_path: Path) -> None:
    payload = build_cockpit_runtime_health_payload(repo_root=tmp_path)
    gate = payload["mvp_brain_gate"]
    assert gate["contract"] == "MVP_RUNTIME_BRAIN_GATE_V1"
    assert gate["bundle_as_of_utc"] == ""
    assert gate["horizon_provenance"] == {}
    assert gate["active_artifact_by_horizon"] == {}
    assert gate["registry_bundle_ok"] is False
