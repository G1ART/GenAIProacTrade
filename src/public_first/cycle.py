"""Alternating public-first cycle coordinator + founder-readable review artifact (Phase 24)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Settings
from db import records as dbrec
from db.client import get_supabase_client
from operator_closeout.next_step import choose_post_patch_next_action
from public_first.census import build_public_first_branch_census
from public_first.plateau_review import (
    MIXED_OR_INSUFFICIENT_EVIDENCE,
    PREMIUM_DISCOVERY_REVIEW_PREPARABLE,
    PUBLIC_FIRST_STILL_IMPROVING,
    conclude_public_first_plateau_review,
)
from public_repair_iteration.depth_iteration import (
    advance_public_depth_iteration,
    resolve_iteration_series_for_operator,
)
from public_repair_iteration.service import advance_public_repair_series


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _last_iteration_member_kind(client: Any, *, series_id: str) -> str:
    members = dbrec.list_public_repair_iteration_members_for_series(
        client, series_id=series_id
    )
    if not members:
        return ""
    last = members[-1]
    if last.get("public_depth_run_id") or str(last.get("member_kind") or "") == "public_depth":
        return "public_depth"
    return "repair_campaign"


def recommend_next_public_first_command(
    *,
    universe: str,
    plateau_conclusion: str,
    executed_action: str | None,
) -> str:
    if plateau_conclusion == PREMIUM_DISCOVERY_REVIEW_PREPARABLE:
        return (
            "프리미엄 디스커버리는 리뷰 전용입니다. "
            f"`export-public-repair-escalation-brief --program-id latest --universe {universe} --out docs/public_repair/escalation_review.json` "
            "로 체크리스트를 확인하세요. 라이브 통합 없음."
        )
    if executed_action == "advance_repair_series":
        return (
            f"다음 권장: `advance-public-first-cycle --universe {universe}` "
            "(교대 리듬) 또는 `run-post-patch-closeout --universe {universe}`."
        )
    if executed_action == "advance_public_depth_iteration":
        return (
            f"다음 권장: `advance-public-first-cycle --universe {universe}` "
            "또는 `run-post-patch-closeout --universe {universe}`."
        )
    return (
        f"다음 권장: `run-post-patch-closeout --universe {universe}` "
        f"또는 `advance-public-first-cycle --universe {universe}`."
    )


def write_latest_public_first_review_md(
    path: Path,
    *,
    census: dict[str, Any],
    plateau_review: dict[str, Any],
    cycle_payload: dict[str, Any] | None = None,
    recommended_command: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    agg_b = census.get("aggregated_persisted_escalation_branch_counts") or {}
    top_branch = max(agg_b, key=lambda k: agg_b[k]) if agg_b else "(none)"
    lines = [
        "# Public-first empirical review (Phase 24)",
        "",
        f"- **Generated (UTC)**: `{_now_iso()}`",
        "",
        "## Branch census (aggregated)",
        "",
        f"- **Series included**: {census.get('series_included_count', 0)}",
        f"- **Included runs (sum, quarantine default)**: {census.get('sum_included_run_count')}",
        f"- **Excluded infra failures (sum)**: {census.get('sum_excluded_infra_failure_count')}",
        f"- **Dominant persisted escalation branch (raw counts)**: `{top_branch}`",
        "",
        "```json",
        json.dumps(agg_b, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Depth operator signal counts (per series snapshot)",
        "",
        "```json",
        json.dumps(census.get("aggregated_depth_operator_signal_counts") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Improvement classifications (aggregated / deduped)",
        "",
        "```json",
        json.dumps(census.get("deduped_improvement_classification_counts") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Latest rerun readiness (program)",
        "",
        "```json",
        json.dumps(census.get("latest_rerun_readiness") or {}, indent=2, ensure_ascii=False, default=str),
        "```",
        "",
        "## Plateau review conclusion",
        "",
        f"- **Conclusion**: `{plateau_review.get('conclusion')}`",
        f"- **Reason**: {plateau_review.get('reason')}",
        f"- **Premium live integration**: {plateau_review.get('premium_live_integration')}",
        "",
    ]
    if cycle_payload:
        lines += [
            "## Cycle execution",
            "",
            f"- **Chosen action**: `{cycle_payload.get('chosen_action')}`",
            f"- **Executed**: {cycle_payload.get('executed')}",
            f"- **Success**: {cycle_payload.get('success')}",
            "",
        ]
    excl_raw = json.dumps(
        census.get("exclusions") or [], indent=2, ensure_ascii=False, default=str
    )
    if len(excl_raw) > 12000:
        excl_raw = excl_raw[:12000] + "\n... truncated"
    lines += [
        "## Exclusions (hygiene)",
        "",
        "```json",
        excl_raw,
        "```",
        "",
        "## Recommended next command",
        "",
        recommended_command,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def export_public_first_plateau_review_bundle(
    client: Any,
    *,
    program_id: str,
    universe_name: str,
    include_closed_series: bool = False,
    series_scan_limit: int = 30,
) -> dict[str, Any]:
    census = build_public_first_branch_census(
        client,
        program_id=program_id,
        universe_name=universe_name,
        series_scan_limit=series_scan_limit,
        include_closed_series=include_closed_series,
    )
    pr = conclude_public_first_plateau_review(census=census)
    return {"ok": True, "census": census, "plateau_review": pr}


def advance_public_first_cycle(
    settings: Settings,
    *,
    program_id: str,
    universe_name: str,
    out_stem: str = "docs/operator_closeout",
    include_closed_series: bool = False,
    series_scan_limit: int = 30,
) -> dict[str, Any]:
    """
    Census → plateau review → coordinator (alternate if improving, else Phase 23 chooser) → optional advance.
    """
    client = get_supabase_client(settings)
    uni = str(universe_name or "").strip()
    census = build_public_first_branch_census(
        client,
        program_id=program_id,
        universe_name=uni,
        series_scan_limit=series_scan_limit,
        include_closed_series=include_closed_series,
    )
    plateau = conclude_public_first_plateau_review(census=census)

    sr = resolve_iteration_series_for_operator(
        client, program_id=program_id, universe_name=uni
    )
    if not sr.get("ok"):
        review_path = Path(out_stem).expanduser() / "latest_public_first_review.md"
        write_latest_public_first_review_md(
            review_path,
            census=census,
            plateau_review=plateau,
            cycle_payload={
                "chosen_action": None,
                "executed": False,
                "success": False,
                "error": sr,
            },
            recommended_command=f"`resolve_iteration_series` 실패: 거버넌스 확인 후 `run-post-patch-closeout --universe {uni}`",
        )
        return {
            "ok": False,
            "error": "series_resolve_failed",
            "series_resolution": sr,
            "census": census,
            "plateau_review": plateau,
            "review_markdown": str(review_path),
        }

    series_id = str(sr["series_id"])
    chosen: str
    reason: str

    if plateau["conclusion"] == PREMIUM_DISCOVERY_REVIEW_PREPARABLE:
        chosen = "hold_for_plateau_review"
        reason = "plateau_review_premium_discovery_preparable_no_auto_advance"
    elif plateau["conclusion"] == PUBLIC_FIRST_STILL_IMPROVING:
        lk = _last_iteration_member_kind(client, series_id=series_id)
        if lk == "public_depth":
            chosen = "advance_repair_series"
            reason = "alternating_rhythm_after_depth_member"
        else:
            chosen = "advance_public_depth_iteration"
            reason = "alternating_rhythm_after_repair_or_empty"
    else:
        ch = choose_post_patch_next_action(client, series_id=series_id, verify_only=False)
        chosen = str(ch.get("action") or "hold_for_plateau_review")
        reason = f"mixed_evidence_delegate_phase23_chooser:{ch.get('reason')}"

    executed = False
    success = True
    advance_out: dict[str, Any] | None = None

    if chosen == "advance_repair_series":
        advance_out = advance_public_repair_series(
            settings,
            program_id=program_id,
            universe_name=uni,
            series_id_override=None,
            attach_repair_run_id=None,
            run_new_campaign=True,
            dry_run_buildout=False,
            skip_reruns=False,
            panel_limit=8000,
            campaign_panel_limit=6000,
            max_symbols_factor=50,
            validation_panel_limit=2000,
            forward_panel_limit=2000,
            state_change_limit=400,
        )
        executed = True
        success = bool(advance_out.get("ok"))
    elif chosen == "advance_public_depth_iteration":
        advance_out = advance_public_depth_iteration(
            settings,
            program_id=program_id,
            universe_name=uni,
            series_id_override=None,
            panel_limit=8000,
            run_validation_panels=False,
            run_forward_returns=False,
            validation_panel_limit=2000,
            forward_panel_limit=2000,
            max_universe_factor_builds=0,
            execute_phase15_16_revalidation=False,
            validation_campaign_panel_limit=6000,
        )
        executed = True
        success = bool(advance_out.get("ok"))

    stem = Path(out_stem).expanduser()
    review_path = stem / "latest_public_first_review.md"
    rec = recommend_next_public_first_command(
        universe=uni,
        plateau_conclusion=str(plateau.get("conclusion") or ""),
        executed_action=chosen if executed and success else None,
    )
    write_latest_public_first_review_md(
        review_path,
        census=census,
        plateau_review=plateau,
        cycle_payload={
            "chosen_action": chosen,
            "executed": executed,
            "success": success if executed else None,
            "coordinator_reason": reason,
            "advance_result_summary": (advance_out or {}).get("operator_summary")
            if advance_out
            else None,
        },
        recommended_command=rec,
    )

    overall_ok = bool(plateau.get("ok")) and (not executed or success)
    return {
        "ok": overall_ok,
        "program_id": program_id,
        "universe_name": uni,
        "series_id": series_id,
        "census": census,
        "plateau_review": plateau,
        "chosen_action": chosen,
        "coordinator_reason": reason,
        "executed": executed,
        "advance_result": advance_out,
        "review_markdown": str(review_path),
        "recommended_next_command": rec,
    }
