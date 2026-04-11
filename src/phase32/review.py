"""Phase 32 클로즈아웃 MD·번들 JSON."""

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


def write_phase32_forward_unlock_and_snapshot_cleanup_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    b = bundle.get("before") or {}
    a = bundle.get("after") or {}
    fwd = bundle.get("forward_return_backfill_phase31_touched") or {}
    sil = bundle.get("silver_present_snapshot_materialization_repair") or {}
    gis = bundle.get("gis_raw_present_no_silver_repair") or {}
    raw = bundle.get("raw_facts_deferred_retry") or {}
    st = bundle.get("stage_transitions") or {}
    p33 = bundle.get("phase33") or {}
    cb = b.get("quarter_snapshot_classification_counts") or {}
    ca = a.get("quarter_snapshot_classification_counts") or {}

    lines = [
        "# Phase 32 — Forward-return unlock (Phase 31 touched) + snapshot cleanup",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        "",
        "## 핵심 지표 (Before → After)",
        "",
        "| 지표 | Before | After |",
        "| --- | --- | --- |",
        f"| joined_recipe_substrate_row_count | `{_f(b.get('joined_recipe_substrate_row_count'))}` | `{_f(a.get('joined_recipe_substrate_row_count'))}` |",
        f"| thin_input_share | `{_f(b.get('thin_input_share'))}` | `{_f(a.get('thin_input_share'))}` |",
        f"| missing_excess_return_1q | `{_f(b.get('missing_excess_return_1q'))}` | `{_f(a.get('missing_excess_return_1q'))}` |",
        f"| missing_validation_symbol_count | `{_f(b.get('missing_validation_symbol_count'))}` | `{_f(a.get('missing_validation_symbol_count'))}` |",
        f"| missing_quarter_snapshot_for_cik | `{_f(b.get('missing_quarter_snapshot_for_cik'))}` | `{_f(a.get('missing_quarter_snapshot_for_cik'))}` |",
        f"| factor_panel_missing_for_resolved_cik | `{_f(b.get('factor_panel_missing_for_resolved_cik'))}` | `{_f(a.get('factor_panel_missing_for_resolved_cik'))}` |",
        "",
        "## 분기 스냅샷 분류 (Before → After)",
        "",
    ]
    keys = sorted(set(cb) | set(ca))
    for k in keys:
        lines.append(f"- `{k}`: `{cb.get(k, 0)}` → `{ca.get(k, 0)}`")

    osum = raw.get("outcome_summary") or {}
    lines += [
        "",
        "## 단계 전이 (워크오더 E — 이름 혼동 금지)",
        "",
        f"- phase31_validation_unblocked_cik_count (번들 근거): `{_f((st.get('phase31_reference') or {}).get('validation_unblocked_cik_count_in_phase31'))}`",
        f"- **forward_return_unlocked_now_count**: `{_f(st.get('forward_return_unlocked_now_count'))}`",
        f"- **quarter_snapshot_materialized_now_count**: `{_f(st.get('quarter_snapshot_materialized_now_count'))}`",
        f"- factor_materialized_now_count (스냅샷 수리 후 cascade): `{_f(st.get('factor_materialized_now_count'))}`",
        f"- validation_panel_refreshed_count (동일 cascade): `{_f(st.get('validation_panel_refreshed_count'))}`",
        f"- downstream_cascade_cik_runs_after_snapshot_repair: `{_f(st.get('downstream_cascade_cik_runs_after_snapshot_repair'))}`",
        f"- gis_seam_actions_count: `{_f(st.get('gis_seam_actions_count'))}`",
        f"- raw_facts_recovered_on_retry_count: `{_f(st.get('raw_facts_recovered_on_retry_count'))}`",
        "",
        "## B. Forward 백필 (Phase 31 터치 상한)",
        "",
        f"- repaired_to_forward_present: `{_f(fwd.get('repaired_to_forward_present'))}`",
        f"- deferred_market_data_gap (error 샘플 기준): `{_f(fwd.get('deferred_market_data_gap'))}`",
        f"- blocked_registry_or_time_window_issue: `{_f(fwd.get('blocked_registry_or_time_window_issue'))}`",
        f"- panels_built: `{_f(fwd.get('panels_built'))}`",
        "",
        "## C. Silver→스냅샷 물질화 누락 수리",
        "",
        f"- snapshot_materialized_now_count: `{_f(sil.get('snapshot_materialized_now_count'))}`",
        "",
        "## D. GIS-like raw→silver",
        "",
        f"- actions: `{_f(len(gis.get('actions') or []))}`",
        "",
        "## Deferred raw facts 재시도",
        "",
        f"- recovered_on_retry: `{_f(osum.get('recovered_on_retry'))}`",
        f"- persistent_external_failure: `{_f(osum.get('persistent_external_failure'))}`",
        f"- persistent_schema_or_mapping_issue: `{_f(osum.get('persistent_schema_or_mapping_issue'))}`",
        "",
        "## Phase 33 recommendation",
        "",
        f"- `{p33.get('phase33_recommendation')}`",
        f"- {p33.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase32_forward_unlock_and_snapshot_cleanup_bundle_json(
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
