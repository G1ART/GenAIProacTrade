"""워커 진입점: 샘플 SEC ingest 실행."""

from __future__ import annotations

import argparse
import json
import sys

from config import ensure_edgar_local_cache, load_settings
from logging_utils import configure_logging

# edgartools가 ~/.edgar 대신 프로젝트 캐시를 쓰도록 ingest import 전에 설정
ensure_edgar_local_cache()

from sec.ingest_company_sample import run_sample_ingest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0: 샘플 SEC filing 메타데이터 ingest")
    parser.add_argument(
        "--ticker",
        default="AAPL",
        help="조회할 상장 종목 티커 (기본 AAPL)",
    )
    args = parser.parse_args()

    configure_logging()
    import logging

    logging.getLogger(__name__).info("ingest 시작 ticker=%s", args.ticker)

    settings = load_settings()
    result = run_sample_ingest(args.ticker, settings)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)
