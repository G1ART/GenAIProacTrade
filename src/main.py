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
    p10.add_argument("--watchlist", default=None)
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
