"""
sp500_proxy_candidates_v1: 공식 편입 후보가 아님.

규칙: config/sp500_proxy_candidates_v1.json 시드 심볼 중
현재 sp500_current(최신 as_of)에 없는 U.S. 리스트 심볼만 candidate 로 적재.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT
from db.client import get_supabase_client
from db.records import (
    fetch_cik_for_ticker,
    fetch_max_as_of_universe,
    fetch_symbols_universe_as_of,
    insert_universe_memberships_batch,
    ingest_run_create_started,
    ingest_run_finalize,
)
from market.run_types import (
    UNIVERSE_CANDIDATE_BUILD,
    UNIVERSE_PROXY_CANDIDATES,
    UNIVERSE_SP500_CURRENT,
)

logger = logging.getLogger(__name__)

DEFAULT_SEED = PROJECT_ROOT / "config" / "sp500_proxy_candidates_v1.json"


def _load_seed(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    syms = data.get("symbols") or []
    return [str(s).upper().strip() for s in syms if str(s).strip()]


def run_build_candidate_universe(
    settings: Any,
    *,
    seed_path: Path | None = None,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    sp_as_of = fetch_max_as_of_universe(client, universe_name=UNIVERSE_SP500_CURRENT)
    if not sp_as_of:
        return {
            "status": "failed",
            "error": "sp500_current 유니버스가 없습니다. 먼저 refresh-universe 를 실행하세요.",
        }
    sp_set = set(fetch_symbols_universe_as_of(client, universe_name=UNIVERSE_SP500_CURRENT, as_of_date=sp_as_of))
    path = seed_path or DEFAULT_SEED
    if not path.exists():
        return {"status": "failed", "error": f"시드 파일 없음: {path}"}
    seed = _load_seed(path)
    candidates = [s for s in seed if s not in sp_set]
    as_of = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    if not candidates:
        msg = (
            "시드의 모든 심볼이 현재 sp500_current 에 포함되어 후보가 0개입니다. "
            "config/sp500_proxy_candidates_v1.json 에서 S&P 500에 없는 티커로 바꾸세요."
        )
        run_id = ingest_run_create_started(
            client,
            run_type=UNIVERSE_CANDIDATE_BUILD,
            target_count=len(seed),
            metadata_json={
                "universe_name": UNIVERSE_PROXY_CANDIDATES,
                "as_of_date": as_of,
                "seed_file": str(path),
                "excluded_sp500_as_of": sp_as_of,
                "seed_symbols": seed,
            },
        )
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="failed",
            success_count=0,
            failure_count=1,
            error_json={
                "error": msg,
                "seed_filtered_out_entirely": True,
                "seed_was": seed,
            },
        )
        return {
            "status": "failed",
            "error": msg,
            "candidate_count": 0,
            "seed_path": str(path),
            "seed_was": seed,
            "hint": "멤버십 가입이 아님. 유니버스는 DB 테이블 적재이며, 후보=시드−S&P500.",
        }
    run_id = ingest_run_create_started(
        client,
        run_type=UNIVERSE_CANDIDATE_BUILD,
        target_count=len(candidates),
        metadata_json={
            "universe_name": UNIVERSE_PROXY_CANDIDATES,
            "as_of_date": as_of,
            "seed_file": str(path),
            "excluded_sp500_as_of": sp_as_of,
            "note": "not_official_index_committee_candidate",
        },
    )
    rows: list[dict[str, Any]] = []
    for sym in candidates:
        cik = fetch_cik_for_ticker(client, ticker=sym)
        rows.append(
            {
                "universe_name": UNIVERSE_PROXY_CANDIDATES,
                "symbol": sym,
                "cik": cik,
                "as_of_date": as_of,
                "membership_status": "candidate",
                "source_name": "seed_sp500_proxy_candidates_v1",
                "source_payload_json": {"seed_file": str(path.name)},
            }
        )
    try:
        insert_universe_memberships_batch(client, rows)
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="completed",
            success_count=len(rows),
            failure_count=0,
            error_json=None,
        )
        return {
            "status": "completed",
            "universe_name": UNIVERSE_PROXY_CANDIDATES,
            "as_of_date": as_of,
            "candidate_count": len(rows),
            "seed_path": str(path),
        }
    except Exception as ex:  # noqa: BLE001
        logger.exception("candidate universe 실패")
        ingest_run_finalize(
            client,
            run_id=run_id,
            status="failed",
            success_count=0,
            failure_count=1,
            error_json={"error": str(ex)},
        )
        return {"status": "failed", "error": str(ex)}
