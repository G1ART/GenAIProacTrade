"""Patch 11 — M2 brain-overlay surfacing tests.

Covers:

- ``overlay_note_block`` returns ``None`` when the bundle carries no
  overlays and returns a well-shaped block when at least one overlay
  is bound to the horizon's active artifact / registry entry.
- Only short ``kind_key`` values from :data:`BRAIN_OVERLAY_KINDS` are
  surfaced; engineering ids (``ovr_*``) never leak.
- ``strip_engineering_ids`` scrubs ``ovr_*`` / ``pcp_*`` /
  ``persona_candidate_id`` tokens.
- ``build_shared_focus_block`` exposes ``overlay_note`` which is
  identical across all four surfaces.
- Coherence signature moves when the overlay's dominant kind changes.
- Research deep-dive ``counter_or_companion`` card includes the
  overlay-sourced counter sentence when ``counter_interpretation_present``
  is true.
- Ask AI ``why_confidence`` / ``whats_missing`` answers embed the
  overlay note when one is present.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from phase47_runtime.product_shell.view_models import compose_today_product_dto
from phase47_runtime.product_shell.view_models_ask import compose_quick_answers_dto
from phase47_runtime.product_shell.view_models_common import (
    BRAIN_OVERLAY_KINDS,
    BRAIN_OVERLAY_WORDING,
    build_shared_focus_block,
    overlay_note_block,
    strip_engineering_ids,
)
from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto
from phase47_runtime.product_shell.view_models_research import (
    compose_research_deepdive_dto,
)


NOW = "2026-04-23T00:00:00Z"


def _bundle(
    overlays: list[dict] | None = None,
    source: str = "real_derived",
) -> SimpleNamespace:
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
                status="active", horizon="short",
                active_artifact_id="art_x", registry_entry_id="reg_x",
                display_family_name_ko="모멘텀", display_family_name_en="Momentum",
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
        brain_overlays=overlays or [],
    )


def _spectrum() -> dict:
    row = {
        "asset_id": "AAPL",
        "spectrum_position": 0.42,
        "what_changed": "Momentum picked up after earnings beat.",
        "rationale_summary": "Short-term flow and breadth both leaning long.",
        "residual_score_semantics_version": "residual_semantics_v1",
        "invalidation_hint": "spectrum_position_crosses_midline",
        "recheck_cadence": "monthly_after_new_filing_or_21_trading_days",
    }
    return {
        "short": {"ok": True, "rows": [row]},
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long":        {"ok": True, "rows": []},
    }


def _overlay(
    *,
    overlay_id="ovr_catalyst_001",
    overlay_type="catalyst_window",
    artifact_id="art_x",
    counter=True,
):
    return {
        "overlay_id": overlay_id,
        "overlay_type": overlay_type,
        "artifact_id": artifact_id,
        "registry_entry_id": "",
        "confidence": 0.75,
        "counter_interpretation_present": counter,
        "expected_direction_hint": "",
        "expiry_or_recheck_rule": "expires_after_next_filing",
    }


# ---------------------------------------------------------------------------
# overlay_note_block helper
# ---------------------------------------------------------------------------


def test_overlay_note_block_none_without_overlays():
    bundle = _bundle(overlays=[])
    assert overlay_note_block(bundle=bundle, horizon_key="short", lang="ko") is None


def test_overlay_note_block_none_for_unbound_horizon():
    """Overlay bound to a different artifact should not surface on the
    short horizon when the active artifact does not match."""
    bundle = _bundle(overlays=[
        _overlay(overlay_id="ovr_x", artifact_id="art_DIFFERENT"),
    ])
    assert overlay_note_block(bundle=bundle, horizon_key="short", lang="ko") is None


def test_overlay_note_block_emits_expected_label_from_table():
    bundle = _bundle(overlays=[_overlay(overlay_type="catalyst_window")])
    ko = overlay_note_block(bundle=bundle, horizon_key="short", lang="ko")
    assert ko is not None
    assert ko["contract_version"] == "BRAIN_OVERLAY_NOTE_V1"
    assert ko["count"] == 1
    assert ko["dominant_kind_key"] == "catalyst_window"
    assert ko["counter_interpretation_present"] is True
    assert ko["items"][0]["kind_key"] == "catalyst_window"
    assert ko["items"][0]["kind_key"] in BRAIN_OVERLAY_KINDS
    assert ko["items"][0]["label"] == BRAIN_OVERLAY_WORDING["ko"]["catalyst_window"]["label"]
    en = overlay_note_block(bundle=bundle, horizon_key="short", lang="en")
    assert en["items"][0]["label"] == BRAIN_OVERLAY_WORDING["en"]["catalyst_window"]["label"]


def test_overlay_note_block_priority_picks_invalidation_first():
    bundle = _bundle(overlays=[
        _overlay(overlay_id="ovr_a", overlay_type="hazard_modifier"),
        _overlay(overlay_id="ovr_b", overlay_type="invalidation_warning"),
        _overlay(overlay_id="ovr_c", overlay_type="catalyst_window"),
    ])
    block = overlay_note_block(bundle=bundle, horizon_key="short", lang="ko")
    assert block is not None
    assert block["dominant_kind_key"] == "invalidation_warning"
    assert block["count"] == 3


def test_overlay_note_block_no_engineering_ids():
    bundle = _bundle(overlays=[
        _overlay(overlay_id="ovr_secret_internal_12345"),
    ])
    block = overlay_note_block(bundle=bundle, horizon_key="short", lang="ko")
    assert block is not None
    serialized = repr(block)
    assert "ovr_" not in serialized
    assert "overlay_id" not in serialized


# ---------------------------------------------------------------------------
# strip_engineering_ids extension
# ---------------------------------------------------------------------------


def test_strip_engineering_ids_scrubs_overlay_and_persona_tokens():
    raw = {
        "story": "see ovr_catalyst_001 and pcp_persona_42",
        "nested": [
            "persona_candidate_id is internal",
            "engineering ref reg_abc lives here",
            "brain_overlay_ids is a telemetry key",
        ],
    }
    cleaned = strip_engineering_ids(raw)
    blob = repr(cleaned)
    assert "ovr_catalyst_001" not in blob
    assert "pcp_persona_42" not in blob
    assert "persona_candidate_id" not in blob
    assert "brain_overlay_ids" not in blob
    assert "reg_abc" not in blob
    assert "[redacted]" in blob


# ---------------------------------------------------------------------------
# Shared focus block embedding
# ---------------------------------------------------------------------------


def test_shared_focus_embeds_overlay_note_when_present():
    bundle = _bundle(overlays=[_overlay()])
    focus = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    ov = focus.get("overlay_note")
    assert ov is not None
    assert ov["dominant_kind_key"] == "catalyst_window"
    sig = focus["coherence_signature"]
    assert sig["overlay_note_kind_key"] == "catalyst_window"


def test_shared_focus_no_overlay_key_when_absent():
    bundle = _bundle(overlays=[])
    focus = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    assert "overlay_note" not in focus
    assert focus["coherence_signature"]["overlay_note_kind_key"] == ""


def test_signature_moves_when_overlay_kind_changes():
    b1 = _bundle(overlays=[_overlay(overlay_type="catalyst_window")])
    b2 = _bundle(overlays=[_overlay(overlay_type="invalidation_warning")])
    f1 = build_shared_focus_block(
        bundle=b1, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    f2 = build_shared_focus_block(
        bundle=b2, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    assert (f1["coherence_signature"]["fingerprint"]
            != f2["coherence_signature"]["fingerprint"])


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_four_surfaces_share_overlay_note(lang):
    bundle = _bundle(overlays=[_overlay()])
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
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang,
    )
    today_short_focus = None
    for hc in today["hero_cards"]:
        if hc["horizon_key"] == "short":
            today_short_focus = hc["shared_focus"]
    assert today_short_focus is not None
    blocks = [
        today_short_focus.get("overlay_note"),
        deepdive["shared_focus"].get("overlay_note"),
        replay["shared_focus"].get("overlay_note"),
        quick["shared_focus"].get("overlay_note"),
    ]
    assert all(b is not None for b in blocks)
    first = blocks[0]
    for b in blocks[1:]:
        assert b == first


# ---------------------------------------------------------------------------
# Research counter card + Ask why_confidence / whats_missing wiring
# ---------------------------------------------------------------------------


def test_research_counter_card_embeds_overlay_sentence_when_counter_present():
    bundle = _bundle(overlays=[_overlay(counter=True)])
    deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko", now_utc=NOW,
    )
    counter_card = next(
        c for c in deepdive["evidence"] if c["kind"] == "counter_or_companion"
    )
    assert "반대 해석" in counter_card["body"]


def test_research_counter_card_no_overlay_sentence_when_counter_false():
    bundle = _bundle(overlays=[_overlay(counter=False)])
    deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko", now_utc=NOW,
    )
    counter_card = next(
        c for c in deepdive["evidence"] if c["kind"] == "counter_or_companion"
    )
    assert "반대 해석" not in counter_card["body"]


def test_ask_why_confidence_embeds_overlay_note():
    bundle = _bundle(overlays=[_overlay(overlay_type="regime_shift")])
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    why = next(a for a in quick["answers"] if a["intent"] == "why_confidence")
    joined = " ".join(why["evidence"])
    assert "체제 변화" in joined


def test_ask_whats_missing_embeds_overlay_counter_note_ko():
    bundle = _bundle(overlays=[_overlay(counter=True)])
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    whats = next(a for a in quick["answers"] if a["intent"] == "whats_missing")
    joined = " ".join(whats["insufficiency"])
    assert "반대 해석" in joined


def test_ask_whats_missing_no_overlay_note_when_counter_false():
    bundle = _bundle(overlays=[_overlay(counter=False)])
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    whats = next(a for a in quick["answers"] if a["intent"] == "whats_missing")
    joined = " ".join(whats["insufficiency"])
    assert "반대 해석" not in joined


def test_full_product_dto_has_no_raw_overlay_ids():
    bundle = _bundle(overlays=[_overlay(overlay_id="ovr_internal_secret")])
    spec = _spectrum()
    today = compose_today_product_dto(
        bundle=bundle, spectrum_by_horizon=spec, lang="ko", now_utc=NOW,
    )
    deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang="ko", now_utc=NOW,
    )
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    for dto in (today, deepdive, quick):
        blob = repr(dto)
        assert "ovr_internal_secret" not in blob
        assert "overlay_id" not in blob
