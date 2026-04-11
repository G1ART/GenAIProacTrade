"""Phase 34 operator closeout MD + JSON."""

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


def write_phase34_forward_validation_propagation_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    s = bundle.get("closeout_summary") or {}
    b = bundle.get("before") or {}
    a = bundle.get("after") or {}
    pgb = bundle.get("propagation_gap_before") or {}
    pcc = (pgb.get("classification_counts") or {})
    pcf = (bundle.get("propagation_gap_final") or {}).get("classification_counts") or {}

    lines = [
        "# Phase 34 — Forward→validation propagation + maturity-aware retry",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        "",
        "## Closeout summary",
        "",
        f"- joined_recipe_substrate_row_count: `{_f(s.get('joined_recipe_substrate_row_count'))}`",
        f"- thin_input_share: `{_f(s.get('thin_input_share'))}`",
        f"- missing_excess_return_1q: `{_f(s.get('missing_excess_return_1q'))}`",
        f"- missing_validation_symbol_count: `{_f(s.get('missing_validation_symbol_count'))}`",
        f"- missing_quarter_snapshot_for_cik: `{_f(s.get('missing_quarter_snapshot_for_cik'))}`",
        f"- factor_panel_missing_for_resolved_cik: `{_f(s.get('factor_panel_missing_for_resolved_cik'))}`",
        f"- forward_row_present_count (final gap): `{_f(s.get('forward_row_present_count'))}`",
        f"- validation_excess_filled_now_count: `{_f(s.get('validation_excess_filled_now_count'))}`",
        f"- symbol_cleared_from_missing_excess_queue_count (after refresh truth): `{_f(s.get('symbol_cleared_from_missing_excess_queue_count'))}`",
        f"- joined_recipe_unlocked_now_count (headline delta): `{_f(s.get('joined_recipe_unlocked_now_count'))}`",
        f"- matured_forward_retry_success_count: `{_f(s.get('matured_forward_retry_success_count'))}`",
        f"- still_not_matured_count: `{_f(s.get('still_not_matured_count'))}`",
        f"- price_coverage_repaired_now_count: `{_f(s.get('price_coverage_repaired_now_count'))}`",
        f"- GIS outcome: `{s.get('gis_outcome')}`",
        f"- GIS blocked_reason: `{s.get('gis_blocked_reason')}`",
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
        "## Propagation gap classification (initial → final)",
        "",
    ]
    for k in sorted(set(pcc.keys()) | set(pcf.keys())):
        lines.append(
            f"- `{k}`: `{pcc.get(k, 0)}` → `{pcf.get(k, 0)}`"
        )

    p35 = s.get("phase35") or bundle.get("phase35") or {}
    lines += [
        "",
        "## Phase 35 recommendation",
        "",
        f"- `{p35.get('phase35_recommendation')}`",
        f"- {p35.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase34_forward_validation_propagation_bundle_json(
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
