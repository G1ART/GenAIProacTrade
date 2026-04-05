"""CLI-facing summaries for operational_runs / operational_failures."""

from __future__ import annotations

from collections import Counter
from typing import Any

from db import records as dbrec


def build_run_health_payload(client: Any, *, limit: int = 80) -> dict[str, Any]:
    runs = dbrec.fetch_operational_runs_recent(client, limit=limit)
    by_status = Counter(str(r.get("status") or "") for r in runs)
    by_component = Counter(str(r.get("component") or "") for r in runs)
    return {
        "run_count": len(runs),
        "by_status": dict(by_status),
        "by_component": dict(by_component),
        "recent_runs": runs,
    }


def build_failures_payload(client: Any, *, limit: int = 80) -> dict[str, Any]:
    fails = dbrec.fetch_operational_failures_recent(client, limit=limit)
    run_cache: dict[str, dict[str, Any] | None] = {}
    enriched: list[dict[str, Any]] = []
    for row in fails:
        oid = str(row.get("operational_run_id") or "")
        if oid and oid not in run_cache:
            run_cache[oid] = dbrec.fetch_operational_run(client, operational_run_id=oid)
        enriched.append({**row, "operational_run": run_cache.get(oid)})

    by_cat = Counter(str(r.get("failure_category") or "") for r in fails)
    return {
        "failure_count": len(fails),
        "by_category": dict(by_cat),
        "failures": enriched,
    }
