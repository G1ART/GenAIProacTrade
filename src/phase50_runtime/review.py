"""Write Phase 50 operator_closeout bundles and review markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase50_registry_controls_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase50_registry_controls_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    lines = [
        "# Phase 50 — Registry controls & operator timing",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Phase 49 input**: `{bundle.get('input_phase49_bundle_path')}`",
        "",
        "## Control plane",
        "",
        "```json",
        json.dumps(bundle.get("control_plane_state"), indent=2, ensure_ascii=False)[:8000],
        "```",
        "",
        "## Trigger controls (effective summary)",
        "",
        "```json",
        json.dumps(bundle.get("trigger_controls"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Runtime audit (tail summary)",
        "",
        "```json",
        json.dumps(bundle.get("runtime_audit_summary"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Phase 51",
        "",
        f"- **`{(bundle.get('phase51') or {}).get('phase51_recommendation')}`**",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase50_positive_path_smoke_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase50_positive_path_smoke_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    lines = [
        "# Phase 50 — Positive path smoke (operator-seeded)",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **OK (metrics)**: `{bundle.get('smoke_metrics_ok')}` / bundle `ok`: `{bundle.get('ok')}`",
        f"- **Seeded source**: `{bundle.get('seeded_trigger_source')}` → job `{bundle.get('seeded_job_type')}`",
        "",
        "## Counts",
        "",
        f"- Triggers: **{len(bundle.get('trigger_results') or [])}**",
        f"- Jobs created: **{len(bundle.get('jobs_created') or [])}**",
        f"- Jobs executed: **{len(bundle.get('jobs_executed') or [])}**",
        f"- Bounded debates: **{len(bundle.get('bounded_debate_outputs') or [])}**",
        f"- Premium candidates: **{len(bundle.get('premium_escalation_candidates') or [])}**",
        f"- Discovery candidates: **{len(bundle.get('discovery_candidates') or [])}**",
        f"- Cockpit outputs: **{len(bundle.get('cockpit_surface_outputs') or [])}**",
        "",
        "## Isolation paths",
        "",
        f"- Registry: `{bundle.get('isolated_registry_path')}`",
        f"- Discovery: `{bundle.get('isolated_discovery_path')}`",
        "",
        "## Phase 51",
        "",
        f"- **`{(bundle.get('phase51') or {}).get('phase51_recommendation')}`**",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
