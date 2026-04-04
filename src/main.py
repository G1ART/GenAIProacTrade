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
    from state_change.runner import run_state_change

    settings = load_settings()
    configure_logging()
    client = get_supabase_client(settings)
    fv = args.factor_version or os.getenv("FACTOR_VERSION") or "v1"
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
    out = generate_memos_for_run(client, run_id=rid, limit=int(args.limit))
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
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
    gim.set_defaults(func=_cmd_generate_investigation_memos)

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
