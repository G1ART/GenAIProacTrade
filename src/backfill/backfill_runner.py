"""Universe backfill 오케스트레이션 — 기존 파이프라인만 호출."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from backfill import STAGE_ORDER
from backfill.checkpoint_report import build_coverage_checkpoint_report
from backfill.staged_cohort import resolve_staged_coverage_tickers
from backfill.universe_resolver import resolve_backfill_tickers
from db import records as dbrec
from factors.panel_build import run_factor_panels_watchlist
from market.forward_returns_run import run_forward_returns_build
from market.price_ingest import run_market_prices_ingest
from market.validation_panel_run import run_validation_panel_build
from research.validation_runner import run_factor_validation_research
from sec.facts_watchlist import run_facts_extract_for_tickers
from sec.snapshot_build_run import run_quarter_snapshot_build_tickers
from sec.watchlist_ingest import run_sec_ingest_for_tickers
from state_change.runner import run_state_change

logger = logging.getLogger(__name__)


def _stage_range(
    start_stage: Optional[str], end_stage: Optional[str]
) -> tuple[int, int]:
    names = STAGE_ORDER
    s = start_stage or names[0]
    e = end_stage or names[-1]
    if s not in names:
        raise ValueError(f"unknown start_stage {s!r}; expected one of {names}")
    if e not in names:
        raise ValueError(f"unknown end_stage {e!r}; expected one of {names}")
    si, ei = names.index(s), names.index(e)
    if si > ei:
        raise ValueError("start_stage must be before or equal to end_stage")
    return si, ei


def _in_range(i: int, lo: int, hi: int) -> bool:
    return lo <= i <= hi


def _filings_per_issuer(mode: str) -> int:
    return {"smoke": 3, "pilot": 6, "full": 10, "extended": 10}.get(mode, 6)


def _snapshot_limit(mode: str) -> int:
    return {"smoke": 25, "pilot": 60, "full": 150, "extended": 150}.get(mode, 60)


def _panel_limit(mode: str) -> int:
    return {"smoke": 800, "pilot": 8000, "full": 75000, "extended": 75000}.get(
        mode, 8000
    )


def _limits_mode(mode: str, coverage_stage: Optional[str]) -> str:
    if coverage_stage:
        return "full"
    return mode


def run_backfill_universe(
    settings: Any,
    client: Any,
    *,
    mode: str,
    universe_name: str,
    symbol_limit: Optional[int] = None,
    start_stage: Optional[str] = None,
    end_stage: Optional[str] = None,
    dry_run: bool = False,
    retry_failed_only: bool = False,
    from_orchestration_run_id: Optional[str] = None,
    rerun_phase5: bool = False,
    rerun_phase6: bool = False,
    sleep_sec: float = 0.55,
    factor_version: str = "v1",
    market_lookback_days: int = 400,
    coverage_stage: Optional[str] = None,
    issuer_target: Optional[int] = None,
    write_coverage_checkpoint: Optional[str] = None,
) -> dict[str, Any]:
    si, ei = _stage_range(start_stage, end_stage)
    stage_results: dict[str, Any] = {}
    retry_tickers: set[str] = set()
    lim_mode = _limits_mode(mode, coverage_stage)
    requested_target: Optional[int] = None

    if retry_failed_only:
        if not from_orchestration_run_id:
            return {
                "status": "failed",
                "error": "retry_failed_only_requires_from_orchestration_run_id",
            }
        prev = dbrec.fetch_backfill_orchestration_run(
            client, run_id=from_orchestration_run_id
        )
        if not prev:
            return {"status": "failed", "error": "orchestration_run_not_found"}
        summ = prev.get("summary_json") or {}
        tickers = list(summ.get("retry_tickers_all") or [])
        if not tickers:
            return {"status": "failed", "error": "no_retry_tickers_in_summary"}
        resolve_meta = {
            "retry_from": from_orchestration_run_id,
            "resolved_symbol_count": len(tickers),
        }
    elif coverage_stage:
        tickers, resolve_meta = resolve_staged_coverage_tickers(
            client,
            universe_name=universe_name,
            coverage_stage=coverage_stage,
            issuer_target=issuer_target,
        )
        requested_target = resolve_meta.get("requested_issuer_target")
    else:
        tickers, resolve_meta = resolve_backfill_tickers(
            client,
            mode=mode,
            universe_name=universe_name,
            symbol_limit=symbol_limit,
        )
        requested_target = symbol_limit

    orch_req = (
        requested_target if coverage_stage else symbol_limit
    )

    orch_id = dbrec.backfill_orch_insert_started(
        client,
        mode=mode,
        universe_name=universe_name,
        requested_symbol_count=orch_req,
        resolved_symbol_count=len(tickers),
        config_json={
            "start_stage": start_stage or STAGE_ORDER[0],
            "end_stage": end_stage or STAGE_ORDER[-1],
            "dry_run": dry_run,
            "retry_failed_only": retry_failed_only,
            "rerun_phase5": rerun_phase5,
            "rerun_phase6": rerun_phase6,
            "coverage_stage": coverage_stage,
            "issuer_target": issuer_target,
            "tickers_preview": tickers[:20],
        },
    )

    def _record(
        name: str,
        status: str,
        *,
        ins: int = 0,
        upd: int = 0,
        skip: int = 0,
        warn: int = 0,
        err: int = 0,
        notes: Optional[dict[str, Any]] = None,
    ) -> None:
        dbrec.insert_backfill_stage_event(
            client,
            orchestration_run_id=orch_id,
            stage_name=name,
            stage_status=status,
            inserted_rows=ins,
            updated_rows=upd,
            skipped_rows=skip,
            warning_count=warn,
            error_count=err,
            notes_json=notes or {},
        )

    try:
        if _in_range(STAGE_ORDER.index("resolve"), si, ei):
            _record(
                "resolve",
                "skipped_dry_run" if dry_run else "completed",
                notes={"resolve_meta": resolve_meta, "tickers": tickers},
            )
            stage_results["resolve"] = {"tickers": tickers, "meta": resolve_meta}

        filings = _filings_per_issuer(lim_mode)
        snap_lim = _snapshot_limit(lim_mode)
        plim = _panel_limit(lim_mode)

        if _in_range(STAGE_ORDER.index("sec"), si, ei):
            if dry_run:
                _record("sec", "skipped_dry_run", notes={"would_tickers": tickers})
            else:
                sec_out = run_sec_ingest_for_tickers(
                    settings,
                    tickers=tickers,
                    filings_per_issuer=filings,
                    client=client,
                    sleep_seconds=sleep_sec,
                    metadata_extra={"backfill_orch_id": orch_id},
                )
                for e in sec_out.get("errors") or []:
                    t = e.get("ticker")
                    if t:
                        retry_tickers.add(str(t).upper())
                _record(
                    "sec",
                    str(sec_out.get("status") or "completed"),
                    ins=int(sec_out.get("success_count") or 0),
                    err=len(sec_out.get("errors") or []),
                    notes={"ingest_run_id": sec_out.get("run_id")},
                )
                stage_results["sec"] = sec_out

        if _in_range(STAGE_ORDER.index("xbrl"), si, ei):
            if dry_run:
                _record("xbrl", "skipped_dry_run")
            else:
                x_out = run_facts_extract_for_tickers(
                    settings,
                    tickers=tickers,
                    client=client,
                    sleep_seconds=sleep_sec,
                    metadata_extra={"backfill_orch_id": orch_id},
                )
                for e in x_out.get("errors") or []:
                    t = e.get("ticker")
                    if t:
                        retry_tickers.add(str(t).upper())
                _record(
                    "xbrl",
                    str(x_out.get("status") or "completed"),
                    ins=int(x_out.get("success_count") or 0),
                    err=len(x_out.get("errors") or []),
                    notes={"ingest_run_id": x_out.get("run_id")},
                )
                stage_results["xbrl"] = x_out

        if _in_range(STAGE_ORDER.index("snapshots"), si, ei):
            if dry_run:
                _record("snapshots", "skipped_dry_run")
            else:
                sn_out = run_quarter_snapshot_build_tickers(
                    settings,
                    tickers=tickers,
                    limit_per_ticker=snap_lim,
                    client=client,
                    sleep_seconds=max(0.05, sleep_sec * 0.3),
                )
                _record(
                    "snapshots",
                    str(sn_out.get("status") or "completed"),
                    ins=int(sn_out.get("success_count") or 0),
                    err=int(sn_out.get("failure_count") or 0),
                )
                stage_results["snapshots"] = sn_out

        if _in_range(STAGE_ORDER.index("factors"), si, ei):
            if dry_run:
                _record("factors", "skipped_dry_run")
            else:
                f_out = run_factor_panels_watchlist(
                    settings,
                    tickers=tickers,
                    sleep_seconds=sleep_sec,
                    factor_version=factor_version,
                    client=client,
                )
                _record(
                    "factors",
                    str(f_out.get("status") or "completed"),
                    ins=int(f_out.get("success_count") or 0),
                    err=int(f_out.get("failure_count") or 0),
                    notes={"ingest_run_id": f_out.get("run_id")},
                )
                stage_results["factors"] = f_out

        if _in_range(STAGE_ORDER.index("market_prices"), si, ei):
            if dry_run:
                _record("market_prices", "skipped_dry_run")
            else:
                m_out = run_market_prices_ingest(
                    settings,
                    universe_name=universe_name,
                    start_date=None,
                    end_date=None,
                    lookback_days=market_lookback_days,
                )
                miss = m_out.get("missing")
                if isinstance(miss, list):
                    miss_err = len(miss)
                elif miss is None:
                    miss_err = 0
                else:
                    miss_err = int(miss)
                _record(
                    "market_prices",
                    str(m_out.get("status") or "completed"),
                    ins=int(m_out.get("symbols_with_data") or 0),
                    err=miss_err,
                    notes={
                        "silver_rows": m_out.get("silver_rows"),
                        "symbols_requested": m_out.get("symbols_requested"),
                    },
                )
                stage_results["market_prices"] = m_out

        if _in_range(STAGE_ORDER.index("forward_returns"), si, ei):
            if dry_run:
                _record("forward_returns", "skipped_dry_run")
            else:
                fw_out = run_forward_returns_build(
                    settings,
                    limit_panels=plim,
                    price_lookahead_days=400,
                )
                _record(
                    "forward_returns",
                    str(fw_out.get("status") or "completed"),
                    ins=int(fw_out.get("success_operations") or 0),
                    err=int(fw_out.get("failures") or 0),
                )
                stage_results["forward_returns"] = fw_out

        if _in_range(STAGE_ORDER.index("validation_panel"), si, ei):
            if dry_run:
                _record("validation_panel", "skipped_dry_run")
            else:
                vp_out = run_validation_panel_build(
                    settings, limit_panels=plim
                )
                _record(
                    "validation_panel",
                    str(vp_out.get("status") or "completed"),
                    ins=int(vp_out.get("rows_upserted") or 0),
                    err=int(vp_out.get("failures") or 0),
                )
                stage_results["validation_panel"] = vp_out

        if _in_range(STAGE_ORDER.index("phase5"), si, ei) and rerun_phase5:
            if dry_run:
                _record("phase5", "skipped_dry_run")
            else:
                p5_notes: dict[str, Any] = {}
                for hz in ("next_month", "next_quarter"):
                    r5 = run_factor_validation_research(
                        client,
                        universe_name=universe_name,
                        horizon_type=hz,
                        factor_version=factor_version,
                        panel_limit=min(plim, 15000),
                    )
                    p5_notes[hz] = {
                        "status": r5.get("status"),
                        "run_id": r5.get("run_id"),
                    }
                _record("phase5", "completed", notes=p5_notes)
                stage_results["phase5"] = p5_notes

        if _in_range(STAGE_ORDER.index("phase6"), si, ei) and rerun_phase6:
            if dry_run:
                _record("phase6", "skipped_dry_run")
            else:
                lim = max(len(tickers) * 3, 200)
                sc = run_state_change(
                    client,
                    universe_name=universe_name,
                    factor_version=factor_version,
                    limit=min(lim, 2000),
                    dry_run=False,
                )
                _record(
                    "phase6",
                    str(sc.get("status") or "completed"),
                    notes=sc,
                )
                stage_results["phase6"] = sc

        summary = {
            "orchestration_run_id": orch_id,
            "tickers": tickers,
            "stage_results_keys": list(stage_results.keys()),
            "retry_tickers_all": sorted(retry_tickers),
            "coverage_stage": coverage_stage,
            "issuer_target": issuer_target,
        }
        checkpoint = build_coverage_checkpoint_report(
            client,
            requested_issuer_target=requested_target
            if coverage_stage
            else symbol_limit,
            resolved_issuer_count=len(tickers),
            coverage_stage=coverage_stage,
        )
        if write_coverage_checkpoint:
            p = Path(write_coverage_checkpoint).expanduser()
            p.write_text(
                json.dumps(checkpoint, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        dbrec.backfill_orch_finalize(
            client,
            run_id=orch_id,
            status="completed",
            summary_json=summary,
        )
        return {
            "status": "completed",
            "orchestration_run_id": orch_id,
            "summary": summary,
            "stage_results": stage_results,
            "coverage_checkpoint": checkpoint,
        }
    except Exception as ex:  # noqa: BLE001
        logger.exception("backfill failed")
        dbrec.backfill_orch_finalize(
            client,
            run_id=orch_id,
            status="failed",
            summary_json={"partial": stage_results},
            error_json={"error": str(ex)},
        )
        return {
            "status": "failed",
            "error": str(ex),
            "orchestration_run_id": orch_id,
            "stage_results": stage_results,
        }
