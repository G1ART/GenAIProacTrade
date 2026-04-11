"""Phase 41 operator closeout — bundle JSON + review MD."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _try_repo_relative(path_str: str | None) -> str:
    if not path_str:
        return ""
    try:
        return str(Path(path_str).resolve().relative_to(_REPO_ROOT.resolve()))
    except (OSError, ValueError):
        return str(path_str)


def write_phase41_falsifier_substrate_bundle_json(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def write_phase41_falsifier_substrate_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pit = bundle.get("pit_execution") or {}
    gate = bundle.get("promotion_gate_phase41") or {}
    p42 = bundle.get("phase42") or {}
    expl = bundle.get("explanation_v4") or {}
    life = bundle.get("lifecycle_status_distribution") or {}
    filing = pit.get("filing_substrate") or {}
    sector = pit.get("sector_substrate") or {}

    lines = [
        "# Phase 41 — Falsifier substrate (filing + sector)",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        f"_Bundle generated (UTC): `{bundle.get('generated_utc', '')}`_",
        "",
        "## Execution summary",
        "",
        f"- ok: `{bundle.get('ok')}`",
        f"- universe: `{bundle.get('universe_name')}`",
        f"- experiment_id: `{pit.get('experiment_id')}`",
        f"- families_rerun: **{pit.get('families_executed_count')}**",
        f"- all_families_leakage_passed: `{pit.get('all_families_leakage_passed')}`",
        "",
        "## Filing substrate summary",
        "",
        f"- `{filing.get('summary', {})}`",
        "",
        "## Sector substrate summary",
        "",
        f"- `{sector.get('summary', {})}`",
        "",
        "## Family reruns",
        "",
        f"- `{pit.get('families_executed', [])}`",
        "",
        "## Before vs after (Phase 40 ref)",
        "",
        f"- `{bundle.get('family_rerun_before_after', {})}`",
        "",
        "## Lifecycle distribution (after)",
        "",
        f"- `{life}`",
        "",
        "## Promotion gate (v4)",
        "",
        f"- gate_status: `{gate.get('gate_status')}`",
        f"- primary_block_category: `{gate.get('primary_block_category')}`",
        f"- phase41_context: `{gate.get('phase41_context')}`",
        "",
        "## Explanation v4",
        "",
        f"- `{_try_repo_relative(str(expl.get('path') or ''))}`",
        "",
        "## Phase 42 recommendation",
        "",
        f"- **`{p42.get('phase42_recommendation')}`**",
        f"- {p42.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
