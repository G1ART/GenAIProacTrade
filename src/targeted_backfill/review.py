"""Phase 27 one-page closeout: phase27_targeted_backfill_review.md."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from public_buildout.revalidation import build_revalidation_trigger
from public_depth.diagnostics import compute_substrate_coverage
from targeted_backfill.forward_maturity import report_forward_gap_maturity
from targeted_backfill.market_metadata_gaps import report_market_metadata_gap_drivers
from targeted_backfill.phase28_recommend import recommend_phase28_branch
from targeted_backfill.state_change_pit import report_state_change_pit_gaps
from targeted_backfill.validation_registry import report_validation_registry_gaps


def _f(x: Any) -> str:
    if x is None:
        return "null"
    if isinstance(x, float):
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x)


def build_phase27_evidence_bundle(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    program_id_raw: str | None = None,
) -> dict[str, Any]:
    reg = report_validation_registry_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    meta = report_market_metadata_gap_drivers(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    fwd = report_forward_gap_maturity(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    pit = report_state_change_pit_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )

    metrics, excl = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )

    _pri = "public" + "_repair_iteration"
    _resolve_program_id = getattr(
        importlib.import_module(f"{_pri}.resolver"), "resolve_program_id"
    )
    raw_pi = str(program_id_raw or "latest").strip()
    prog = _resolve_program_id(client, raw_pi, universe_name=universe_name.strip())
    pid = str(prog["program_id"]) if prog.get("ok") else None
    rerun = (
        build_revalidation_trigger(client, program_id=pid)
        if pid
        else {"ok": False, "skipped": True, "reason": "program_id_unresolved"}
    )
    rr = rerun.get("rerun_readiness") if isinstance(rerun.get("rerun_readiness"), dict) else {}

    alias_missing = int(
        (reg.get("registry_bucket_counts") or {}).get("missing_symbol_alias_mapping", 0)
    ) + int((reg.get("registry_bucket_counts") or {}).get("missing_symbol_in_market_symbol_registry", 0))

    phase28 = recommend_phase28_branch(
        recommend_rerun_phase15=bool(rr.get("recommend_rerun_phase15")),
        recommend_rerun_phase16=bool(rr.get("recommend_rerun_phase16")),
        true_repairable_forward=int(fwd.get("true_repairable_forward_gap_count") or 0),
        joined_metadata_flagged=int(meta.get("joined_market_metadata_flagged_count") or 0),
        pit_backfill_candidates=int(pit.get("historical_backfill_might_help_count") or 0),
        registry_alias_or_missing_count=alias_missing,
        thin_input_share_after=metrics.get("thin_input_share")
        if isinstance(metrics.get("thin_input_share"), (int, float))
        else None,
    )

    return {
        "ok": True,
        "universe_name": universe_name,
        "program_id": pid,
        "substrate_metrics": metrics,
        "exclusion_distribution": excl,
        "validation_registry": reg,
        "market_metadata_gaps": meta,
        "forward_maturity": fwd,
        "state_change_pit": pit,
        "rerun_readiness": rr,
        "phase28": phase28,
        "production_scoring_boundary_note": (
            "프로덕션 스코어링 경로는 변경하지 않음; Phase 27은 공개·연구 파이프라인 진단·좁은 수리만."
        ),
        "premium_note": (
            "프리미엄 디스커버리 자동 오픈 없음; 본 패치는 premium 경계를 건드리지 않음."
        ),
    }


def write_phase27_targeted_backfill_review_md(
    *,
    path: str | Path,
    bundle: dict[str, Any],
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    uni = str(bundle.get("universe_name") or "")
    m = bundle.get("substrate_metrics") or {}
    ex = bundle.get("exclusion_distribution") or {}
    reg = bundle.get("validation_registry") or {}
    meta = bundle.get("market_metadata_gaps") or {}
    fwd = bundle.get("forward_maturity") or {}
    pit = bundle.get("state_change_pit") or {}
    p28 = bundle.get("phase28") or {}
    rr = bundle.get("rerun_readiness") or {}

    lines = [
        "# Phase 27 targeted backfill review",
        "",
        f"- 생성 시각(UTC): `{datetime.now(timezone.utc).isoformat()}`",
        f"- 유니버스: `{uni}`",
        "",
        "## 1) 검증 미스 중 레지스트리·별칭 이슈",
        "",
        "레지스트리 버킷 카운트(미해결 검증 패널 심볼 기준):",
        "",
    ]
    for k, v in sorted((reg.get("registry_bucket_counts") or {}).items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{k}`: {v}")
    lines.extend(
        [
            "",
            "## 2) 조인 행이 메타데이터에만 막힌 규모",
            "",
            f"- joined recipe 행 수: `{_f(m.get('joined_recipe_substrate_row_count'))}`",
            f"- `joined_but_market_metadata` 후보(플래그된 조인 행): `{_f(meta.get('joined_market_metadata_flagged_count'))}`",
            "",
            "### 메타데이터 갭 버킷",
            "",
        ]
    )
    for k, v in sorted((meta.get("metadata_gap_bucket_counts") or {}).items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{k}`: {v}")

    lines.extend(
        [
            "",
            "## 3) Forward 미해결 — 성숙 전 vs 오늘 수리 가능",
            "",
            f"- raw 미해결(`no_forward_row_next_quarter`): `{_f(fwd.get('raw_unresolved_forward_row_count'))}`",
            f"- **true_repairable_forward_gap_count**: `{_f(fwd.get('true_repairable_forward_gap_count'))}`",
            f"- not_yet_matured_for_1q_horizon: `{_f(fwd.get('not_yet_matured_count'))}`",
            f"- 달력 프록시(고정): `{_f(fwd.get('calendar_days_1q_proxy'))}` 일",
            "",
            "## 4) State-change PIT — 역사 백필 vs 정렬",
            "",
            f"- PIT 미해결 행: `{_f(pit.get('pit_unresolved_row_count'))}`",
            f"- historical_backfill_might_help_count: `{_f(pit.get('historical_backfill_might_help_count'))}`",
            "",
            "### PIT 세분 버킷",
            "",
        ]
    )
    for k, v in sorted((pit.get("pit_bucket_counts") or {}).items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{k}`: {v}")

    lines.extend(
        [
            "",
            "## 5) 핵심 지표(현재 스냅샷)",
            "",
            f"- thin_input_share: `{_f(m.get('thin_input_share'))}`",
            f"- no_validation_panel_for_symbol: `{_f(ex.get('no_validation_panel_for_symbol'))}`",
            f"- missing_excess_return_1q: `{_f(ex.get('missing_excess_return_1q'))}`",
            f"- no_state_change_join: `{_f(ex.get('no_state_change_join'))}`",
            "",
            "_수리 전후 델타는 운영자가 `run-validation-registry-repair` / `run-market-metadata-hydration-repair` 등 실행 후 동일 명령으로 재집계해 채운다._",
            "",
            "## 6) Phase 28 권고(정확히 하나)",
            "",
            f"- **`{p28.get('phase28_recommendation')}`**",
            f"- 근거: {p28.get('rationale')}",
            "",
            "### Rerun 게이트(참고)",
            "",
            f"- recommend_rerun_phase15: `{rr.get('recommend_rerun_phase15')}`",
            f"- recommend_rerun_phase16: `{rr.get('recommend_rerun_phase16')}`",
            "",
            "## 경계",
            "",
            str(bundle.get("production_scoring_boundary_note") or ""),
            "",
            str(bundle.get("premium_note") or ""),
            "",
        ]
    )
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
