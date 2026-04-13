"""Phase 48 bundle + review markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase48_proactive_research_runtime_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase48_proactive_research_runtime_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p49 = bundle.get("phase49") or {}
    lines = [
        "# Phase 48 — Proactive research runtime (single cycle)",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Phase 46 input**: `{bundle.get('input_phase46_bundle_path')}`",
        "",
        "## Triggers (this cycle)",
        "",
        f"- Count: **{len(bundle.get('trigger_results') or [])}**",
        "",
        "## Jobs",
        "",
        f"- Created: **{len(bundle.get('jobs_created') or [])}**",
        f"- Executed: **{len(bundle.get('jobs_executed') or [])}**",
        "",
        "## Bounded debate",
        "",
        f"- Outputs: **{len(bundle.get('bounded_debate_outputs') or [])}**",
        "",
        "## Premium escalation candidates",
        "",
        f"- Count: **{len(bundle.get('premium_escalation_candidates') or [])}**",
        "",
        "## Discovery candidates (not recommendations)",
        "",
        f"- New this cycle: **{len(bundle.get('discovery_candidates') or [])}**",
        "",
        "## Cockpit surface",
        "",
        f"- Output records: **{len(bundle.get('cockpit_surface_outputs') or [])}**",
        "",
        "## Budget policy",
        "",
        "```json",
        json.dumps(bundle.get("budget_policy") or {}, indent=2),
        "```",
        "",
        "## Phase 49",
        "",
        f"- **`{p49.get('phase49_recommendation')}`**",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
