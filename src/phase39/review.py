"""Phase 39 operator closeout — bundle JSON + review MD."""

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


def write_phase39_hypothesis_family_expansion_bundle_json(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def write_phase39_hypothesis_family_expansion_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    gate = bundle.get("promotion_gate_phase39") or {}
    p38 = bundle.get("phase38_evidence_summary") or {}
    contract = bundle.get("pit_runner_family_contract") or {}
    p40 = bundle.get("phase40") or {}
    expl = bundle.get("explanation_v2") or {}
    by_stance = bundle.get("adversarial_review_count_by_stance") or {}
    life = bundle.get("lifecycle_status_distribution") or {}

    lines = [
        "# Phase 39 — Hypothesis family expansion + governance",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        f"_Bundle generated (UTC): `{bundle.get('generated_utc', '')}`_",
        "",
        "## Phase 38 evidence summary (inputs)",
        "",
        f"- pit_ok: `{p38.get('pit_ok')}`",
        f"- leakage_passed: `{p38.get('leakage_passed')}`",
        f"- experiment_id: `{p38.get('experiment_id')}`",
        f"- phase38_resolution_status: `{p38.get('phase38_resolution_status')}`",
        f"- fixture still mismatch all specs: `{p38.get('fixture_still_mismatch_all_specs')}`",
        "",
        "## Deliverables checklist",
        "",
        "- **A. Hypothesis families**: expanded structured hypotheses (draft) + primary lifecycle update.",
        "- **B. Lifecycle**: append-only `lifecycle_transitions` on status change.",
        "- **C. Adversarial**: original preserved; multi-stance reviews appended.",
        "- **D. PIT contract**: `pit_runner_family_contract` in bundle.",
        "- **E. Gate**: lifecycle-aware `primary_block_category` + history append.",
        "- **F. Explanation v2**: path below.",
        "",
        "## Hypothesis family count",
        "",
        f"- **{bundle.get('hypothesis_family_count')}**",
        "",
        "## Lifecycle status distribution",
        "",
        f"- `{life}`",
        "",
        "## Adversarial review count by stance",
        "",
        f"- `{by_stance}`",
        "",
        "## Promotion gate",
        "",
        f"- gate_status: `{gate.get('gate_status')}`",
        f"- primary_block_category: `{gate.get('primary_block_category')}`",
        f"- lifecycle_snapshot: `{gate.get('lifecycle_snapshot')}`",
        "",
        "## PIT runner family contract (summary)",
        "",
        f"- contract_version: `{contract.get('contract_version')}`",
        f"- fixture_class: `{contract.get('fixture_class')}`",
        f"- family_bindings: **{len(contract.get('family_bindings') or [])}** entries",
        f"- leakage reused across families: `{contract.get('leakage_audit', {}).get('reused_across_families')}`",
        "",
        "## Explanation v2 output path",
        "",
        f"- `{_try_repo_relative(str(expl.get('path') or ''))}`",
        "",
        "## Phase 40 recommendation",
        "",
        f"- **`{p40.get('phase40_recommendation')}`**",
        f"- {p40.get('rationale', '')}",
        "",
        "## Persistent writes",
        "",
    ]
    pw = bundle.get("persistent_writes") or {}
    if isinstance(pw, dict):
        for k, v in sorted(pw.items(), key=lambda x: str(x[0])):
            lines.append(f"- `{k}` → `{_try_repo_relative(str(v))}`")
    else:
        lines.append(f"- `{pw}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
