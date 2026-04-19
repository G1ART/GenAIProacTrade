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
