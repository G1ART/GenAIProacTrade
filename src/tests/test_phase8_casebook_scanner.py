"""Phase 8: outlier heuristics, prioritizer gates, message fields (no DB)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from casebook.outlier_builder import build_message_fields, detect_outliers_for_candidate
from scanner.prioritizer import (
    DEFAULT_MIN_PRIORITY_SCORE,
    DEFAULT_TOP_N,
    compute_priority_score,
    rank_watchlist_candidates,
)


def test_message_fields_present() -> None:
    m = build_message_fields(
        short_title="t",
        why_matters="w",
        what_wrong="x",
        unknown="u",
        plain="p",
    )
    assert m["message_short_title"] == "t"
    assert "message_plain_language" in m


def test_reaction_gap_detection() -> None:
    cand = {
        "id": "c1",
        "cik": "0001",
        "ticker": "TEST",
        "as_of_date": "2024-06-01",
        "candidate_class": "investigate_now",
        "candidate_rank": 1,
        "issuer_id": None,
    }
    score = {
        "state_change_score_v1": 1.5,
        "state_change_direction": "increase",
        "missing_component_count": 0,
        "gating_status": "ok",
    }
    panel = {"excess_return_1m": -0.03, "signal_available_date": "2024-06-03"}
    rows = detect_outliers_for_candidate(
        candidate=cand,
        score=score,
        validation_panel=panel,
        forward_row=None,
        memo=None,
        harness_row={"payload_json": {}},
        components=[],
        company_name="Test Co",
    )
    types = {r["outlier_type"] for r in rows}
    assert "reaction_gap" in types
    assert all(r.get("is_heuristic") is True for r in rows)
    assert all(r.get("message_why_matters") for r in rows)


def test_watchlist_bounded_and_gated() -> None:
    cands = []
    for i in range(30):
        cands.append(
            (
                {
                    "id": f"id{i}",
                    "candidate_class": "investigate_now",
                    "candidate_rank": i + 1,
                },
                {
                    "state_change_score_v1": 0.1 * (30 - i),
                    "state_change_direction": "increase",
                },
            )
        )
    ranked = rank_watchlist_candidates(
        cands,
        top_n=5,
        min_priority_score=DEFAULT_MIN_PRIORITY_SCORE,
        max_candidate_rank=60,
    )
    assert len(ranked) <= 5


def test_empty_watchlist_when_min_score_extreme() -> None:
    cand = (
        {"id": "x", "candidate_class": "investigate_now", "candidate_rank": 5},
        {"state_change_score_v1": 0.01, "state_change_direction": "increase"},
    )
    ranked = rank_watchlist_candidates(
        [cand],
        top_n=DEFAULT_TOP_N,
        min_priority_score=9999.0,
        max_candidate_rank=60,
    )
    assert ranked == []


def test_challenge_divergence_with_referee_fail() -> None:
    cand = {
        "id": "c1",
        "cik": "0001",
        "ticker": "T",
        "as_of_date": "2024-06-01",
        "candidate_class": "investigate_watch",
        "candidate_rank": 2,
    }
    memo = {
        "id": "m1",
        "referee_passed": False,
        "referee_flags_json": [{"code": "x"}],
        "memo_json": {},
    }
    rows = detect_outliers_for_candidate(
        candidate=cand,
        score={"state_change_score_v1": 0.5, "state_change_direction": "increase", "missing_component_count": 0, "gating_status": "ok"},
        validation_panel=None,
        forward_row=None,
        memo=memo,
        harness_row={"payload_json": {}},
        components=[],
        company_name="Co",
    )
    assert any(r["outlier_type"] == "thesis_challenge_divergence" for r in rows)


def test_cli_help_phase8_commands() -> None:
    root = Path(__file__).resolve().parents[2]
    env = {**__import__("os").environ, "PYTHONPATH": str(root / "src")}
    for cmd in (
        "smoke-phase8",
        "build-outlier-casebook",
        "build-daily-signal-snapshot",
        "report-daily-watchlist",
        "export-casebook-samples",
    ):
        r = subprocess.run(
            [sys.executable, str(root / "src" / "main.py"), cmd, "-h"],
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
        )
        assert r.returncode == 0, (cmd, r.stderr)


def test_compute_priority_monotonic_with_score() -> None:
    c = {"candidate_class": "investigate_now", "candidate_rank": 1}
    s1 = {"state_change_score_v1": 1.0, "state_change_direction": "up"}
    s2 = {"state_change_score_v1": 2.0, "state_change_direction": "up"}
    assert compute_priority_score(c, s2) > compute_priority_score(c, s1)
