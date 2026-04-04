"""Batch: materialize inputs + generate memos for a state_change run."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from harness.memo_builder.pipeline import generate_investigation_memo_v1


def claims_rows_from_memo(memo_id: str, memo: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, eb in enumerate(memo.get("evidence_blocks") or []):
        if not isinstance(eb, dict):
            continue
        label = str(eb.get("uncertainty_label") or "unverifiable")
        if label not in ("confirmed", "plausible_hypothesis", "unverifiable"):
            label = "unverifiable"
        rows.append(
            {
                "memo_id": memo_id,
                "claim_key": f"evidence_block_{i}",
                "claim_text": str(eb.get("kind") or "evidence")
                + ": "
                + str(eb.get("ref") or "")[:2000],
                "uncertainty_label": label,
                "evidence_ref_json": {"block": eb},
            }
        )
    th = memo.get("thesis_interpretation") or {}
    if isinstance(th, dict) and th.get("text"):
        rows.append(
            {
                "memo_id": memo_id,
                "claim_key": "thesis",
                "claim_text": str(th["text"])[:8000],
                "uncertainty_label": str(
                    th.get("uncertainty_label") or "plausible_hypothesis"
                ),
                "evidence_ref_json": {"section": "thesis"},
            }
        )
    ch = memo.get("strongest_counter_argument") or {}
    if isinstance(ch, dict) and ch.get("alternate_interpretation"):
        rows.append(
            {
                "memo_id": memo_id,
                "claim_key": "challenge_alternate",
                "claim_text": str(ch["alternate_interpretation"])[:8000],
                "uncertainty_label": "plausible_hypothesis",
                "evidence_ref_json": {"section": "challenge"},
            }
        )
    return rows


def generate_memos_for_run(
    client: Any,
    *,
    run_id: str,
    limit: int = 200,
) -> dict[str, Any]:
    inputs = dbrec.fetch_ai_harness_inputs_for_run(client, run_id=run_id, limit=limit)
    done = 0
    errors: list[dict[str, Any]] = []
    for row in inputs:
        cand_id = str(row["candidate_id"])
        payload = row.get("payload_json") or {}
        if not isinstance(payload, dict):
            errors.append({"candidate_id": cand_id, "error": "bad_payload"})
            continue
        try:
            ver = dbrec.fetch_max_memo_version(client, candidate_id=cand_id) + 1
            memo = generate_investigation_memo_v1(payload, memo_version=ver)
            ref = memo.get("referee_result") or {}
            passed = bool(ref.get("passed"))
            mid = dbrec.insert_investigation_memo(
                client,
                candidate_id=cand_id,
                input_id=str(row["id"]),
                memo_version=ver,
                generation_mode=str(memo.get("generation_mode") or "unknown"),
                memo_json=memo,
                referee_passed=passed,
                referee_flags_json=list(ref.get("flags") or []),
            )
            dbrec.insert_investigation_memo_claims_batch(
                client, claims_rows_from_memo(mid, memo)
            )
            dbrec.upsert_operator_review_queue(
                client,
                candidate_id=cand_id,
                issuer_id=payload.get("issuer_id"),
                cik=str(payload.get("cik") or ""),
                as_of_date=str(payload.get("as_of_date") or ""),
                status="pending",
                memo_id=mid,
            )
            done += 1
        except Exception as ex:  # noqa: BLE001
            errors.append({"candidate_id": cand_id, "error": str(ex)})
    return {"run_id": run_id, "memos_created": done, "errors": errors}
