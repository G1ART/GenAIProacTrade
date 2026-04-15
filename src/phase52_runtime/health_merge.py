"""Merge Phase 52 source / queue / budget visibility into Phase 51 runtime health summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase52_runtime.event_queue import default_event_queue_path, queue_depth_pending
from phase52_runtime.source_budgets import default_budget_state_path, load_budget_state
from phase52_runtime.source_registry import default_external_source_registry_path, load_source_registry


def merge_phase52_into_summary(
    summary: dict[str, Any],
    repo_root: Path,
    *,
    source_registry_path: Path | None = None,
    budget_state_path: Path | None = None,
    event_queue_path: Path | None = None,
) -> None:
    reg_p = source_registry_path or default_external_source_registry_path(repo_root)
    if not reg_p.is_file():
        return
    reg = load_source_registry(reg_p)
    if not (reg.get("sources") or []):
        return
    bud_p = budget_state_path or default_budget_state_path(repo_root)
    q_p = event_queue_path or default_event_queue_path(repo_root)
    bud = load_budget_state(bud_p)
    qd = queue_depth_pending(q_p)
    per_source: list[dict[str, Any]] = []
    for s in reg.get("sources") or []:
        sid = str(s.get("source_id") or "")
        if not sid:
            continue
        st = (bud.get("by_source_id") or {}).get(sid) or {}
        per_source.append(
            {
                "source_id": sid,
                "source_name": s.get("source_name"),
                "enabled": s.get("enabled"),
                "queue_mode": s.get("queue_mode"),
                "active_signing_key_id": s.get("active_signing_key_id"),
                "outcome_counts": st.get("outcome_counts") or {},
                "recent_auth_failures_tail": (st.get("recent_auth_failures") or [])[-5:],
                "recent_rate_limits_tail": (st.get("recent_rate_limits") or [])[-5:],
                "recent_routing_rejections_tail": (st.get("recent_routing_rejections") or [])[-5:],
            }
        )
    summary["external_source_activity_v52"] = {
        "sources": per_source,
        "queue_depth_pending": qd,
        "registry_configured": True,
        "registry_path": str(reg_p),
    }
