"""Phase 40 operator closeout — bundle JSON + review MD."""

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


def write_phase40_family_spec_bindings_bundle_json(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def write_phase40_family_spec_bindings_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pit = bundle.get("pit_execution") or {}
    gate = bundle.get("promotion_gate_phase40") or {}
    p41 = bundle.get("phase41") or {}
    expl = bundle.get("explanation_v3") or {}
    life = bundle.get("lifecycle_status_distribution") or {}
    fam_summ = bundle.get("family_level_summary") or []
    leak_bf = bundle.get("leakage_audit_by_family") or {}
    adv_bf = bundle.get("adversarial_review_count_by_family_tag") or {}

    lines = [
        "# Phase 40 — Family PIT spec bindings + shared leakage audit",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        f"_Bundle generated (UTC): `{bundle.get('generated_utc', '')}`_",
        "",
        "## Execution summary",
        "",
        f"- ok: `{bundle.get('ok')}`",
        f"- universe: `{bundle.get('universe_name')}`",
        f"- experiment_id: `{pit.get('experiment_id')}`",
        f"- families_executed_count: **{bundle.get('families_executed_count')}**",
        f"- implemented_family_spec_count: **{bundle.get('implemented_family_spec_count')}**",
        f"- all_families_leakage_passed: `{pit.get('all_families_leakage_passed')}`",
        "",
        "## Family-level outcomes",
        "",
        f"- `{fam_summ}`",
        "",
        "## Leakage audit by family",
        "",
        f"- `{leak_bf}`",
        "",
        "## Lifecycle distribution (after)",
        "",
        f"- `{life}`",
        "",
        "## Adversarial reviews (Phase 40 family tags)",
        "",
        f"- `{adv_bf}`",
        "",
        "## Promotion gate",
        "",
        f"- gate_status: `{gate.get('gate_status')}`",
        f"- primary_block_category: `{gate.get('primary_block_category')}`",
        f"- phase40_context: `{gate.get('phase40_context')}`",
        "",
        "## Explanation v3",
        "",
        f"- `{_try_repo_relative(str(expl.get('path') or ''))}`",
        "",
        "## Phase 41 recommendation",
        "",
        f"- **`{p41.get('phase41_recommendation')}`**",
        f"- {p41.get('rationale', '')}",
        "",
        "## Persistent writes",
        "",
    ]
    pw = bundle.get("persistent_writes") or {}
    if isinstance(pw, dict):
        for k, v in sorted(pw.items(), key=lambda x: str(x[0])):
            lines.append(f"- `{k}` → `{_try_repo_relative(str(v))}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
