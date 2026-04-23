"""Patch 10C — Ask AI retrieval-grounded golden-set regression.

Scope B of the Patch 10C workorder says:

> 자유입력 품질을 아래 대표 질문 세트로 검증한다.
> - 지금 가장 중요한 건 무엇인가요?
> - 무엇이 바뀌었나요?
> - 진행 중 연구를 보여 주세요
> - 다음에 무엇을 검토하면 좋을까요?
> - 최근 결정을 보여 주세요
> - 이 항목을 리플레이로 열기
> - 몇 개의 out-of-scope 질문
> - 몇 개의 low-evidence / degraded 질문
>
> 각 질문에 대해 아래를 확인한다.
> - surfaced context + 허용 retrieval 범위 안에서만 답하는가
> - 근거 밖으로 추론을 확장하지 않는가
> - hidden system action을 암시하지 않는가
> - engineering ID를 노출하지 않는가
> - evidence 부족 시 honest degraded로 떨어지는가

This suite encodes exactly those checks. The LLM layer is replaced by
three deterministic fakes:

1. ``_fake_llm_well_behaved`` — returns a grounded one-line body.
2. ``_fake_llm_hallucinating`` — returns a body that mentions a
   foreign ticker and advice language (for hallucination-guard tests).
3. ``_fake_llm_failure`` — raises / returns ``ok=False`` (for
   degraded-path tests).

The suite then walks the golden question set and asserts:

- No engineering ID leaks in ``claim`` / ``evidence`` / ``insufficiency``.
- No buy/sell / price-target language in any ``grounded`` answer.
- Every out-of-scope question returns ``kind == "out_of_scope"`` with
  a non-empty ``insufficiency`` list — no fabricated synthesis.
- Every LLM-failure case collapses to ``kind == "degraded"``.
- Hallucinated LLM bodies are downgraded to ``kind == "partial"`` and
  the raw LLM body is discarded.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from phase47_runtime.product_shell.view_models_ask import (
    _focus_context_card,
    classify_question_scope,
    scan_response_for_hallucinations,
    scrub_free_text_answer,
    surfaced_context_summary,
)
from phase47_runtime.product_shell.view_models_common import (
    ENG_ID_PATTERNS,
    strip_engineering_ids,
)


# ---------------------------------------------------------------------------
# Synthetic bundle + spectrum for a stable focus (AAPL / short)
# ---------------------------------------------------------------------------


def _bundle(source: str = "real_derived") -> SimpleNamespace:
    return SimpleNamespace(
        as_of_utc="2026-04-23T00:00:00Z",
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
        metadata={"built_at_utc": "2026-04-23T00:00:00Z",
                  "graduation_tier": "production"},
    )


def _spectrum(position: float = 0.42) -> dict:
    return {
        "short": {
            "ok": True,
            "rows": [
                {
                    "asset_id": "AAPL",
                    "spectrum_position": position,
                    "rank_index": 0,
                    "rank_movement": "up",
                    "what_changed": "Momentum picked up after earnings beat.",
                    "rationale_summary": "Short-term flow and breadth leaning long.",
                },
            ],
        },
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long":        {"ok": True, "rows": []},
    }


@pytest.fixture
def ctx_ko():
    return _focus_context_card(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )


@pytest.fixture
def ctx_en():
    return _focus_context_card(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="en",
    )


# ---------------------------------------------------------------------------
# Fake LLM callables
# ---------------------------------------------------------------------------


def _fake_llm_well_behaved(body: str):
    def thunk():
        return {
            "ok": True,
            "response": {"body": body, "source": "test-fake"},
        }
    return thunk


def _fake_llm_failure_raises():
    def thunk():
        raise RuntimeError("simulated LLM outage")
    return thunk


def _fake_llm_failure_not_ok():
    def thunk():
        return {"ok": False, "response": {"body": "(should not be shown)"}}
    return thunk


def _fake_llm_empty_body():
    def thunk():
        return {"ok": True, "response": {"body": "   "}}
    return thunk


# ---------------------------------------------------------------------------
# Helpers: leak / advice assertions
# ---------------------------------------------------------------------------


_ADVICE_IN_BODY_KO = ("매수", "매도", "목표가", "살 것", "팔 것")
_ADVICE_IN_BODY_EN = ("buy", "sell", "target price", "short this", "go long")


def _has_engineering_leak(s: str) -> bool:
    for pat in ENG_ID_PATTERNS:
        if pat.search(s or ""):
            return True
    return False


def _assert_no_leak(answer: dict[str, Any]) -> None:
    for field in ("claim", "evidence", "insufficiency"):
        for line in answer.get(field) or []:
            assert not _has_engineering_leak(line), f"leak in {field}: {line!r}"
    banner = str(answer.get("banner") or "")
    assert not _has_engineering_leak(banner)


def _assert_no_hidden_system_action(answer: dict[str, Any]) -> None:
    """Grounded answers must never imply the system will perform
    follow-up actions. Partial / degraded / out-of-scope answers use
    fixed wording that is allowed to reference 'safe mode' but never
    promises action."""
    forbidden = (
        "i will run", "i'll open", "i have scheduled", "i scheduled",
        "실행했습니다", "예약했", "자동으로 열", "자동 실행",
    )
    for field in ("claim", "evidence"):
        for line in answer.get(field) or []:
            low = str(line).lower()
            for pat in forbidden:
                assert pat not in low, f"hidden-action phrasing: {line!r}"


# ---------------------------------------------------------------------------
# 1) In-scope questions — LLM well-behaved
# ---------------------------------------------------------------------------


IN_SCOPE_QUESTIONS_KO: list[str] = [
    "지금 가장 중요한 건 무엇인가요?",
    "무엇이 바뀌었나요?",
    "진행 중 연구를 보여 주세요.",
    "다음에 무엇을 검토하면 좋을까요?",
    "최근 결정을 보여 주세요.",
    "이 항목을 리플레이로 열기.",
]


IN_SCOPE_QUESTIONS_EN: list[str] = [
    "What is the most important thing right now?",
    "What changed?",
    "Show me the ongoing research.",
    "What should I review next?",
    "Show me recent decisions.",
    "Open this in replay.",
]


@pytest.mark.parametrize("q", IN_SCOPE_QUESTIONS_KO)
def test_golden_in_scope_ko_is_grounded(ctx_ko, q: str):
    llm = _fake_llm_well_behaved("이 구간의 현재 요약: 근거 상 중립적입니다.")
    a = scrub_free_text_answer(prompt=q, context=ctx_ko,
                               conversation_callable=llm, lang="ko")
    assert a["kind"] == "grounded"
    assert a["grounded"] is True
    assert a["claim"] and a["claim"][0]
    _assert_no_leak(a)
    _assert_no_hidden_system_action(a)
    for field in ("claim", "evidence"):
        for line in a.get(field) or []:
            low = line.lower()
            for advice in _ADVICE_IN_BODY_KO + _ADVICE_IN_BODY_EN:
                assert advice not in low, f"advice leak in grounded: {line!r}"


@pytest.mark.parametrize("q", IN_SCOPE_QUESTIONS_EN)
def test_golden_in_scope_en_is_grounded(ctx_en, q: str):
    llm = _fake_llm_well_behaved(
        "Summary for this horizon: the reading is broadly neutral under the surfaced evidence."
    )
    a = scrub_free_text_answer(prompt=q, context=ctx_en,
                               conversation_callable=llm, lang="en")
    assert a["kind"] == "grounded"
    _assert_no_leak(a)
    _assert_no_hidden_system_action(a)


# ---------------------------------------------------------------------------
# 2) Out-of-scope questions — classifier short-circuits before LLM
# ---------------------------------------------------------------------------


OUT_OF_SCOPE_ADVICE_KO = [
    "지금 AAPL 매수 추천해 주세요.",
    "AAPL 목표가는 얼마예요?",
    "지금 살까요 팔까요?",
]

OUT_OF_SCOPE_ADVICE_EN = [
    "Should I buy AAPL right now?",
    "What is the price target for AAPL?",
    "Tell me your recommendation and overweight position.",
]

OUT_OF_SCOPE_FOREIGN_KO = [
    "TSLA는 어떻게 보고 있나요?",
    "NVDA 전망 알려 주세요.",
]

OUT_OF_SCOPE_OFF_TOPIC_KO = [
    "AAPL 콜옵션 체인에서 어떤 행사가가 좋아요?",
]


@pytest.mark.parametrize("q", OUT_OF_SCOPE_ADVICE_KO + OUT_OF_SCOPE_ADVICE_EN)
def test_golden_out_of_scope_advice_is_shortcircuited(ctx_ko, ctx_en, q):
    # A thunk that would fail the test if actually called: prompts in
    # this list must be classified before the LLM layer runs.
    def forbidden_llm():
        raise AssertionError("LLM should not be called for out-of-scope advice")
    ctx = ctx_ko if any(ord(c) > 127 for c in q) else ctx_en
    lang = "ko" if ctx is ctx_ko else "en"
    a = scrub_free_text_answer(prompt=q, context=ctx,
                               conversation_callable=forbidden_llm, lang=lang)
    assert a["kind"] == "out_of_scope"
    assert a["grounded"] is False
    assert a["insufficiency"], "must carry an honest insufficiency statement"
    _assert_no_leak(a)


@pytest.mark.parametrize("q", OUT_OF_SCOPE_FOREIGN_KO)
def test_golden_out_of_scope_foreign_ticker(ctx_ko, q):
    def forbidden_llm():
        raise AssertionError("LLM should not be called for foreign-ticker prompts")
    a = scrub_free_text_answer(prompt=q, context=ctx_ko,
                               conversation_callable=forbidden_llm, lang="ko")
    assert a["kind"] == "out_of_scope"
    assert "foreign_ticker" in a["scope"]["flagged_terms"] or a["scope"]["kind"] == "foreign_ticker"
    _assert_no_leak(a)


@pytest.mark.parametrize("q", OUT_OF_SCOPE_OFF_TOPIC_KO)
def test_golden_out_of_scope_off_topic(ctx_ko, q):
    def forbidden_llm():
        raise AssertionError("LLM should not be called for off-topic prompts")
    a = scrub_free_text_answer(prompt=q, context=ctx_ko,
                               conversation_callable=forbidden_llm, lang="ko")
    assert a["kind"] == "out_of_scope"
    assert a["scope"]["kind"] == "off_topic"
    _assert_no_leak(a)


# ---------------------------------------------------------------------------
# 3) Hallucinated LLM bodies — downgraded to partial
# ---------------------------------------------------------------------------


HALLUCINATED_BODIES_EN = [
    "Based on my analysis TSLA is a strong buy — target price $300.",
    "Recommend overweight position and go long NVDA as well.",
    "Target $250 for AAPL, you should buy this week.",
]


@pytest.mark.parametrize("body", HALLUCINATED_BODIES_EN)
def test_golden_hallucinated_llm_is_downgraded_to_partial(ctx_en, body):
    a = scrub_free_text_answer(
        prompt="Please summarize the current reading.",
        context=ctx_en,
        conversation_callable=_fake_llm_well_behaved(body),
        lang="en",
    )
    assert a["kind"] == "partial"
    assert a["grounded"] is False
    # Raw LLM body MUST NOT leak through.
    for field in ("claim", "evidence", "insufficiency"):
        for line in a.get(field) or []:
            assert body not in line
    # Guard flags record what tripped.
    assert a.get("guard_flags"), "partial answer must list guard_flags"
    _assert_no_leak(a)


# ---------------------------------------------------------------------------
# 4) LLM failure paths — collapse to degraded
# ---------------------------------------------------------------------------


def test_golden_llm_raise_collapses_to_degraded(ctx_ko):
    a = scrub_free_text_answer(
        prompt="무엇이 바뀌었나요?",
        context=ctx_ko,
        conversation_callable=_fake_llm_failure_raises(),
        lang="ko",
    )
    assert a["kind"] == "degraded"
    assert a["grounded"] is False
    _assert_no_leak(a)


def test_golden_llm_not_ok_collapses_to_degraded(ctx_en):
    a = scrub_free_text_answer(
        prompt="What changed?",
        context=ctx_en,
        conversation_callable=_fake_llm_failure_not_ok(),
        lang="en",
    )
    assert a["kind"] == "degraded"
    _assert_no_leak(a)


def test_golden_empty_prompt_is_rejected(ctx_ko):
    a = scrub_free_text_answer(
        prompt="   ",
        context=ctx_ko,
        conversation_callable=_fake_llm_well_behaved("anything"),
        lang="ko",
    )
    assert a["kind"] == "empty_prompt"
    _assert_no_leak(a)


def test_golden_empty_llm_body_collapses_to_degraded(ctx_en):
    a = scrub_free_text_answer(
        prompt="What changed?",
        context=ctx_en,
        conversation_callable=_fake_llm_empty_body(),
        lang="en",
    )
    assert a["kind"] == "degraded"
    _assert_no_leak(a)


# ---------------------------------------------------------------------------
# 5) Low-evidence / preparing focus — degraded honesty
# ---------------------------------------------------------------------------


def test_golden_preparing_focus_still_bounded():
    """Even when the focus horizon is preparing, in-scope prompts get
    a grounded answer but out-of-scope prompts short-circuit cleanly."""
    ctx = _focus_context_card(
        bundle=_bundle(source="insufficient_evidence"),
        spectrum_by_horizon={
            "short": {"ok": True, "rows": []},
            "medium": {"ok": True, "rows": []},
            "medium_long": {"ok": True, "rows": []},
            "long": {"ok": True, "rows": []},
        },
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    # Grounded path is still allowed — the LLM sees the surfaced
    # paragraph explaining "preparing" state.
    a_ok = scrub_free_text_answer(
        prompt="지금 어떻게 읽고 있나요?",
        context=ctx,
        conversation_callable=_fake_llm_well_behaved(
            "이 구간은 실데이터가 아직 준비 중이라 결론을 유보합니다."
        ),
        lang="ko",
    )
    assert a_ok["kind"] == "grounded"
    _assert_no_leak(a_ok)
    # Advice prompt still short-circuits.
    a_ad = scrub_free_text_answer(
        prompt="이 종목 매수해도 될까요?",
        context=ctx,
        conversation_callable=_fake_llm_well_behaved("(should not be called)"),
        lang="ko",
    )
    assert a_ad["kind"] == "out_of_scope"
    _assert_no_leak(a_ad)


# ---------------------------------------------------------------------------
# 6) Classifier / scanner unit coverage (small, fast, exhaustive)
# ---------------------------------------------------------------------------


def test_classifier_flags_ko_advice_language():
    ctx = {"asset_id": "AAPL"}
    s = classify_question_scope("지금 AAPL 매수 추천 부탁합니다.", context=ctx)
    assert s["kind"] == "advice_request"


def test_classifier_flags_en_advice_language():
    ctx = {"asset_id": "AAPL"}
    s = classify_question_scope("should i buy aapl now?", context=ctx)
    assert s["kind"] == "advice_request"


def test_classifier_flags_foreign_ticker_only_when_focus_present():
    with_focus = {"asset_id": "AAPL"}
    no_focus = {"asset_id": ""}
    s1 = classify_question_scope("What about MSFT?", context=with_focus)
    s2 = classify_question_scope("What about MSFT?", context=no_focus)
    assert s1["kind"] == "foreign_ticker"
    assert s2["kind"] == "in_scope"


def test_classifier_does_not_flag_common_acronyms():
    ctx = {"asset_id": "AAPL"}
    # Acronyms like EPS/ETF must not count as foreign tickers.
    s = classify_question_scope("What is AAPL's EPS vs the ETF peers?", context=ctx)
    assert s["kind"] == "in_scope"


def test_classifier_flags_off_topic_option_chain():
    ctx = {"asset_id": "AAPL"}
    s = classify_question_scope("AAPL call option chain view?", context=ctx)
    assert s["kind"] == "off_topic"


def test_scan_response_detects_price_target():
    flags = scan_response_for_hallucinations(
        "Our target price is $250 for the stock.", context={"asset_id": "AAPL"},
    )
    assert "price_target" in flags


def test_scan_response_detects_foreign_ticker():
    flags = scan_response_for_hallucinations(
        "We also like NVDA going forward.", context={"asset_id": "AAPL"},
    )
    assert "foreign_ticker" in flags


def test_scan_response_detects_advice_language():
    flags = scan_response_for_hallucinations(
        "You should buy this right now.", context={"asset_id": "AAPL"},
    )
    assert "advice_language" in flags


def test_scan_response_clean_when_bounded(ctx_en):
    flags = scan_response_for_hallucinations(
        "The current short-horizon reading for AAPL is broadly neutral under surfaced evidence.",
        context=ctx_en,
    )
    assert flags == []


def test_surfaced_context_summary_is_scrubbed(ctx_en):
    text = surfaced_context_summary(ctx_en, lang="en")
    assert "AAPL" in text
    assert "buy" not in text.lower() or "never issue buy" in text.lower()
    assert not any(p.search(text) for p in ENG_ID_PATTERNS)
