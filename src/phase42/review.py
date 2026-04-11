"""Phase 42 operator closeout — bundle JSON + review MD."""

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


def write_phase42_evidence_accumulation_bundle_json(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def write_phase42_evidence_accumulation_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    gate = bundle.get("promotion_gate_phase42") or {}
    score = bundle.get("family_evidence_scorecard") or {}
    disc = bundle.get("discrimination_summary") or {}
    narrow = bundle.get("hypothesis_narrowing") or {}
    p43 = bundle.get("phase43") or {}
    expl = bundle.get("explanation_v5") or {}

    lines = [
        "# Phase 42 — Evidence accumulation",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        f"_Bundle generated (UTC): `{bundle.get('generated_utc', '')}`_",
        "",
        "## Execution summary",
        "",
        f"- ok: `{bundle.get('ok')}`",
        f"- phase41_bundle: `{bundle.get('phase41_bundle_path', '')}`",
        f"- stable_run_digest: `{bundle.get('stable_run_digest', '')}`",
        "",
        "## Scorecard",
        "",
        f"- `{score}`",
        "",
        "## Discrimination",
        "",
        f"- `{disc}`",
        "",
        "## Narrowing",
        "",
        f"- `{narrow}`",
        "",
        "## Promotion gate",
        "",
        f"- gate_status: `{gate.get('gate_status')}`",
        f"- primary_block_category: `{gate.get('primary_block_category')}`",
        f"- phase42_context: `{gate.get('phase42_context')}`",
        "",
        "## Explanation v5",
        "",
        f"- `{_try_repo_relative(str(expl.get('path') or ''))}`",
        "",
        "## Phase 43 recommendation",
        "",
        f"- **`{p43.get('phase43_recommendation')}`**",
        f"- {p43.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
