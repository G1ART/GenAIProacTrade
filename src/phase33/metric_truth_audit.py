"""Phase 32 터치 집합 기준 forward 지표 진실(행·심볼 큐·joined) 분리."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from db import records as dbrec
from phase33.phase32_bundle_io import (
    forward_gap_report_from_bundle,
    load_phase32_bundle,
    phase32_bundle_repaired_symbol_count,
    phase32_touched_symbols,
)
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.constants import EXCESS_FIELD
from research_validation.metrics import safe_float


def _panel_rows_for_symbols(
    client: Any, *, symbols: list[str], panel_limit: int
) -> list[dict[str, Any]]:
    if not symbols:
        return []
    return dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=symbols, limit=panel_limit
    )


def report_forward_metric_truth_audit(
    client: Any,
    *,
    universe_name: str,
    phase32_bundle: dict[str, Any] | None = None,
    phase32_bundle_path: str | None = None,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    if phase32_bundle is None:
        if not phase32_bundle_path:
            raise ValueError("phase32_bundle or phase32_bundle_path required")
        phase32_bundle = load_phase32_bundle(phase32_bundle_path)

    touched = phase32_touched_symbols(phase32_bundle)
    gap = forward_gap_report_from_bundle(phase32_bundle)
    entries = [e for e in (gap.get("target_entries") or []) if e.get("symbol")]
    touched_in_queue_at_phase32_gap_report = {
        str(e.get("symbol") or "").upper().strip()
        for e in entries
        if e.get("in_missing_excess_return_1q_queue")
    }

    fb = phase32_bundle.get("forward_return_backfill_phase31_touched") or {}
    per_after = fb.get("per_symbol_after") or {}
    bundle_symbol_unblocked = sum(
        1 for v in per_after.values() if v.get("forward_return_unblocked_now")
    )
    bundle_repaired = phase32_bundle_repaired_symbol_count(phase32_bundle)

    panels = _panel_rows_for_symbols(client, symbols=touched, panel_limit=panel_limit)
    rows_excess_null = sum(1 for p in panels if safe_float(p.get(EXCESS_FIELD)) is None)
    rows_excess_present = sum(1 for p in panels if safe_float(p.get(EXCESS_FIELD)) is not None)

    queues: dict[str, list[str]] = {}
    cov_live, excl_live = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        symbol_queues_out=queues,
    )
    miss_live = {s.upper().strip() for s in queues.get("missing_excess_return_1q", [])}

    symbol_cleared_from_missing_excess_queue_count = sum(
        1 for s in touched_in_queue_at_phase32_gap_report if s and s not in miss_live
    )
    touched_still_in_queue = sorted(
        s for s in touched if s in miss_live
    )

    joined_before = int(
        (phase32_bundle.get("before") or {}).get("joined_recipe_substrate_row_count")
        or -1
    )
    joined_live = int(cov_live.get("joined_recipe_substrate_row_count") or 0)
    joined_delta = (
        joined_live - joined_before if joined_before >= 0 else None
    )

    phase32_after_miss = int(
        (phase32_bundle.get("after") or {}).get("missing_excess_return_1q") or -1
    )
    miss_live_headline = int(excl_live.get("missing_excess_return_1q") or 0)

    why_no_headline_drop = (
        "Phase 32의 repaired_to_forward_present는 심볼당 대표 시그널일 1건 기준으로 "
        "next_quarter excess가 채워졌는지 본 것이다. missing_excess_return_1q 큐는 "
        "해당 심볼의 검증 패널 행 중 excess가 하나라도 비면 심볼 전체를 큐에 넣는다. "
        "따라서 일부 시그널만 채워도 심볼은 큐에 남을 수 있고, 다른 심볼/행이 새로 들어오면 "
        "헤드라인 카운트는 오히려 늘어난다."
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "phase32_touched_symbol_count": len(touched),
        "forward_row_unblocked_now_count_bundle_phase32": bundle_repaired,
        "forward_return_unblocked_flag_count_in_per_symbol_after": bundle_symbol_unblocked,
        "validation_panel_rows_for_touched_symbols": {
            "row_count": len(panels),
            "excess_null_row_count": rows_excess_null,
            "excess_present_row_count": rows_excess_present,
        },
        "symbol_cleared_from_missing_excess_queue_count": symbol_cleared_from_missing_excess_queue_count,
        "touched_symbols_still_in_missing_excess_queue": touched_still_in_queue,
        "joined_recipe_substrate_row_count_phase32_before": joined_before,
        "joined_recipe_substrate_row_count_live": joined_live,
        "joined_recipe_unlocked_now_count_delta": joined_delta,
        "missing_excess_return_1q_headline_phase32_after_snapshot": phase32_after_miss,
        "missing_excess_return_1q_headline_live": miss_live_headline,
        "why_repaired_count_did_not_reduce_headline_excess": why_no_headline_drop,
        "metrics_live": cov_live,
        "exclusion_distribution_live": dict(excl_live),
    }


def export_forward_metric_truth_audit(
    rep: dict[str, Any],
    *,
    out_json: str,
) -> str:
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())
