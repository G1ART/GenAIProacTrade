"""RefereeGate: blocks execution language and missing mandatory sections."""

from __future__ import annotations

import re
from typing import Any

_FORBIDDEN_SUBSTRINGS = (
    "buy ",
    " sell",
    "sell ",
    "long ",
    "short ",
    "portfolio",
    "allocation",
    "execute trade",
    "매수",
    "매도",
    "alpha generation",
    "outperform",
    "underweight",
    "overweight",
    "strong buy",
    "price target",
)

_CERTAINTY_PHRASES = (
    "guaranteed return",
    "sure thing",
    "cannot lose",
    "risk-free profit",
)


def _collect_text_blobs(memo: dict[str, Any]) -> list[str]:
    blobs: list[str] = []

    def _walk(x: Any) -> None:
        if isinstance(x, str):
            blobs.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                _walk(v)
        elif isinstance(x, list):
            for v in x:
                _walk(v)

    _walk(memo)
    return blobs


def referee_gate_scan(memo: dict[str, Any]) -> dict[str, Any]:
    flags: list[dict[str, str]] = []
    combined = "\n".join(_collect_text_blobs(memo)).lower()

    for sub in _FORBIDDEN_SUBSTRINGS:
        if sub.lower() in combined:
            flags.append(
                {
                    "code": "forbidden_execution_or_promotion_language",
                    "detail": "matched:" + repr(sub),
                }
            )

    for ph in _CERTAINTY_PHRASES:
        if ph.lower() in combined:
            flags.append(
                {"code": "certainty_overstatement", "detail": "matched:" + repr(ph)}
            )

    if re.search(r"\b\d{1,3}\s*%\s*(return)", combined):
        flags.append(
            {
                "code": "unsupported_numeric_return_claim",
                "detail": "percent_return_phrase",
            }
        )

    sca = memo.get("strongest_counter_argument")
    if not isinstance(sca, dict) or not str(sca.get("alternate_interpretation") or "").strip():
        flags.append(
            {
                "code": "missing_mandatory_counter_argument",
                "detail": "alternate_interpretation_empty",
            }
        )

    unc = memo.get("uncertainty_labels")
    if not isinstance(unc, list) or len(unc) < 1:
        flags.append(
            {"code": "missing_uncertainty_labels", "detail": "need_labels"}
        )

    syn = memo.get("synthesis") or {}
    if isinstance(syn, dict):
        st = str(syn.get("text") or "").lower()
        if st and ("thesis" not in st and "challenge" not in st and "both" not in st):
            flags.append(
                {
                    "code": "synthesis_may_erase_disagreement",
                    "detail": "reference_thesis_and_challenge",
                }
            )

    return {"passed": len(flags) == 0, "flags": flags}
