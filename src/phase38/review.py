"""Phase 38 operator closeout."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_phase38_db_bound_pit_runner_bundle_json(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return str(p.resolve())


def write_phase38_db_bound_pit_runner_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pit = bundle.get("pit_execution") or {}
    adv = bundle.get("adversarial_review_updated") or {}
    gate = bundle.get("promotion_gate_v1") or {}
    p39 = bundle.get("phase39") or {}
    cb = bundle.get("casebook_update_summary") or {}
    leak = pit.get("leakage_audit") or {}

    lines = [
        "# Phase 38 — DB-bound PIT runner (alternate specs)",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        f"_Bundle generated (UTC): `{bundle.get('generated_utc', '')}`_",
        "",
        "## PIT execution",
        "",
        f"- ok: `{bundle.get('ok')}`",
        f"- experiment_id: `{pit.get('experiment_id')}`",
        f"- universe: `{bundle.get('universe_name')}`",
        f"- baseline_run_id: `{pit.get('runs_resolved', {}).get('baseline_run_id')}`",
        f"- alternate_run_id: `{pit.get('runs_resolved', {}).get('alternate_run_id')}`",
        "",
        "### Executed specs",
        "",
    ]
    for s in pit.get("executed_specs") or []:
        lines.append(f"- `{s.get('spec_key')}` — run `{s.get('state_change_run_id')}`")
    lines.extend(
        [
            "",
            "### Summary counts (raw)",
            "",
            f"- baseline: `{pit.get('summary_counts', {}).get('baseline')}`",
            f"- alternate_prior_run: `{pit.get('summary_counts', {}).get('alternate_prior_run')}`",
            f"- lag: `{pit.get('summary_counts', {}).get('lag_signal_bound')}`",
            "",
            "### Standard rollup (four buckets)",
            "",
            f"- `{bundle.get('summary_counts_standard')}`",
            "",
            "## Leakage audit",
            "",
            f"- passed: `{leak.get('passed')}`",
            f"- violations: {len(leak.get('violations') or [])}",
            "",
            "## Adversarial review",
            "",
            f"- phase38_resolution_status: `{adv.get('phase38_resolution_status')}`",
            f"- leakage_audit_passed: `{adv.get('phase38_leakage_audit_passed')}`",
            f"- evidence: {adv.get('phase38_evidence_summary', '')[:500]}",
            "",
            "## Promotion gate v1",
            "",
            f"- gate_status: `{gate.get('gate_status')}`",
            f"- blocking_reasons: `{gate.get('blocking_reasons')}`",
            "",
            "## Casebook",
            "",
            f"- `{cb}`",
            "",
            "## Explanation surface",
            "",
            f"- `{bundle.get('explanation_surface', {}).get('path')}`",
            "",
            "## Phase 39 recommendation",
            "",
            f"- **`{p39.get('phase39_recommendation')}`**",
            f"- {p39.get('rationale', '')}",
            "",
        ]
    )
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
