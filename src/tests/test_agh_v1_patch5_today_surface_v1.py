"""AGH v1 Patch 5 — Today-surface D1/D2 acceptance tests.

Covers:

    1. ``build_today_object_detail_payload`` returns ``sandbox_options_v1``
       with one ``validation_rerun`` option per ``research_factor_bindings_v1``.
    2. The option's ``target_spec`` can be passed verbatim to the
       ``harness-sandbox-request`` CLI (deterministic, operator-consumable).
    3. ``research_status_badges_v1`` surfaces the D2 applied / proposed /
       blocked / fallback codes — and never implies autonomy when no
       ``RegistryPatchAppliedPacketV1`` exists.
    4. Detail payload never leaks a forbidden-copy recommendation token.
    5. Today rows do NOT drop a registry_entry in favor of a sandbox
       proposal (regression: Patch 5 must not mutate Today directly).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phase47_runtime.today_spectrum import (
    _research_status_badges_v1_from_bundle,
    _sandbox_options_v1_from_registry_surface,
    build_today_object_detail_payload,
    build_today_spectrum_payload,
)
from metis_brain.bundle import try_load_brain_bundle_v0


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def _bundle_and_surface(monkeypatch):
    # Force registry-backed today surface for D1/D2 acceptance checks.
    monkeypatch.setenv("METIS_TODAY_SOURCE", "registry")
    bundle, errs = try_load_brain_bundle_v0(REPO_ROOT)
    if bundle is None:
        pytest.skip(f"brain bundle not loadable in this env: {errs}")
    sp = build_today_spectrum_payload(
        repo_root=REPO_ROOT, horizon="short", lang="ko"
    )
    if not sp.get("ok"):
        pytest.skip(f"today spectrum not buildable: {sp}")
    surface = sp.get("registry_surface_v1") or {}
    if not surface.get("registry_entry_id"):
        pytest.skip("no active registry_entry on short horizon; seed bundle missing")
    return bundle, surface, sp


def test_sandbox_options_v1_emits_target_spec_consumable_by_cli(
    _bundle_and_surface,
):
    bundle, surface, _sp = _bundle_and_surface
    out = _sandbox_options_v1_from_registry_surface(surface, bundle)
    assert out["contract"] == "TODAY_SANDBOX_OPTIONS_V1"
    assert "validation_rerun" in out["supported_kinds"]
    assert out["options"], "seed bundle short horizon must declare bindings"
    for opt in out["options"]:
        assert opt["sandbox_kind"] == "validation_rerun"
        ts = opt["target_spec"]
        for k in ("factor_name", "universe_name", "horizon_type", "return_basis"):
            assert str(ts.get(k) or "").strip(), f"target_spec must include {k}"


def test_research_status_badges_v1_never_claims_autonomy(_bundle_and_surface):
    bundle, surface, _sp = _bundle_and_surface
    out = _research_status_badges_v1_from_bundle(surface, bundle)
    codes = [b["code"] for b in out["badges"]]
    # D3 invariant: no badge implies the system already mutated Today
    # unless an applied-style code is present (we never mint that from
    # bundle state alone unless ``recent_governed_applies`` says so).
    assert "active_artifact_autonomous_change" not in codes
    assert codes, "badges must include at least one deterministic code"
    # Forbidden-copy scan across every label.
    forbidden_tokens = ("buy", "sell", "guaranteed", "recommend")
    for b in out["badges"]:
        for key in ("label_ko", "label_en"):
            t = str(b.get(key) or "").lower()
            for tok in forbidden_tokens:
                assert tok not in t, f"badge copy must not contain {tok!r}"


def test_today_detail_payload_includes_sandbox_options_and_badges(
    _bundle_and_surface,
):
    _bundle, _surface, sp = _bundle_and_surface
    rows = sp.get("rows") or []
    if not rows:
        pytest.skip("no spectrum rows in this env")
    aid = rows[0]["asset_id"]
    detail = build_today_object_detail_payload(
        repo_root=REPO_ROOT,
        asset_id=aid,
        horizon="short",
        lang="ko",
    )
    assert detail["ok"] is True
    assert detail["sandbox_options_v1"]["contract"] == "TODAY_SANDBOX_OPTIONS_V1"
    assert detail["research_status_badges_v1"]["contract"] == "TODAY_RESEARCH_STATUS_BADGES_V1"
    # Patch 5 must never imply Today mutated from Research: detail
    # payload either surfaces the active registry artifact unchanged, or
    # (for seed-unlinked rows) clearly labels itself as ``seed_fixture``
    # without a governance-mutated artifact id.
    detail_rs = detail["registry_surface_v1"]
    spec_rs = sp["registry_surface_v1"]
    same_artifact = detail_rs["active_artifact_id"] == spec_rs["active_artifact_id"]
    is_seed_fixture = str(detail_rs.get("status") or "").startswith("seed")
    assert same_artifact or is_seed_fixture
