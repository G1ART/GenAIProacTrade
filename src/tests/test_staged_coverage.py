"""Staged coverage cohort — 결정적 해석·CLI 플래그 (DB 없음)."""

from __future__ import annotations

import pytest

from backfill.staged_cohort import (
    COVERAGE_STAGES,
    resolve_issuer_target,
    resolve_staged_coverage_tickers,
)
from research.universe_slices import (
    UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1,
    UNIVERSE_SP500_CURRENT,
)


def test_coverage_stages_frozen() -> None:
    assert "stage_a" in COVERAGE_STAGES
    assert "full" in COVERAGE_STAGES


def test_resolve_issuer_target_defaults() -> None:
    assert resolve_issuer_target("stage_a", None) == 150
    assert resolve_issuer_target("stage_b", None) == 300
    assert resolve_issuer_target("full", None) is None
    assert resolve_issuer_target("stage_a", 99) == 99


def test_resolve_staged_sp500_sorted_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    syms = [f"ZZ{i:02d}" for i in range(5)] + [f"AA{i:02d}" for i in range(5)]

    def _slice(_c: object, _u: str) -> list[str]:
        return list(syms)

    monkeypatch.setattr(
        "backfill.staged_cohort.resolve_slice_symbols",
        _slice,
    )
    tickers, meta = resolve_staged_coverage_tickers(
        object(),
        universe_name=UNIVERSE_SP500_CURRENT,
        coverage_stage="stage_a",
        issuer_target=4,
    )
    assert meta["resolved_symbol_count"] == 4
    assert tickers == sorted(syms)[:4]
    assert meta["fallback_used"] is False


def test_resolve_staged_fallback_when_sp500_short(monkeypatch: pytest.MonkeyPatch) -> None:
    sp = [f"S{i:03d}" for i in range(3)]
    combined_extra = [f"S{i:03d}" for i in range(3)] + [f"X{i:03d}" for i in range(10)]

    def _slice(_c: object, u: str) -> list[str]:
        if u == UNIVERSE_SP500_CURRENT:
            return list(sp)
        if u == UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1:
            return sorted(set(combined_extra))
        raise AssertionError(u)

    monkeypatch.setattr(
        "backfill.staged_cohort.resolve_slice_symbols",
        _slice,
    )
    tickers, meta = resolve_staged_coverage_tickers(
        object(),
        universe_name=UNIVERSE_SP500_CURRENT,
        coverage_stage="stage_a",
        issuer_target=8,
    )
    assert meta["fallback_used"] is True
    assert len(tickers) == 8
    assert set(sp).issubset(set(tickers))


def test_resolve_staged_unknown_stage() -> None:
    with pytest.raises(ValueError):
        resolve_staged_coverage_tickers(
            object(),
            universe_name=UNIVERSE_SP500_CURRENT,
            coverage_stage="not_a_stage",
            issuer_target=10,
        )


def test_cli_help_report_sparse_flags() -> None:
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    env = {**__import__("os").environ, "PYTHONPATH": str(root / "src")}
    r = subprocess.run(
        [sys.executable, str(root / "src" / "main.py"), "report-backfill-status", "-h"],
        cwd=str(root),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "--include-sparse-diagnostics" in r.stdout


def test_cli_help_includes_coverage_flags() -> None:
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    env = {**__import__("os").environ, "PYTHONPATH": str(root / "src")}
    r = subprocess.run(
        [sys.executable, str(root / "src" / "main.py"), "backfill-universe", "-h"],
        cwd=str(root),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "--coverage-stage" in r.stdout
    assert "--issuer-target" in r.stdout
