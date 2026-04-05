"""RefereeGate: blocks execution language and missing mandatory sections."""

from __future__ import annotations

import json
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

_CHALLENGE_REQUIRED_KEYS = (
    "alternate_interpretation",
    "data_insufficiency_risk",
    "why_change_may_not_matter",
    "what_would_falsify_thesis",
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


def _allowed_numeric_context(memo: dict[str, Any]) -> str:
    parts = [
        json.dumps(memo.get("deterministic_signal_summary"), default=str),
        json.dumps(memo.get("evidence_blocks"), default=str),
        json.dumps(memo.get("source_trace"), default=str),
    ]
    return "\n".join(parts).lower()


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
    elif isinstance(sca, dict):
        for key in _CHALLENGE_REQUIRED_KEYS:
            if not str(sca.get(key) or "").strip():
                flags.append(
                    {
                        "code": "challenge_dimension_incomplete",
                        "detail": f"missing_or_empty:{key}",
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
        if syn.get("thesis_preserved") is not True or syn.get("challenge_preserved") is not True:
            flags.append(
                {
                    "code": "disagreement_not_structurally_preserved",
                    "detail": "thesis_preserved/challenge_preserved must be true",
                }
            )

    lim = str(memo.get("limitations_and_missingness") or "")
    evb = memo.get("evidence_blocks") or []
    unver = sum(
        1
        for b in evb
        if isinstance(b, dict)
        and str(b.get("uncertainty_label")) == "unverifiable"
    )
    if len(lim.strip()) < 80 and unver >= 2:
        flags.append(
            {
                "code": "limitations_too_thin_for_evidence_risk",
                "detail": "expand_limitations_or_evidence_unverifiable",
            }
        )

    dis_risk = ""
    if isinstance(sca, dict):
        dis_risk = str(sca.get("data_insufficiency_risk") or "").lower()
    if "none flagged" not in dis_risk and "missing" in dis_risk:
        if "missing-data" not in lim.lower() and "missing data" not in lim.lower():
            flags.append(
                {
                    "code": "possible_missingness_not_echoed_in_limitations",
                    "detail": "challenge_cites_data_risk_but_limitations_silent",
                }
            )

    allowed_ctx = _allowed_numeric_context(memo)
    th = memo.get("thesis_interpretation") or {}
    thesis_text = str(th.get("text") or "") if isinstance(th, dict) else ""
    for m in re.finditer(r"\d+\.\d+", thesis_text):
        tok = m.group(0).lower()
        if tok and tok not in allowed_ctx:
            flags.append(
                {
                    "code": "unsupported_numeric_in_thesis",
                    "detail": f"token:{tok}",
                }
            )
            break

    return {"passed": len(flags) == 0, "flags": flags}
