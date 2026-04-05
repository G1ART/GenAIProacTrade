"""Registry report payload (kept separate from DB records for CLI imports)."""

from __future__ import annotations

from typing import Any

from research_registry.registry import build_registry_report_payload

__all__ = ["build_registry_report_payload"]


def format_registry_report(client: Any, *, limit: int = 200) -> dict[str, Any]:
    return build_registry_report_payload(client, limit=limit)
