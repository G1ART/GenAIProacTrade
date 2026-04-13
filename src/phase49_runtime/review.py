"""Phase 49 bundle + review markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase49_daemon_scheduler_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase49_daemon_scheduler_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    agg = bundle.get("aggregate_metrics") or {}
    p50 = bundle.get("phase50") or {}
    lines = [
        "# Phase 49 — Daemon scheduler (multi-cycle triggers & metrics)",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Phase 46 input**: `{bundle.get('input_phase46_bundle_path')}`",
        f"- **Cycles requested**: **{bundle.get('cycles_requested')}**",
        f"- **Sleep between cycles (s)**: **{bundle.get('sleep_seconds_between_cycles')}**",
        "",
        "## Aggregate metrics",
        "",
        "```json",
        json.dumps(agg, indent=2),
        "```",
        "",
        "## Per-cycle summary",
        "",
    ]
    for s in bundle.get("cycle_summaries") or []:
        lines.append(
            f"- Cycle **{s.get('cycle_index')}**: triggers={s.get('n_triggers')}, "
            f"jobs_created={s.get('n_jobs_created')}, jobs_executed={s.get('n_jobs_executed')}, "
            f"debates={s.get('n_bounded_debate_outputs')}"
        )
    lines.extend(
        [
            "",
            "## Phase 50 (next fork token)",
            "",
            f"- **`{p50.get('phase50_recommendation')}`**",
            "",
        ]
    )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
