"""Per-source rate limits and rolling window caps (deterministic, persisted)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_budget_state_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "external_source_budget_state_v1.json"


def load_budget_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "by_source_id": {}}
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "by_source_id": {}}


def save_budget_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _minute_key(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M")


def _append_tail(lst: list[Any], item: dict[str, Any], *, max_len: int = 25) -> None:
    lst.append(item)
    del lst[:-max_len]


def check_and_consume_budget(
    *,
    source: dict[str, Any],
    source_id: str,
    budget_path: Path,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """
    Enforce rate_limit_per_minute and max_events_per_window / window_seconds.
    Mutates and persists budget state on success (consumes one slot).
    """
    now = now or datetime.now(timezone.utc)
    per_min = int(source.get("rate_limit_per_minute") or 0) or 60
    max_win = int(source.get("max_events_per_window") or 0) or 1000
    win_sec = int(source.get("window_seconds") or 0) or 3600

    st = load_budget_state(budget_path)
    by = dict(st.get("by_source_id") or {})
    cur = dict(by.get(source_id) or {})
    mk = _minute_key(now)
    if cur.get("current_minute_key") != mk:
        cur["current_minute_key"] = mk
        cur["events_this_minute"] = 0
    n_min = int(cur.get("events_this_minute") or 0)
    if n_min >= per_min:
        cur.setdefault("recent_rate_limits", [])
        _append_tail(
            cur["recent_rate_limits"],
            {"timestamp": now.isoformat(), "reason": "rate_limit_per_minute", "limit": per_min},
        )
        by[source_id] = cur
        st["by_source_id"] = by
        save_budget_state(budget_path, st)
        return False, "rate_limit_per_minute"

    ws = cur.get("window_started_at_utc")
    wcount = int(cur.get("events_this_window") or 0)
    if not ws:
        cur["window_started_at_utc"] = now.isoformat()
        cur["events_this_window"] = 0
        wcount = 0
    else:
        try:
            wstart = datetime.fromisoformat(str(ws).replace("Z", "+00:00"))
        except ValueError:
            wstart = now
            cur["window_started_at_utc"] = now.isoformat()
            cur["events_this_window"] = 0
            wcount = 0
        elapsed = (now - wstart).total_seconds()
        if elapsed >= win_sec:
            cur["window_started_at_utc"] = now.isoformat()
            cur["events_this_window"] = 0
            wcount = 0
        elif wcount >= max_win:
            cur.setdefault("recent_rate_limits", [])
            _append_tail(
                cur["recent_rate_limits"],
                {"timestamp": now.isoformat(), "reason": "max_events_per_window", "limit": max_win},
            )
            by[source_id] = cur
            st["by_source_id"] = by
            save_budget_state(budget_path, st)
            return False, "max_events_per_window"

    cur["events_this_minute"] = n_min + 1
    cur["events_this_window"] = wcount + 1
    by[source_id] = cur
    st["by_source_id"] = by
    save_budget_state(budget_path, st)
    return True, "ok"


def record_auth_failure(
    *,
    source_id: str,
    budget_path: Path,
    reason: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    st = load_budget_state(budget_path)
    by = dict(st.get("by_source_id") or {})
    cur = dict(by.get(source_id) or {})
    cur.setdefault("recent_auth_failures", [])
    _append_tail(cur["recent_auth_failures"], {"timestamp": now.isoformat(), "reason": reason})
    by[source_id] = cur
    st["by_source_id"] = by
    save_budget_state(budget_path, st)


def record_routing_rejection(
    *,
    source_id: str,
    budget_path: Path,
    reason: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    st = load_budget_state(budget_path)
    by = dict(st.get("by_source_id") or {})
    cur = dict(by.get(source_id) or {})
    cur.setdefault("recent_routing_rejections", [])
    _append_tail(cur["recent_routing_rejections"], {"timestamp": now.isoformat(), "reason": reason})
    by[source_id] = cur
    st["by_source_id"] = by
    save_budget_state(budget_path, st)


def record_outcome(
    *,
    source_id: str,
    budget_path: Path,
    outcome: str,
    now: datetime | None = None,
) -> None:
    """Aggregate counters for runtime health (per source_id)."""
    now = now or datetime.now(timezone.utc)
    st = load_budget_state(budget_path)
    by = dict(st.get("by_source_id") or {})
    cur = dict(by.get(source_id) or {})
    agg = dict(cur.get("outcome_counts") or {})
    agg[outcome] = int(agg.get(outcome) or 0) + 1
    cur["outcome_counts"] = agg
    cur["last_outcome_at"] = now.isoformat()
    by[source_id] = cur
    st["by_source_id"] = by
    save_budget_state(budget_path, st)


