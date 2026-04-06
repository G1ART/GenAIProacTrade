"""CLI: ingest, facts extract, quarter snapshots, smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from config import ensure_edgar_local_cache, load_settings
from logging_utils import configure_logging

ensure_edgar_local_cache()


def _cmd_ingest_single(args: argparse.Namespace) -> int:
    from sec.ingest_company_sample import run_sample_ingest

    settings = load_settings()
    configure_logging()
    result = run_sample_ingest(args.ticker, settings)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_ingest_watchlist(args: argparse.Namespace) -> int:
    from sec.watchlist_ingest import run_watchlist_ingest

    settings = load_settings()
    configure_logging()
    path: Path | None = None
    if args.watchlist:
        path = Path(args.watchlist).expanduser()
    elif os.getenv("WATCHLIST_PATH"):
        path = Path(os.environ["WATCHLIST_PATH"]).expanduser()
    result = run_watchlist_ingest(
        settings,
        watchlist_path=path,
        sleep_seconds=args.sleep,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") != "failed" else 1


def _cmd_smoke_sec(_args: argparse.Namespace) -> int:
    """SEC에 최소 1회 접속 가능한지 확인 (네트워크 필요)."""
    import sec.ingest_company_sample  # noqa: F401 — 모듈 로드 시 edgar 캐시 부트스트랩

    from edgar import Company, set_identity

    settings = load_settings()
    configure_logging()
    set_identity(settings.edgar_identity)
    c = Company("AAPL")
    out = {"ok": True, "sample_cik": str(getattr(c, "cik", ""))}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def _cmd_smoke_db(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_db_select_one

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_db_select_one(client)
    print(json.dumps({"ok": True, "supabase": "reachable"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_extract_facts_single(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from sec.facts.facts_pipeline import run_facts_extract_for_ticker

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    forms = tuple(args.forms.split(",")) if args.forms else ("10-Q", "10-K")
    out = run_facts_extract_for_ticker(
        client,
        settings,
        args.ticker,
        forms=forms,
        run_validation_hook=True,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_extract_facts_watchlist(args: argparse.Namespace) -> int:
    from sec.facts_watchlist import run_facts_watchlist

    settings = load_settings()
    configure_logging()
    path: Path | None = None
    if args.watchlist:
        path = Path(args.watchlist).expanduser()
    elif os.getenv("WATCHLIST_PATH"):
        path = Path(os.environ["WATCHLIST_PATH"]).expanduser()
    forms = tuple(args.forms.split(",")) if args.forms else ("10-Q", "10-K")
    out = run_facts_watchlist(
        settings,
        watchlist_path=path,
        sleep_seconds=args.sleep,
        forms=forms,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") != "failed" else 1


def _cmd_build_quarter_snapshots(args: argparse.Namespace) -> int:
    from sec.snapshot_build_run import run_quarter_snapshot_build

    settings = load_settings()
    configure_logging()
    out = run_quarter_snapshot_build(
        settings,
        ticker=args.ticker,
        limit=args.limit,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") != "failed" else 1


def _cmd_compute_factors_single(args: argparse.Namespace) -> int:
    from factors.panel_build import run_factor_panels_for_ticker

    settings = load_settings()
    configure_logging()
    fv = args.factor_version or os.environ.get("FACTOR_VERSION", "v1")
    out = run_factor_panels_for_ticker(settings, args.ticker, factor_version=fv)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("ok") else 1


def _cmd_compute_factors_watchlist(args: argparse.Namespace) -> int:
    from pathlib import Path

    from factors.panel_build import run_factor_panels_watchlist
    from watchlist_config import default_watchlist_path, load_watchlist

    settings = load_settings()
    configure_logging()
    path: Path | None = None
    if args.watchlist:
        path = Path(args.watchlist).expanduser()
    elif os.getenv("WATCHLIST_PATH"):
        path = Path(os.environ["WATCHLIST_PATH"]).expanduser()
    tickers, _ = load_watchlist(path)
    fv = args.factor_version or os.environ.get("FACTOR_VERSION", "v1")
    out = run_factor_panels_watchlist(
        settings,
        tickers=tickers,
        sleep_seconds=args.sleep,
        factor_version=fv,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") != "failed" else 1


def _cmd_smoke_factors_phase3(_args: argparse.Namespace) -> int:
    """factor_panels 테이블 + 공식 sanity (네트워크 없음)."""
    from db.client import get_supabase_client
    from db.records import smoke_factor_panels_db
    from factors.formulas import compute_accruals

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_factor_panels_db(client)
    cur = {"net_income": 100.0, "operating_cash_flow": 40.0, "total_assets": 200.0}
    prior = {"total_assets": 100.0}
    val, _cov, _qf = compute_accruals(cur, prior)
    out = {
        "db_factor_panels_table": "ok",
        "formula_sanity_accruals": val,
        "expected_accruals_rough": (100 - 40) / ((200 + 100) / 2),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_show_factor_panel(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import fetch_cik_for_ticker, fetch_factor_panels_for_cik

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    cik = fetch_cik_for_ticker(client, ticker=args.ticker.upper().strip())
    if not cik:
        print(json.dumps({"error": "issuer_not_found"}, indent=2))
        return 1
    rows = fetch_factor_panels_for_cik(client, cik=cik, limit=args.limit)
    print(json.dumps({"cik": cik, "ticker": args.ticker.upper().strip(), "panels": rows}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_refresh_universe(args: argparse.Namespace) -> int:
    from market.run_types import UNIVERSE_SP500_CURRENT
    from market.universe_refresh import run_universe_refresh_sp500

    settings = load_settings()
    configure_logging()
    u = (args.universe or UNIVERSE_SP500_CURRENT).strip()
    if u != UNIVERSE_SP500_CURRENT:
        print(json.dumps({"error": "unsupported_universe", "universe": u}, indent=2))
        return 1
    out = run_universe_refresh_sp500(settings)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_build_candidate_universe(args: argparse.Namespace) -> int:
    from pathlib import Path

    from market.candidate_universe_build import run_build_candidate_universe

    settings = load_settings()
    configure_logging()
    seed = Path(args.seed).expanduser() if args.seed else None
    out = run_build_candidate_universe(settings, seed_path=seed)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_ingest_market_prices(args: argparse.Namespace) -> int:
    from datetime import date

    from market.price_ingest import run_market_prices_ingest

    settings = load_settings()
    configure_logging()
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    out = run_market_prices_ingest(
        settings,
        universe_name=args.universe.strip(),
        start_date=start,
        end_date=end,
        lookback_days=int(args.lookback_days),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_refresh_market_metadata(args: argparse.Namespace) -> int:
    from market.price_ingest import run_market_metadata_refresh

    settings = load_settings()
    configure_logging()
    out = run_market_metadata_refresh(settings, universe_name=args.universe.strip())
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_ingest_risk_free(args: argparse.Namespace) -> int:
    from datetime import date

    from market.risk_free_ingest import run_risk_free_ingest

    settings = load_settings()
    configure_logging()
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    out = run_risk_free_ingest(
        settings,
        start_date=start,
        end_date=end,
        lookback_years=int(args.lookback_years),
        fred_http_timeout_sec=int(args.fred_timeout),
        fred_retries=int(args.fred_retries),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_build_forward_returns(args: argparse.Namespace) -> int:
    from market.forward_returns_run import run_forward_returns_build

    settings = load_settings()
    configure_logging()
    out = run_forward_returns_build(
        settings,
        limit_panels=int(args.limit_panels),
        price_lookahead_days=int(args.price_lookahead_days),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_build_validation_panel(args: argparse.Namespace) -> int:
    from market.validation_panel_run import run_validation_panel_build

    settings = load_settings()
    configure_logging()
    out = run_validation_panel_build(settings, limit_panels=int(args.limit_panels))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_smoke_market(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from market.smoke_market import run_smoke_market

    settings = load_settings()
    configure_logging()
    out = run_smoke_market(settings)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_validation(_args: argparse.Namespace) -> int:
    from market.smoke_market import run_smoke_validation

    settings = load_settings()
    configure_logging()
    out = run_smoke_validation(settings)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_run_factor_validation(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research.validation_runner import run_factor_validation_research

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = run_factor_validation_research(
        client,
        universe_name=str(args.universe),
        horizon_type=str(args.horizon),
        factor_version=str(args.factor_version or "v1"),
        panel_limit=int(args.panel_limit),
        include_ols=bool(args.ols),
        apply_winsorize=bool(args.winsorize),
        n_quantiles=int(args.n_quantiles),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_report_factor_summary(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research.cli_report import print_factor_summary_cli

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    return print_factor_summary_cli(
        client,
        factor_name=str(args.factor),
        universe_name=str(args.universe),
        horizon_type=str(args.horizon),
        return_basis=str(args.return_basis or "raw"),
    )


def _cmd_smoke_research(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_research_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_research_tables(client)
    print(json.dumps({"db_factor_validation_research": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_run_state_change(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.run_logger import OperationalRunSession
    from state_change.runner import run_state_change

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    fv = args.factor_version or os.getenv("FACTOR_VERSION") or "v1"
    with OperationalRunSession(
        client,
        run_type="state_change",
        component="state_change_engine_v1",
        metadata_json={
            "universe": str(args.universe),
            "factor_version": str(fv),
            "dry_run": bool(args.dry_run),
        },
    ) as op:
        out = run_state_change(
            client,
            universe_name=str(args.universe),
            factor_version=str(fv),
            as_of_date=args.as_of_date,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=int(args.limit),
            dry_run=bool(args.dry_run),
            include_nullable_overlays=bool(args.include_nullable_overlays),
        )
        st = str(out.get("status") or "")
        if st == "no_observations":
            op.finish_failed(
                error_class="pipeline",
                error_code="no_observations",
                message=str(out.get("hint") or out.get("message") or "no_observations"),
                failure_category="source_data_missing",
            )
        elif st == "dry_run":
            op.finish_success(
                rows_read=int(out.get("scores") or 0),
                rows_written=0,
                warnings_count=int(out.get("warnings") or 0),
                trace_json={
                    "dry_run": True,
                    "components": out.get("components"),
                    "scores": out.get("scores"),
                    "candidates": out.get("candidates"),
                },
            )
        elif st == "completed":
            op.finish_success(
                rows_read=int(out.get("scores_written") or 0),
                rows_written=int(out.get("components_written") or 0)
                + int(out.get("scores_written") or 0)
                + int(out.get("candidates_written") or 0),
                warnings_count=int(out.get("warnings") or 0),
                trace_json={"state_change_run_id": out.get("run_id")},
            )
        else:
            op.finish_warning(
                rows_read=None,
                rows_written=None,
                message=f"unexpected_status={st}",
                trace_json={"out": out},
            )
    if args.output_json:
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    else:
        print(
            "status={} run_id={} components={} scores={} candidates={} warnings={}".format(
                out.get("status"),
                out.get("run_id"),
                out.get("components_written", out.get("components", "?")),
                out.get("scores_written", out.get("scores", "?")),
                out.get("candidates_written", out.get("candidates", "?")),
                out.get("warnings"),
            )
        )
        if out.get("hint"):
            print("hint:", out.get("hint"), file=sys.stderr)
    st = str(out.get("status") or "")
    if st == "failed":
        return 1
    return 0


def _cmd_report_state_change_summary(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from state_change.cli_report import emit_state_change_summary
    from state_change.reports import build_state_change_run_report, resolve_report_run_id

    if not args.run_id and not args.universe:
        print("오류: --run-id 또는 --universe 중 하나를 지정하세요.", file=sys.stderr)
        return 1
    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = resolve_report_run_id(
        client, universe_name=args.universe, run_id=args.run_id
    )
    if not rid:
        payload = {
            "ok": False,
            "error": "no_completed_run_found",
            "hint": (
                "해당 universe에 status=completed 인 state_change_runs 가 없습니다. "
                "run-state-change 가 observations=0 으로 끝나면 run 행이 생기지 않습니다. "
                "issuer_quarter_factor_panels 를 채운 뒤 run-state-change 를 다시 실행하거나, "
                "이미 있는 run 이 있다면 --run-id 로 지정하세요."
            ),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(payload["hint"], file=sys.stderr)
        return 1
    payload = build_state_change_run_report(
        client,
        run_id=rid,
        scores_limit=int(args.scores_limit),
        candidates_limit=int(args.candidates_limit),
    )
    emit_state_change_summary(payload, output_json=bool(args.output_json))
    return 0 if payload.get("ok") else 1


def _cmd_smoke_state_change(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_state_change_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_state_change_tables(client)
    print(json.dumps({"db_state_change_phase6": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_smoke_backfill(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_backfill_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_backfill_tables(client)
    print(json.dumps({"db_backfill_orchestration": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_backfill_universe(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from backfill.backfill_runner import run_backfill_universe

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    fv = args.factor_version or os.environ.get("FACTOR_VERSION", "v1")
    out = run_backfill_universe(
        settings,
        client,
        mode=str(args.mode),
        universe_name=str(args.universe),
        symbol_limit=args.symbol_limit,
        start_stage=args.start_stage,
        end_stage=args.end_stage,
        dry_run=bool(args.dry_run),
        retry_failed_only=bool(args.retry_failed_only),
        from_orchestration_run_id=args.from_orchestration_run_id,
        rerun_phase5=bool(args.rerun_phase5),
        rerun_phase6=bool(args.rerun_phase6),
        sleep_sec=float(args.sleep),
        factor_version=str(fv),
        market_lookback_days=int(args.market_lookback_days),
        coverage_stage=args.coverage_stage,
        issuer_target=args.issuer_target,
        write_coverage_checkpoint=args.write_coverage_checkpoint,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "completed" else 1


def _cmd_report_backfill_status(args: argparse.Namespace) -> int:
    from pathlib import Path

    from backfill.cli_report import emit_backfill_report
    from backfill.status_report import build_backfill_status_payload
    from db.client import get_supabase_client

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    include_sparse = bool(args.include_sparse_diagnostics) or bool(
        args.write_sparse_diagnostics
    )
    payload = build_backfill_status_payload(
        client,
        mode=str(args.mode),
        universe_name=str(args.universe),
        symbol_limit=args.symbol_limit,
        include_diagnostics=not args.no_diagnostics,
        thin_threshold=int(args.thin_threshold),
        orchestration_run_id=args.orchestration_run_id,
        coverage_stage=args.coverage_stage,
        issuer_target=args.issuer_target,
        include_coverage_checkpoint=bool(args.include_coverage_checkpoint),
        include_sparse_diagnostics=include_sparse,
    )
    if args.write_diagnostics:
        p = Path(args.write_diagnostics).expanduser()
        diag = payload.get("join_diagnostics") or {}
        p.write_text(
            json.dumps(diag, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    if args.write_sparse_diagnostics:
        p2 = Path(args.write_sparse_diagnostics).expanduser()
        sp = payload.get("sparse_issuer_diagnostics") or {}
        p2.write_text(
            json.dumps(sp, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    emit_backfill_report(payload, output_json=bool(args.output_json))
    return 0


def _cmd_smoke_harness(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_harness_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_harness_tables(client)
    print(json.dumps({"phase7_harness_tables": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_build_ai_harness_inputs(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from harness.input_materializer import materialize_inputs_for_run

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = args.run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=args.universe
    )
    if not rid:
        print(
            json.dumps(
                {"error": "no_completed_state_change_run", "universe": args.universe},
                ensure_ascii=False,
            )
        )
        return 1
    out = materialize_inputs_for_run(client, run_id=rid, limit=int(args.limit))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_generate_investigation_memos(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from harness.run_batch import generate_memos_for_run
    from observability.run_logger import OperationalRunSession

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = args.run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=args.universe
    )
    if not rid:
        print(
            json.dumps(
                {"error": "no_completed_state_change_run", "universe": args.universe},
                ensure_ascii=False,
            )
        )
        return 1
    cfilter: set[str] | None = None
    if getattr(args, "candidate_ids", None):
        cfilter = {x.strip() for x in str(args.candidate_ids).split(",") if x.strip()}
    with OperationalRunSession(
        client,
        run_type="ai_harness",
        component="investigation_memo_batch",
        metadata_json={"state_change_run_id": rid, "universe": args.universe},
        linked_external_id=rid,
    ) as op:
        out = generate_memos_for_run(
            client,
            run_id=rid,
            limit=int(args.limit),
            force_new_memo_version=bool(args.force_new_memo_version),
            candidate_ids=cfilter,
        )
        ins = int(out.get("memos_inserted_new_version") or 0)
        rep = int(out.get("memos_replaced_in_place") or 0)
        errs = out.get("errors") or []
        n_err = len(errs)
        if n_err and ins + rep == 0:
            op.finish_failed(
                error_class="memo_pipeline",
                error_code="all_candidates_failed",
                message=str(errs[0].get("error") if errs else "errors")[:2000],
                failure_category="execution_error",
            )
        elif n_err:
            op.finish_warning(
                rows_read=ins + rep + n_err,
                rows_written=ins + rep,
                message=f"{n_err} memo candidate errors (see trace)",
                trace_json={"errors_sample": errs[:5], **out},
            )
        elif ins + rep == 0:
            op.finish_empty_valid(
                rows_read=0,
                trace_json={**out, "note": "no_inputs_or_all_filtered"},
            )
        else:
            op.finish_success(
                rows_read=ins + rep,
                rows_written=ins + rep,
                warnings_count=0,
                trace_json=out,
            )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    ins2 = int(out.get("memos_inserted_new_version") or 0)
    rep2 = int(out.get("memos_replaced_in_place") or 0)
    if out.get("errors") and ins2 + rep2 == 0:
        return 1
    return 0


def _cmd_set_review_queue_status(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from harness.rerun_policy import assert_valid_queue_transition

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    cid = str(args.candidate_id)
    existing = dbrec.fetch_operator_review_queue_row(client, candidate_id=cid)
    assert_valid_queue_transition(
        existing.get("status") if existing else None, str(args.status)
    )
    dbrec.update_operator_review_queue_status(
        client,
        candidate_id=cid,
        status=str(args.status),
        status_reason=args.reason,
    )
    row = dbrec.fetch_operator_review_queue_row(client, candidate_id=cid)
    print(json.dumps({"ok": True, "row": row}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_export_phase7_evidence_bundle(args: argparse.Namespace) -> int:
    from pathlib import Path

    from db.client import get_supabase_client
    from db import records as dbrec
    from harness.run_batch import generate_memos_for_run

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)

    ids: list[str] = []
    if args.candidate_ids:
        ids = [x.strip() for x in args.candidate_ids.split(",") if x.strip()]
    elif args.from_run:
        r = (
            client.table("state_change_candidates")
            .select("id")
            .eq("run_id", str(args.from_run))
            .limit(int(args.sample_n))
            .execute()
        )
        ids = [str(x["id"]) for x in (r.data or [])]
    if len(ids) < 1:
        if args.from_run and not args.candidate_ids:
            print(
                json.dumps(
                    {
                        "error": "from_run_returned_zero_candidates",
                        "run_id_used": str(args.from_run),
                        "hint": "This UUID must be state_change_runs.id (not a git SHA). "
                        "Confirm rows: select count(*) from state_change_candidates "
                        "where run_id = '<id>';",
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(
                json.dumps(
                    {
                        "error": "no_candidate_ids",
                        "hint": "Pass --candidate-ids uuid,uuid or --from-run <state_change_runs.id>",
                    },
                    ensure_ascii=False,
                )
            )
        return 1

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []

    for cid in ids:
        cand = dbrec.fetch_state_change_candidate(client, candidate_id=cid)
        if not cand:
            manifest.append({"candidate_id": cid, "error": "candidate_not_found"})
            continue
        run_id = str(cand["run_id"])
        sub = out_dir / cid
        sub.mkdir(parents=True, exist_ok=True)
        inp = dbrec.fetch_ai_harness_input_for_candidate(
            client, candidate_id=cid, contract_version="ai_harness_input_v1"
        )
        (sub / "state_change_candidate.json").write_text(
            json.dumps(cand, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        (sub / "ai_harness_input.json").write_text(
            json.dumps(inp or {}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        g1 = generate_memos_for_run(
            client,
            run_id=run_id,
            limit=2000,
            candidate_ids={cid},
            force_new_memo_version=False,
        )
        g2 = generate_memos_for_run(
            client,
            run_id=run_id,
            limit=2000,
            candidate_ids={cid},
            force_new_memo_version=False,
        )
        (sub / "rerun_generate_summary.json").write_text(
            json.dumps({"first": g1, "second": g2}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        memo = dbrec.fetch_latest_memo_for_candidate(client, candidate_id=cid)
        qrow = dbrec.fetch_operator_review_queue_row(client, candidate_id=cid)
        claims: list[dict[str, object]] = []
        if memo:
            claims = dbrec.fetch_investigation_memo_claims(
                client, memo_id=str(memo["id"])
            )
        (sub / "investigation_memo.json").write_text(
            json.dumps(memo or {}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        (sub / "investigation_memo_claims.json").write_text(
            json.dumps(claims, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        (sub / "operator_review_queue.json").write_text(
            json.dumps(qrow or {}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        pj = (inp or {}).get("payload_json") if isinstance(inp, dict) else None
        ticker_hint = pj.get("ticker") if isinstance(pj, dict) else None
        manifest.append(
            {
                "candidate_id": cid,
                "run_id": run_id,
                "ticker_hint": ticker_hint,
                "memo_id": (memo or {}).get("id"),
                "referee_passed": (memo or {}).get("referee_passed"),
                "claims_count": len(claims),
            }
        )

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({"out_dir": str(out_dir), "manifest": manifest}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_review_queue(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import fetch_operator_review_queue

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rows = fetch_operator_review_queue(
        client, status=args.status, limit=int(args.limit)
    )
    print(json.dumps({"count": len(rows), "items": rows}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_phase8(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_phase8_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase8_tables(client)
    print(json.dumps({"phase8_tables": "ok"}, indent=2, ensure_ascii=False))
    return 0


def _cmd_build_outlier_casebook(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from casebook.build_run import run_outlier_casebook_build
    from observability.run_logger import OperationalRunSession

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = args.run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=args.universe
    )
    if not rid:
        print(
            json.dumps(
                {"error": "no_completed_state_change_run", "universe": args.universe},
                ensure_ascii=False,
            )
        )
        return 1
    with OperationalRunSession(
        client,
        run_type="outlier_casebook",
        component="casebook_build_v1",
        metadata_json={
            "universe": args.universe,
            "state_change_run_id": rid,
            "candidate_limit": int(args.candidate_limit),
        },
        linked_external_id=rid,
    ) as op:
        out = run_outlier_casebook_build(
            client,
            state_change_run_id=rid,
            universe_name=args.universe,
            candidate_limit=int(args.candidate_limit),
        )
        if out.get("error") == "state_change_run_not_found":
            op.finish_failed(
                error_class="input",
                error_code="state_change_run_not_found",
                message=str(out.get("run_id") or ""),
                failure_category="configuration_error",
            )
        else:
            ec = int(out.get("entries_created") or 0)
            scanned = int(out.get("candidates_scanned") or 0)
            errs = out.get("errors") or []
            crid = str(out.get("casebook_run_id") or "")
            trace = {**out, "heuristic_marked_in_entries": True}
            if ec == 0 and not errs:
                op.finish_empty_valid(rows_read=scanned, trace_json=trace)
            elif errs and ec == 0:
                op.finish_failed(
                    error_class="casebook",
                    error_code="all_candidates_errored",
                    message=str(errs[0])[:2000],
                    failure_category="execution_error",
                )
            elif errs:
                op.finish_warning(
                    rows_read=scanned,
                    rows_written=ec,
                    message=f"{len(errs)} candidate errors during casebook scan",
                    trace_json=trace,
                )
            else:
                op.finish_success(
                    rows_read=scanned,
                    rows_written=ec,
                    warnings_count=0,
                    trace_json=trace,
                )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    if out.get("error"):
        return 1
    errs = out.get("errors") or []
    if errs and int(out.get("entries_created") or 0) == 0:
        return 1
    return 0


def _cmd_build_daily_signal_snapshot(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from observability.run_logger import OperationalRunSession
    from scanner.daily_build import run_daily_scanner_build

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    rid = args.run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=args.universe
    )
    if not rid:
        print(
            json.dumps(
                {"error": "no_completed_state_change_run", "universe": args.universe},
                ensure_ascii=False,
            )
        )
        return 1
    with OperationalRunSession(
        client,
        run_type="daily_scanner",
        component="scanner_daily_build_v1",
        metadata_json={
            "universe": args.universe,
            "state_change_run_id": rid,
            "as_of_calendar_date": args.as_of_date,
        },
        linked_external_id=rid,
    ) as op:
        out = run_daily_scanner_build(
            client,
            state_change_run_id=rid,
            universe_name=args.universe,
            as_of_calendar_date=args.as_of_date,
            candidate_scan_limit=int(args.candidate_limit),
            top_n=int(args.top_n),
            min_priority_score=float(args.min_priority_score),
            max_candidate_rank=int(args.max_candidate_rank),
        )
        wl = int(out.get("watchlist_entries") or 0)
        stats = out.get("stats") or {}
        scanned = int(stats.get("candidates_scanned") or 0)
        sid = str(out.get("scanner_run_id") or "")
        trace = {
            **out,
            "watchlist_empty_allowed": True,
            "message_layer_heuristic": True,
        }
        if wl == 0:
            op.finish_empty_valid(
                rows_read=scanned,
                trace_json=trace,
            )
        else:
            op.finish_success(
                rows_read=scanned,
                rows_written=wl + 1,
                trace_json=trace,
            )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_daily_watchlist(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    sid = args.scanner_run_id
    if not sid:
        latest = dbrec.fetch_latest_scanner_run(
            client, universe_name=args.universe or None
        )
        if not latest:
            print(json.dumps({"error": "no_scanner_runs"}, ensure_ascii=False))
            return 1
        sid = str(latest["id"])
    run_row = dbrec.fetch_scanner_run(client, scanner_run_id=sid)
    snap = dbrec.fetch_daily_snapshot_for_scanner(client, scanner_run_id=sid)
    wl = dbrec.fetch_watchlist_for_scanner(client, scanner_run_id=sid, limit=200)
    print(
        json.dumps(
            {
                "scanner_run_id": sid,
                "scanner_run": run_row,
                "daily_signal_snapshot": snap,
                "watchlist": wl,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


def _cmd_export_casebook_samples(args: argparse.Namespace) -> int:
    from pathlib import Path

    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    crid = args.casebook_run_id
    state_change_run_id = args.state_change_run_id
    if not crid and not state_change_run_id and getattr(args, "universe", None):
        state_change_run_id = dbrec.fetch_latest_state_change_run_id(
            client, universe_name=str(args.universe)
        )
    if not crid and state_change_run_id:
        r = (
            client.table("outlier_casebook_runs")
            .select("id")
            .eq("state_change_run_id", str(state_change_run_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if r.data:
            crid = str(r.data[0]["id"])
    if not crid:
        print(
            json.dumps(
                {
                    "error": "no_casebook_run",
                    "hint": (
                        "--casebook-run-id or --state-change-run-id or "
                        "--universe (최신 completed state_change → 최신 casebook)"
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 1
    rows = dbrec.fetch_outlier_casebook_entries_for_run(
        client, casebook_run_id=crid, limit=int(args.limit)
    )
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "casebook_run_id.txt").write_text(crid, encoding="utf-8")
    (out_dir / "entries.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    manifest = [
        {
            "entry_id": x.get("id"),
            "candidate_id": x.get("candidate_id"),
            "outlier_type": x.get("outlier_type"),
            "ticker": x.get("ticker"),
        }
        for x in rows[: int(args.limit)]
    ]
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({"out_dir": str(out_dir), "count": len(rows), "manifest": manifest}, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_phase9_observability(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db.records import smoke_phase9_observability_tables

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_phase9_observability_tables(client)
    print(
        json.dumps(
            {"phase9_observability_tables": "ok", "operational_runs": "reachable"},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_report_run_health(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.reporting import build_run_health_payload

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = build_run_health_payload(client, limit=int(args.limit))
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_failures(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.reporting import build_failures_payload

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = build_failures_payload(client, limit=int(args.limit))
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_research_registry(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research_registry.reporting import format_registry_report

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = format_registry_report(client, limit=int(args.limit))
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_seed_phase9_research_samples(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from research_registry.registry import ensure_sample_hypotheses

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = ensure_sample_hypotheses(client)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_seed_source_registry(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from sources.registry import seed_registry_from_constants

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = seed_registry_from_constants(client)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_source_registry(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from sources.reporting import build_source_registry_report

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = build_source_registry_report(client)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_report_overlay_gap(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec
    from sources.reporting import build_overlay_gap_report

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    payload = build_overlay_gap_report(client)
    if getattr(args, "persist", False):
        rid = dbrec.insert_source_overlay_gap_report(client, payload_json=payload)
        payload = {**payload, "persisted_gap_report_id": rid}
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_source_adapters(_args: argparse.Namespace) -> int:
    from sources.contracts import validate_probe_result
    from sources.estimates_adapter import EstimatesAdapter
    from sources.price_quality_adapter import PriceQualityAdapter
    from sources.transcripts_adapter import TranscriptsAdapter

    probes = [
        TranscriptsAdapter().probe(),
        EstimatesAdapter().probe(),
        PriceQualityAdapter().probe(),
    ]
    for p in probes:
        validate_probe_result(p)
    out = {
        "adapter_smoke": "ok",
        "probes": [
            {
                "adapter_name": p.adapter_name,
                "availability": p.availability,
                "normalization_schema_version": p.normalization_schema_version,
                "failure_behavior": p.failure_behavior,
                "rights_source_id": p.rights.source_id if p.rights else None,
            }
            for p in probes
        ],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_export_source_roi_matrix(_args: argparse.Namespace) -> int:
    from sources.reporting import OVERLAY_ROI_RANKED

    print(json.dumps(OVERLAY_ROI_RANKED, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_probe_transcripts_provider(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.run_logger import OperationalRunSession
    from sources import transcripts_provider_binding as bind
    from sources.transcripts_ingest import run_fmp_probe_and_update_overlay

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    with OperationalRunSession(
        client,
        run_type="transcript_overlay",
        component="fmp_transcript_probe",
        metadata_json={"cli": "probe-transcripts-provider"},
    ) as op:
        try:
            out = run_fmp_probe_and_update_overlay(
                client, settings, operational_run_id=op.operational_run_id
            )
        except Exception as e:
            op.finish_failed(
                error_class="execution_error",
                error_code="probe_exception",
                message=str(e),
                failure_category="execution_error",
            )
            print(json.dumps({"ok": False, "error": str(e), "probe": None}, indent=2))
            return 1
        ps = out.get("probe_status")
        if ps == bind.NOT_CONFIGURED:
            op.finish_failed(
                error_class="configuration_error",
                error_code=str(out.get("detail") or "not_configured"),
                message="Transcript provider not configured for FMP probe",
                failure_category="configuration_error",
            )
            print(json.dumps({"ok": True, "truthful_blocked": True, "probe": out}, indent=2))
            return 1
        if ps == bind.FAILED_RIGHTS_OR_AUTH:
            op.finish_failed(
                error_class="auth_or_rights",
                error_code="fmp_http_auth_or_subscription",
                message="FMP returned auth/subscription/rights failure",
                failure_category="other",
            )
            print(json.dumps({"ok": False, "probe": out}, indent=2))
            return 1
        if ps == bind.FAILED_NETWORK:
            op.finish_failed(
                error_class="network_error",
                error_code="fmp_network",
                message=str(out.get("detail") or "network"),
                failure_category="other",
            )
            print(json.dumps({"ok": False, "probe": out}, indent=2))
            return 1
        if ps == bind.CONFIGURED_BUT_UNVERIFIED:
            op.finish_warning(
                rows_read=1,
                rows_written=1,
                message="unexpected_response_shape",
                trace_json={"probe": out},
            )
            print(json.dumps({"ok": True, "probe": out}, indent=2))
            return 0
        if ps == bind.PARTIAL:
            op.finish_warning(
                rows_read=1,
                rows_written=1,
                message="partial_transcript_probe",
                trace_json={"probe": out},
            )
            print(json.dumps({"ok": True, "probe": out}, indent=2))
            return 0
        op.finish_success(
            rows_read=1,
            rows_written=1,
            trace_json={"probe": out},
        )
        print(json.dumps({"ok": True, "probe": out}, indent=2))
        return 0


def _cmd_ingest_transcripts_sample(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from observability.run_logger import OperationalRunSession
    from sources import transcripts_provider_binding as bind
    from sources.transcripts_ingest import run_fmp_sample_ingest

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    with OperationalRunSession(
        client,
        run_type="transcript_overlay",
        component="fmp_transcript_ingest_sample",
        metadata_json={
            "cli": "ingest-transcripts-sample",
            "symbol": args.symbol,
            "year": args.year,
            "quarter": args.quarter,
        },
    ) as op:
        if not bind.fmp_api_key_present(settings):
            op.finish_failed(
                error_class="configuration_error",
                error_code="FMP_API_KEY_missing",
                message="ingest blocked: FMP_API_KEY not configured",
                failure_category="configuration_error",
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "truthful_blocked": True,
                        "error": "FMP_API_KEY_not_configured",
                        "operational_run_id": op.operational_run_id,
                    },
                    indent=2,
                )
            )
            return 1
        try:
            out = run_fmp_sample_ingest(
                client,
                settings,
                symbol=args.symbol,
                year=int(args.year),
                quarter=int(args.quarter),
                operational_run_id=op.operational_run_id,
            )
        except Exception as e:
            op.finish_failed(
                error_class="execution_error",
                error_code="ingest_exception",
                message=str(e),
                failure_category="execution_error",
            )
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
            return 1
        if out.get("classify") == bind.FAILED_RIGHTS_OR_AUTH:
            op.finish_failed(
                error_class="auth_or_rights",
                error_code="fmp_ingest_auth",
                message="ingest_http_auth_or_rights",
                failure_category="other",
            )
            print(json.dumps({"ok": False, "ingest": out}, indent=2))
            return 1
        if out.get("overlay_availability") == "available" and out.get(
            "normalization_status"
        ) == "ok":
            op.finish_success(rows_read=1, rows_written=2, trace_json={"ingest": out})
        else:
            op.finish_warning(
                rows_read=1,
                rows_written=2,
                message="partial_or_empty_transcript_ingest",
                trace_json={"ingest": out},
            )
        print(json.dumps({"ok": True, "ingest": out}, indent=2))
        return 0


def _cmd_report_transcripts_overlay_status(_args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from sources.transcripts_ingest import report_transcripts_overlay_status

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    print(json.dumps(report_transcripts_overlay_status(client), indent=2, default=str))
    return 0


def _cmd_export_transcript_normalization_sample(args: argparse.Namespace) -> int:
    from db.client import get_supabase_client
    from db import records as dbrec

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    t = args.ticker.upper().strip()
    row = dbrec.fetch_latest_normalized_transcript_for_ticker(client, ticker=t)
    if not row:
        print(json.dumps({"ok": False, "error": "no_row", "ticker": t}, indent=2))
        return 1
    redacted = {k: v for k, v in row.items() if k != "transcript_text"}
    redacted["transcript_text_len"] = len(str(row.get("transcript_text") or ""))
    redacted["transcript_text_prefix_120"] = str(row.get("transcript_text") or "")[:120]
    print(json.dumps({"ok": True, "row": redacted}, indent=2, default=str))
    return 0


def _cmd_run_public_core_cycle(args: argparse.Namespace) -> int:
    from pathlib import Path

    from db.client import get_supabase_client
    from observability.run_logger import OperationalRunSession
    from public_core.cycle import default_cycle_out_dir, run_public_core_cycle

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    out = Path(args.out_dir).expanduser() if args.out_dir else None
    with OperationalRunSession(
        client,
        run_type="public_core_cycle",
        component="run_public_core_cycle_v1",
        metadata_json={
            "cli": "run-public-core-cycle",
            "universe": args.universe,
            "ensure_state_change": bool(args.ensure_state_change),
        },
    ) as op:
        try:
            payload = run_public_core_cycle(
                client,
                settings,
                universe=str(args.universe),
                state_change_run_id=args.state_change_run_id,
                ensure_state_change=bool(args.ensure_state_change),
                factor_version=str(args.factor_version or "v1"),
                state_change_limit=int(args.state_change_limit),
                harness_limit=int(args.harness_limit),
                memo_limit=int(args.memo_limit),
                casebook_candidate_limit=int(args.casebook_candidate_limit),
                scanner_candidate_limit=int(args.scanner_candidate_limit),
                scanner_top_n=int(args.scanner_top_n),
                min_priority_score=float(args.min_priority_score),
                max_candidate_rank=int(args.max_candidate_rank),
                as_of_calendar_date=args.as_of_date,
                out_dir=out,
            )
        except Exception as e:
            op.finish_failed(
                error_class="execution_error",
                error_code="public_core_cycle_exception",
                message=str(e),
                failure_category="execution_error",
            )
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
            return 1
        if not payload.get("ok"):
            op.finish_failed(
                error_class="pipeline",
                error_code=str(payload.get("error") or "cycle_not_ok"),
                message=str(payload.get("hint") or payload.get("error") or "")[:2000],
                failure_category="configuration_error",
            )
        else:
            n_warn = len(payload.get("warnings") or [])
            wl = 0
            for s in payload.get("stages") or []:
                if s.get("name") == "scanner_watchlist" and isinstance(s.get("out"), dict):
                    wl = int((s["out"] or {}).get("watchlist_entries") or 0)
            op.finish_success(
                rows_read=len(payload.get("stages") or []),
                rows_written=max(1, wl + 1),
                warnings_count=n_warn,
                trace_json={
                    "state_change_run_id": payload.get("state_change_run_id"),
                    "out_dir": str(out or default_cycle_out_dir()),
                },
            )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0 if payload.get("ok") else 1


def _cmd_report_public_core_cycle(args: argparse.Namespace) -> int:
    from pathlib import Path

    from public_core.cycle import default_cycle_out_dir, load_latest_cycle_summary

    base = Path(args.out_dir).expanduser() if args.out_dir else default_cycle_out_dir()
    summary = load_latest_cycle_summary(base=base)
    if not summary:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "no_cycle_summary",
                    "hint": f"Run run-public-core-cycle first (writes {base / 'cycle_summary.json'})",
                },
                indent=2,
            )
        )
        return 1
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_smoke_facts(_args: argparse.Namespace) -> int:
    """DB facts 테이블 도달 + (선택) 단일 티커 XBRL 로드 가능 여부."""
    import sec.ingest_company_sample  # noqa: F401

    from db.client import get_supabase_client
    from db.records import smoke_facts_db
    from sec.facts.extract_facts import extract_facts_for_ticker

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    smoke_facts_db(client)
    ex = extract_facts_for_ticker("AAPL", settings.edgar_identity)
    out = {
        "db_facts_table": "ok",
        "xbrl_probe": {
            "ok": ex.get("ok"),
            "raw_fact_count": ex.get("raw_fact_count"),
            "accession_no": ex.get("accession_no"),
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if ex.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GenAIProacTrade SEC / XBRL worker CLI")
    sub = p.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("ingest-single", help="단일 티커 최근 공시 ingest")
    p1.add_argument("--ticker", required=True, help="예: NVDA")
    p1.set_defaults(func=_cmd_ingest_single)

    p2 = sub.add_parser("ingest-watchlist", help="config/watchlist.json 기반 배치 ingest")
    p2.add_argument(
        "--watchlist",
        default=None,
        help="JSON 경로 (기본: 프로젝트 config/watchlist.json 또는 WATCHLIST_PATH)",
    )
    p2.add_argument(
        "--sleep",
        type=float,
        default=float(os.getenv("INGEST_TICKER_SLEEP_SEC", "0.65")),
        help="티커 간 대기 초 (rate limit)",
    )
    p2.set_defaults(func=_cmd_ingest_watchlist)

    p3 = sub.add_parser("smoke-sec", help="edgartools + SEC 연결 스모크")
    p3.set_defaults(func=_cmd_smoke_sec)

    p4 = sub.add_parser("smoke-db", help="Supabase 연결 스모크")
    p4.set_defaults(func=_cmd_smoke_db)

    p5 = sub.add_parser("extract-facts-single", help="단일 티커 최근 10-Q/10-K XBRL facts 추출·적재")
    p5.add_argument("--ticker", required=True)
    p5.add_argument(
        "--forms",
        default=None,
        help="쉼표 구분, 예: 10-Q,10-K (기본: 10-Q,10-K)",
    )
    p5.set_defaults(func=_cmd_extract_facts_single)

    p6 = sub.add_parser("extract-facts-watchlist", help="워치리스트 티커별 facts 추출·적재")
    p6.add_argument("--watchlist", default=None)
    p6.add_argument(
        "--sleep",
        type=float,
        default=float(os.getenv("INGEST_TICKER_SLEEP_SEC", "0.65")),
    )
    p6.add_argument("--forms", default=None, help="쉼표 구분 form 목록")
    p6.set_defaults(func=_cmd_extract_facts_watchlist)

    p7 = sub.add_parser(
        "build-quarter-snapshots",
        help="DB silver_xbrl_facts 기준 분기 스냅샷 재계산",
    )
    p7.add_argument("--ticker", default=None, help="issuer_master 티커로 CIK 한정")
    p7.add_argument("--limit", type=int, default=20, help="처리할 고유 (cik, accession) 상한")
    p7.set_defaults(func=_cmd_build_quarter_snapshots)

    p8 = sub.add_parser("smoke-facts", help="facts 테이블 + SEC XBRL 프로브 (네트워크)")
    p8.set_defaults(func=_cmd_smoke_facts)

    p9 = sub.add_parser("compute-factors-single", help="단일 티커 스냅샷 → factor panel 적재")
    p9.add_argument("--ticker", required=True)
    p9.add_argument(
        "--factor-version",
        default=None,
        help="기본 v1 또는 환경변수 FACTOR_VERSION",
    )
    p9.set_defaults(func=_cmd_compute_factors_single)

    p10 = sub.add_parser("compute-factors-watchlist", help="워치리스트 티커별 factor panel 적재")
    p10.add_argument(
        "--watchlist",
        default=None,
        help="tickers가 든 JSON 경로. 생략 시 WATCHLIST_PATH, 둘 다 없으면 config/watchlist.json",
    )
    p10.add_argument(
        "--sleep",
        type=float,
        default=float(os.getenv("INGEST_TICKER_SLEEP_SEC", "0.65")),
    )
    p10.add_argument("--factor-version", default=None)
    p10.set_defaults(func=_cmd_compute_factors_watchlist)

    p11 = sub.add_parser(
        "smoke-factors",
        help="issuer_quarter_factor_panels 테이블 + accruals 공식 sanity (DB 필요)",
    )
    p11.set_defaults(func=_cmd_smoke_factors_phase3)

    p12 = sub.add_parser("show-factor-panel", help="티커별 최근 factor panel 조회")
    p12.add_argument("--ticker", required=True)
    p12.add_argument("--limit", type=int, default=5)
    p12.set_defaults(func=_cmd_show_factor_panel)

    pu = sub.add_parser(
        "refresh-universe",
        help="S&P 500 current → universe_memberships (네트워크: 위키/프로바이더)",
    )
    pu.add_argument(
        "--universe",
        default="sp500_current",
        help="현재는 sp500_current 만 지원",
    )
    pu.set_defaults(func=_cmd_refresh_universe)

    pc = sub.add_parser(
        "build-candidate-universe",
        help="sp500_proxy_candidates_v1 시드 기반 후보 유니버스 (공식 후보 아님)",
    )
    pc.add_argument(
        "--seed",
        default=None,
        help="JSON 시드 경로 (기본: config/sp500_proxy_candidates_v1.json)",
    )
    pc.set_defaults(func=_cmd_build_candidate_universe)

    pp = sub.add_parser(
        "ingest-market-prices",
        help="유니버스 심볼 일봉 → raw/silver (프로바이더 네트워크)",
    )
    pp.add_argument(
        "--universe",
        required=True,
        help="sp500_current | sp500_proxy_candidates_v1",
    )
    pp.add_argument("--start", default=None, help="YYYY-MM-DD (선택)")
    pp.add_argument("--end", default=None, help="YYYY-MM-DD (선택)")
    pp.add_argument(
        "--lookback-days",
        type=int,
        default=int(os.getenv("MARKET_PRICE_LOOKBACK_DAYS", "400")),
    )
    pp.set_defaults(func=_cmd_ingest_market_prices)

    pm = sub.add_parser(
        "refresh-market-metadata",
        help="프로바이더 메타(있을 때만) → market_metadata_latest",
    )
    pm.add_argument("--universe", required=True)
    pm.set_defaults(func=_cmd_refresh_market_metadata)

    pr = sub.add_parser(
        "ingest-risk-free",
        help="FRED DTB3 CSV → risk_free_rates_daily (네트워크)",
    )
    pr.add_argument("--start", default=None, help="YYYY-MM-DD")
    pr.add_argument("--end", default=None, help="YYYY-MM-DD")
    pr.add_argument("--lookback-years", type=int, default=3)
    pr.add_argument(
        "--fred-timeout",
        type=int,
        default=240,
        help="FRED CSV httpx read 타임아웃(초). 느린 네트워크면 300~600",
    )
    pr.add_argument(
        "--fred-retries",
        type=int,
        default=3,
        help="FRED 다운로드 실패 시 재시도 횟수",
    )
    pr.set_defaults(func=_cmd_ingest_risk_free)

    pf = sub.add_parser(
        "build-forward-returns",
        help="factor panels + silver 가격 + 무위험 → forward_returns_daily_horizons",
    )
    pf.add_argument("--limit-panels", type=int, default=2000)
    pf.add_argument("--price-lookahead-days", type=int, default=400)
    pf.set_defaults(func=_cmd_build_forward_returns)

    pv = sub.add_parser(
        "build-validation-panel",
        help="factor + forward + 메타 → factor_market_validation_panels",
    )
    pv.add_argument("--limit-panels", type=int, default=2000)
    pv.set_defaults(func=_cmd_build_validation_panel)

    sm = sub.add_parser(
        "smoke-market",
        help="Phase 4 시장 테이블 + 스텁 프로바이더 형태 (DB 필요)",
    )
    sm.set_defaults(func=_cmd_smoke_market)

    sv = sub.add_parser("smoke-validation", help="validation 패널 테이블 도달 (DB 필요)")
    sv.set_defaults(func=_cmd_smoke_validation)

    prv = sub.add_parser(
        "run-factor-validation",
        help="Phase 5: factor_market_validation_panels 기반 기술 검증 적재 (연구용)",
    )
    prv.add_argument(
        "--universe",
        required=True,
        help="sp500_current | sp500_proxy_candidates_v1 | combined_largecap_research_v1",
    )
    prv.add_argument(
        "--horizon",
        required=True,
        choices=("next_month", "next_quarter"),
        help="선행 지평",
    )
    prv.add_argument("--factor-version", default="v1")
    prv.add_argument("--panel-limit", type=int, default=8000)
    prv.add_argument(
        "--ols",
        action="store_true",
        help="단순 OLS 보조 요약(summary_json); robust/FM 미구현",
    )
    prv.add_argument(
        "--winsorize",
        action="store_true",
        help="팩터 winsorize(1%%/99%%) 후 상관·분위",
    )
    prv.add_argument("--n-quantiles", type=int, default=5)
    prv.set_defaults(func=_cmd_run_factor_validation)

    prp = sub.add_parser(
        "report-factor-summary",
        help="최근 completed 검증 run 기준 터미널 요약 (투자 추천 아님)",
    )
    prp.add_argument("--factor", required=True, help="예: accruals")
    prp.add_argument("--universe", required=True)
    prp.add_argument(
        "--horizon",
        required=True,
        choices=("next_month", "next_quarter"),
    )
    prp.add_argument(
        "--return-basis",
        default="raw",
        choices=("raw", "excess"),
    )
    prp.set_defaults(func=_cmd_report_factor_summary)

    srr = sub.add_parser(
        "smoke-research",
        help="Phase 5 factor_validation_* 테이블 도달 (DB·마이그레이션 필요)",
    )
    srr.set_defaults(func=_cmd_smoke_research)

    psc = sub.add_parser(
        "run-state-change",
        help="Phase 6: deterministic issuer-date state change (검증 패널·선행수익 미입력)",
    )
    psc.add_argument(
        "--universe",
        required=True,
        help="sp500_current | sp500_proxy_candidates_v1 | combined_largecap_research_v1",
    )
    psc.add_argument("--factor-version", default=None)
    psc.add_argument("--as-of-date", default=None, help="단일 as_of_date 필터 YYYY-MM-DD")
    psc.add_argument("--start-date", default=None)
    psc.add_argument("--end-date", default=None)
    psc.add_argument("--limit", type=int, default=200, help="처리 issuer 상한")
    psc.add_argument("--dry-run", action="store_true")
    psc.add_argument(
        "--include-nullable-overlays",
        action="store_true",
        help="contamination 등 nullable 오버레이 메타 포함(점수는 여전히 결정적)",
    )
    psc.add_argument(
        "--output-json",
        action="store_true",
        help="전체 결과 JSON; 생략 시 한 줄 요약",
    )
    psc.set_defaults(func=_cmd_run_state_change)

    prs = sub.add_parser(
        "report-state-change-summary",
        help="Phase 6: 최근(또는 지정) state change run 요약",
    )
    prs.add_argument("--run-id", default=None, help="우선 사용할 run UUID")
    prs.add_argument(
        "--universe",
        default=None,
        help="run-id 없을 때 completed 최신 run 조회용 유니버스명",
    )
    prs.add_argument("--scores-limit", type=int, default=15)
    prs.add_argument("--candidates-limit", type=int, default=20)
    prs.add_argument("--output-json", action="store_true")
    prs.set_defaults(func=_cmd_report_state_change_summary)

    ssc = sub.add_parser(
        "smoke-state-change",
        help="Phase 6 state_change_* 테이블 도달 (DB·마이그레이션 필요)",
    )
    ssc.set_defaults(func=_cmd_smoke_state_change)

    sbk = sub.add_parser(
        "smoke-backfill",
        help="backfill_orchestration_* 테이블 도달 (DB·마이그레이션 필요)",
    )
    sbk.set_defaults(func=_cmd_smoke_backfill)

    bfu = sub.add_parser(
        "backfill-universe",
        help="유니버스 단위 deterministic 백필 (SEC→facts→snapshots→factors→시장→선행→검증패널)",
    )
    bfu.add_argument(
        "--mode",
        required=True,
        choices=("smoke", "pilot", "full", "extended"),
        help="smoke≈5티커, pilot≈pilot JSON∩유니버스, full/extended=유니버스(캡 가능)",
    )
    bfu.add_argument(
        "--universe",
        required=True,
        help="sp500_current | sp500_proxy_candidates_v1 | combined_largecap_research_v1",
    )
    bfu.add_argument(
        "--symbol-limit",
        type=int,
        default=None,
        help="full/extended 에서 처리 상한(미지정 시 유니버스 전체)",
    )
    bfu.add_argument(
        "--start-stage",
        default=None,
        help="resolve|sec|xbrl|snapshots|factors|market_prices|forward_returns|validation_panel|phase5|phase6",
    )
    bfu.add_argument("--end-stage", default=None, help="start-stage 와 동일 집합")
    bfu.add_argument("--dry-run", action="store_true")
    bfu.add_argument(
        "--retry-failed-only",
        action="store_true",
        help="이전 오케스트레이션 summary 의 retry_tickers_all 만 재시도",
    )
    bfu.add_argument(
        "--from-orchestration-run-id",
        default=None,
        dest="from_orchestration_run_id",
        help="retry-failed-only 시 필수",
    )
    bfu.add_argument("--rerun-phase5", action="store_true")
    bfu.add_argument("--rerun-phase6", action="store_true")
    bfu.add_argument(
        "--sleep",
        type=float,
        default=float(os.getenv("INGEST_TICKER_SLEEP_SEC", "0.55")),
    )
    bfu.add_argument("--factor-version", default=None)
    bfu.add_argument(
        "--market-lookback-days",
        type=int,
        default=int(os.getenv("MARKET_PRICE_LOOKBACK_DAYS", "400")),
    )
    bfu.add_argument(
        "--coverage-stage",
        default=None,
        choices=("stage_a", "stage_b", "full"),
        help="결정적 코호트 확장: stage_a≈150·stage_b≈300·full=전체(issuer-target로 캡 가능). "
        "지정 시 티커는 유니버스 정렬 앞쪽부터 채움(--mode full 권장).",
    )
    bfu.add_argument(
        "--issuer-target",
        type=int,
        default=None,
        help="coverage-stage 와 함께: 목표 issuer 수(미지정 시 stage_a=150, stage_b=300, full=전체).",
    )
    bfu.add_argument(
        "--write-coverage-checkpoint",
        default=None,
        metavar="PATH",
        help="완료 시 coverage_checkpoint JSON을 파일로 저장",
    )
    bfu.add_argument("--output-json", action="store_true", help="항상 JSON 출력(기본도 JSON)")
    bfu.set_defaults(func=_cmd_backfill_universe)

    rbs = sub.add_parser(
        "report-backfill-status",
        help="RPC 커버리지·조인 진단·최근 backfill run 요약",
    )
    rbs.add_argument(
        "--mode",
        default="pilot",
        choices=("smoke", "pilot", "full", "extended"),
        help="진단에 쓸 티커 해석 모드",
    )
    rbs.add_argument(
        "--universe",
        default="sp500_current",
        help="sp500_current | sp500_proxy_candidates_v1 | combined_largecap_research_v1",
    )
    rbs.add_argument("--symbol-limit", type=int, default=None)
    rbs.add_argument(
        "--no-diagnostics",
        action="store_true",
        help="조인·thin issuer 조회 생략(빠른 카운트만)",
    )
    rbs.add_argument("--thin-threshold", type=int, default=4)
    rbs.add_argument(
        "--orchestration-run-id",
        default=None,
        help="특정 오케스트레이션 run 상세",
    )
    rbs.add_argument(
        "--write-diagnostics",
        default=None,
        help="join_diagnostics JSON 저장 경로",
    )
    rbs.add_argument(
        "--coverage-stage",
        default=None,
        choices=("stage_a", "stage_b", "full"),
        help="resolve·join_diagnostics 에 staged 코호트 사용",
    )
    rbs.add_argument(
        "--issuer-target",
        type=int,
        default=None,
        help="coverage-stage 와 함께 목표 issuer 수",
    )
    rbs.add_argument(
        "--include-coverage-checkpoint",
        action="store_true",
        help="페이로드에 coverage_checkpoint 포함",
    )
    rbs.add_argument(
        "--include-sparse-diagnostics",
        action="store_true",
        help="페이로드에 sparse_issuer_diagnostics 포함",
    )
    rbs.add_argument(
        "--write-sparse-diagnostics",
        default=None,
        metavar="PATH",
        help="sparse_issuer_diagnostics JSON 저장(자동으로 포함 조회)",
    )
    rbs.add_argument("--output-json", action="store_true")
    rbs.set_defaults(func=_cmd_report_backfill_status)

    sh7 = sub.add_parser(
        "smoke-harness",
        help="Phase 7 ai_harness_* 테이블 도달 (마이그레이션 필요)",
    )
    sh7.set_defaults(func=_cmd_smoke_harness)

    hai = sub.add_parser(
        "build-ai-harness-inputs",
        help="state_change_candidates → ai_harness_candidate_inputs 결정적 적재",
    )
    hai.add_argument(
        "--universe",
        default="sp500_current",
        help="run-id 미지정 시 최근 completed state_change_runs 기준",
    )
    hai.add_argument("--run-id", default=None, dest="run_id")
    hai.add_argument("--limit", type=int, default=500)
    hai.set_defaults(func=_cmd_build_ai_harness_inputs)

    gim = sub.add_parser(
        "generate-investigation-memos",
        help="harness input → investigation_memos + operator_review_queue",
    )
    gim.add_argument("--universe", default="sp500_current")
    gim.add_argument("--run-id", default=None, dest="run_id")
    gim.add_argument("--limit", type=int, default=500)
    gim.add_argument(
        "--candidate-ids",
        default=None,
        help="쉼표 구분 candidate_id만 처리(해당 run의 harness input 행이 있어야 함)",
    )
    gim.add_argument(
        "--force-new-memo-version",
        action="store_true",
        help="항상 memo_version=max+1로 신규 행 삽입(감사용; 기본은 동일 hash면 in-place 치환)",
    )
    gim.set_defaults(func=_cmd_generate_investigation_memos)

    srq = sub.add_parser(
        "set-review-queue-status",
        help="operator_review_queue 상태 변경(감사 reason 권장)",
    )
    srq.add_argument("--candidate-id", required=True, dest="candidate_id")
    srq.add_argument(
        "--status",
        required=True,
        choices=("pending", "reviewed", "needs_followup", "blocked_insufficient_data"),
    )
    srq.add_argument("--reason", default=None, help="status_reason 텍스트")
    srq.set_defaults(func=_cmd_set_review_queue_status)

    ep7 = sub.add_parser(
        "export-phase7-evidence-bundle",
        help="실데이터 후보별 입력·메모·클레임·큐·재실행 요약 JSON 덤프",
    )
    ep7.add_argument(
        "--candidate-ids",
        default=None,
        help="쉼표 구분 UUID (3개 이상 권장)",
    )
    ep7.add_argument(
        "--from-run",
        default=None,
        dest="from_run",
        metavar="RUN_ID",
        help="state_change_runs.id — 앞에서 sample_n개 후보 선택",
    )
    ep7.add_argument("--sample-n", type=int, default=3, dest="sample_n")
    ep7.add_argument(
        "--out-dir",
        default="docs/phase7_real_samples/latest",
        help="출력 디렉터리",
    )
    ep7.set_defaults(func=_cmd_export_phase7_evidence_bundle)

    rrq = sub.add_parser(
        "report-review-queue",
        help="operator_review_queue 조회 JSON",
    )
    rrq.add_argument(
        "--status",
        default=None,
        choices=("pending", "reviewed", "needs_followup", "blocked_insufficient_data"),
    )
    rrq.add_argument("--limit", type=int, default=200)
    rrq.set_defaults(func=_cmd_report_review_queue)

    sp8 = sub.add_parser(
        "smoke-phase8",
        help="Phase 8 casebook/scanner 테이블 도달 (마이그레이션 필요)",
    )
    sp8.set_defaults(func=_cmd_smoke_phase8)

    boc = sub.add_parser(
        "build-outlier-casebook",
        help="state_change run → outlier_casebook_runs + entries (휴리스틱 v1)",
    )
    boc.add_argument("--universe", default="sp500_current")
    boc.add_argument("--run-id", default=None, dest="run_id")
    boc.add_argument("--candidate-limit", type=int, default=600, dest="candidate_limit")
    boc.set_defaults(func=_cmd_build_outlier_casebook)

    bds = sub.add_parser(
        "build-daily-signal-snapshot",
        help="일일 스냅샷 + 저잡음 우선순위 워치리스트 (scanner_runs + daily_*)",
    )
    bds.add_argument("--universe", default="sp500_current")
    bds.add_argument("--run-id", default=None, dest="run_id")
    bds.add_argument("--as-of-date", default=None, dest="as_of_date")
    bds.add_argument("--candidate-limit", type=int, default=500, dest="candidate_limit")
    bds.add_argument("--top-n", type=int, default=15, dest="top_n")
    bds.add_argument(
        "--min-priority-score",
        type=float,
        default=20.0,
        dest="min_priority_score",
    )
    bds.add_argument(
        "--max-candidate-rank",
        type=int,
        default=60,
        dest="max_candidate_rank",
    )
    bds.set_defaults(func=_cmd_build_daily_signal_snapshot)

    rdw = sub.add_parser(
        "report-daily-watchlist",
        help="최근 또는 지정 scanner_run의 스냅샷 + 워치리스트 JSON",
    )
    rdw.add_argument("--scanner-run-id", default=None, dest="scanner_run_id")
    rdw.add_argument(
        "--universe",
        default=None,
        help="scanner_run_id 없을 때 최신 run 필터(선택)",
    )
    rdw.set_defaults(func=_cmd_report_daily_watchlist)

    ecs = sub.add_parser(
        "export-casebook-samples",
        help="casebook 엔트리 JSON을 디렉터리에 덤프 (실데이터 증거용)",
    )
    ecs.add_argument("--casebook-run-id", default=None, dest="casebook_run_id")
    ecs.add_argument("--state-change-run-id", default=None, dest="state_change_run_id")
    ecs.add_argument(
        "--universe",
        default=None,
        help="casebook/state_change id 없을 때: 해당 universe 최신 completed run의 최신 casebook",
    )
    ecs.add_argument("--limit", type=int, default=50)
    ecs.add_argument(
        "--out-dir",
        default="docs/phase8_samples/latest",
        help="출력 디렉터리",
    )
    ecs.set_defaults(func=_cmd_export_casebook_samples)

    sp9 = sub.add_parser(
        "smoke-phase9-observability",
        help="Phase 9 operational_runs / hypothesis_registry 테이블 도달",
    )
    sp9.set_defaults(func=_cmd_smoke_phase9_observability)

    rrh = sub.add_parser(
        "report-run-health",
        help="operational_runs 최근 요약 (상태·컴포넌트별 카운트)",
    )
    rrh.add_argument("--limit", type=int, default=80)
    rrh.set_defaults(func=_cmd_report_run_health)

    rf9 = sub.add_parser(
        "report-failures",
        help="operational_failures 최근 + 연결 run 메타",
    )
    rf9.add_argument("--limit", type=int, default=80)
    rf9.set_defaults(func=_cmd_report_failures)

    rrr = sub.add_parser(
        "report-research-registry",
        help="hypothesis_registry + promotion_gate_events + 거버넌스 경계 요약",
    )
    rrr.add_argument("--limit", type=int, default=200)
    rrr.set_defaults(func=_cmd_report_research_registry)

    srs = sub.add_parser(
        "seed-phase9-research-samples",
        help="샘플 가설 2건(idempotent) + 게이트 이벤트 — 실DB 증거용",
    )
    srs.set_defaults(func=_cmd_seed_phase9_research_samples)

    ssr = sub.add_parser(
        "seed-source-registry",
        help="data_source_registry 시드 upsert (마이그레이션 시드와 정합)",
    )
    ssr.set_defaults(func=_cmd_seed_source_registry)

    rsr = sub.add_parser(
        "report-source-registry",
        help="소스 레지스트리 + 오버레이 가용성 요약 JSON",
    )
    rsr.set_defaults(func=_cmd_report_source_registry)

    rog = sub.add_parser(
        "report-overlay-gap",
        help="고ROI 프리미엄 오버레이 갭·자격·영향 레이어 보고",
    )
    rog.add_argument(
        "--persist",
        action="store_true",
        help="source_overlay_gap_reports 에 payload 저장",
    )
    rog.set_defaults(func=_cmd_report_overlay_gap)

    ssa = sub.add_parser(
        "smoke-source-adapters",
        help="transcripts/estimates/price_quality 어댑터 seam probe (자격 없음=not_available_yet)",
    )
    ssa.set_defaults(func=_cmd_smoke_source_adapters)

    esr = sub.add_parser(
        "export-source-roi-matrix",
        help="코드 내장 ROI 순위 행렬 JSON (DB 불필요)",
    )
    esr.set_defaults(func=_cmd_export_source_roi_matrix)

    p11a = sub.add_parser(
        "probe-transcripts-provider",
        help="Phase 11: FMP earning_call_transcript 프로브 + source_overlay_availability 갱신",
    )
    p11a.set_defaults(func=_cmd_probe_transcripts_provider)

    p11b = sub.add_parser(
        "ingest-transcripts-sample",
        help="Phase 11: 단일 심볼·분기 샘플 ingest (raw_transcript_payloads_fmp + normalized_transcripts)",
    )
    p11b.add_argument("--symbol", default="AAPL", help="거래 심볼")
    p11b.add_argument("--year", type=int, default=2020)
    p11b.add_argument("--quarter", type=int, default=3)
    p11b.set_defaults(func=_cmd_ingest_transcripts_sample)

    p11c = sub.add_parser(
        "report-transcripts-overlay-status",
        help="Phase 11: earnings_call_transcripts 오버레이 행 + 메타 JSON",
    )
    p11c.set_defaults(func=_cmd_report_transcripts_overlay_status)

    p11d = sub.add_parser(
        "export-transcript-normalization-sample",
        help="Phase 11: 정규화 행 샘플 (본문 길이·접두만; 전문 미공개)",
    )
    p11d.add_argument("--ticker", default="AAPL")
    p11d.set_defaults(func=_cmd_export_transcript_normalization_sample)

    p12a = sub.add_parser(
        "run-public-core-cycle",
        help="Phase 12: 공개 코어 end-to-end (state change → harness → memo → casebook → watchlist) + 번들",
    )
    p12a.add_argument("--universe", default="sp500_current")
    p12a.add_argument("--state-change-run-id", default=None, dest="state_change_run_id")
    p12a.add_argument(
        "--ensure-state-change",
        action="store_true",
        help="completed run 없으면 run_state_change 한 번 시도(패널 전제)",
    )
    p12a.add_argument("--factor-version", default="v1")
    p12a.add_argument("--state-change-limit", type=int, default=200)
    p12a.add_argument("--harness-limit", type=int, default=500)
    p12a.add_argument("--memo-limit", type=int, default=500)
    p12a.add_argument("--casebook-candidate-limit", type=int, default=600)
    p12a.add_argument("--scanner-candidate-limit", type=int, default=500)
    p12a.add_argument("--scanner-top-n", type=int, default=15)
    p12a.add_argument("--min-priority-score", type=float, default=20.0)
    p12a.add_argument("--max-candidate-rank", type=int, default=60)
    p12a.add_argument("--as-of-date", default=None, dest="as_of_date")
    p12a.add_argument(
        "--out-dir",
        default=None,
        help="기본: docs/public_core_cycle/latest",
    )
    p12a.set_defaults(func=_cmd_run_public_core_cycle)

    p12b = sub.add_parser(
        "report-public-core-cycle",
        help="Phase 12: 마지막 run-public-core-cycle 요약 JSON 재출력",
    )
    p12b.add_argument(
        "--out-dir",
        default=None,
        help="cycle_summary.json 위치(기본 docs/public_core_cycle/latest)",
    )
    p12b.set_defaults(func=_cmd_report_public_core_cycle)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except RuntimeError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
