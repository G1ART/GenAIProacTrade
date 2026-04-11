"""Phase 33 operator closeout MD + JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _f(x: Any) -> str:
    if x is None:
        return "null"
    if isinstance(x, float):
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x)


def write_phase33_forward_coverage_truth_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    b = bundle.get("before") or {}
    a = bundle.get("after") or {}
    st = bundle.get("stage_semantics_truth") or {}
    mt = bundle.get("metric_truth_audit_after") or {}
    pc = bundle.get("price_coverage_backfill") or {}
    pcr = bundle.get("price_coverage_gap_report") or {}
    gis = bundle.get("gis_deterministic_inspect") or {}
    p34 = bundle.get("phase34") or {}
    cb = b.get("quarter_snapshot_classification_counts") or {}
    ca = (a.get("quarter_snapshot_classification_counts") or {}) or cb

    q_after = bundle.get("quarter_snapshot_classification_counts_after") or ca

    lines = [
        "# Phase 33 — Forward coverage truth + metric alignment",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        "",
        "## Truth semantics (do not conflate)",
        "",
        f"- **forward_row_unblocked_now_count** (forward upsert ops this run): `{_f(st.get('forward_row_unblocked_now_count'))}`",
        f"- **symbol_cleared_from_missing_excess_queue_count** (touched-set truth, live): `{_f(st.get('symbol_cleared_from_missing_excess_queue_count'))}`",
        f"- **joined_recipe_unlocked_now_count** (delta): `{_f(st.get('joined_recipe_unlocked_now_count'))}`",
        f"- **price_coverage_repaired_now_count**: `{_f(st.get('price_coverage_repaired_now_count'))}`",
        f"- excess-null rows on touched symbols (live): `{_f(st.get('validation_panel_excess_null_rows_touched_set_live'))}`",
        "",
        "## Headline substrate (Before → After)",
        "",
        "| Metric | Before | After |",
        "| --- | --- | --- |",
        f"| joined_recipe_substrate_row_count | `{_f(b.get('joined_recipe_substrate_row_count'))}` | `{_f(a.get('joined_recipe_substrate_row_count'))}` |",
        f"| thin_input_share | `{_f(b.get('thin_input_share'))}` | `{_f(a.get('thin_input_share'))}` |",
        f"| missing_excess_return_1q | `{_f(b.get('missing_excess_return_1q'))}` | `{_f(a.get('missing_excess_return_1q'))}` |",
        f"| missing_validation_symbol_count | `{_f(b.get('missing_validation_symbol_count'))}` | `{_f(a.get('missing_validation_symbol_count'))}` |",
        f"| missing_quarter_snapshot_for_cik | `{_f(b.get('missing_quarter_snapshot_for_cik'))}` | `{_f(a.get('missing_quarter_snapshot_for_cik'))}` |",
        f"| factor_panel_missing_for_resolved_cik | `{_f(b.get('factor_panel_missing_for_resolved_cik'))}` | `{_f(a.get('factor_panel_missing_for_resolved_cik'))}` |",
        "",
        "## Quarter snapshot classification (end of run)",
        "",
    ]
    for k in sorted(q_after.keys()):
        lines.append(f"- `{k}`: `{q_after.get(k)}`")

    cc = (pcr.get("classification_counts") or {})
    lines += [
        "",
        "## Price coverage classification (Phase 32 NQ failures)",
        "",
    ]
    for k in sorted(cc.keys()):
        lines.append(f"- `{k}`: `{cc.get(k)}`")

    lines += [
        "",
        "## Price backfill",
        "",
        f"- repaired: `{_f(pc.get('price_coverage_repaired_now_count'))}`",
        f"- deferred: `{_f(pc.get('price_coverage_deferred_count'))}`",
        f"- blocked: `{_f(pc.get('price_coverage_blocked_count'))}`",
        "",
        "## Why Phase 32 repair count vs headline",
        "",
        str(mt.get("why_repaired_count_did_not_reduce_headline_excess") or ""),
        "",
        "## GIS (narrow)",
        "",
        f"- outcome: `{gis.get('outcome')}`",
        f"- blocked_reason: `{gis.get('blocked_reason')}`",
        "",
        "## Phase 34 recommendation",
        "",
        f"- `{p34.get('phase34_recommendation')}`",
        f"- {p34.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase33_forward_coverage_truth_bundle_json(
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
