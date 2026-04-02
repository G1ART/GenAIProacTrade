"""유니버스 → CIK 범위 (Phase 5 research 슬라이스 재사용)."""

from __future__ import annotations

from typing import Any

from research.universe_slices import ALL_RESEARCH_SLICES, resolve_slice_symbols


def resolve_universe_symbols(client: Any, universe_name: str) -> list[str]:
    return resolve_slice_symbols(client, universe_name)


def assert_known_universe(universe_name: str) -> None:
    if universe_name.strip() not in ALL_RESEARCH_SLICES:
        raise ValueError(
            f"unknown universe {universe_name!r}; expected one of {ALL_RESEARCH_SLICES}"
        )
