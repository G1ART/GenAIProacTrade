"""Bounded Non-Quant Cash-Out v1 — BNCO-6 long-horizon honesty.

Verifies that horizon_provenance.source projects into the canonical 4 values
(``real_derived / real_derived_with_degraded_challenger / template_fallback
/ insufficient_evidence``) and that cockpit runtime health exposes a
``horizon_state_v1`` that uses that same vocabulary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from phase51_runtime.cockpit_health_surface import (
    HORIZON_STATE_V1_VALUES,
    _horizon_state_v1_from_provenance,
    build_cockpit_runtime_health_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_current_bundle() -> dict:
    p = REPO_ROOT / "data" / "mvp" / "metis_brain_bundle_from_db_v0.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_horizon_state_v1_values_are_canonical_four_only() -> None:
    assert HORIZON_STATE_V1_VALUES == (
        "real_derived",
        "real_derived_with_degraded_challenger",
        "template_fallback",
        "insufficient_evidence",
    )


def test_horizon_state_projects_unknown_sources_to_insufficient_evidence() -> None:
    prov = {
        "short": {"source": "real_derived"},
        "medium": {"source": "real_derived_with_degraded_challenger"},
        "medium_long": {"source": "template_fallback"},
        "long": {"source": "degraded_pending_real_derived"},  # non-canonical
    }
    out = _horizon_state_v1_from_provenance(prov, ("short", "medium", "medium_long", "long"))
    assert out == {
        "short": "real_derived",
        "medium": "real_derived_with_degraded_challenger",
        "medium_long": "template_fallback",
        "long": "insufficient_evidence",
    }


def test_horizon_state_defaults_missing_horizons_to_insufficient_evidence() -> None:
    out = _horizon_state_v1_from_provenance({}, ("short", "medium"))
    assert out == {"short": "insufficient_evidence", "medium": "insufficient_evidence"}


def test_cockpit_health_exposes_horizon_state_v1_for_current_bundle() -> None:
    payload = build_cockpit_runtime_health_payload(repo_root=REPO_ROOT)
    hstate = payload["mvp_brain_gate"]["horizon_state_v1"]
    assert set(hstate.keys()) == {"short", "medium", "medium_long", "long"}
    for v in hstate.values():
        assert v in HORIZON_STATE_V1_VALUES


def test_cockpit_health_projects_unknown_source_on_custom_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = _load_current_bundle()
    prov = dict(raw.get("horizon_provenance") or {})
    # Force a horizon to have a legacy / unknown source label. The surface
    # MUST still degrade it to insufficient_evidence — never surface
    # overclaim.
    prov["long"] = {
        "source": "degraded_pending_real_derived",
        "reason": "simulated_legacy_label_for_test",
        "contributing_gates": [],
    }
    raw["horizon_provenance"] = prov
    p = tmp_path / "bundle.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(p))
    payload = build_cockpit_runtime_health_payload(repo_root=REPO_ROOT)
    hstate = payload["mvp_brain_gate"]["horizon_state_v1"]
    assert hstate["long"] == "insufficient_evidence"


def test_bundle_builder_canonicalizes_degraded_pending_to_insufficient_evidence() -> None:
    """Direct unit test of the canonicalization step in
    ``build_bundle_full_from_validation_v1``.

    We patch the provenance inside the builder's scope via module reload
    or directly invoke the projection logic: here, since the logic lives
    inline, we just verify the post-build bundle has no
    ``degraded_pending_real_derived`` left on the canonical 4 horizons.
    """
    raw = _load_current_bundle()
    prov = raw.get("horizon_provenance") or {}
    for hz, entry in prov.items():
        src = str((entry or {}).get("source") or "")
        # The canonical 4 set must be the closed universe for operators.
        assert src in HORIZON_STATE_V1_VALUES, (hz, src)


def test_metis_brain_bundle_build_v2_has_insufficient_evidence_reason_hint() -> None:
    cfg_path = REPO_ROOT / "data" / "mvp" / "metis_brain_bundle_build_v2.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    fb = cfg.get("horizon_fallback_labels") or {}
    for hz_key in ("medium_long", "long"):
        entry = fb.get(hz_key) or {}
        assert entry.get("insufficient_evidence_reason_hint"), (
            f"{hz_key}: missing insufficient_evidence_reason_hint"
        )
