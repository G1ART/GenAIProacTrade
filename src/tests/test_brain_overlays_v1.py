"""Pragmatic Brain Absorption v1 — Milestone C.

Covers the BrainOverlayV1 schema, seed loading, bundle integrity enforcement
of overlay bindings, and runtime cash-out (cockpit health summary + Today
registry surface overlay ids).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from metis_brain.brain_overlays_v1 import (
    BrainOverlaySeedFileV1,
    BrainOverlayV1,
    load_brain_overlays_seed,
    overlay_influence_lookup,
    summarize_overlays_for_runtime,
    validate_overlays_against_bundle,
)
from metis_brain.bundle import BrainBundleV0, validate_active_registry_integrity


REPO_ROOT = Path(__file__).resolve().parents[2]


def _minimal_overlay(**overrides) -> dict:
    base = {
        "overlay_id": "ovr_test_v1",
        "overlay_type": "regime_shift",
        "artifact_id": "art_x",
        "source_artifact_refs": [
            {"kind": "earnings_transcript", "pointer": "seed:test:v1", "summary": "s"}
        ],
        "pit_timestamp_window": {"starts_at": "2026-01-01T00:00:00Z", "ends_at": "2026-04-01T00:00:00Z"},
        "awareness_lag_rule": "only_applied_after_transcript_publication_date",
        "confidence": 0.5,
        "counter_interpretation_present": True,
        "reasons": ["reason_a"],
        "provenance_summary": "seed:test",
        "expiry_or_recheck_rule": "recheck_2026-06-01",
    }
    base.update(overrides)
    return base


def test_overlay_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError):
        BrainOverlayV1.model_validate(_minimal_overlay(overlay_type="not_a_real_type"))


def test_overlay_confidence_range() -> None:
    with pytest.raises(ValidationError):
        BrainOverlayV1.model_validate(_minimal_overlay(confidence=1.5))
    with pytest.raises(ValidationError):
        BrainOverlayV1.model_validate(_minimal_overlay(confidence=-0.1))


def test_overlay_requires_exactly_one_target() -> None:
    # Both set → rejected at bound_reference().
    ov_both = BrainOverlayV1.model_validate(
        _minimal_overlay(artifact_id="art_x", registry_entry_id="reg_x")
    )
    with pytest.raises(ValueError):
        ov_both.bound_reference()
    # Neither set → rejected.
    ov_neither = BrainOverlayV1.model_validate(
        _minimal_overlay(artifact_id="", registry_entry_id="")
    )
    with pytest.raises(ValueError):
        ov_neither.bound_reference()
    # Only artifact set → accepted.
    ov_ok = BrainOverlayV1.model_validate(_minimal_overlay())
    assert ov_ok.bound_reference() == ("artifact_id", "art_x")


def test_validate_overlays_against_bundle_flags_missing_target() -> None:
    ov = BrainOverlayV1.model_validate(_minimal_overlay(artifact_id="missing_art"))
    errs = validate_overlays_against_bundle(
        [ov], artifact_ids={"real_art"}, registry_entry_ids={"real_reg"}
    )
    assert errs and "missing_art" in errs[0]


def test_summarize_overlays_and_influence_lookup() -> None:
    overlays = [
        BrainOverlayV1.model_validate(_minimal_overlay(overlay_id="a", artifact_id="art_1")),
        BrainOverlayV1.model_validate(
            _minimal_overlay(overlay_id="b", overlay_type="catalyst_window", artifact_id="", registry_entry_id="reg_1")
        ),
    ]
    summary = summarize_overlays_for_runtime(overlays)
    assert summary["total"] == 2
    assert summary["count_by_type"] == {"regime_shift": 1, "catalyst_window": 1}
    lookup = overlay_influence_lookup(overlays)
    assert lookup == {"art_1": ["a"], "reg_1": ["b"]}


def _load_current_bundle() -> dict:
    p = REPO_ROOT / "data" / "mvp" / "metis_brain_bundle_from_db_v0.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_bundle_accepts_valid_overlays() -> None:
    raw = _load_current_bundle()
    raw["brain_overlays"] = [
        _minimal_overlay(artifact_id="art_short_demo_v0"),
        _minimal_overlay(
            overlay_id="ovr_reg_test_v1",
            artifact_id="",
            registry_entry_id="reg_short_demo_v0",
        ),
    ]
    bundle = BrainBundleV0.model_validate(raw)
    errs = validate_active_registry_integrity(bundle)
    assert errs == [], f"overlays bound to real bundle entities must be accepted: {errs}"


def test_bundle_rejects_overlay_with_unknown_artifact() -> None:
    raw = _load_current_bundle()
    raw["brain_overlays"] = [_minimal_overlay(artifact_id="art_does_not_exist")]
    bundle = BrainBundleV0.model_validate(raw)
    errs = validate_active_registry_integrity(bundle)
    assert any("art_does_not_exist" in e for e in errs), errs


def test_seed_file_loads_and_binds_to_current_bundle() -> None:
    overlays, errors = load_brain_overlays_seed(REPO_ROOT)
    assert errors == []
    assert overlays, "bounded seed must contain at least one overlay"
    raw = _load_current_bundle()
    art_ids = {a["artifact_id"] for a in raw.get("artifacts") or []}
    reg_ids = {e["registry_entry_id"] for e in raw.get("registry_entries") or []}
    binding_errs = validate_overlays_against_bundle(
        overlays, artifact_ids=art_ids, registry_entry_ids=reg_ids
    )
    assert binding_errs == [], f"seed overlays must resolve in current bundle: {binding_errs}"


def test_cockpit_health_exposes_overlay_summary() -> None:
    from phase51_runtime.cockpit_health_surface import build_cockpit_runtime_health_payload

    # Patch bundle so the loader can read a bundle with overlays merged in.
    raw = _load_current_bundle()
    raw["brain_overlays"] = [_minimal_overlay(artifact_id="art_short_demo_v0")]
    tmp_bundle = REPO_ROOT / "data" / "mvp" / "_pba_v1_c_test_bundle.json"
    tmp_bundle.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    import os

    prev = os.environ.get("METIS_BRAIN_BUNDLE")
    os.environ["METIS_BRAIN_BUNDLE"] = str(tmp_bundle)
    try:
        payload = build_cockpit_runtime_health_payload(repo_root=REPO_ROOT)
    finally:
        if prev is None:
            os.environ.pop("METIS_BRAIN_BUNDLE", None)
        else:
            os.environ["METIS_BRAIN_BUNDLE"] = prev
        tmp_bundle.unlink(missing_ok=True)
    brain_gate = payload["mvp_brain_gate"]
    assert brain_gate["contract"] == "MVP_RUNTIME_BRAIN_GATE_V1"
    summary = brain_gate["brain_overlays_summary"]
    assert summary["contract"] == "METIS_BRAIN_OVERLAYS_SUMMARY_V1"
    assert summary["total"] == 1
    assert summary["items"][0]["overlay_id"] == "ovr_test_v1"


def test_today_registry_surface_carries_overlay_ids() -> None:
    from phase47_runtime.today_spectrum import _registry_surface_v1_from_bundle_entry

    raw = _load_current_bundle()
    raw["brain_overlays"] = [
        _minimal_overlay(overlay_id="ovr_a", artifact_id="art_short_demo_v0"),
        _minimal_overlay(
            overlay_id="ovr_b",
            artifact_id="",
            registry_entry_id="reg_short_demo_v0",
        ),
    ]
    bundle = BrainBundleV0.model_validate(raw)
    ent = next(e for e in bundle.registry_entries if e.registry_entry_id == "reg_short_demo_v0")
    surface = _registry_surface_v1_from_bundle_entry(bundle, ent)
    assert set(surface["brain_overlay_ids"]) == {"ovr_a", "ovr_b"}
