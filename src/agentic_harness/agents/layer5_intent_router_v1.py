"""Layer 5 - Intent Router v1 (AGH v1 Patch 5).

Deterministic, keyword-based normalization of free-form user questions
into one of the seven ``USER_QUESTION_KINDS`` supported by the harness:

    * ``why_changed``            - "왜 바뀌었나 / why did this change"
    * ``system_status``          - "상태 / 큐 / status / queue"
    * ``research_pending``       - "대기 중 연구 / pending research"
    * ``deeper_rationale``       - "근거 좀 더 / deeper rationale"
    * ``what_remains_unproven``  - "아직 증명되지 않은 / what remains unproven"
    * ``what_to_watch``          - "지켜봐야 할 / what to watch"
    * ``sandbox_request``        - "샌드박스 재실행 / rerun validation"

The router is deliberately rule-based (no LLM) because the *routing*
decision drives which packets the state reader is allowed to include in
the bundle that is eventually shown to the LLM. Wrapping it in an LLM
would create a two-way channel the Patch 5 non-negotiables forbid
(LLM-derived writes + unbounded intent inflation).

Matching strategy (deterministic):
  1. Normalize the question: lowercase + strip leading/trailing spaces.
  2. For each kind (in priority order), check whether any of its keyword
     lists matches. A match is a substring match on the normalized
     question. Korean and English keyword banks are evaluated
     independently, then OR'd together — no language flag is required.
  3. If no kind matches, default to ``why_changed`` (the Patch 2 default).

Priority order (most specific first): sandbox_request > deeper_rationale
> what_remains_unproven > what_to_watch > system_status > research_pending
> why_changed. ``sandbox_request`` wins because it is the only intent
that can deterministically cause a bounded closed-loop job to be
enqueued; we do not want a "왜 바뀌었나" keyword to shadow an operator's
explicit "재검증 요청".
"""

from __future__ import annotations

from typing import Iterable

from agentic_harness.llm.contract import USER_QUESTION_KINDS


_KEYWORDS_KO: dict[str, tuple[str, ...]] = {
    "sandbox_request": (
        "재검증",
        "샌드박스",
        "재실행",
        "다시 검증",
        "다시 돌려",
        "rerun",
    ),
    "deeper_rationale": (
        "근거",
        "왜 그렇게",
        "더 자세",
        "더 깊이",
        "심층",
        "rationale",
        "이유를 더",
    ),
    "what_remains_unproven": (
        "증명되지 않",
        "불확실",
        "확실하지",
        "아직 모르",
        "unproven",
        "uncertain",
    ),
    "what_to_watch": (
        "지켜",
        "관찰",
        "앞으로 볼",
        "앞으로 지켜",
        "watch",
        "watchlist",
        "모니터",
    ),
    "system_status": (
        "상태",
        "큐",
        "헬스",
        "건강",
        "status",
        "queue",
        "packet",
        "system",
    ),
    "research_pending": (
        "연구",
        "후보",
        "대기",
        "계류",
        "research",
        "pending",
        "candidate",
    ),
    "why_changed": (
        "왜",
        "바뀌",
        "변동",
        "움직",
        "어째서",
        "why",
        "changed",
        "move",
    ),
}


_PRIORITY_ORDER: tuple[str, ...] = (
    "sandbox_request",
    "deeper_rationale",
    "what_remains_unproven",
    "what_to_watch",
    "system_status",
    "research_pending",
    "why_changed",
)


def _contains_any(haystack: str, needles: Iterable[str]) -> bool:
    for n in needles:
        s = str(n or "").strip().lower()
        if s and s in haystack:
            return True
    return False


def route_user_question_v1(
    question: str, *, lang: str = "ko"
) -> str:
    """Normalize a free-form user question into one of
    ``USER_QUESTION_KINDS``. Never raises; always returns a member of the
    tuple.

    The ``lang`` hint is not used to gate the Korean bank (we OR in both
    banks regardless) but is reserved so a future Patch can bias
    ambiguous phrasings based on the UI locale.
    """

    _ = lang  # reserved for future locale-biased tie-breaks
    q = str(question or "").strip().lower()
    if not q:
        return "why_changed"
    for kind in _PRIORITY_ORDER:
        if kind not in USER_QUESTION_KINDS:
            # Defensive: if contract drops a kind we silently skip it.
            continue
        if _contains_any(q, _KEYWORDS_KO.get(kind, ())):
            return kind
    return "why_changed"


__all__ = [
    "route_user_question_v1",
    "USER_QUESTION_KINDS",
]
