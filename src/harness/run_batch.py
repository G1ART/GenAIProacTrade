"""Batch: materialize inputs + generate memos for a state_change run."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from harness.memo_builder.pipeline import GENERATION_MODE, generate_investigation_memo_v1
from harness.rerun_policy import (
    decide_memo_write_mode,
    resolve_queue_status_on_memo_regen,
)


def _trace_base(memo: dict[str, Any]) -> dict[str, Any]:
    st = memo.get("source_trace") or {}
    return {
        "source_trace": st,
        "memo_schema_version": memo.get("memo_schema_version"),
        "memo_version": memo.get("memo_version"),
    }


def claims_rows_from_memo(
    memo_id: str, memo: dict[str, Any], candidate_id: str
) -> list[dict[str, Any]]:
    """Phase 7.1 claim rows: role, statement, trace_refs, verdict defaults."""
    rows: list[dict[str, Any]] = []
    base_trace = _trace_base(memo)
    th = memo.get("thesis_interpretation") or {}
    ch = memo.get("strongest_counter_argument") or {}
    syn = memo.get("synthesis") or {}
    ch_alt = str(ch.get("alternate_interpretation") or "") if isinstance(ch, dict) else ""
    th_txt = str(th.get("text") or "") if isinstance(th, dict) else ""

    def _row(
        *,
        claim_id: str,
        claim_role: str,
        statement: str,
        uncertainty_label: str,
        support_summary: str,
        counter_evidence_summary: str,
        trace_refs: dict[str, Any],
        needs_verification: bool,
        evidence_ref_json: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "memo_id": memo_id,
            "candidate_id": candidate_id,
            "claim_id": claim_id,
            "claim_key": claim_id,
            "claim_text": statement[:8000],
            "statement": statement[:8000],
            "claim_role": claim_role,
            "uncertainty_label": uncertainty_label,
            "support_summary": support_summary[:4000],
            "counter_evidence_summary": counter_evidence_summary[:4000],
            "trace_refs": trace_refs,
            "needs_verification": needs_verification,
            "verdict": "pending",
            "claim_revision": 1,
            "evidence_ref_json": evidence_ref_json,
        }

    for i, eb in enumerate(memo.get("evidence_blocks") or []):
        if not isinstance(eb, dict):
            continue
        label = str(eb.get("uncertainty_label") or "unverifiable")
        if label not in ("confirmed", "plausible_hypothesis", "unverifiable"):
            label = "unverifiable"
        stmt = (
            str(eb.get("kind") or "evidence")
            + ": "
            + str(eb.get("ref") or "")[:2000]
        )
        rows.append(
            _row(
                claim_id=f"evidence_block_{i}",
                claim_role="evidence",
                statement=stmt,
                uncertainty_label=label,
                support_summary="Deterministic harness input / filing or score handle.",
                counter_evidence_summary="",
                trace_refs={**base_trace, "evidence_index": i},
                needs_verification=label != "confirmed",
                evidence_ref_json={"block": eb},
            )
        )

    if isinstance(th, dict) and th.get("text"):
        ul = str(th.get("uncertainty_label") or "plausible_hypothesis")
        rows.append(
            _row(
                claim_id="thesis_main",
                claim_role="thesis",
                statement=str(th["text"])[:8000],
                uncertainty_label=ul,
                support_summary="Anchored to deterministic_signal_summary and Phase 6 class/score (see trace).",
                counter_evidence_summary=(ch_alt[:2000] if ch_alt else "See challenge claims."),
                trace_refs={**base_trace, "section": "thesis_interpretation"},
                needs_verification=True,
                evidence_ref_json={"section": "thesis", "anchors": th.get("anchors")},
            )
        )

    if isinstance(ch, dict):
        dims = [
            ("challenge_alternate", "alternate_interpretation", "challenge"),
            ("challenge_data_insufficiency", "data_insufficiency_risk", "challenge"),
            ("challenge_contamination", "contamination_regime_risk", "challenge"),
            ("challenge_why_not_matter", "why_change_may_not_matter", "challenge"),
            ("challenge_falsify", "what_would_falsify_thesis", "challenge"),
        ]
        for cid, key, _sec in dims:
            val = ch.get(key)
            if val is None:
                continue
            stmt = str(val)[:8000]
            if not stmt.strip():
                continue
            rows.append(
                _row(
                    claim_id=cid,
                    claim_role="challenge",
                    statement=stmt,
                    uncertainty_label="plausible_hypothesis",
                    support_summary="Structured counter-case dimension from ChallengeAgent.",
                    counter_evidence_summary=th_txt[:2000] if th_txt else "See thesis_main.",
                    trace_refs={**base_trace, "section": key},
                    needs_verification=True,
                    evidence_ref_json={"section": "strongest_counter_argument", "key": key},
                )
            )

    if isinstance(syn, dict) and syn.get("text"):
        rows.append(
            _row(
                claim_id="synthesis_main",
                claim_role="synthesis",
                statement=str(syn.get("text") or "")[:8000],
                uncertainty_label=str(syn.get("uncertainty_label") or "unverifiable"),
                support_summary="Holds thesis and challenge in tension without forced consensus.",
                counter_evidence_summary=str(syn.get("explicit_disagreement_note") or "")[
                    :2000
                ],
                trace_refs={**base_trace, "section": "synthesis"},
                needs_verification=True,
                evidence_ref_json={
                    "thesis_preserved": syn.get("thesis_preserved"),
                    "challenge_preserved": syn.get("challenge_preserved"),
                },
            )
        )

    ref = memo.get("referee_result") or {}
    for fi, flg in enumerate(ref.get("flags") or []):
        if not isinstance(flg, dict):
            continue
        code = str(flg.get("code") or "referee_flag")
        det = str(flg.get("detail") or "")
        rows.append(
            _row(
                claim_id=f"referee_flag_{fi}",
                claim_role="referee",
                statement=f"{code}: {det}"[:8000],
                uncertainty_label="confirmed",
                support_summary="RefereeGate structural scan output.",
                counter_evidence_summary="",
                trace_refs={**base_trace, "referee_flag_index": fi},
                needs_verification=False,
                evidence_ref_json=dict(flg),
            )
        )

    return rows


def generate_memos_for_run(
    client: Any,
    *,
    run_id: str,
    limit: int = 200,
    force_new_memo_version: bool = False,
    candidate_ids: set[str] | None = None,
) -> dict[str, Any]:
    inputs = dbrec.fetch_ai_harness_inputs_for_run(client, run_id=run_id, limit=limit)
    inserted = 0
    replaced = 0
    errors: list[dict[str, Any]] = []
    for row in inputs:
        cand_id = str(row["candidate_id"])
        if candidate_ids is not None and cand_id not in candidate_ids:
            continue
        payload = row.get("payload_json") or {}
        if not isinstance(payload, dict):
            errors.append({"candidate_id": cand_id, "error": "bad_payload"})
            continue
        ph = str(row.get("payload_hash") or "")
        try:
            latest = dbrec.fetch_latest_memo_for_candidate(client, candidate_id=cand_id)
            write_mode = decide_memo_write_mode(
                payload_hash=ph,
                generation_mode=GENERATION_MODE,
                latest_memo=latest,
                force_new_version=force_new_memo_version,
            )
            existing_q = dbrec.fetch_operator_review_queue_row(
                client, candidate_id=cand_id
            )

            if write_mode == "in_place_replace":
                assert latest is not None
                mid = str(latest["id"])
                ver = int(latest["memo_version"])
                memo = generate_investigation_memo_v1(
                    payload, memo_version=ver, memo_id=mid
                )
                ref = memo.get("referee_result") or {}
                passed = bool(ref.get("passed"))
                dbrec.update_investigation_memo(
                    client,
                    memo_id=mid,
                    input_id=str(row["id"]),
                    memo_json=memo,
                    referee_passed=passed,
                    referee_flags_json=list(ref.get("flags") or []),
                    input_payload_hash=ph,
                )
                dbrec.delete_investigation_memo_claims_for_memo(client, memo_id=mid)
                dbrec.insert_investigation_memo_claims_batch(
                    client, claims_rows_from_memo(mid, memo, cand_id)
                )
                qstatus = resolve_queue_status_on_memo_regen(
                    existing_q, referee_passed=passed
                )
                dbrec.upsert_operator_review_queue(
                    client,
                    candidate_id=cand_id,
                    issuer_id=payload.get("issuer_id"),
                    cik=str(payload.get("cik") or ""),
                    as_of_date=str(payload.get("as_of_date") or ""),
                    status=qstatus,
                    memo_id=mid,
                )
                replaced += 1
                continue

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
                input_payload_hash=ph,
            )
            dbrec.insert_investigation_memo_claims_batch(
                client, claims_rows_from_memo(mid, memo, cand_id)
            )
            qstatus = resolve_queue_status_on_memo_regen(
                existing_q, referee_passed=passed
            )
            dbrec.upsert_operator_review_queue(
                client,
                candidate_id=cand_id,
                issuer_id=payload.get("issuer_id"),
                cik=str(payload.get("cik") or ""),
                as_of_date=str(payload.get("as_of_date") or ""),
                status=qstatus,
                memo_id=mid,
            )
            inserted += 1
        except Exception as ex:  # noqa: BLE001
            errors.append({"candidate_id": cand_id, "error": str(ex)})
    return {
        "run_id": run_id,
        "memos_inserted_new_version": inserted,
        "memos_replaced_in_place": replaced,
        "errors": errors,
    }
