"""Phase 43 operator closeout — bundle JSON, review MD, before/after audit MD, explanation v6."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase43.before_after_audit import render_before_after_audit_md
from phase43.explanation_v6 import render_phase43_explanation_v6_md

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _try_repo_relative(path_str: str | None) -> str:
    if not path_str:
        return ""
    try:
        return str(Path(path_str).resolve().relative_to(_REPO_ROOT.resolve()))
    except (OSError, ValueError):
        return str(path_str)


def write_phase43_targeted_substrate_backfill_bundle_json(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def write_phase43_targeted_substrate_before_after_audit_md(
    out_path: str,
    *,
    rows: list[dict[str, Any]],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_before_after_audit_md(rows=rows), encoding="utf-8")
    return str(p.resolve())


def write_phase43_targeted_substrate_backfill_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    expl = bundle.get("explanation_v6") or {}
    lines = [
        "# Phase 43 — Bounded targeted substrate backfill",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        f"_Bundle generated (UTC): `{bundle.get('generated_utc', '')}`_",
        "",
        "## Summary",
        "",
        f"- ok: `{bundle.get('ok')}`",
        f"- universe: `{bundle.get('universe_name')}`",
        f"- input Phase 42 bundle: `{bundle.get('input_phase42_supabase_bundle_path')}`",
        f"- phase42_rerun_used_supabase_fresh: `{bundle.get('phase42_rerun_used_supabase_fresh')}`",
        "",
        "## Scorecard before / after (Phase 42)",
        "",
        f"- before: `{bundle.get('scorecard_before')}`",
        f"- after: `{bundle.get('scorecard_after')}`",
        f"- digest: `{bundle.get('stable_run_digest_before')}` → `{bundle.get('stable_run_digest_after')}`",
        "",
        "## Gate before / after",
        "",
        f"- before: `{ (bundle.get('gate_before') or {}).get('primary_block_category')}`",
        f"- after: `{ (bundle.get('gate_after') or {}).get('primary_block_category')}`",
        "",
        "## Phase 44",
        "",
        f"- **`{(bundle.get('phase44') or {}).get('phase44_recommendation')}`**",
        f"- {(bundle.get('phase44') or {}).get('rationale', '')}",
        "",
        "## Artifacts",
        "",
        f"- Before/after audit: `{_try_repo_relative(str(bundle.get('before_after_audit_md_path') or ''))}`",
        f"- Explanation v6: `{_try_repo_relative(str(expl.get('path') or ''))}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
