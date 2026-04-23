"""Patch 11 — M0 residual semantics wiring tests.

Verifies:

1. ``build_message_layer_v1_for_row`` now returns the three residual
   fields (``residual_score_semantics_version`` / ``invalidation_hint``
   / ``recheck_cadence``) so the Today message dict carries them
   through to the UI / Spec §6.4 object layer.
2. ``view_models_common.residual_freshness_block`` normalizes raw
   engineering slugs into a short ``recheck_cadence_key`` /
   ``invalidation_hint_kind`` plus KO/EN labels from
   ``RESIDUAL_WORDING``.
3. ``build_shared_focus_block`` embeds the resulting residual_freshness
   block on the focus, and raw engineering slugs do not leak.
4. The Patch 10C ``compute_coherence_signature`` now mixes
   ``recheck_cadence_key`` + ``invalidation_hint_kind`` into the
   fingerprint, so a recheck-cadence flip (or invalidation-hint change)
   is detectable while KO↔EN stays invariant.
5. All four Product Shell surfaces (Today / Research / Replay / Ask)
   embed the *same* residual_freshness block for the same focus.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from phase47_runtime.message_layer_v1 import (
    MESSAGE_LAYER_V1_KEYS,
    build_message_layer_v1_for_row,
)
from phase47_runtime.product_shell.view_models import compose_today_product_dto
from phase47_runtime.product_shell.view_models_ask import (
    compose_ask_product_dto,
)
from phase47_runtime.product_shell.view_models_common import (
    INVALIDATION_HINT_KINDS,
    RECHECK_CADENCE_KINDS,
    RESIDUAL_WORDING,
    build_shared_focus_block,
    compute_coherence_signature,
    normalize_invalidation_hint,
    normalize_recheck_cadence,
    residual_freshness_block,
    residual_wording,
    strip_engineering_ids,
)
from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto
from phase47_runtime.product_shell.view_models_research import (
    compose_research_deepdive_dto,
)


NOW = "2026-04-23T00:00:00Z"

_RAW_RECHECK = "quarterly_after_new_filing_or_63_trading_days"
_RAW_HINT = "spectrum_position_crosses_midline"
_RAW_VERSION = "residual_semantics_v1"


def _row(
    *,
    asset_id: str = "AAPL",
    position: float = 0.42,
    recheck: str = _RAW_RECHECK,
    hint: str = _RAW_HINT,
    version: str = _RAW_VERSION,
    what_changed: str = "Momentum picked up after earnings beat.",
    rationale: str = "Short-term flow and breadth both leaning long.",
) -> dict:
    return {
        "asset_id": asset_id,
        "spectrum_position": position,
        "rank_index": 0,
        "rank_movement": "up",
        "what_changed": what_changed,
        "rationale_summary": rationale,
        "confidence_band": "medium",
        "residual_score_semantics_version": version,
        "invalidation_hint": hint,
        "recheck_cadence": recheck,
    }


def _spectrum(**row_kwargs) -> dict:
    primary = _row(**row_kwargs)
    return {
        "short": {"ok": True, "rows": [primary]},
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long":        {"ok": True, "rows": []},
    }


def _bundle(source: str = "real_derived") -> SimpleNamespace:
    return SimpleNamespace(
        as_of_utc=NOW,
        horizon_provenance={
            "short":       {"source": source},
            "medium":      {"source": source},
            "medium_long": {"source": source},
            "long":        {"source": source},
        },
        registry_entries=[
            SimpleNamespace(
                status="active",
                horizon="short",
                active_artifact_id="art_x",
                registry_entry_id="reg_x",
                display_family_name_ko="모멘텀",
                display_family_name_en="Momentum",
            ),
        ],
        artifacts=[
            SimpleNamespace(
                artifact_id="art_x",
                display_family_name_ko="모멘텀",
                display_family_name_en="Momentum",
            ),
        ],
        metadata={"built_at_utc": NOW, "graduation_tier": "production"},
    )


# ---------------------------------------------------------------------------
# 1. message_layer_v1 passthrough
# ---------------------------------------------------------------------------


def test_message_layer_dict_carries_residual_three_fields():
    row = _row()
    msg = build_message_layer_v1_for_row(
        row=row,
        horizon="short",
        lang="ko",
        active_model_family="momentum",
        rationale_summary=row["rationale_summary"],
        what_changed=row["what_changed"],
        confidence_band="medium",
        linked_registry_entry_id="reg_x",
        linked_artifact_id="art_x",
    )
    assert "residual_score_semantics_version" in MESSAGE_LAYER_V1_KEYS
    assert "invalidation_hint" in MESSAGE_LAYER_V1_KEYS
    assert "recheck_cadence" in MESSAGE_LAYER_V1_KEYS
    assert msg["residual_score_semantics_version"] == _RAW_VERSION
    assert msg["invalidation_hint"] == _RAW_HINT
    assert msg["recheck_cadence"] == _RAW_RECHECK


def test_message_layer_dict_empty_when_row_has_no_residual():
    row = _row(recheck="", hint="", version="")
    msg = build_message_layer_v1_for_row(
        row=row, horizon="short", lang="ko",
        active_model_family="momentum",
        rationale_summary=row["rationale_summary"],
        what_changed=row["what_changed"],
        confidence_band="medium",
        linked_registry_entry_id="reg_x", linked_artifact_id="art_x",
    )
    assert msg["residual_score_semantics_version"] == ""
    assert msg["invalidation_hint"] == ""
    assert msg["recheck_cadence"] == ""


# ---------------------------------------------------------------------------
# 2. Normalizer + residual_freshness_block helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("monthly_after_new_filing_or_21_trading_days", "monthly"),
        ("quarterly_after_new_filing_or_63_trading_days", "quarterly"),
        ("semi_annually_after_new_filing_or_126_trading_days", "semi_annually"),
        ("annually_after_new_filing_or_252_trading_days", "annually"),
        ("", "unknown"),
        (None, "unknown"),
        ("totally_unknown_slug", "unknown"),
    ],
)
def test_normalize_recheck_cadence(raw, expected):
    assert normalize_recheck_cadence(raw) == expected
    assert expected in RECHECK_CADENCE_KINDS


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("factor_validation_pit_fail", "pit_fail"),
        ("confidence_band_drops_to_low", "confidence_drop"),
        ("spectrum_position_crosses_midline", "midline_cross"),
        ("horizon_returns_reverse_sign", "return_reversal"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_normalize_invalidation_hint(raw, expected):
    assert normalize_invalidation_hint(raw) == expected
    assert expected in INVALIDATION_HINT_KINDS


def test_residual_freshness_block_none_when_no_info():
    assert residual_freshness_block({}, lang="ko") is None
    assert residual_freshness_block(
        {"asset_id": "AAPL"}, lang="en",
    ) is None


def test_residual_freshness_block_labels_match_table():
    block_ko = residual_freshness_block(_row(), lang="ko")
    assert block_ko is not None
    assert block_ko["contract_version"] == "RESIDUAL_SEMANTICS_V1"
    assert block_ko["recheck_cadence_key"] == "quarterly"
    assert block_ko["invalidation_hint_kind"] == "midline_cross"
    assert block_ko["recheck_cadence_label"] == \
        RESIDUAL_WORDING["ko"]["recheck"]["quarterly"]["label"]
    assert block_ko["invalidation_hint_label"] == \
        RESIDUAL_WORDING["ko"]["invalidation"]["midline_cross"]["label"]

    block_en = residual_freshness_block(_row(), lang="en")
    assert block_en is not None
    assert block_en["recheck_cadence_label"] == \
        RESIDUAL_WORDING["en"]["recheck"]["quarterly"]["label"]
    assert block_en["invalidation_hint_label"] == \
        RESIDUAL_WORDING["en"]["invalidation"]["midline_cross"]["label"]


def test_residual_freshness_block_no_raw_slugs_leak():
    """The customer-facing block must only carry short keys + labels;
    no raw engineering slug (``*_days``, ``residual_semantics_v1``,
    ``spectrum_position_crosses_midline``) should appear in any value."""
    block = residual_freshness_block(_row(), lang="ko")
    assert block is not None
    serialized = repr(block)
    assert _RAW_RECHECK not in serialized
    assert _RAW_HINT not in serialized
    assert _RAW_VERSION not in serialized


def test_residual_wording_axis_lookup_unknown_falls_back():
    fallback = residual_wording("recheck", "not_a_real_kind", lang="ko")
    assert fallback["label"] == \
        RESIDUAL_WORDING["ko"]["recheck"]["unknown"]["label"]


# ---------------------------------------------------------------------------
# 3. build_shared_focus_block embeds residual_freshness
# ---------------------------------------------------------------------------


def test_shared_focus_block_embeds_residual_freshness_when_row_matches():
    block = build_shared_focus_block(
        bundle=_bundle(),
        spectrum_by_horizon=_spectrum(),
        asset_id="AAPL",
        horizon_key="short",
        lang="ko",
    )
    assert block["row_matched"] is True
    rf = block.get("residual_freshness")
    assert rf is not None
    assert rf["recheck_cadence_key"] == "quarterly"
    assert rf["invalidation_hint_kind"] == "midline_cross"


def test_shared_focus_block_omits_residual_when_row_missing():
    block = build_shared_focus_block(
        bundle=_bundle(),
        spectrum_by_horizon={
            "short": {"ok": True, "rows": []},
            "medium": {"ok": True, "rows": []},
            "medium_long": {"ok": True, "rows": []},
            "long": {"ok": True, "rows": []},
        },
        asset_id="AAPL",
        horizon_key="short",
        lang="ko",
    )
    assert block["row_matched"] is False
    assert "residual_freshness" not in block


# ---------------------------------------------------------------------------
# 4. Coherence signature extension
# ---------------------------------------------------------------------------


def _sig(**overrides):
    base = dict(
        asset_id="AAPL",
        horizon_key="short",
        position=0.42,
        grade_key="a",
        stance_key="long",
        source_key="live",
        what_changed="x",
        rationale_summary="y",
    )
    base.update(overrides)
    return compute_coherence_signature(**base)


def test_signature_backward_compatible_when_no_residual():
    """With empty recheck/invalidation/overlay keys the signature inputs
    are equivalent to the Patch 10C contract (unchanged call site)."""
    a = _sig()
    b = _sig(recheck_cadence_key="", invalidation_hint_kind="", overlay_note_kind_key="")
    assert a["fingerprint"] == b["fingerprint"]
    assert a["contract_version"] == "COHERENCE_V1"


def test_signature_changes_when_recheck_cadence_flips():
    a = _sig(recheck_cadence_key="monthly")
    b = _sig(recheck_cadence_key="quarterly")
    assert a["fingerprint"] != b["fingerprint"]


def test_signature_changes_when_invalidation_hint_changes():
    a = _sig(invalidation_hint_kind="midline_cross")
    b = _sig(invalidation_hint_kind="pit_fail")
    assert a["fingerprint"] != b["fingerprint"]


def test_signature_language_independent_for_residual():
    """KO vs EN focus blocks for the same row produce identical fingerprints."""
    bundle = _bundle()
    spec = _spectrum()
    ko = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    en = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang="en",
    )
    assert (ko["coherence_signature"]["fingerprint"]
            == en["coherence_signature"]["fingerprint"])
    assert ko["residual_freshness"]["recheck_cadence_key"] == \
        en["residual_freshness"]["recheck_cadence_key"]
    assert (ko["residual_freshness"]["recheck_cadence_label"]
            != en["residual_freshness"]["recheck_cadence_label"])


def test_shared_focus_signature_moves_when_recheck_flips():
    bundle = _bundle()
    a = build_shared_focus_block(
        bundle=bundle,
        spectrum_by_horizon=_spectrum(recheck="monthly_after_new_filing_or_21_trading_days"),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    b = build_shared_focus_block(
        bundle=bundle,
        spectrum_by_horizon=_spectrum(recheck="quarterly_after_new_filing_or_63_trading_days"),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    assert (a["coherence_signature"]["fingerprint"]
            != b["coherence_signature"]["fingerprint"])


# ---------------------------------------------------------------------------
# 5. Four surfaces embed identical residual_freshness block
# ---------------------------------------------------------------------------


def _today_short_focus(today_dto):
    for hc in today_dto["hero_cards"]:
        if hc["horizon_key"] == "short":
            return hc["shared_focus"]
    raise AssertionError("Today DTO missing short hero card")


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_four_surfaces_embed_identical_residual_block(lang):
    bundle = _bundle()
    spec = _spectrum()
    today = compose_today_product_dto(
        bundle=bundle, spectrum_by_horizon=spec, lang=lang, now_utc=NOW,
    )
    deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=NOW,
    )
    replay = compose_replay_product_dto(
        bundle=bundle, spectrum_by_horizon=spec, lineage=None,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=NOW,
    )
    ask = compose_ask_product_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=NOW,
    )
    focus_blocks = [
        _today_short_focus(today),
        deepdive["shared_focus"],
        replay["shared_focus"],
        ask["shared_focus"],
    ]
    residual_blocks = [fb.get("residual_freshness") for fb in focus_blocks]
    assert all(rb is not None for rb in residual_blocks), residual_blocks
    first = residual_blocks[0]
    for rb in residual_blocks[1:]:
        assert rb == first


def test_product_dto_does_not_leak_raw_residual_slugs():
    """Full Today + Research DTOs after strip scrubber must never contain
    raw engineering recheck-cadence or invalidation-hint slugs."""
    bundle = _bundle()
    spec = _spectrum()
    today = compose_today_product_dto(
        bundle=bundle, spectrum_by_horizon=spec, lang="ko", now_utc=NOW,
    )
    scrubbed = strip_engineering_ids(today)
    blob = repr(scrubbed)
    assert _RAW_RECHECK not in blob
    assert _RAW_HINT not in blob
    # The scrubber also catches `_v\d+` slugs; the raw version slug
    # should either be redacted or simply absent.
    assert _RAW_VERSION not in blob
