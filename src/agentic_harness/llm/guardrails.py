"""Forbidden-copy guardrails for Layer 5 LLM outputs.

Shares the forbidden token list with
``agentic_harness.contracts.packets_v1`` so a token blocked on a packet
can never appear on the surface either.
"""

from __future__ import annotations

import re
from typing import Iterable


_GUARDRAIL_PATTERNS = [
    re.compile(r"\bbuy\b", re.IGNORECASE),
    re.compile(r"\bsell\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\b", re.IGNORECASE),
    re.compile(r"\brecommend(?:s|ed|ing)?\b", re.IGNORECASE),
    re.compile(r"will\s+definitely", re.IGNORECASE),
    re.compile(r"확실", re.IGNORECASE),
    re.compile(r"반드시\s*오른"),
    re.compile(r"반드시\s*내린"),
    re.compile(r"무조건\s*(?:오른|내린)"),
]


def guardrail_violations(texts: Iterable[str]) -> list[str]:
    out: list[str] = []
    for t in texts:
        s = str(t or "")
        for pat in _GUARDRAIL_PATTERNS:
            m = pat.search(s)
            if m is not None:
                out.append(m.group(0))
    return out


def passes_guardrail(*texts: str) -> bool:
    return not guardrail_violations(list(texts))


def redact_forbidden(text: str, placeholder: str = "[REDACTED]") -> str:
    """Replace every forbidden-copy match with ``placeholder``.

    Used when we must persist a record of the blocked content into a packet
    payload (which itself forbids those tokens). The category of what was
    blocked is reported separately via ``fallback_reason`` so redacted
    evidence is still auditable.
    """

    s = str(text or "")
    for pat in _GUARDRAIL_PATTERNS:
        s = pat.sub(placeholder, s)
    return s


def redact_mapping(obj):  # type: ignore[no-untyped-def]
    """Recursively redact forbidden tokens inside a JSON-like structure."""

    if isinstance(obj, str):
        return redact_forbidden(obj)
    if isinstance(obj, list):
        return [redact_mapping(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(redact_mapping(v) for v in obj)
    if isinstance(obj, dict):
        return {k: redact_mapping(v) for k, v in obj.items()}
    return obj


def validate_cited_ids_subset(
    *, cited_packet_ids: list[str], allowed_packet_ids: list[str]
) -> list[str]:
    """Return any cited ids that are NOT in the allowed set (hallucinations)."""

    allowed = set(str(x) for x in allowed_packet_ids)
    return [pid for pid in cited_packet_ids if pid not in allowed]


def validate_research_structured_v1(
    *,
    research_structured: dict | None,
    routed_kind: str,
    allowed_packet_ids: list[str],
) -> list[str]:
    """AGH v1 Patch 5 — Research acceptance guardrail.

    Returns a list of blocking reasons if the LLM-returned
    ``research_structured_v1`` block violates any of the Patch 5
    acceptance invariants. An empty list means acceptance.

    Invariants (from Workorder §5.B):

    * If ``routed_kind`` is one of ``RESEARCH_STRUCTURED_KINDS`` and no
      structured block was produced, that is acceptable only when the
      enclosing answer carries ``blocking_reasons`` explaining why.
      (Reported as ``missing_research_structured_for_research_kind`` so
      the caller can decide whether to template-fallback.)
    * ``evidence_cited`` entries must be ``allowed_packet_ids`` subset
      (also cross-checked on the Pydantic contract, but enforced here so
      the surface packet never loses blocked context to silent coercion).
    * Text fields must pass ``guardrail_violations``; each bullet list
      is scanned together with the free-text ``rationale``.
    * ``proposed_sandbox_request`` is not scanned for *subset* here —
      the Pydantic contract already enforces the ``SANDBOX_KINDS`` enum
      and required ``target_spec`` fields.
    """

    from agentic_harness.llm.contract import RESEARCH_STRUCTURED_KINDS

    blocking: list[str] = []
    if routed_kind in RESEARCH_STRUCTURED_KINDS and not research_structured:
        blocking.append(
            "missing_research_structured_for_research_kind:" + str(routed_kind)
        )
        return blocking
    if not research_structured:
        return blocking

    if not isinstance(research_structured, dict):
        blocking.append("research_structured_v1_must_be_dict")
        return blocking

    evidence = research_structured.get("evidence_cited") or []
    if not isinstance(evidence, list):
        blocking.append("research_structured_v1.evidence_cited_must_be_list")
        return blocking
    allowed = set(str(x) for x in allowed_packet_ids)
    bogus = [pid for pid in evidence if str(pid) not in allowed]
    if bogus:
        blocking.append(
            f"research_structured_v1.evidence_cited_hallucinated:count={len(bogus)}"
        )

    texts: list[str] = []
    for key in (
        "summary_bullets_ko",
        "summary_bullets_en",
        "residual_uncertainty_bullets",
        "what_to_watch_bullets",
    ):
        v = research_structured.get(key) or []
        if not isinstance(v, list):
            blocking.append(f"research_structured_v1.{key}_must_be_list")
            continue
        texts.extend(str(x) for x in v)
    prop = research_structured.get("proposed_sandbox_request")
    if isinstance(prop, dict):
        if "rationale" in prop:
            texts.append(str(prop.get("rationale") or ""))

    violations = guardrail_violations(texts)
    if violations:
        blocking.append(
            f"research_structured_v1.forbidden_copy:count={len(set(violations))}"
        )

    # AGH v1 Patch 6 — locale_coverage honesty. Default is ``dual`` (both
    # KO+EN populated). If the LLM claims ``dual`` but one locale is
    # empty, reject with ``locale_claim_mismatch``. Partial claims
    # (``ko_only`` / ``en_only`` / ``degraded``) are accepted but the
    # renderer surfaces a degraded-coverage badge.
    cov = str(research_structured.get("locale_coverage") or "dual").strip() or "dual"
    ko_has = bool(research_structured.get("summary_bullets_ko"))
    en_has = bool(research_structured.get("summary_bullets_en"))
    if cov == "dual":
        if not (ko_has and en_has):
            blocking.append(
                "research_structured_v1.locale_claim_mismatch:"
                "dual_claim_but_missing_locale"
            )
    elif cov == "ko_only":
        if not ko_has or en_has:
            blocking.append(
                "research_structured_v1.locale_claim_mismatch:"
                "ko_only_claim_invariant_broken"
            )
    elif cov == "en_only":
        if not en_has or ko_has:
            blocking.append(
                "research_structured_v1.locale_claim_mismatch:"
                "en_only_claim_invariant_broken"
            )
    elif cov == "degraded":
        if ko_has or en_has:
            blocking.append(
                "research_structured_v1.locale_claim_mismatch:"
                "degraded_claim_but_bullets_present"
            )
    else:
        blocking.append(
            f"research_structured_v1.locale_coverage_unknown:{cov}"
        )

    return blocking
