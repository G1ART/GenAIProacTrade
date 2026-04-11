"""Phase 36 operator closeout MD + JSON."""

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


def write_phase36_substrate_freeze_and_research_handoff_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    s = bundle.get("closeout_summary") or {}
    fr = bundle.get("substrate_freeze_readiness") or {}
    p37 = bundle.get("phase37") or {}

    lines = [
        "# Phase 36 — Substrate freeze + metadata reconciliation + residual join audit",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        "",
        "## Closeout summary",
        "",
        f"- joined_recipe_substrate_row_count: `{_f(s.get('joined_recipe_substrate_row_count'))}`",
        f"- joined_market_metadata_flagged_count: `{_f(s.get('joined_market_metadata_flagged_count'))}`",
        f"- thin_input_share: `{_f(s.get('thin_input_share'))}`",
        f"- missing_excess_return_1q: `{_f(s.get('missing_excess_return_1q'))}`",
        f"- missing_validation_symbol_count: `{_f(s.get('missing_validation_symbol_count'))}`",
        f"- missing_quarter_snapshot_for_cik: `{_f(s.get('missing_quarter_snapshot_for_cik'))}`",
        f"- factor_panel_missing_for_resolved_cik: `{_f(s.get('factor_panel_missing_for_resolved_cik'))}`",
        f"- no_state_change_join: `{_f(s.get('no_state_change_join'))}`",
        f"- metadata_flags_cleared_now_count: `{_f(s.get('metadata_flags_cleared_now_count'))}`",
        f"- metadata_flags_still_present_count: `{_f(s.get('metadata_flags_still_present_count'))}`",
        f"- no_state_change_join_cleared_now_count: `{_f(s.get('no_state_change_join_cleared_now_count'))}`",
        f"- residual_join_rows_still_blocked_count: `{_f(s.get('residual_join_rows_still_blocked_count'))}`",
        f"- maturity_deferred_symbol_count: `{_f(s.get('maturity_deferred_symbol_count'))}`",
        f"- GIS outcome: `{s.get('gis_outcome')}`",
        "",
        "## Substrate freeze",
        "",
        f"- substrate_freeze_recommendation: `{fr.get('substrate_freeze_recommendation')}`",
        f"- rationale: {fr.get('rationale', '')}",
        "",
        "## Phase 37 recommendation",
        "",
        f"- `{p37.get('phase37_recommendation')}`",
        f"- {p37.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase36_substrate_freeze_and_research_handoff_bundle_json(
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


def write_phase36_1_complete_narrow_integrity_round_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    s = bundle.get("closeout_summary") or {}
    fr = bundle.get("substrate_freeze_readiness") or {}
    p37 = bundle.get("phase37") or {}
    m2 = bundle.get("joined_metadata_reconciliation_two_pass") or {}
    pit = bundle.get("residual_pit_deferral") or {}

    lines = [
        "# Phase 36.1 — Complete narrow integrity round + public-core freeze line",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        "",
        "## Closeout summary",
        "",
        f"- joined_recipe_substrate_row_count: `{_f(s.get('joined_recipe_substrate_row_count'))}`",
        f"- joined_market_metadata_flagged_count: `{_f(s.get('joined_market_metadata_flagged_count'))}`",
        f"- no_state_change_join: `{_f(s.get('no_state_change_join'))}`",
        f"- metadata_flags_cleared_now_count: `{_f(s.get('metadata_flags_cleared_now_count'))}`",
        f"- metadata_flags_still_present_count: `{_f(s.get('metadata_flags_still_present_count'))}`",
        f"- validation_rebuild_target_count_after_hydration: `{_f(s.get('validation_rebuild_target_count_after_hydration'))}`",
        f"- residual_pit_deferred_row_count: `{_f(s.get('residual_pit_deferred_row_count'))}`",
        f"- substrate_freeze_recommendation: `{s.get('substrate_freeze_recommendation')}`",
        f"- phase37_recommendation: `{s.get('phase37_recommendation')}`",
        "",
        "## Metadata reconciliation (two-pass)",
        "",
        f"- bucket counts before: `{s.get('metadata_reconciliation_bucket_counts_before')}`",
        f"- bucket counts mid (after hydration): `{s.get('metadata_reconciliation_bucket_counts_mid')}`",
        f"- bucket counts after (after validation rebuild): `{s.get('metadata_reconciliation_bucket_counts_after')}`",
        f"- validation_rebuild_factor_panels_submitted: `{_f(m2.get('validation_rebuild_factor_panels_submitted'))}`",
        "",
        "## Residual no_state_change_join — PIT lab deferral",
        "",
        f"- policy: `{pit.get('policy')}`",
        f"- deferred_row_count: `{_f(pit.get('deferred_row_count'))}`",
        f"- bucket_counts: `{pit.get('residual_join_bucket_counts')}`",
        f"- symbols_deferred: `{pit.get('symbols_deferred')}`",
        "",
        "## Substrate freeze (re-evaluated)",
        "",
        f"- `{fr.get('substrate_freeze_recommendation')}`",
        f"- {fr.get('rationale', '')}",
        "",
        "## Phase 37",
        "",
        f"- `{p37.get('phase37_recommendation')}`",
        f"- {p37.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase36_1_complete_narrow_integrity_round_bundle_json(
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
