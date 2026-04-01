from __future__ import annotations

import pytest

from sec.validation.arelle_check import (
    compare_statement_concept_presence,
    validate_xbrl_fact_presence,
)


def test_validate_xbrl_fact_presence_skips_without_arelle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sec.validation.arelle_check._check_arelle", lambda: False)
    r = validate_xbrl_fact_presence(
        cik="1",
        accession_no="a",
        source_fact_count=100,
        mapped_silver_count=5,
    )
    assert r["status"] == "skipped"
    assert r["source_fact_count"] == 100


def test_compare_statement_concept_presence_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sec.validation.arelle_check._check_arelle", lambda: True)
    r = compare_statement_concept_presence(
        cik="1",
        accession_no="a",
        canonical_present=["revenue", "net_income"],
    )
    assert r["status"] == "arelle_assist_pending"
    assert r["canonical_present"] == ["revenue", "net_income"]
