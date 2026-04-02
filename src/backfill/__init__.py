"""
Deterministic universe backfill orchestration (수동 DB 입력 금지).

기존 SEC / facts / snapshot / factor / market / validation CLI 파이프라인을
순서대로 호출하고, stage별 메트릭을 backfill_* 테이블에 남김.
"""

from __future__ import annotations

STAGE_ORDER = [
    "resolve",
    "sec",
    "xbrl",
    "snapshots",
    "factors",
    "market_prices",
    "forward_returns",
    "validation_panel",
    "phase5",
    "phase6",
]
