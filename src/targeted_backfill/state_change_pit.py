"""Phase 27 D: state-change PIT 갭 세분(재실행 vs 역사 백필 vs 정렬)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from research_validation.metrics import norm_cik, norm_signal_date
from state_change.runner import run_state_change
from substrate_closure.diagnose import report_state_change_join_gaps
from targeted_backfill.constants import (
    PIT_ALIGNMENT_SLACK_CALENDAR_DAYS,
    PIT_HISTORY_SHORT_MAX_CALENDAR_DAYS,
)

_BUCKET_NO_PRE_SIGNAL = "no_pre_signal_state_change_asof"
_BUCKET_WINDOW_SHORT = "state_change_history_window_too_short"
_BUCKET_ALIGN = "signal_to_state_change_alignment_gap"
_BUCKET_JOIN_LOGIC = "join_logic_candidate"


def classify_state_change_pit_row(
    *,
    symbol: str,
    cik: str,
    signal_date_raw: Any,
    earliest_sc_raw: Any,
) -> dict[str, Any]:
    sym = str(symbol or "").upper().strip()
    sig_s = norm_signal_date(signal_date_raw)
    es = norm_signal_date(earliest_sc_raw) if earliest_sc_raw else None
    ck = norm_cik(cik)
    if not sig_s or not es:
        return {
            "symbol": sym,
            "cik": ck,
            "signal_date": sig_s,
            "earliest_sc": es,
            "pit_bucket": _BUCKET_JOIN_LOGIC,
            "note": "missing_dates",
        }
    sig_d = date.fromisoformat(sig_s[:10])
    e_d = date.fromisoformat(es[:10])
    delta = (e_d - sig_d).days
    if delta <= 0:
        return {
            "symbol": sym,
            "cik": ck,
            "signal_date": sig_s,
            "earliest_sc": es,
            "pit_bucket": _BUCKET_JOIN_LOGIC,
            "delta_calendar_days": delta,
            "note": "earliest_on_or_before_signal_expected_elsewhere",
        }
    if delta <= PIT_ALIGNMENT_SLACK_CALENDAR_DAYS:
        b = _BUCKET_ALIGN
    elif delta <= PIT_HISTORY_SHORT_MAX_CALENDAR_DAYS:
        b = _BUCKET_WINDOW_SHORT
    else:
        b = _BUCKET_NO_PRE_SIGNAL
    return {
        "symbol": sym,
        "cik": ck,
        "signal_date": sig_s,
        "earliest_sc": es,
        "pit_bucket": b,
        "delta_calendar_days": delta,
    }


def report_state_change_pit_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    state_change_scores_limit: int = 50_000,
) -> dict[str, Any]:
    base = report_state_change_join_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        state_change_scores_limit=state_change_scores_limit,
    )
    pit_rows = list(
        (base.get("row_reason_buckets") or {}).get("all_state_change_as_of_after_signal_pit_gap", [])
    )
    classified: list[dict[str, Any]] = []
    bc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pit_rows:
        c = classify_state_change_pit_row(
            symbol=str(row.get("symbol") or ""),
            cik=str(row.get("cik") or ""),
            signal_date_raw=row.get("signal_date"),
            earliest_sc_raw=row.get("earliest_sc"),
        )
        merged = {**row, **c}
        classified.append(merged)
        bc[str(c.get("pit_bucket") or "")].append(merged)

    historical_backfill_candidates = len(bc.get(_BUCKET_WINDOW_SHORT, []))

    return {
        "ok": True,
        "universe_name": universe_name,
        "pit_unresolved_row_count": len(pit_rows),
        "historical_backfill_might_help_count": historical_backfill_candidates,
        "pit_bucket_counts": {k: len(v) for k, v in bc.items()},
        "pit_buckets_sample": {k: v[:40] for k, v in bc.items()},
        "pit_all_rows": classified,
        "state_change_join_base": {
            "metrics": base.get("metrics"),
            "row_reason_counts": base.get("row_reason_counts"),
        },
    }


def export_state_change_pit_gap_rows(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    import csv
    import json
    from pathlib import Path

    rep = report_state_change_pit_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    rows = list(rep.get("pit_all_rows") or [])

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv" and rows:
        keys = sorted({k for row in rows for k in row})
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    elif fmt == "csv":
        p.write_text("symbol,cik,signal_date,earliest_sc,pit_bucket\n", encoding="utf-8")
    else:
        p.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "path": str(p), "count": len(rows), "format": fmt}


def run_state_change_history_backfill_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    history_backfill_days: int = 800,
    state_change_limit: int = 500,
    factor_version: str = "v1",
) -> dict[str, Any]:
    from db.client import get_supabase_client

    c = get_supabase_client(settings)
    before_pit = report_state_change_pit_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    before_full = report_state_change_join_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    ex_before = int((before_full.get("exclusion_distribution") or {}).get("no_state_change_join", 0))

    end_d = date.today()
    start_d = end_d - timedelta(days=max(30, history_backfill_days))
    sc_out = run_state_change(
        c,
        universe_name=universe_name,
        factor_version=factor_version,
        limit=max(1, state_change_limit),
        dry_run=False,
        start_date=start_d.isoformat(),
        end_date=end_d.isoformat(),
    )

    after_full = report_state_change_join_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    ex_after = int((after_full.get("exclusion_distribution") or {}).get("no_state_change_join", 0))
    after_pit = report_state_change_pit_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )

    return {
        "ok": True,
        "repair": "state_change_history_backfill",
        "universe_name": universe_name,
        "window": {"start_date": start_d.isoformat(), "end_date": end_d.isoformat()},
        "before": {
            "no_state_change_join": ex_before,
            "pit_unresolved_row_count": before_pit.get("pit_unresolved_row_count"),
        },
        "after": {
            "no_state_change_join": ex_after,
            "pit_unresolved_row_count": after_pit.get("pit_unresolved_row_count"),
        },
        "state_change_run_result": sc_out,
        "note": (
            "동일 엔진이 아니라 start_date/end_date 를 확장한 결정적 역사 윈도우 실행입니다. "
            "효과 없으면 join_logic_candidate 또는 팩터 히스토리 한계로 분류합니다."
        ),
    }
