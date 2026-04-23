"""Patch 11 — Copy & engineering-ID no-leak scanner (Brain Bundle v3).

Extends the 10A/10B/10C no-leak guarantees with the new Patch 11
surface area:

- ``shared_focus.residual_freshness`` — never leak the raw slug forms
  (``residual_semantics_v1`` lowercase is scrubbed; only the normalized
  controlled-vocabulary keys survive).
- ``shared_focus.long_horizon_support`` — only the tier label / body /
  tier_key survive; raw ``n_rows`` / ``coverage_ratio`` telemetry is
  stripped at the view layer.
- ``shared_focus.overlay_note`` — only ``kind_key`` (one of five
  buckets) and localized label/body survive; ``ovr_*`` overlay ids
  never appear.
- Static artifacts (``index.html``, ``product_shell.js``,
  ``product_shell.css``) must not carry any ``ovr_*`` / ``pcp_*`` /
  ``persona_candidate_id`` tokens.
- Locale dictionary gains three new families
  (``brain_overlay.*``, ``residual.*``, ``long_horizon_support.*``)
  with strict KO/EN parity.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from phase47_runtime.phase47e_user_locale import SHELL
from phase47_runtime.product_shell.view_models import compose_today_product_dto
from phase47_runtime.product_shell.view_models_ask import (
    compose_ask_product_dto,
    compose_quick_answers_dto,
)
from phase47_runtime.product_shell.view_models_common import (
    BRAIN_OVERLAY_KINDS,
    BRAIN_OVERLAY_WORDING,
    ENG_ID_PATTERNS,
    INVALIDATION_HINT_KINDS,
    LONG_HORIZON_SUPPORT_WORDING,
    LONG_HORIZON_TIER_KEYS,
    RECHECK_CADENCE_KINDS,
    RESIDUAL_WORDING,
    SHARED_WORDING,
    build_shared_focus_block,
    strip_engineering_ids,
)
from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto
from phase47_runtime.product_shell.view_models_research import (
    compose_research_deepdive_dto,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATIC = _REPO_ROOT / "src" / "phase47_runtime" / "static"
_PRODUCT_STATIC: tuple[Path, ...] = (
    _STATIC / "index.html",
    _STATIC / "product_shell.js",
    _STATIC / "product_shell.css",
)


# ---------------------------------------------------------------------------
# Synthetic bundle carrying all Patch 11 surface area at once.
# ---------------------------------------------------------------------------


_NOW = "2026-04-23T00:00:00Z"


def _row(residual: bool = True) -> dict:
    r = {
        "asset_id":           "AAPL",
        "spectrum_position":  0.42,
        "what_changed":       "Momentum picked up after earnings beat.",
        "rationale_summary":  "Short-term flow and breadth leaning long.",
    }
    if residual:
        r["residual_score_semantics_version"] = "residual_semantics_v1"
        r["invalidation_hint"] = "spectrum_position_crosses_midline"
        r["recheck_cadence"] = "monthly_after_new_filing_or_21_trading_days"
    return r


def _bundle() -> SimpleNamespace:
    return SimpleNamespace(
        as_of_utc=_NOW,
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "insufficient_evidence"},
        },
        registry_entries=[SimpleNamespace(
            status="active", horizon="short",
            active_artifact_id="art_x", registry_entry_id="reg_x",
            display_family_name_ko="모멘텀", display_family_name_en="Momentum",
            challenger_artifact_ids=["art_ch"],
        )],
        artifacts=[SimpleNamespace(
            artifact_id="art_x",
            display_family_name_ko="모멘텀",
            display_family_name_en="Momentum",
        )],
        metadata={"built_at_utc": _NOW, "graduation_tier": "production"},
        brain_overlays=[{
            "overlay_id":        "ovr_secret_internal_999",
            "overlay_type":      "catalyst_window",
            "artifact_id":       "art_x",
            "registry_entry_id": "",
            "confidence":        0.8,
            "counter_interpretation_present": True,
            "expected_direction_hint": "",
            "expiry_or_recheck_rule": "expires_after_next_filing",
        }],
        long_horizon_support_by_horizon={
            "medium_long": {
                "contract_version": "LONG_HORIZON_SUPPORT_V1",
                "tier_key":         "limited",
                "n_rows":           25,
                "n_symbols":        10,
                "coverage_ratio":   0.55,
                "as_of_utc":        _NOW,
                "reason":           "limited_evidence",
            },
            "long": {
                "contract_version": "LONG_HORIZON_SUPPORT_V1",
                "tier_key":         "sample",
                "n_rows":           3,
                "n_symbols":        2,
                "coverage_ratio":   0.1,
                "as_of_utc":        _NOW,
                "reason":           "sample",
            },
        },
        spectrum_rows_by_horizon={
            "short":       [_row()],
            "medium":      [_row()],
            "medium_long": [_row()],
            "long":        [_row(residual=False)],
        },
    )


def _spectrum() -> dict:
    return {
        "short":       {"ok": True, "rows": [_row()]},
        "medium":      {"ok": True, "rows": [_row()]},
        "medium_long": {"ok": True, "rows": [_row()]},
        "long":        {"ok": True, "rows": [_row(residual=False)]},
    }


# ---------------------------------------------------------------------------
# Static asset scans
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("artifact_path", _PRODUCT_STATIC)
def test_static_artifact_no_overlay_or_persona_engineering_ids(artifact_path):
    text = artifact_path.read_text(encoding="utf-8")
    for pat in (r"\bovr_[A-Za-z0-9_]+", r"\bpcp_[A-Za-z0-9_]+"):
        import re
        m = re.search(pat, text)
        assert m is None, (
            f"{artifact_path.name} leaks {m.group(0)!r} — engineering ids "
            "must never appear in customer static assets."
        )


# ---------------------------------------------------------------------------
# Controlled-vocabulary surfaces
# ---------------------------------------------------------------------------


def test_residual_vocab_covers_controlled_keys_both_langs():
    for lg in ("ko", "en"):
        for kind in RECHECK_CADENCE_KINDS:
            entry = RESIDUAL_WORDING[lg]["recheck"][kind]
            assert entry["label"] and entry["body"], f"{lg}.{kind}"
        for kind in INVALIDATION_HINT_KINDS:
            entry = RESIDUAL_WORDING[lg]["invalidation"][kind]
            assert entry["label"] and entry["body"], f"{lg}.{kind}"


def test_long_horizon_support_wording_covers_all_tiers_both_langs():
    for lg in ("ko", "en"):
        for tier in LONG_HORIZON_TIER_KEYS:
            entry = LONG_HORIZON_SUPPORT_WORDING[lg][tier]
            assert entry["label"] and entry["body"], f"{lg}.{tier}"


def test_brain_overlay_wording_covers_all_five_buckets_both_langs():
    for lg in ("ko", "en"):
        for kind in BRAIN_OVERLAY_KINDS:
            entry = BRAIN_OVERLAY_WORDING[lg][kind]
            assert entry["label"] and entry["body"], f"{lg}.{kind}"


def test_shared_wording_is_ko_en_parallel():
    ko = SHARED_WORDING["ko"]
    en = SHARED_WORDING["en"]
    assert set(ko.keys()) == set(en.keys())
    for key in ko:
        # Each SHARED_WORDING bucket maps to a dict of subfields
        # (``title`` / ``body`` / ``chip`` ...). KO and EN must both
        # be dicts with the same subkeys.
        assert isinstance(ko[key], dict) and ko[key]
        assert isinstance(en[key], dict) and en[key]
        assert set(ko[key].keys()) == set(en[key].keys()), f"{key}"
        # Subfields MUST always be strings (possibly empty for optional
        # ``body`` entries) and exist in both locales.
        for sub, val in ko[key].items():
            assert isinstance(val, str), f"ko.{key}.{sub} not str"
            assert isinstance(en[key][sub], str), f"en.{key}.{sub} not str"


# ---------------------------------------------------------------------------
# DTO no-leak
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_full_dtos_have_no_raw_overlay_or_persona_ids(lang):
    bundle = _bundle()
    spec = _spectrum()
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
    ask = compose_ask_product_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=_NOW,
    )
    for dto in (today, deepdive, replay, quick, ask):
        blob = repr(dto)
        assert "ovr_" not in blob, f"ovr_ leak in DTO: {dto.get('contract')}"
        assert "pcp_" not in blob
        assert "persona_candidate_id" not in blob
        # The raw ``overlay_id`` key name from the internal overlay
        # record must never appear in product DTOs.
        assert "overlay_id" not in blob


def test_shared_focus_residual_has_no_raw_slug_leak():
    bundle = _bundle()
    focus = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    rf = focus.get("residual_freshness")
    assert rf is not None
    blob = repr(rf).lower()
    # Raw slug wording must not leak into the user-facing block.
    assert "trading_days" not in blob
    assert "crosses_midline" not in blob
    assert "confidence_band_drops_to_low" not in blob
    assert "pit_validation_fails" not in blob


def test_shared_focus_long_horizon_support_has_no_raw_telemetry():
    bundle = _bundle()
    focus = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="medium_long", lang="en",
    )
    lh = focus.get("long_horizon_support")
    assert lh is not None
    assert "tier_key" in lh
    assert "n_rows" not in lh
    assert "coverage_ratio" not in lh
    assert "n_symbols" not in lh


def test_shared_focus_overlay_note_has_no_engineering_ids():
    bundle = _bundle()
    focus = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="en",
    )
    ov = focus.get("overlay_note")
    assert ov is not None
    blob = repr(ov)
    assert "ovr_" not in blob
    assert "overlay_id" not in blob


# ---------------------------------------------------------------------------
# Scrubber sanity — regression guard on the new engineering-id patterns.
# ---------------------------------------------------------------------------


def test_scrubber_recognises_patch_11_engineering_id_patterns():
    """The scrubber must understand three *new* engineering-id families."""
    cleaned = strip_engineering_ids({
        "evidence": [
            "ovr_catalyst_001 is leaking",
            "pcp_persona_xyz123 is leaking",
            "brain_overlay_ids is leaking",
        ],
    })
    blob = repr(cleaned)
    assert "ovr_catalyst_001" not in blob
    assert "pcp_persona_xyz123" not in blob
    assert "brain_overlay_ids" not in blob


def test_eng_id_patterns_include_patch_11_additions():
    """Defensive check — the pattern list must not drop the new entries."""
    joined = " ".join(p.pattern for p in ENG_ID_PATTERNS)
    assert "ovr_" in joined
    assert "pcp_" in joined
    assert "persona_candidate_id" in joined
    assert "brain_overlay_ids" in joined


# ---------------------------------------------------------------------------
# Locale SHELL parity (KO ↔ EN) for any new keys touched by Patch 11.
# ---------------------------------------------------------------------------


def test_shell_ko_en_parity_for_locale_keys():
    """SHELL dictionary must keep KO and EN keysets aligned so no
    customer-visible label silently falls back across languages."""
    ko = SHELL.get("ko", {})
    en = SHELL.get("en", {})
    missing_in_en = sorted(set(ko) - set(en))
    missing_in_ko = sorted(set(en) - set(ko))
    assert not missing_in_en, f"SHELL missing in EN: {missing_in_en}"
    assert not missing_in_ko, f"SHELL missing in KO: {missing_in_ko}"
