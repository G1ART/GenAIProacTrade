"""Normalized cohort row for Phase 43 (exact Phase 41/42 falsifier fixture)."""

from __future__ import annotations

from typing import TypedDict


class CohortTargetRow(TypedDict, total=False):
    symbol: str
    cik: str
    signal_available_date: str
    filing_blocker_cause_before: str
    sector_blocker_cause_before: str
    residual_join_bucket: str
