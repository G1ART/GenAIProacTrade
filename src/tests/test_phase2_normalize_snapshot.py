from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from sec.facts.build_quarter_snapshot import build_snapshot_row
from sec.facts.normalize_facts import (
    dataframe_row_to_raw_fact_dict,
    make_fact_period_key,
    parse_primary_fiscal_from_facts,
    raw_dict_to_silver_candidate,
    raw_dedupe_key,
)


def test_raw_dedupe_key_stable() -> None:
    a = raw_dedupe_key(
        concept="us-gaap:Assets",
        context_ref="c-1",
        period_start=None,
        period_end=None,
        instant_date=date(2025, 12, 31),
        unit_ref="usd",
        value_repr="1.0",
    )
    b = raw_dedupe_key(
        concept="us-gaap:Assets",
        context_ref="c-1",
        period_start=None,
        period_end=None,
        instant_date=date(2025, 12, 31),
        unit_ref="usd",
        value_repr="1.0",
    )
    assert a == b
    c = raw_dedupe_key(
        concept="us-gaap:Assets",
        context_ref="c-2",
        period_start=None,
        period_end=None,
        instant_date=date(2025, 12, 31),
        unit_ref="usd",
        value_repr="1.0",
    )
    assert a != c


def test_dataframe_row_to_raw_and_silver() -> None:
    row = pd.Series(
        {
            "concept": "us-gaap:NetIncomeLoss",
            "context_ref": "c1",
            "value": None,
            "numeric_value": 100.0,
            "period_type": "duration",
            "period_start": pd.Timestamp("2025-09-28"),
            "period_end": pd.Timestamp("2025-12-27"),
            "fiscal_year": 2026,
            "fiscal_period": "Q1",
            "unit_ref": "usd",
        }
    )
    raw = dataframe_row_to_raw_fact_dict(
        row,
        cik="0000320193",
        accession_no="0000320193-26-000006",
        filed_at=datetime(2026, 1, 30, tzinfo=timezone.utc),
        accepted_at=None,
    )
    assert raw["cik"] == "0000320193"
    assert raw["concept"] == "us-gaap:NetIncomeLoss"
    assert raw["value_numeric"] == 100.0
    silver = raw_dict_to_silver_candidate(raw)
    assert silver is not None
    assert silver["canonical_concept"] == "net_income"
    assert silver["fact_type"] == "duration"
    assert silver["fiscal_year"] == 2026


def test_parse_primary_fiscal_dei() -> None:
    raw_rows = [
        {
            "concept": "dei:DocumentFiscalYearFocus",
            "value_numeric": 2026.0,
            "value_text": None,
        },
        {
            "concept": "dei:DocumentFiscalPeriodFocus",
            "value_numeric": None,
            "value_text": "Q1",
        },
    ]
    fy, fp = parse_primary_fiscal_from_facts(raw_rows)
    assert fy == 2026
    assert fp == "Q1"


def test_build_snapshot_partial_missing() -> None:
    raw_rows = [
        {
            "concept": "dei:DocumentFiscalYearFocus",
            "value_numeric": 2026.0,
            "value_text": None,
        },
        {
            "concept": "dei:DocumentFiscalPeriodFocus",
            "value_numeric": None,
            "value_text": "Q1",
        },
    ]
    silver_rows = [
        {
            "canonical_concept": "revenue",
            "source_concept": "us-gaap:Revenues",
            "numeric_value": 1.0e9,
            "fact_type": "duration",
            "fiscal_year": 2026,
            "fiscal_period": "Q1",
            "fact_period_key": make_fact_period_key(
                fact_type="duration",
                fiscal_year=2026,
                fiscal_period="Q1",
                period_start=date(2025, 9, 28),
                period_end=date(2025, 12, 27),
                instant_date=None,
            ),
        }
    ]
    snap = build_snapshot_row(
        raw_rows=raw_rows,
        silver_rows=silver_rows,
        cik="0000320193",
        accession_no="0000320193-26-000006",
        filed_at=datetime(2026, 1, 30, tzinfo=timezone.utc),
        accepted_at=None,
    )
    assert snap["revenue"] == 1.0e9
    assert snap["net_income"] is None
    assert "net_income" in snap["snapshot_json"]["missing_canonicals"]
    assert "revenue" in snap["snapshot_json"]["filled_canonicals"]
