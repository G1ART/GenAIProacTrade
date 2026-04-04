"""End-to-end memo JSON from Harness input v1."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from harness.contracts import MEMO_SCHEMA_VERSION
from harness.referee.gate import referee_gate_scan
from harness.roles.deterministic_agents import (
    run_challenge_agent,
    run_synthesis_agent,
    run_thesis_agent,
    signal_summary_block,
)

GENERATION_MODE = "deterministic_skeleton_v1"


def _evidence_blocks(inp: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for h in inp.get("filing_source_handles") or []:
        blocks.append(
            {
                "kind": "filing_handle",
                "ref": h,
                "uncertainty_label": "confirmed",
            }
        )
    blocks.append(
        {
            "kind": "deterministic_score_row",
            "ref": {
                "state_change_score": inp.get("state_change_score"),
                "direction": inp.get("state_change_direction"),
            },
            "uncertainty_label": "confirmed"
            if inp.get("state_change_score") is not None
            else "unverifiable",
        }
    )
    return blocks


def _limitations(inp: dict[str, Any]) -> str:
    parts = [
        "This memo is an analytical overlay; it does not modify deterministic tables.",
        "Forward returns in validation panels are research join fields, not used here as predictive features.",
    ]
    if inp.get("missing_data_indicators"):
        parts.append(
            "Missing-data flags: " + ", ".join(str(x) for x in inp["missing_data_indicators"])
        )
    return " ".join(parts)


def generate_investigation_memo_v1(
    inp: dict[str, Any],
    *,
    memo_id: str | None = None,
    memo_version: int = 1,
) -> dict[str, Any]:
    thesis = run_thesis_agent(inp)
    challenge = run_challenge_agent(inp)
    synthesis = run_synthesis_agent(inp, thesis, challenge)

    memo: dict[str, Any] = {
        "memo_id": memo_id or str(uuid.uuid4()),
        "memo_schema_version": MEMO_SCHEMA_VERSION,
        "candidate_id": inp.get("candidate_id"),
        "memo_version": memo_version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generation_mode": GENERATION_MODE,
        "deterministic_signal_summary": {
            "block": signal_summary_block(inp),
            "uncertainty_label": "confirmed",
        },
        "thesis_interpretation": thesis,
        "strongest_counter_argument": challenge,
        "synthesis": synthesis,
        "uncertainty_labels": [
            thesis.get("uncertainty_label"),
            challenge.get("uncertainty_label"),
            synthesis.get("uncertainty_label"),
        ],
        "evidence_blocks": _evidence_blocks(inp),
        "limitations_and_missingness": _limitations(inp),
        "operator_status": "pending_review",
        "source_trace": {
            "contract_version": inp.get("contract_version"),
            "payload_hash": inp.get("payload_hash"),
            "cik": inp.get("cik"),
            "as_of_date": inp.get("as_of_date"),
            "state_change_run_id": inp.get("state_change_run_id"),
        },
    }

    ref = referee_gate_scan(memo)
    memo["referee_result"] = ref
    memo["referee_flags"] = ref.get("flags") or []
    return memo
