"""Pytest defaults — keep tmp_path-only trees on seed while product default is registry (MVP Spec §3.3)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _metis_today_source_seed_for_isolated_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real repo runs use registry by default; tests that copy only today_spectrum_seed need seed."""
    monkeypatch.setenv("METIS_TODAY_SOURCE", "seed")
