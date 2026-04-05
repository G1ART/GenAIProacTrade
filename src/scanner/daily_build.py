"""Daily scanner: snapshot stats + bounded watchlist rows."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from db import records as dbrec
from message_contract import OVERLAY_FUTURE_SEAMS_DEFAULT
from sources.provenance import build_overlay_awareness_snapshot
from scanner.prioritizer import (
    DEFAULT_MAX_CANDIDATE_RANK,
    DEFAULT_MIN_PRIORITY_SCORE,
    DEFAULT_TOP_N,
    rank_watchlist_candidates,
)
from scanner.transcript_enrichment import (
    build_transcript_enrichment_for_ticker,
    optional_why_matters_transcript_clause,
)


def _memo_json(memo: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not memo:
        return {}
    mj = memo.get("memo_json")
    return mj if isinstance(mj, dict) else {}


def _summaries_from_memo(
    memo: Optional[dict[str, Any]],
    score_row: dict[str, Any],
    cand: dict[str, Any],
) -> tuple[str, str, str, str]:
    mj = _memo_json(memo)
    th = mj.get("thesis_interpretation") or {}
    ch = mj.get("strongest_counter_argument") or {}
    det = mj.get("deterministic_signal_summary") or {}
    if isinstance(th, dict) and th.get("text"):
        thesis = str(th["text"])[:600]
    else:
        thesis = (
            f"Deterministic class={cand.get('candidate_class')}, "
            f"direction={score_row.get('state_change_direction')}, "
            f"score={score_row.get('state_change_score_v1')}."
        )
    ch_parts = []
    if isinstance(ch, dict):
        if ch.get("alternate_interpretation"):
            ch_parts.append(str(ch["alternate_interpretation"])[:350])
        if ch.get("data_insufficiency_risk"):
            ch_parts.append(str(ch["data_insufficiency_risk"])[:350])
    challenge = " ".join(ch_parts) if ch_parts else (
        "Counter-case: data gaps, regime mismatch, and non-price relevance remain live risks."
    )
    if isinstance(det, dict):
        dtxt = str(det.get("block") or det)[:500]
    else:
        dtxt = str(det)[:500]
    unc = mj.get("uncertainty_labels")
    if isinstance(unc, list) and unc:
        uncertainty = "Memo uncertainty labels: " + ", ".join(str(x) for x in unc[:6])
    else:
        uncertainty = (
            "Uncertainty: plausible_hypothesis / unverifiable mix; see harness memo taxonomy if present."
        )
    return dtxt, thesis, challenge, uncertainty


def run_daily_scanner_build(
    client: Any,
    *,
    state_change_run_id: str,
    universe_name: str,
    as_of_calendar_date: Optional[str] = None,
    candidate_scan_limit: int = 500,
    top_n: int = DEFAULT_TOP_N,
    min_priority_score: float = DEFAULT_MIN_PRIORITY_SCORE,
    max_candidate_rank: int = DEFAULT_MAX_CANDIDATE_RANK,
) -> dict[str, Any]:
    as_of = as_of_calendar_date or date.today().isoformat()
    overlay_snap = build_overlay_awareness_snapshot(client)

    candidates = dbrec.fetch_state_change_candidates_for_run(
        client, run_id=state_change_run_id, limit=candidate_scan_limit
    )
    class_counts: dict[str, int] = {}
    pairs: list[tuple[dict[str, Any], Optional[dict[str, Any]]]] = []
    for c in candidates:
        cc = str(c.get("candidate_class") or "")
        class_counts[cc] = class_counts.get(cc, 0) + 1
        sc = dbrec.fetch_state_change_score_for_cik_date(
            client,
            run_id=state_change_run_id,
            cik=str(c.get("cik") or ""),
            as_of_date=str(c.get("as_of_date") or ""),
        )
        pairs.append((c, sc))

    policy = {
        "top_n": top_n,
        "min_priority_score": min_priority_score,
        "max_candidate_rank": max_candidate_rank,
        "candidate_scan_limit": candidate_scan_limit,
        "low_noise_note": "Intentionally bounded; empty watchlist allowed if gate fails all rows.",
    }
    sid = dbrec.insert_scanner_run(
        client,
        as_of_calendar_date=as_of,
        state_change_run_id=state_change_run_id,
        universe_name=universe_name,
        policy_json=policy,
    )

    ranked = rank_watchlist_candidates(
        pairs,
        top_n=top_n,
        min_priority_score=min_priority_score,
        max_candidate_rank=max_candidate_rank,
    )

    stats = {
        "candidates_scanned": len(candidates),
        "class_counts": class_counts,
        "watchlist_selected": len(ranked),
        "state_change_run_id": state_change_run_id,
        "as_of_calendar_date": as_of,
    }
    dbrec.insert_daily_signal_snapshot(client, scanner_run_id=sid, stats_json=stats)

    watch_rows: list[dict[str, Any]] = []
    for i, (cand, score_row, pr) in enumerate(ranked, start=1):
        cid = str(cand.get("id") or "")
        memo = dbrec.fetch_latest_memo_for_candidate(client, candidate_id=cid)
        dsum, thesis, challenge, unc = _summaries_from_memo(memo, score_row, cand)
        ticker = str(cand.get("ticker") or "").strip() or str(cand.get("cik") or "")
        as_of_d = str(cand.get("as_of_date") or "")
        reason = (
            f"priority={pr:.1f}, class={cand.get('candidate_class')}, "
            f"rank={cand.get('candidate_rank')}, |score|={abs(float(score_row.get('state_change_score_v1') or 0)):.3f}"
        )
        action_note = (
            "Review window: issuer-date snapshot only; no execution horizon implied."
        )
        regime_w = None
        if memo:
            mj = _memo_json(memo)
            lim = str(mj.get("limitations_and_missingness") or "")[:400]
            if lim:
                regime_w = lim[:500]

        tenr = build_transcript_enrichment_for_ticker(client, ticker=ticker)
        why_base = (
            f"Ranks in top-{top_n} deterministic attention slice for {universe_name} "
            "without implying price direction."
        )
        why = why_base + optional_why_matters_transcript_clause(tenr)

        watch_rows.append(
            {
                "scanner_run_id": sid,
                "candidate_id": cid,
                "priority_rank": i,
                "priority_score": pr,
                "deterministic_signal_summary": dsum,
                "thesis_summary": thesis,
                "challenge_summary": challenge,
                "uncertainty_summary": unc,
                "reason_in_watchlist": reason,
                "actionability_note": action_note,
                "regime_warning": regime_w,
                "source_trace": {
                    "scanner_run_id": sid,
                    "candidate_id": cid,
                    "state_change_run_id": state_change_run_id,
                    "memo_id": memo.get("id") if memo else None,
                },
                "message_short_title": f"Watch: {ticker} ({as_of_d})",
                "message_why_matters": why,
                "message_what_could_wrong": challenge[:800],
                "message_unknown": unc[:800],
                "message_plain_language": (
                    f"{ticker} on {as_of_d}: state-change signal is elevated in our internal ranking. "
                    "This is prioritization for human review, not a forecast."
                ),
                "overlay_future_seams_json": dict(OVERLAY_FUTURE_SEAMS_DEFAULT),
                "overlay_awareness_json": overlay_snap,
                "transcript_enrichment_json": tenr,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    dbrec.insert_daily_watchlist_entries_batch(client, watch_rows)
    return {
        "scanner_run_id": sid,
        "watchlist_entries": len(watch_rows),
        "stats": stats,
        "policy": policy,
    }
