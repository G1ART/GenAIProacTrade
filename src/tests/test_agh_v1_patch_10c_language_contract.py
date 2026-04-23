"""Patch 10C — language contract tightening (Scope E).

The workorder asks us to pin the product language for ten buckets
across all four surfaces:

- sample / preparing / limited_evidence / production / freshness
- what_changed / knowable_then / bounded_ask / next_step
- out_of_scope

These tests assert:

1. Every Product Shell DTO that claims coherence exposes the ten-bucket
   vocabulary somewhere (either under ``shared_wording`` or via a
   direct embed that uses the same phrasing as :data:`SHARED_WORDING`).
2. When a horizon is preparing or sample, the DTO's degraded copy is
   identical to the corresponding shared-wording bucket body.
3. The Ask AI out-of-scope path quotes the ``out_of_scope`` bucket's
   title as its banner — the only place we tolerate the exact string.
4. No surface invents its own "sample scenario" / "preparing" phrasing
   outside of :data:`SHARED_WORDING`.
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
    scrub_free_text_answer,
)
from phase47_runtime.product_shell.view_models_common import (
    SHARED_WORDING,
    SHARED_WORDING_KINDS,
    shared_wording,
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
            SimpleNamespace(status="active", horizon="short",
                            active_artifact_id="art_x",
                            registry_entry_id="reg_x",
                            display_family_name_ko="모멘텀",
                            display_family_name_en="Momentum"),
        ],
        artifacts=[
            SimpleNamespace(artifact_id="art_x",
                            display_family_name_ko="모멘텀",
                            display_family_name_en="Momentum"),
        ],
        metadata={"built_at_utc": NOW, "graduation_tier": "production"},
    )


def _spectrum(position: float = 0.42) -> dict:
    return {
        "short": {"ok": True, "rows": [{
            "asset_id": "AAPL", "spectrum_position": position,
            "rank_index": 0, "rank_movement": "up",
            "what_changed": "Momentum picked up.",
            "rationale_summary": "Short-term flow leaning long.",
        }]},
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long":        {"ok": True, "rows": []},
    }


# ---------------------------------------------------------------------------
# 1) shared_wording block reachable on every surface
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_today_exposes_shared_wording(lang):
    today = compose_today_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lang=lang, now_utc=NOW,
    )
    sw = today["shared_wording"]
    assert sw["bounded_ask"]["title"] == shared_wording("bounded_ask", lang=lang)["title"]
    assert sw["next_step"]["title"] == shared_wording("next_step", lang=lang)["title"]


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_research_landing_exposes_shared_wording(lang):
    landing = compose_research_landing_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lang=lang, now_utc=NOW,
    )
    sw = landing["shared_wording"]
    for k in ("bounded_ask", "limited_evidence", "sample", "preparing"):
        assert sw[k]["title"] == shared_wording(k, lang=lang)["title"]


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_research_deepdive_exposes_shared_wording(lang):
    dto = compose_research_deepdive_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short",
        lang=lang, now_utc=NOW,
    )
    sw = dto["shared_wording"]
    for k in ("bounded_ask", "what_changed", "next_step"):
        assert sw[k]["title"] == shared_wording(k, lang=lang)["title"]


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_replay_exposes_shared_wording(lang):
    dto = compose_replay_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lineage=None, asset_id="AAPL", horizon_key="short",
        lang=lang, now_utc=NOW,
    )
    sw = dto["shared_wording"]
    for k in ("knowable_then", "bounded_ask", "limited_evidence", "next_step"):
        assert sw[k]["title"] == shared_wording(k, lang=lang)["title"]
    # knowable_then is also pinned to its own top-level key for direct
    # UI rendering.
    assert dto["knowable_then"] == shared_wording("knowable_then", lang=lang)


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_ask_landing_exposes_shared_wording(lang):
    dto = compose_ask_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short",
        lang=lang, now_utc=NOW,
    )
    sw = dto["shared_wording"]
    for k in ("bounded_ask", "out_of_scope", "next_step"):
        assert sw[k]["title"] == shared_wording(k, lang=lang)["title"]


# ---------------------------------------------------------------------------
# 2) preparing / sample source_key drives the shared body
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_preparing_focus_body_matches_shared_wording(lang):
    spectrum = {"short": {"ok": True, "rows": []},
                "medium": {"ok": True, "rows": []},
                "medium_long": {"ok": True, "rows": []},
                "long": {"ok": True, "rows": []}}
    bundle = _bundle(source="insufficient_evidence")
    dto = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short",
        lang=lang, now_utc=NOW,
    )
    body = dto["shared_focus"]["evidence_summary"]["body"]
    assert body == shared_wording("preparing", lang=lang)["body"]


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_sample_focus_body_matches_shared_wording(lang):
    spectrum = {"short": {"ok": True, "rows": []},
                "medium": {"ok": True, "rows": []},
                "medium_long": {"ok": True, "rows": []},
                "long": {"ok": True, "rows": []}}
    bundle = _bundle(source="template_fallback")
    dto = compose_replay_product_dto(
        bundle=bundle, spectrum_by_horizon=spectrum,
        lineage=None, asset_id="AAPL", horizon_key="short",
        lang=lang, now_utc=NOW,
    )
    body = dto["shared_focus"]["evidence_summary"]["body"]
    assert body == shared_wording("sample", lang=lang)["body"]


# ---------------------------------------------------------------------------
# 3) Ask AI out-of-scope quotes the shared bucket
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang, prompt", [
    ("ko", "AAPL 지금 매수 추천해 주세요."),
    ("en", "Should I buy AAPL now?"),
])
def test_out_of_scope_banner_matches_shared_wording(lang, prompt):
    from phase47_runtime.product_shell.view_models_ask import _focus_context_card
    ctx = _focus_context_card(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang=lang,
    )
    def llm():
        raise AssertionError("LLM must not be called for out-of-scope")
    a = scrub_free_text_answer(
        prompt=prompt, context=ctx, conversation_callable=llm, lang=lang,
    )
    assert a["banner"] == shared_wording("out_of_scope", lang=lang)["title"]


# ---------------------------------------------------------------------------
# 4) Surfaces do not reintroduce ad-hoc phrasing for the degraded buckets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_shared_wording_kinds_are_total(lang):
    # Every bucket has KO + EN + all three field names.
    for kind in SHARED_WORDING_KINDS:
        ko = SHARED_WORDING["ko"][kind]
        en = SHARED_WORDING["en"][kind]
        assert set(ko.keys()) == {"title", "body", "chip"}
        assert set(en.keys()) == {"title", "body", "chip"}
        assert ko["title"] and en["title"]
        assert ko["chip"] and en["chip"]


def test_shared_wording_unknown_falls_back_safely():
    block = shared_wording("this-bucket-does-not-exist", lang="ko")
    assert block["title"] == SHARED_WORDING["ko"]["limited_evidence"]["title"]
