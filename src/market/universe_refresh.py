"""S&P 500 current 유니버스 갱신 → universe_memberships + registry."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from db.client import get_supabase_client
from db.records import (
    fetch_cik_for_ticker,
    insert_universe_memberships_batch,
    upsert_market_symbol_registry,
    ingest_run_create_started,
    ingest_run_finalize,
)
from market.provider_factory import get_market_provider
from market.run_types import UNIVERSE_REFRESH, UNIVERSE_SP500_CURRENT

logger = logging.getLogger(__name__)


def run_universe_refresh_sp500(settings: Any) -> dict[str, Any]:
    client = get_supabase_client(settings)
    provider = get_market_provider()
    as_of = date.today()
    as_of_s = as_of.isoformat()
    run_id = ingest_run_create_started(
        client,
        run_type=UNIVERSE_REFRESH,
        target_count=None,
        metadata_json={
            "universe_name": UNIVERSE_SP500_CURRENT,
            "as_of_date": as_of_s,
            "provider": provider.name,
        },
    )
    success = 0
    failures = 0
    quality: list[dict[str, Any]] = []
    try:
        constituents = provider.fetch_index_constituents(UNIVERSE_SP500_CURRENT)
        if not constituents:
            raise RuntimeError(
                "구성 종목이 비어 있습니다. 네트워크·파서·MARKET_DATA_PROVIDER=stub 여부를 확인하세요."
            )
        memberships: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()
        for c in constituents:
            sym = c.symbol.upper().strip()
            wiki_cik = (c.cik or "").strip() or None
            im_cik = fetch_cik_for_ticker(client, ticker=sym)
            chosen = im_cik or wiki_cik
            if im_cik and wiki_cik and im_cik != wiki_cik:
                quality.append(
                    {
                        "symbol": sym,
                        "flag": "cik_mismatch_wiki_vs_issuer_master",
                        "issuer_master_cik": im_cik,
                        "source_cik": wiki_cik,
                    }
                )
            memberships.append(
                {
                    "universe_name": UNIVERSE_SP500_CURRENT,
                    "symbol": sym,
                    "cik": chosen,
                    "as_of_date": as_of_s,
                    "membership_status": "constituent",
                    "source_name": provider.name,
                    "source_payload_json": dict(c.raw_payload) | {"name": c.name},
                }
            )
            upsert_market_symbol_registry(
                client,
                {
                    "symbol": sym,
                    "cik": chosen,
                    "company_name": c.name,
                    "exchange": None,
                    "currency": "USD",
                    "asset_type": "common_stock",
                    "is_active": True,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "source_name": provider.name,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            success += 1
        insert_universe_memberships_batch(client, memberships)
        status = "completed"
    except Exception as ex:  # noqa: BLE001
        logger.exception("universe_refresh 실패")
        failures = 1
        status = "failed"
        quality.append({"error": str(ex)})
    ingest_run_finalize(
        client,
        run_id=run_id,
        status=status,
        success_count=success,
        failure_count=failures,
        error_json={"quality_flags": quality} if quality else None,
    )
    return {
        "status": status,
        "universe_name": UNIVERSE_SP500_CURRENT,
        "as_of_date": as_of_s,
        "success_count": success,
        "failure_count": failures,
        "quality_flags": quality,
    }
