"""Phase 28 클로즈아웃 MD (`phase28_provider_metadata_and_factor_panel_review.md`)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _f(x: Any) -> str:
    if x is None:
        return "null"
    if isinstance(x, float):
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x)


def write_phase28_provider_metadata_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    """번들(JSON)을 사람이 읽는 한 페이지 요약으로 쓴다."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    before = bundle.get("before") or {}
    after = bundle.get("after") or {}
    hyd = (bundle.get("market_metadata_hydration_repair") or {}).get("hydration") or {}
    fac = bundle.get("factor_materialization_repair") or {}
    mat = bundle.get("factor_materialization_report_latest") or {}

    lines = [
        "# Phase 28 — Provider metadata & factor panel materialization",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        "",
        "## 요약",
        "",
        "- **메타데이터 수화**: `run_market_metadata_hydration_repair` 경로(Phase 27)를 오케스트레이션에 포함.",
        "- **팩터·검증 패널**: 스냅샷 대비 factor 패널 누락 → `run_factor_panels_for_cik`, factor 대비 validation 누락 → `run_validation_panel_build_from_rows` (CIK당 상한).",
        "",
        "## Before → After (기판·레지스트리)",
        "",
        f"| 항목 | Before | After |",
        f"| --- | --- | --- |",
        f"| joined_recipe_substrate_row_count | `{_f(before.get('joined_recipe_substrate_row_count'))}` | `{_f(after.get('joined_recipe_substrate_row_count'))}` |",
        f"| joined_market_metadata_flagged_count | `{_f(before.get('joined_market_metadata_flagged_count'))}` | `{_f(after.get('joined_market_metadata_flagged_count'))}` |",
        f"| thin_input_share | `{_f(before.get('thin_input_share'))}` | `{_f(after.get('thin_input_share'))}` |",
        f"| missing_validation_symbol_count | `{_f(before.get('missing_validation_symbol_count'))}` | `{_f(after.get('missing_validation_symbol_count'))}` |",
        f"| registry_blocker_symbol_total | `{_f((before.get('registry_gap_rollup') or {}).get('registry_blocker_symbol_total'))}` | `{_f((after.get('registry_gap_rollup') or {}).get('registry_blocker_symbol_total'))}` |",
        "",
        "## 메타데이터 수화 (마지막 실행)",
        "",
        f"- status: `{hyd.get('status', '')}`",
        f"- provider: `{hyd.get('provider', '')}`",
        f"- provider_rows_returned: `{_f(hyd.get('provider_rows_returned'))}`",
        f"- rows_upserted: `{_f(hyd.get('rows_upserted'))}`",
        f"- rows_already_current: `{_f(hyd.get('rows_already_current'))}`",
        f"- rows_missing_after_requery: `{_f(hyd.get('rows_missing_after_requery'))}`",
        f"- blocked_reason: `{hyd.get('blocked_reason') or ''}`",
        "",
        "## 팩터 물질화 수리",
        "",
        f"- factor_panel_repairs_attempted: `{_f(fac.get('factor_panel_repairs_attempted'))}`",
        f"- validation_panel_repairs_attempted: `{_f(fac.get('validation_panel_repairs_attempted'))}`",
        "",
        "### materialization_bucket_counts (최종 스냅샷)",
        "",
    ]
    mbc = mat.get("materialization_bucket_counts") or {}
    for k in sorted(mbc.keys()):
        lines.append(f"- `{k}`: `{mbc[k]}`")
    lines.extend(
        [
            "",
            "## 프로바이더 메타 no-op 방지",
            "",
            "`MARKET_DATA_PROVIDER=stub` 등으로 `provider_rows_returned=0`이면 수화는 **`blocked`** + `blocked_reason=provider_returned_zero_metadata_rows` 로 종료한다(완료 위장 금지).",
            "Yahoo chart 프로바이더는 차트 구간으로 `avg_daily_volume`·`as_of_date` 등을 채운다.",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    p.write_text(text, encoding="utf-8")
    return str(p)
