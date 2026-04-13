"""Multi-cycle scheduler: runs Phase 48 proactive runtime N times, aggregates metrics."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase48_runtime.orchestrator import run_phase48_proactive_research_runtime

from phase49_runtime.phase50_recommend import recommend_phase50


def run_phase49_daemon_scheduler_multi_cycle(
    *,
    phase46_bundle_in: str,
    cycles: int = 2,
    sleep_seconds: float = 0.0,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
    discovery_path: Path | None = None,
    decision_ledger_path: Path | None = None,
    skip_alerts: bool = False,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    p46_in = Path(phase46_bundle_in)
    p46_resolved = p46_in if p46_in.is_absolute() else (root / p46_in).resolve()

    n = max(1, int(cycles))
    sleep_s = max(0.0, float(sleep_seconds))

    cycle_results: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    t0 = time.perf_counter()

    for i in range(n):
        if i > 0 and sleep_s > 0:
            time.sleep(sleep_s)
        cyc = run_phase48_proactive_research_runtime(
            phase46_bundle_in=str(p46_resolved),
            repo_root=root,
            registry_path=registry_path,
            discovery_path=discovery_path,
            decision_ledger_path=decision_ledger_path,
            skip_alerts=skip_alerts,
        )
        cycle_results.append(cyc)
        cockpit = cyc.get("cockpit_surface_outputs") or []
        alert_like = sum(
            1 for o in cockpit if isinstance(o, dict) and o.get("kind") == "alert_ledger_append"
        )
        summaries.append(
            {
                "cycle_index": i,
                "phase48_generated_utc": cyc.get("generated_utc"),
                "n_triggers": len(cyc.get("trigger_results") or []),
                "n_jobs_created": len(cyc.get("jobs_created") or []),
                "n_jobs_executed": len(cyc.get("jobs_executed") or []),
                "n_bounded_debate_outputs": len(cyc.get("bounded_debate_outputs") or []),
                "n_discovery_candidates": len(cyc.get("discovery_candidates") or []),
                "n_cockpit_surface_outputs": len(cockpit),
                "n_alert_ledger_appends_observed": alert_like,
            }
        )

    elapsed = time.perf_counter() - t0
    completed = len(summaries)
    total_jobs = sum(s["n_jobs_created"] for s in summaries)

    aggregate_metrics: dict[str, Any] = {
        "cycles_completed": completed,
        "total_triggers": sum(s["n_triggers"] for s in summaries),
        "total_jobs_created": total_jobs,
        "total_jobs_executed": sum(s["n_jobs_executed"] for s in summaries),
        "total_bounded_debate_outputs": sum(s["n_bounded_debate_outputs"] for s in summaries),
        "total_discovery_candidates": sum(s["n_discovery_candidates"] for s in summaries),
        "total_cockpit_surface_outputs": sum(s["n_cockpit_surface_outputs"] for s in summaries),
        "total_alert_ledger_appends_observed": sum(
            s["n_alert_ledger_appends_observed"] for s in summaries
        ),
        "elapsed_seconds": round(elapsed, 6),
        "jobs_created_avg_per_cycle": round(total_jobs / completed, 4) if completed else 0.0,
    }

    gen = datetime.now(timezone.utc).isoformat()
    return {
        "ok": True,
        "phase": "phase49_daemon_scheduler_multi_cycle_triggers_and_metrics_v1",
        "generated_utc": gen,
        "input_phase46_bundle_path": str(p46_resolved),
        "cycles_requested": n,
        "sleep_seconds_between_cycles": sleep_s,
        "cycle_summaries": summaries,
        "aggregate_metrics": aggregate_metrics,
        "phase48_cycles": cycle_results,
        "last_phase48_cycle": cycle_results[-1] if cycle_results else {},
        "phase50": recommend_phase50(),
    }
