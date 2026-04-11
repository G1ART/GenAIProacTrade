"""Phase 40 pit_engine — no DB."""

from __future__ import annotations

from phase40.pit_engine import (
    STANDARD_BUCKETS,
    classify_row_outcome,
    count_joined_in_family,
    rollup_standard,
)


def test_classify_join_key_mismatch_reason() -> None:
    cat, _det = classify_row_outcome(
        None,
        "state_change_built_but_join_key_mismatch",
        signal_bound="2025-01-01",
    )
    assert cat == "still_join_key_mismatch"


def test_rollup_skips_alternate_not_executed() -> None:
    specs = {
        "a": {"outcome_category": "still_join_key_mismatch"},
        "b": {"outcome_category": "alternate_spec_not_executed"},
    }
    r = rollup_standard(specs)
    assert r["still_join_key_mismatch"] == 1
    assert sum(r.values()) == 1


def test_count_joined_in_family() -> None:
    rows = [
        {"spec_results": {"x": {"outcome_category": "reclassified_to_joined"}}},
        {"spec_results": {"x": {"outcome_category": "still_join_key_mismatch"}}},
    ]
    assert count_joined_in_family(rows) == 1


def test_standard_buckets_tuple() -> None:
    assert "reclassified_to_joined" in STANDARD_BUCKETS
