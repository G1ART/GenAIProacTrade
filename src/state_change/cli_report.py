"""터미널용 state change 요약 출력."""

from __future__ import annotations

import json
from typing import Any


def format_state_change_summary_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"[오류] {payload.get('error', 'unknown')}: run_id={payload.get('run_id')}"
    run = payload["run"]
    lines = [
        "=== State change run 요약 (Phase 6, 조사 후보 레이어) ===",
        f"run_id: {run.get('id')}",
        f"status: {run.get('status')}",
        f"universe: {run.get('universe_name')}",
        f"as_of: {run.get('as_of_date_start')} .. {run.get('as_of_date_end')}",
        f"factor_version: {run.get('factor_version')}  config: {run.get('config_version')}",
        f"rows(total child rows): {run.get('row_count')}  warnings: {run.get('warning_count')}",
        "",
        "candidate_class_counts:",
    ]
    for k, v in sorted((payload.get("candidate_class_counts") or {}).items()):
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("top_candidates (rank, class, cik, ticker, as_of, confidence):")
    for c in payload.get("top_candidates") or []:
        lines.append(
            f"  #{c.get('candidate_rank')}  {c.get('candidate_class')}  "
            f"{c.get('cik')} {c.get('ticker') or '-'}  {c.get('as_of_date')}  "
            f"{c.get('confidence_band')}"
        )
    lines.append("")
    lines.append("top_scores (cik, score, direction, gating):")
    for s in payload.get("top_scores") or []:
        lines.append(
            f"  {s.get('cik')}  score={s.get('state_change_score_v1')}  "
            f"{s.get('state_change_direction')}  gate={s.get('gating_status')}"
        )
    return "\n".join(lines)


def emit_state_change_summary(
    payload: dict[str, Any],
    *,
    output_json: bool,
) -> None:
    if output_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(format_state_change_summary_text(payload))
