"""Phase 6 state change run 요약 (실행 신호·알파 아님)."""

from __future__ import annotations

from typing import Any, Optional

from db import records as dbrec


def build_state_change_run_report(
    client: Any,
    *,
    run_id: str,
    scores_limit: int = 15,
    candidates_limit: int = 20,
) -> dict[str, Any]:
    run = dbrec.fetch_state_change_run(client, run_id=run_id)
    if not run:
        return {"ok": False, "error": "run_not_found", "run_id": run_id}
    scores = dbrec.fetch_state_change_scores_for_run(
        client, run_id=run_id, limit=scores_limit
    )
    cands = dbrec.fetch_state_change_candidates_for_run(
        client, run_id=run_id, limit=candidates_limit
    )
    class_counts = dbrec.fetch_state_change_candidate_class_counts(
        client, run_id=run_id
    )
    return {
        "ok": True,
        "run": run,
        "top_scores": scores,
        "top_candidates": cands,
        "candidate_class_counts": class_counts,
    }


def resolve_report_run_id(
    client: Any,
    *,
    universe_name: Optional[str],
    run_id: Optional[str],
) -> Optional[str]:
    if run_id:
        return run_id
    if universe_name:
        return dbrec.fetch_latest_state_change_run_id(
            client, universe_name=universe_name
        )
    return None
