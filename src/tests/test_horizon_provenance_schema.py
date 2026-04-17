"""Schema tests for the horizon_provenance + display_* alias layer (Step 2)."""

from __future__ import annotations

import json
from pathlib import Path

from metis_brain.bundle import BrainBundleV0, try_load_brain_bundle_v0
from metis_brain.schemas_v0 import (
    ActiveHorizonRegistryEntryV0,
    ModelArtifactPacketV0,
)


def _load_template_bundle() -> dict:
    root = Path(__file__).resolve().parents[2]
    p = root / "data" / "mvp" / "metis_brain_bundle_v0.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_artifact_display_fields_default_empty() -> None:
    a = ModelArtifactPacketV0(
        artifact_id="x",
        created_at="",
        created_by="",
        horizon="short",
        universe="u",
        sector_scope="s",
        thesis_family="t",
        feature_set="f",
        feature_transforms="ft",
        weighting_rule="w",
        score_formula="sf",
        banding_rule="b",
        ranking_direction="r",
        invalidation_conditions="i",
        expected_holding_horizon="short",
        confidence_rule="c",
        evidence_requirements="e",
        validation_pointer="v",
        replay_eligibility="re",
        notes_for_message_layer="n",
    )
    assert a.display_id == ""
    assert a.display_family_name_ko == ""
    assert a.display_family_name_en == ""


def test_registry_entry_display_fields_default_empty() -> None:
    e = ActiveHorizonRegistryEntryV0(
        registry_entry_id="r1",
        horizon="short",
        active_model_family_name="fam",
        active_artifact_id="x",
        universe="u",
        sector_scope="s",
        effective_from="",
        effective_to="",
        scoring_endpoint_contract="inline_spectrum_rows_v0",
        message_contract_version="v1",
        replay_lineage_pointer="",
        status="active",
    )
    assert e.display_id == ""
    assert e.display_family_name_ko == ""


def test_bundle_horizon_provenance_defaults_to_empty_dict() -> None:
    raw = _load_template_bundle()
    bundle = BrainBundleV0.model_validate(raw)
    assert isinstance(bundle.horizon_provenance, dict)
    assert bundle.horizon_provenance == {}


def test_bundle_accepts_horizon_provenance_with_fallback_labels() -> None:
    raw = _load_template_bundle()
    raw["horizon_provenance"] = {
        "short": {
            "source": "real_derived",
            "factor_name": "accruals",
            "validation_horizon_type": "next_month",
            "return_basis": "raw",
            "run_id": "run-x",
            "pit_pass": True,
            "pit_rule": "accepted_at_signal_date_pit_rule_v0",
            "coverage_pass": True,
            "monotonicity_pass": True,
            "spectrum_row_count": 195,
            "artifact_id": "art_short_demo_v0",
            "registry_entry_id": "reg_short_demo_v0",
            "display_id": "art_short_value_accruals_v1",
            "display_family_name_ko": "단기 가치(발생액)",
            "display_family_name_en": "Short value — accruals",
        },
        "medium_long": {
            "source": "template_fallback",
            "reason": "forward_returns_horizon_not_yet_emitted_for_next_half_year",
            "artifact_id": "art_medium_long_demo_v0",
            "registry_entry_id": "reg_medium_long_demo_v0",
            "display_family_name_ko": "중장기 (샘플 전용)",
            "display_family_name_en": "Medium-long (sample only)",
        },
    }
    raw["artifacts"][0]["display_id"] = "art_short_value_accruals_v1"
    raw["artifacts"][0]["display_family_name_ko"] = "단기 가치(발생액)"
    raw["registry_entries"][0]["display_id"] = "reg_short_value_v1"
    bundle = BrainBundleV0.model_validate(raw)
    assert bundle.horizon_provenance["short"]["source"] == "real_derived"
    assert bundle.horizon_provenance["medium_long"]["source"] == "template_fallback"
    assert bundle.artifacts[0].display_id == "art_short_value_accruals_v1"
    assert bundle.registry_entries[0].display_id == "reg_short_value_v1"


def test_template_bundle_still_loads_via_try_load_with_new_fields() -> None:
    root = Path(__file__).resolve().parents[2]
    bundle, errs = try_load_brain_bundle_v0(root)
    assert errs == []
    assert bundle is not None
    assert isinstance(bundle.horizon_provenance, dict)
