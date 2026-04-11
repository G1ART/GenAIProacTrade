"""Phase 35 operator closeout MD + JSON."""

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


def write_phase35_join_displacement_and_maturity_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    s = bundle.get("closeout_summary") or {}
    b = bundle.get("before") or {}
    a = bundle.get("after") or {}
    di = bundle.get("forward_validation_join_displacement_initial") or {}
    hyp = (di.get("hypothesis_phase34_excess_to_no_state_change_join") or {})

    lines = [
        "# Phase 35 — Join displacement + state_change seam + maturity schedule",
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
        f"- no_state_change_join (after): `{_f(s.get('no_state_change_join'))}`",
        f"- joined_recipe_unlocked_now_count (headline delta): `{_f(s.get('joined_recipe_unlocked_now_count'))}`",
        f"- no_state_change_join_cleared_count: `{_f(s.get('no_state_change_join_cleared_count'))}`",
        f"- matured_eligible_now_count: `{_f(s.get('matured_eligible_now_count'))}`",
        f"- still_not_matured_count: `{_f(s.get('still_not_matured_count'))}`",
        f"- matured_forward_retry_success_count: `{_f(s.get('matured_forward_retry_success_count'))}`",
        f"- price_coverage_repaired_now_count: `{_f(s.get('price_coverage_repaired_now_count'))}`",
        f"- GIS outcome: `{s.get('gis_outcome')}`",
        "",
        "## Hypothesis (23 synchronized → no_state_change_join)",
        "",
        f"- supported_by_counts: `{hyp.get('supported_by_counts')}`",
        f"- included_in_joined_recipe_substrate: `{hyp.get('included_in_joined_recipe_substrate')}`",
        f"- excluded_no_state_change_join: `{hyp.get('excluded_no_state_change_join')}`",
        f"- excluded_other_reason: `{hyp.get('excluded_other_reason')}`",
        "",
        "## Headline substrate (Before → After)",
        "",
        "| Metric | Before | After |",
        "| --- | --- | --- |",
        f"| joined_recipe_substrate_row_count | `{_f(b.get('joined_recipe_substrate_row_count'))}` | `{_f(a.get('joined_recipe_substrate_row_count'))}` |",
        f"| thin_input_share | `{_f(b.get('thin_input_share'))}` | `{_f(a.get('thin_input_share'))}` |",
        f"| missing_excess_return_1q | `{_f(b.get('missing_excess_return_1q'))}` | `{_f(a.get('missing_excess_return_1q'))}` |",
        f"| no_state_change_join | `{_f((b.get('exclusion_distribution') or {}).get('no_state_change_join'))}` | `{_f((a.get('exclusion_distribution') or {}).get('no_state_change_join'))}` |",
        "",
        "## Displacement counts on synchronized set (initial → final)",
        "",
        f"- initial: `{s.get('displacement_synchronized_set_initial')}`",
        f"- final: `{s.get('displacement_synchronized_set_final')}`",
        "",
    ]
    p36 = s.get("phase36") or bundle.get("phase36") or {}
    lines += [
        "## Phase 36 recommendation",
        "",
        f"- `{p36.get('phase36_recommendation')}`",
        f"- {p36.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase35_join_displacement_and_maturity_bundle_json(
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
