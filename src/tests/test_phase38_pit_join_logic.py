"""Phase 38 PIT join logic (no DB)."""

from __future__ import annotations

from phase38.pit_join_logic import pick_state_change_at_or_before_signal, pit_safe_pick
from phase40.pit_engine import add_calendar_days
from phase38.phase39_recommend import recommend_phase39_after_phase38
from research_validation.metrics import state_change_rows_by_cik_sorted


def test_pick_before_signal() -> None:
    rows = [
        {"cik": "0000000001", "as_of_date": "2025-01-01", "state_change_score_v1": 0.1},
        {"cik": "0000000001", "as_of_date": "2025-06-01", "state_change_score_v1": 0.2},
    ]
    by_cik = state_change_rows_by_cik_sorted(rows)
    p, r = pick_state_change_at_or_before_signal(
        by_cik, cik="1", signal_date="2025-03-15"
    )
    assert r == "picked"
    assert p is not None
    assert str(p.get("as_of_date"))[:10] == "2025-01-01"


def test_join_key_mismatch_when_all_after_signal() -> None:
    rows = [
        {"cik": "0000000001", "as_of_date": "2026-09-28", "state_change_score_v1": 0.1},
    ]
    by_cik = state_change_rows_by_cik_sorted(rows)
    p, r = pick_state_change_at_or_before_signal(
        by_cik, cik="1", signal_date="2025-12-08"
    )
    assert r == "state_change_built_but_join_key_mismatch"
    assert p is None


def test_pit_safe_pick() -> None:
    row = {"as_of_date": "2025-01-01"}
    ok, _ = pit_safe_pick(row, signal_bound="2025-12-01")
    assert ok


def test_add_calendar_days() -> None:
    assert add_calendar_days("2025-11-27", 7) == "2025-12-04"


def test_phase39_when_leakage_fails() -> None:
    p39 = recommend_phase39_after_phase38(
        pit_result={"leakage_audit": {"passed": False}, "row_results": []}
    )
    assert "remediate" in p39["phase39_recommendation"]
