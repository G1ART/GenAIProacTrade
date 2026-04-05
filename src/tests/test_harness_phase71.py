"""Phase 7.1: rerun policy, claim rows shape, referee structure, queue validation."""

from __future__ import annotations

import pytest

from harness.memo_builder.pipeline import generate_investigation_memo_v1
from harness.referee.gate import referee_gate_scan
from harness.rerun_policy import (
    assert_valid_queue_transition,
    decide_memo_write_mode,
    resolve_queue_status_on_memo_regen,
)
from harness.run_batch import claims_rows_from_memo
from tests.test_harness_phase7 import _minimal_input


def test_decide_memo_in_place_when_hash_matches() -> None:
    latest = {
        "input_payload_hash": "abc",
        "generation_mode": "deterministic_skeleton_v1",
    }
    assert (
        decide_memo_write_mode(
            payload_hash="abc",
            generation_mode="deterministic_skeleton_v1",
            latest_memo=latest,
            force_new_version=False,
        )
        == "in_place_replace"
    )


def test_decide_memo_new_version_when_hash_differs() -> None:
    latest = {
        "input_payload_hash": "old",
        "generation_mode": "deterministic_skeleton_v1",
    }
    assert (
        decide_memo_write_mode(
            payload_hash="new",
            generation_mode="deterministic_skeleton_v1",
            latest_memo=latest,
            force_new_version=False,
        )
        == "insert_new_version"
    )


def test_queue_status_preserves_reviewed() -> None:
    assert (
        resolve_queue_status_on_memo_regen(
            {"status": "reviewed"}, referee_passed=False
        )
        == "reviewed"
    )


def test_queue_status_needs_followup_when_referee_fails_fresh() -> None:
    assert (
        resolve_queue_status_on_memo_regen(None, referee_passed=False)
        == "needs_followup"
    )


def test_assert_valid_queue_transition() -> None:
    assert_valid_queue_transition("pending", "reviewed")
    with pytest.raises(ValueError):
        assert_valid_queue_transition("pending", "invalid_status")


def test_claim_rows_have_roles_and_trace() -> None:
    inp = _minimal_input()
    memo = generate_investigation_memo_v1(inp, memo_version=1, memo_id="m1")
    rows = claims_rows_from_memo("m1", memo, str(inp["candidate_id"]))
    roles = {r["claim_role"] for r in rows}
    assert "thesis" in roles
    assert "challenge" in roles
    assert "synthesis" in roles
    assert "evidence" in roles
    for r in rows:
        assert r.get("statement")
        assert r.get("uncertainty_label") in (
            "confirmed",
            "plausible_hypothesis",
            "unverifiable",
        )
        assert "trace_refs" in r
        assert r.get("verdict") == "pending"


def test_referee_flags_challenge_incomplete() -> None:
    memo = generate_investigation_memo_v1(_minimal_input(), memo_version=1)
    memo["strongest_counter_argument"] = {
        "alternate_interpretation": "x",
        "data_insufficiency_risk": "",
        "why_change_may_not_matter": "y",
        "what_would_falsify_thesis": "z",
    }
    r = referee_gate_scan(memo)
    assert r["passed"] is False
    assert any(
        x.get("code") == "challenge_dimension_incomplete" for x in r["flags"]
    )


def test_referee_flags_synthesis_preservation() -> None:
    memo = generate_investigation_memo_v1(_minimal_input(), memo_version=1)
    memo["synthesis"]["thesis_preserved"] = False
    r = referee_gate_scan(memo)
    assert r["passed"] is False
    assert any(
        x.get("code") == "disagreement_not_structurally_preserved"
        for x in r["flags"]
    )
