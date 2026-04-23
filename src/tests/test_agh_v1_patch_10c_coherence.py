"""Patch 10C — cross-surface coherence tests.

Scope A of the Patch 10C workorder says:

> 같은 `STATE.focus {asset_id, horizon_key}`에 대해 Today / Research /
> Replay / Ask AI 가 같은 message memory를 참조하게 만든다. (A1)
> 문자열 완전 일치가 아니라 의미 일치가 목표다. (A2)

This suite constructs one synthetic brain bundle + spectrum payload
and runs all four Product Shell composers with the same focus pair
``(AAPL, short)``. It then asserts:

- The ``coherence_signature.fingerprint`` is identical across Today
  (hero card for ``short``), Research landing (the AAPL tile on the
  ``short`` column), Research deep-dive, Replay, and Ask AI
  context / quick-answers DTOs.
- The ``stance.key``, ``grade.key``, ``confidence.source_key`` are
  identical.
- The ``evidence_summary.body`` is byte-for-byte equal across
  surfaces (modulo language — we test KO and EN independently).
- Switching language keeps the fingerprint identical (Scope A2:
  semantic alignment, not string equality).
- Switching evidence text alters the fingerprint (a silent rationale
  edit must be detectable).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from phase47_runtime.product_shell.view_models import compose_today_product_dto
from phase47_runtime.product_shell.view_models_research import (
    compose_research_deepdive_dto,
    compose_research_landing_dto,
)
from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto
from phase47_runtime.product_shell.view_models_ask import (
    compose_ask_product_dto,
    compose_quick_answers_dto,
)


NOW = "2026-04-23T00:00:00Z"


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


def _spectrum(
    position: float = 0.42,
    what_changed: str = "Momentum picked up after earnings beat.",
    rationale: str = "Short-term flow and breadth both leaning long.",
) -> dict:
    return {
        "short": {
            "ok": True,
            "rows": [
                {
                    "asset_id": "AAPL",
                    "spectrum_position": position,
                    "rank_index": 0,
                    "rank_movement": "up",
                    "what_changed": what_changed,
                    "rationale_summary": rationale,
                },
                {
                    "asset_id": "MSFT",
                    "spectrum_position": position - 0.1,
                    "rank_index": 1,
                    "rank_movement": "flat",
                    "what_changed": "",
                    "rationale_summary": "Steady setup; no material change.",
                },
            ],
        },
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long":        {"ok": True, "rows": []},
    }


def _compose_all(lang: str, bundle, spectrum):
    today = compose_today_product_dto(
        bundle=bundle, spectrum_by_horizon=spectrum, lang=lang, now_utc=NOW,
    )
    research_landing = compose_research_landing_dto(
        bundle=bundle, spectrum_by_horizon=spectrum, lang=lang, now_utc=NOW,
    )
    research_deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=NOW,
    )
    replay = compose_replay_product_dto(
        bundle=bundle, spectrum_by_horizon=spectrum, lineage=None,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=NOW,
    )
    ask = compose_ask_product_dto(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=NOW,
    )
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang=lang,
    )
    return today, research_landing, research_deepdive, replay, ask, quick


def _today_aapl_short_focus(today_dto) -> dict:
    """The Today DTO exposes focus_candidates per horizon. Pick the
    ``short`` card so we compare against the same focus the other
    surfaces used."""
    for hc in today_dto["hero_cards"]:
        if hc["horizon_key"] == "short":
            return hc["shared_focus"]
    raise AssertionError("Today DTO missing the short hero card")


def _research_landing_aapl_focus(landing_dto) -> dict:
    for col in landing_dto["columns"]:
        if col["horizon_key"] != "short":
            continue
        for tile in col["tiles"]:
            if tile["ticker"] == "AAPL":
                return tile["shared_focus"]
    raise AssertionError("Research landing missing AAPL tile on short")


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_fingerprint_identical_across_surfaces(lang):
    bundle = _bundle()
    spectrum = _spectrum()
    today, landing, deepdive, replay, ask, quick = _compose_all(lang, bundle, spectrum)

    fps = [
        _today_aapl_short_focus(today)["coherence_signature"]["fingerprint"],
        _research_landing_aapl_focus(landing)["coherence_signature"]["fingerprint"],
        deepdive["shared_focus"]["coherence_signature"]["fingerprint"],
        replay["shared_focus"]["coherence_signature"]["fingerprint"],
        ask["shared_focus"]["coherence_signature"]["fingerprint"],
        quick["shared_focus"]["coherence_signature"]["fingerprint"],
    ]
    assert len(set(fps)) == 1, f"fingerprints diverged: {fps}"


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_stance_grade_confidence_identical_across_surfaces(lang):
    bundle = _bundle()
    spectrum = _spectrum()
    today, landing, deepdive, replay, ask, quick = _compose_all(lang, bundle, spectrum)

    focuses = [
        _today_aapl_short_focus(today),
        _research_landing_aapl_focus(landing),
        deepdive["shared_focus"],
        replay["shared_focus"],
        ask["shared_focus"],
        quick["shared_focus"],
    ]
    stance_keys = {f["stance"]["key"] for f in focuses}
    grade_keys = {f["grade"]["key"] for f in focuses}
    source_keys = {f["confidence"]["source_key"] for f in focuses}
    assert len(stance_keys) == 1
    assert len(grade_keys) == 1
    assert len(source_keys) == 1


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_evidence_summary_body_identical_across_surfaces(lang):
    bundle = _bundle()
    spectrum = _spectrum()
    today, landing, deepdive, replay, ask, quick = _compose_all(lang, bundle, spectrum)

    bodies = {
        _today_aapl_short_focus(today)["evidence_summary"]["body"],
        _research_landing_aapl_focus(landing)["evidence_summary"]["body"],
        deepdive["shared_focus"]["evidence_summary"]["body"],
        replay["shared_focus"]["evidence_summary"]["body"],
        ask["shared_focus"]["evidence_summary"]["body"],
        quick["shared_focus"]["evidence_summary"]["body"],
    }
    assert len(bodies) == 1, f"evidence_summary.body diverged: {bodies}"


def test_fingerprint_is_language_independent():
    bundle = _bundle()
    spectrum = _spectrum()
    ko = _compose_all("ko", bundle, spectrum)
    en = _compose_all("en", bundle, spectrum)
    ko_fp = ko[2]["shared_focus"]["coherence_signature"]["fingerprint"]
    en_fp = en[2]["shared_focus"]["coherence_signature"]["fingerprint"]
    assert ko_fp == en_fp


def test_fingerprint_changes_when_rationale_changes():
    bundle = _bundle()
    spec_a = _spectrum(rationale="Original rationale text.")
    spec_b = _spectrum(rationale="Tweaked rationale text.")
    a = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spec_a,
        asset_id="AAPL", horizon_key="short", lang="ko", now_utc=NOW,
    )
    b = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spec_b,
        asset_id="AAPL", horizon_key="short", lang="ko", now_utc=NOW,
    )
    assert (a["shared_focus"]["coherence_signature"]["fingerprint"]
            != b["shared_focus"]["coherence_signature"]["fingerprint"])


def test_fingerprint_changes_when_position_crosses_grade_tier():
    bundle = _bundle()
    # 0.42 (grade A, stance long) vs 0.81 (grade A+, stance strong_long)
    spec_lo = _spectrum(position=0.42)
    spec_hi = _spectrum(position=0.81)
    a = compose_replay_product_dto(
        bundle=bundle, spectrum_by_horizon=spec_lo, lineage=None,
        asset_id="AAPL", horizon_key="short", lang="ko", now_utc=NOW,
    )
    b = compose_replay_product_dto(
        bundle=bundle, spectrum_by_horizon=spec_hi, lineage=None,
        asset_id="AAPL", horizon_key="short", lang="ko", now_utc=NOW,
    )
    assert (a["shared_focus"]["coherence_signature"]["fingerprint"]
            != b["shared_focus"]["coherence_signature"]["fingerprint"])
    assert (a["shared_focus"]["grade"]["key"]
            != b["shared_focus"]["grade"]["key"])


def test_shared_focus_block_is_embedded_via_strip_scrubber():
    """shared_focus comes out of strip_engineering_ids unchanged —
    the scrubber preserves the 12-hex fingerprint and the
    ``COHERENCE_V1`` contract label."""
    bundle = _bundle()
    spectrum = _spectrum()
    deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang="ko", now_utc=NOW,
    )
    sig = deepdive["shared_focus"]["coherence_signature"]
    assert sig["contract_version"] == "COHERENCE_V1"
    assert "[redacted]" not in sig["fingerprint"]
    assert len(sig["fingerprint"]) == 12


def test_today_primary_focus_matches_strongest_hero():
    bundle = _bundle()
    spectrum = _spectrum(position=0.42)
    today = compose_today_product_dto(
        bundle=bundle, spectrum_by_horizon=spectrum, lang="en", now_utc=NOW,
    )
    primary = today["primary_focus"]
    assert primary is not None
    # Only 'short' has live rows in this spectrum, so the strongest
    # hero is the short card. Verify the primary focus matches.
    assert primary["horizon_key"] == "short"
    assert primary["asset_id"] == "AAPL"
    assert today["coherence_signature"] == primary["coherence_signature"]


def test_focus_candidates_list_exposed_on_today_and_research_landing():
    bundle = _bundle()
    spectrum = _spectrum()
    today = compose_today_product_dto(
        bundle=bundle, spectrum_by_horizon=spectrum, lang="ko", now_utc=NOW,
    )
    landing = compose_research_landing_dto(
        bundle=bundle, spectrum_by_horizon=spectrum, lang="ko", now_utc=NOW,
    )
    assert today["focus_candidates"]
    assert landing["focus_candidates"]
    # Every candidate exposes a signature.
    for c in today["focus_candidates"] + landing["focus_candidates"]:
        assert "signature" in c and c["signature"]["fingerprint"]
