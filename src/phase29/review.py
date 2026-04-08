"""Phase 29 클로즈아웃 MD."""

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


def write_phase29_validation_refresh_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    b = bundle.get("before") or {}
    a = bundle.get("after") or {}
    stale = bundle.get("stale_validation_refresh") or {}
    q = bundle.get("quarter_snapshot_backfill_repair") or {}
    p30 = bundle.get("phase30") or {}

    lines = [
        "# Phase 29 — Validation refresh after metadata + quarter snapshot backfill",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        "",
        "## 요약 지표 (Before → After)",
        "",
        f"| 지표 | Before | After |",
        f"| --- | --- | --- |",
        f"| joined_market_metadata_flagged_count | `{_f(b.get('joined_market_metadata_flagged_count'))}` | `{_f(a.get('joined_market_metadata_flagged_count'))}` |",
        f"| missing_quarter_snapshot_for_cik | `{_f(b.get('missing_quarter_snapshot_for_cik'))}` | `{_f(a.get('missing_quarter_snapshot_for_cik'))}` |",
        f"| missing_validation_symbol_count | `{_f(b.get('missing_validation_symbol_count'))}` | `{_f(a.get('missing_validation_symbol_count'))}` |",
        f"| thin_input_share | `{_f(b.get('thin_input_share'))}` | `{_f(a.get('thin_input_share'))}` |",
        "",
        "## Stale validation refresh (메타 플래그)",
        "",
        f"- validation_panels_rebuilt_for_metadata: `{_f(stale.get('validation_panels_rebuilt_for_metadata'))}`",
        f"- validation_metadata_flags_cleared_count: `{_f(stale.get('validation_metadata_flags_cleared_count'))}`",
        f"- validation_metadata_flags_still_present_after: `{_f(stale.get('validation_metadata_flags_still_present_after'))}`",
        f"- candidate_validation_rows: `{_f(stale.get('candidate_validation_rows'))}`",
        "",
        "## Quarter snapshot backfill (상한)",
        "",
        f"- cik_repairs_attempted: `{_f(q.get('cik_repairs_attempted'))}`",
        f"- cik_repairs_succeeded: `{_f(q.get('cik_repairs_succeeded'))}`",
        "",
        "### 분류 스냅샷 (수리 전 counts)",
        "",
    ]
    cls0 = b.get("quarter_snapshot_classification_counts") or {}
    for k in sorted(cls0.keys()):
        lines.append(f"- `{k}`: `{cls0[k]}`")

    cleared = int(stale.get("validation_metadata_flags_cleared_count") or 0)
    jmf_b = b.get("joined_market_metadata_flagged_count")
    jmf_a = a.get("joined_market_metadata_flagged_count")
    mq_b = b.get("missing_quarter_snapshot_for_cik")
    mq_a = a.get("missing_quarter_snapshot_for_cik")
    mv_b = b.get("missing_validation_symbol_count")
    mv_a = a.get("missing_validation_symbol_count")
    moved = False
    try:
        if jmf_b is not None and jmf_a is not None and int(jmf_a) < int(jmf_b):
            moved = True
        if mq_b is not None and mq_a is not None and int(mq_a) < int(mq_b):
            moved = True
        if mv_b is not None and mv_a is not None and int(mv_a) < int(mv_b):
            moved = True
    except (TypeError, ValueError):
        pass
    if cleared > 0:
        moved = True
    cls_moved = bool(cls0) and bool(
        a.get("quarter_snapshot_classification_counts")
    ) and cls0 != (a.get("quarter_snapshot_classification_counts") or {})

    lines.extend(["", "## 수용 기준(워크오더) 대비", ""])
    if moved or cls_moved:
        lines.append(
            "- 이번 번들에서 **지표 개선·플래그 해소·분류 변화** 중 하나 이상이 관측됨(위 표·stale·분류 참고)."
        )
    else:
        lines.append(
            "- **주요 지표가 Before/After에서 동일**하거나, 이번 상한 내 수리로는 델타가 없음. "
            "다음 솔기: `report-quarter-snapshot-backfill-gaps` 분류·`report-stale-validation-metadata-flags` 후보 수·"
            "메타 갭 드라이버(`metadata_asof_misaligned` 등) 재확인."
        )
    lines.extend(
        [
            "",
            "## Phase 30 권고",
            "",
            f"- **`{p30.get('phase30_recommendation', '')}`**",
            f"- rationale: {p30.get('rationale', '')}",
            "",
            "## 비목표 확인",
            "",
            "프리미엄 오픈·임계 완화·Phase 15/16 강제·프로덕션 스코어 경로 변경 없음.",
            "",
        ]
    )
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)
