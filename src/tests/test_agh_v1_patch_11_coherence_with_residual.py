"""Patch 11 — Cross-surface coherence with residual / overlay / long-horizon.

The Patch 10C coherence signature already fingerprints
``(asset_id, horizon_key, source_key, grade_key, stance_key, rows_count,
as_of_utc)``. Patch 11 extends the fingerprint with three new
semantically-meaningful keys:

- ``recheck_cadence_key``     — controlled key from RECHECK_CADENCE_KINDS
- ``invalidation_hint_kind``  — controlled key from INVALIDATION_HINT_KINDS
- ``overlay_note_kind_key``   — dominant kind_key from BRAIN_OVERLAY_KINDS

Goals:

1. When two shared_focus blocks are identical in Patch 10C fields but
   differ in any of the Patch 11 additions, their fingerprints MUST
   differ (the signature tracks real semantic drift).
2. When no Patch 11 additions are present, the signature still
   fingerprints correctly and all four Product Shell surfaces agree
   on the same 12-hex value for the same focus.
3. Switching language MUST NOT change the fingerprint.
4. Patch 11 additions do NOT alter the 12-hex width of the signature.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from phase47_runtime.product_shell.view_models import compose_today_product_dto
from phase47_runtime.product_shell.view_models_ask import compose_quick_answers_dto
from phase47_runtime.product_shell.view_models_common import (
    build_shared_focus_block,
    compute_coherence_signature,
)
from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto
from phase47_runtime.product_shell.view_models_research import (
    compose_research_deepdive_dto,
)


_NOW = "2026-04-23T00:00:00Z"


def _bundle(overlays: list[dict] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        as_of_utc=_NOW,
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "real_derived"},
        },
        registry_entries=[SimpleNamespace(
            status="active", horizon="short",
            active_artifact_id="art_x", registry_entry_id="reg_x",
            display_family_name_ko="모멘텀", display_family_name_en="Momentum",
        )],
        artifacts=[SimpleNamespace(
            artifact_id="art_x",
            display_family_name_ko="모멘텀",
            display_family_name_en="Momentum",
        )],
        metadata={"built_at_utc": _NOW, "graduation_tier": "production"},
        brain_overlays=overlays or [],
    )


def _row(
    *,
    recheck: str = "monthly_after_new_filing_or_21_trading_days",
    invalidation: str = "spectrum_position_crosses_midline",
) -> dict:
    return {
        "asset_id":           "AAPL",
        "spectrum_position":  0.42,
        "what_changed":       "Momentum picked up after earnings beat.",
        "rationale_summary":  "Short-term flow and breadth leaning long.",
        "residual_score_semantics_version": "residual_semantics_v1",
        "invalidation_hint":  invalidation,
        "recheck_cadence":    recheck,
    }


def _spec(**row_overrides) -> dict:
    row = _row(**row_overrides)
    return {
        "short":       {"ok": True, "rows": [row]},
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long":        {"ok": True, "rows": []},
    }


def _overlay(kind: str) -> dict:
    return {
        "overlay_id":        f"ovr_{kind}",
        "overlay_type":      kind,
        "artifact_id":       "art_x",
        "registry_entry_id": "",
        "counter_interpretation_present": True,
    }


# ---------------------------------------------------------------------------
# Patch 10C fingerprint still works with no Patch 11 additions.
# ---------------------------------------------------------------------------


def test_fingerprint_width_is_preserved():
    focus = build_shared_focus_block(
        bundle=_bundle(), spectrum_by_horizon=_spec(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    fp = focus["coherence_signature"]["fingerprint"]
    assert isinstance(fp, str)
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)


def test_fingerprint_is_language_independent():
    f_ko = build_shared_focus_block(
        bundle=_bundle(), spectrum_by_horizon=_spec(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    f_en = build_shared_focus_block(
        bundle=_bundle(), spectrum_by_horizon=_spec(),
        asset_id="AAPL", horizon_key="short", lang="en",
    )["coherence_signature"]["fingerprint"]
    assert f_ko == f_en


# ---------------------------------------------------------------------------
# Patch 11 — residual semantics drift is captured.
# ---------------------------------------------------------------------------


def test_fingerprint_moves_with_recheck_cadence_change():
    f_monthly = build_shared_focus_block(
        bundle=_bundle(),
        spectrum_by_horizon=_spec(recheck="monthly_after_new_filing_or_21_trading_days"),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    f_quarterly = build_shared_focus_block(
        bundle=_bundle(),
        spectrum_by_horizon=_spec(recheck="quarterly_after_new_filing_or_63_trading_days"),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    assert f_monthly != f_quarterly


def test_fingerprint_moves_with_invalidation_hint_change():
    f_mid = build_shared_focus_block(
        bundle=_bundle(),
        spectrum_by_horizon=_spec(invalidation="spectrum_position_crosses_midline"),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    f_conf = build_shared_focus_block(
        bundle=_bundle(),
        spectrum_by_horizon=_spec(invalidation="confidence_band_drops_to_low"),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    assert f_mid != f_conf


# ---------------------------------------------------------------------------
# Patch 11 — overlay dominant kind captured.
# ---------------------------------------------------------------------------


def test_fingerprint_moves_with_overlay_kind_change():
    f_catalyst = build_shared_focus_block(
        bundle=_bundle(overlays=[_overlay("catalyst_window")]),
        spectrum_by_horizon=_spec(), asset_id="AAPL",
        horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    f_invalid = build_shared_focus_block(
        bundle=_bundle(overlays=[_overlay("invalidation_warning")]),
        spectrum_by_horizon=_spec(), asset_id="AAPL",
        horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    assert f_catalyst != f_invalid


def test_fingerprint_same_when_only_non_fingerprinted_fields_change():
    """Adding a second overlay that does not change the *dominant* kind
    should NOT move the fingerprint (the signature captures semantics,
    not identity)."""
    b1 = _bundle(overlays=[_overlay("catalyst_window")])
    b2 = _bundle(overlays=[_overlay("catalyst_window"),
                           _overlay("catalyst_window")])
    f1 = build_shared_focus_block(
        bundle=b1, spectrum_by_horizon=_spec(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    f2 = build_shared_focus_block(
        bundle=b2, spectrum_by_horizon=_spec(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )["coherence_signature"]["fingerprint"]
    assert f1 == f2


# ---------------------------------------------------------------------------
# Cross-surface parity holds even after Patch 11 additions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_four_surfaces_agree_on_patch_11_fingerprint(lang):
    bundle = _bundle(overlays=[_overlay("catalyst_window")])
    spec = _spec()
    today = compose_today_product_dto(
        bundle=bundle, spectrum_by_horizon=spec, lang=lang, now_utc=_NOW,
    )
    deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=_NOW,
    )
    replay = compose_replay_product_dto(
        bundle=bundle, spectrum_by_horizon=spec, lineage=None,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=_NOW,
    )
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang,
    )
    today_short = next(
        hc for hc in today["hero_cards"] if hc["horizon_key"] == "short"
    )
    fp_set = {
        today_short["coherence_signature"]["fingerprint"],
        deepdive["shared_focus"]["coherence_signature"]["fingerprint"],
        replay["shared_focus"]["coherence_signature"]["fingerprint"],
        quick["shared_focus"]["coherence_signature"]["fingerprint"],
    }
    assert len(fp_set) == 1, f"Fingerprints diverged across surfaces: {fp_set}"


# ---------------------------------------------------------------------------
# compute_coherence_signature direct: Patch 11 params have sane defaults.
# ---------------------------------------------------------------------------


def test_compute_coherence_signature_accepts_patch_11_kwargs_with_defaults():
    base_kwargs = dict(
        asset_id="AAPL",
        horizon_key="short",
        position=0.42,
        grade_key="a",
        stance_key="long",
        source_key="live",
        what_changed="x",
        rationale_summary="y",
    )
    sig = compute_coherence_signature(**base_kwargs)
    assert len(sig["fingerprint"]) == 12

    sig_explicit = compute_coherence_signature(
        **base_kwargs,
        recheck_cadence_key="",
        invalidation_hint_kind="",
        overlay_note_kind_key="",
    )
    assert sig["fingerprint"] == sig_explicit["fingerprint"], (
        "Default-valued Patch 11 kwargs MUST produce the same fingerprint "
        "as the Patch 10C backward-compatible path."
    )

    sig_with = compute_coherence_signature(
        **base_kwargs, recheck_cadence_key="monthly",
    )
    assert sig_with["fingerprint"] != sig["fingerprint"]
