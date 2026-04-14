"""Source-scoped routing: raw types and normalized triggers."""

from __future__ import annotations

from typing import Any


def routing_allows_event(
    *,
    source: dict[str, Any],
    raw_event_type: str,
    normalized_trigger_type: str | None,
) -> tuple[bool, str]:
    allowed_raw = set(str(x) for x in (source.get("allowed_raw_event_types") or []) if x)
    allow_nt = set(str(x) for x in (source.get("normalized_trigger_allowlist") or []) if x)
    rt = str(raw_event_type or "").strip()
    nt = str(normalized_trigger_type or "").strip()
    if allowed_raw and rt not in allowed_raw:
        return False, f"raw_event_type_not_allowed:{rt}"
    if allow_nt and nt not in allow_nt:
        return False, f"normalized_trigger_not_allowed:{nt}"
    return True, "ok"
