"""CLI: ingest-single | ingest-watchlist | smoke-sec | smoke-db"""

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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GenAIProacTrade Phase 1 worker CLI")
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
