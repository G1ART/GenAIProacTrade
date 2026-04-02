"""Phase 6: state change 결정성·누수 방지·CLI (DB 없음 가능)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from state_change.candidates import IssuerDateScoreRow, classify_candidate
from state_change.cli_report import format_state_change_summary_text
from state_change.components import apply_direction_level, apply_direction_delta
from state_change.scoring import (
    SubScoreParts,
    population_zscores,
    resolve_component_weights,
    weighted_composite,
)
from state_change.signal_registry import STATE_CHANGE_SIGNALS_V1, StateChangeSignalSpec
from state_change.transforms import build_lag_series


ROOT = Path(__file__).resolve().parents[2]
STATE_CHANGE_DIR = ROOT / "src" / "state_change"


def test_population_zscores_deterministic() -> None:
    xs = [2.0, 4.0, 6.0, 8.0, 10.0]
    a = population_zscores(xs)
    b = population_zscores(xs)
    assert a is not None and a == b


def test_build_lag_series_short_history_graceful() -> None:
    ls = build_lag_series([10.0, 20.0], 0)
    assert ls.current == 10.0
    assert ls.lag_1 is None
    assert ls.lag_2 is None
    assert ls.lag_4 is None


def test_weighted_composite_excludes_null_overlays() -> None:
    w = resolve_component_weights(has_contamination=False, has_regime=False)
    parts = SubScoreParts(0.4, 0.4, 0.4, 0.4, None, None)
    score, den, inc = weighted_composite(parts, base_weights=w)
    assert "contamination" not in inc and "regime_fit" not in inc
    assert den == pytest.approx(1.0)
    assert score == pytest.approx(0.4)


def test_weighted_composite_null_not_neutral_zero() -> None:
    """축 전부 None 이면 합성 0·den 0 — '중립 0점'과 동일 수치로 쓰이지 않도록 호출측에서 구분."""
    w = resolve_component_weights(has_contamination=False, has_regime=False)
    parts = SubScoreParts(None, None, None, None, None, None)
    score, den, _ = weighted_composite(parts, base_weights=w)
    assert den == 0.0
    assert score == 0.0


def test_signal_direction_mapping() -> None:
    gp = next(s for s in STATE_CHANGE_SIGNALS_V1 if s.signal_name == "gross_profitability")
    assert apply_direction_level(3.0, gp) > 0
    assert apply_direction_delta(3.0, gp) > 0
    low = StateChangeSignalSpec(
        signal_name="_test_low",
        source_column="x",
        preferred_direction="lower_is_positive",
        level_method="cross_section_z",
        velocity_method="first_difference",
        acceleration_method="delta_of_delta",
        persistence_method="same_sign_streak",
        min_history_required=1,
        winsorize_policy_nullable=None,
        notes="test",
    )
    assert apply_direction_level(3.0, low) < 0


def test_candidate_ranking_deterministic() -> None:
    rows = [
        IssuerDateScoreRow(
            cik="0002",
            ticker=None,
            as_of_date="2024-03-31",
            score=0.1,
            direction="mixed",
            confidence_band="medium",
            gating_status="ok",
            missing_component_count=0,
            included_component_count=3,
        ),
        IssuerDateScoreRow(
            cik="0001",
            ticker=None,
            as_of_date="2024-03-31",
            score=-0.1,
            direction="mixed",
            confidence_band="medium",
            gating_status="ok",
            missing_component_count=0,
            included_component_count=3,
        ),
        IssuerDateScoreRow(
            cik="0003",
            ticker=None,
            as_of_date="2024-06-30",
            score=0.2,
            direction="strengthening",
            confidence_band="high",
            gating_status="ok",
            missing_component_count=0,
            included_component_count=4,
        ),
    ]
    ranked = sorted(
        rows,
        key=lambda r: (abs(r.score), r.as_of_date, r.cik),
        reverse=True,
    )
    assert ranked[0].cik == "0003"
    assert ranked[1].cik == "0002"
    assert ranked[2].cik == "0001"
    c0, _, _, _ = classify_candidate(ranked[0], rank=1, total_ranked=3)
    assert c0 in (
        "investigate_now",
        "investigate_watch",
        "recheck_later",
        "insufficient_data",
        "excluded",
    )


def test_state_change_package_no_validation_panel_queries() -> None:
    """factor_market_validation_panels 를 state change 입력으로 조회하지 않음."""
    bad_substrings = (
        "fetch_factor_market_validation",
        'table("factor_market_validation_panels"',
        ".table('factor_market_validation_panels'",
    )
    for path in sorted(STATE_CHANGE_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for b in bad_substrings:
            assert b not in text, f"{path.name} must not reference validation panel fetch: {b}"


def test_loaders_docstring_leakage_guard() -> None:
    p = STATE_CHANGE_DIR / "loaders.py"
    t = p.read_text(encoding="utf-8")
    assert "factor_market_validation_panels" in t
    assert "금지" in t or "미사용" in t or "미조회" in t


def test_format_state_change_summary_text() -> None:
    payload = {
        "ok": True,
        "run": {
            "id": "u1",
            "status": "completed",
            "universe_name": "sp500_current",
            "as_of_date_start": "2023-01-01",
            "as_of_date_end": "2023-12-31",
            "factor_version": "v1",
            "config_version": "state_change_v1",
            "row_count": 10,
            "warning_count": 0,
        },
        "candidate_class_counts": {"investigate_watch": 2, "excluded": 1},
        "top_candidates": [
            {
                "candidate_rank": 1,
                "candidate_class": "investigate_watch",
                "cik": "0001",
                "ticker": "TST",
                "as_of_date": "2023-06-30",
                "confidence_band": "medium",
            }
        ],
        "top_scores": [
            {
                "cik": "0001",
                "state_change_score_v1": 0.12,
                "state_change_direction": "mixed",
                "gating_status": "ok",
            }
        ],
    }
    s = format_state_change_summary_text(payload)
    assert "investigate_watch" in s
    assert "0001" in s


def _run_main(argv: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, str(ROOT / "src" / "main.py"), *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.parametrize(
    "cmd",
    [
        ["run-state-change", "-h"],
        ["report-state-change-summary", "-h"],
        ["smoke-state-change", "-h"],
    ],
)
def test_state_change_cli_help(cmd: list[str]) -> None:
    r = _run_main(cmd)
    assert r.returncode == 0, r.stderr


def test_run_state_change_requires_universe() -> None:
    r = _run_main(["run-state-change"])
    assert r.returncode != 0
