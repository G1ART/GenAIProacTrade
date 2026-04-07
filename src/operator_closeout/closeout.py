"""Single-command post-patch closeout orchestration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Settings
from db.client import get_supabase_client
from operator_closeout.migrations import (
    default_migrations_dir,
    generate_migration_bundle_file,
    report_required_migrations,
)
from operator_closeout.next_step import choose_post_patch_next_action
from operator_closeout.phase_state import verify_db_phase_state
from public_repair_iteration.depth_iteration import (
    advance_public_depth_iteration,
    export_public_depth_series_brief,
    resolve_iteration_series_for_operator,
)
from public_repair_iteration.service import advance_public_repair_series


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_guided_operator_error(payload: dict[str, Any]) -> str:
    """Short lines for humans — avoid raw JSON dumps on known errors."""
    err = str(payload.get("error") or "")
    lines = [f"error: {err}"]
    hint = payload.get("operator_hint") or payload.get("hint")
    if hint:
        lines.append(str(hint))
    if err == "ambiguous_latest_program_need_universe":
        u = payload.get("universes_seen") or []
        if u:
            lines.append("가능한 --universe 후보: " + ", ".join(str(x) for x in u))
        else:
            lines.append("다음에 --universe <name> 을 지정하세요.")
    if err == "ambiguous_multiple_active_series":
        ids = payload.get("series_ids") or []
        if ids:
            lines.append("series_ids: " + ", ".join(str(i) for i in ids))
    if err == "operator_universe_active_series_mismatch":
        su = payload.get("series_universe")
        ru = payload.get("requested_universe")
        lines.append(f"active_series_universe={su!r} requested_universe={ru!r}")
    return "\n".join(lines)


def write_closeout_summary_markdown(
    path: Path,
    *,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    m = payload.get("migration_report") or {}
    phase = payload.get("phase_state") or {}
    series = payload.get("series_resolution") or {}
    chooser = payload.get("chooser") or {}
    action = payload.get("action_taken") or {}
    lines = [
        "# Operator closeout summary",
        "",
        f"- **Generated (UTC)**: `{_now_iso()}`",
        "",
        "## Migrations",
        "",
        f"- **Required migrations satisfied (schema_migrations probe)**: {m.get('ok')}",
        f"- **History probe OK**: {m.get('applied_probe_ok')}",
    ]
    if m.get("probe_error"):
        lines.append(f"- **Probe note**: `{m['probe_error']}`")
    miss = m.get("missing_migrations") or []
    if miss:
        lines.append("- **Missing vs DB**:")
        for row in miss:
            lines.append(f"  - `{row.get('filename')}` — {row.get('reason')}")
    lines += [
        "",
        "## Database phase smokes (phase17–22)",
        "",
        f"- **All passed**: {phase.get('ok')}",
    ]
    if phase.get("failed_at"):
        lines.append(f"- **Failed at**: `{phase.get('failed_at')}`")
    lines += [
        "",
        "## Active series (internal ID — audit only; operator did not paste UUID)",
        "",
        f"- **Resolved**: {series.get('ok')}",
        f"- **Rule**: `{series.get('resolved_rule', 'n/a')}`",
    ]
    if series.get("series_id"):
        lines.append(f"- **series_id (audit)**: `{series['series_id']}`")
    if series.get("created_series") is not None:
        lines.append(f"- **Newly created open slot**: {series.get('created_series')}")
    lines += [
        "",
        "## Chooser decision",
        "",
        f"- **Next action**: `{chooser.get('action')}`",
        f"- **Why**: {chooser.get('reason', 'n/a')}",
        f"- **Escalation (latest)**: `{chooser.get('escalation_recommendation', 'n/a')}`",
        f"- **Depth operator signal**: `{chooser.get('depth_operator_signal', 'n/a')}`",
        "",
        "## Action executed",
        "",
        f"- **Kind**: `{action.get('kind', 'none')}`",
        f"- **Success**: {action.get('ok')}",
    ]
    if action.get("error"):
        lines.append(f"- **Error**: {action['error']}")
    if action.get("paths"):
        lines.append("- **Artifact paths**:")
        for k, v in (action.get("paths") or {}).items():
            lines.append(f"  - {k}: `{v}`")
    lines += [
        "",
        "## Next recommended step",
        "",
        str(payload.get("next_recommended_human") or "See chooser section."),
        "",
        "## Public-first path",
        "",
        str(payload.get("public_first_line") or ""),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_post_patch_closeout(
    settings: Settings,
    *,
    universe: str,
    program_id_raw: str = "latest",
    out_stem: str = "docs/operator_closeout",
    verify_only: bool = False,
    skip_migration_report: bool = False,
    write_bundle_on_missing: bool = True,
    migrations_dir: Path | None = None,
) -> dict[str, Any]:
    """
    One-command closeout: migration report → phase smokes → series resolve/create →
    chooser → optional advance → brief export → markdown summary.
    """
    from public_repair_iteration.resolver import resolve_program_id

    repo_root = Path(__file__).resolve().parents[2]
    mig_dir = migrations_dir or default_migrations_dir(repo_root)
    summary_path = Path(out_stem).expanduser() / "latest_closeout_summary.md"
    stem_path = Path(out_stem).expanduser()

    client = get_supabase_client(settings)
    migration_report: dict[str, Any] = {"skipped": True}
    if not skip_migration_report:
        migration_report = report_required_migrations(client, migrations_dir=mig_dir)

    phase_state = verify_db_phase_state(client)

    lines_out: list[str] = []
    lines_out.append("[run-post-patch-closeout] migration_probe_ok=" + str(migration_report.get("applied_probe_ok")))
    lines_out.append("[run-post-patch-closeout] migration_report_ok=" + str(migration_report.get("ok")))
    lines_out.append("[run-post-patch-closeout] phase_smokes_ok=" + str(phase_state.get("ok")))

    fatal_migration = (
        not skip_migration_report
        and migration_report.get("applied_probe_ok")
        and not migration_report.get("ok")
    )
    if fatal_migration and write_bundle_on_missing:
        bundle_path = stem_path / "bundle_pending_migrations.sql"
        gen = generate_migration_bundle_file(migration_report, out_path=bundle_path, migrations_dir=mig_dir)
        migration_report["bundle_path"] = gen.get("path")
        lines_out.append(f"[run-post-patch-closeout] wrote_bundle={gen.get('written')} path={gen.get('path')}")

    if fatal_migration:
        payload = {
            "ok": False,
            "stage": "migrations_missing",
            "migration_report": migration_report,
            "phase_state": phase_state,
            "operator_lines": lines_out,
            "next_recommended_human": "Apply listed SQL migrations in order, then re-run run-post-patch-closeout.",
            "public_first_line": "n/a — unblock schema first.",
        }
        write_closeout_summary_markdown(summary_path, payload=payload)
        return {**payload, "summary_markdown": str(summary_path)}

    if not skip_migration_report and migration_report.get("applied_probe_ok") is False:
        lines_out.append(
            "[run-post-patch-closeout] warn: cannot read supabase_migrations.schema_migrations "
            "via API — using phase smokes as schema truth."
        )

    if not phase_state.get("ok"):
        payload = {
            "ok": False,
            "stage": "phase_smoke_failed",
            "migration_report": migration_report,
            "phase_state": phase_state,
            "operator_lines": lines_out,
            "next_recommended_human": f"Fix schema at `{phase_state.get('failed_at')}` then re-run.",
            "public_first_line": "n/a — schema smokes failed.",
        }
        write_closeout_summary_markdown(summary_path, payload=payload)
        return {**payload, "summary_markdown": str(summary_path)}

    pr = resolve_program_id(client, program_id_raw, universe_name=universe.strip())
    if not pr.get("ok"):
        payload = {
            "ok": False,
            "stage": "program_resolve_failed",
            "migration_report": migration_report,
            "phase_state": phase_state,
            "program_resolve": pr,
            "operator_lines": lines_out + [format_guided_operator_error({**pr, "error": pr.get("error")})],
            "next_recommended_human": format_guided_operator_error(
                {**pr, "error": pr.get("error"), "hint": pr.get("hint")}
            ),
            "public_first_line": "n/a — program not resolved.",
        }
        write_closeout_summary_markdown(summary_path, payload=payload)
        return {**payload, "summary_markdown": str(summary_path)}

    pid = str(pr["program_id"])
    sr = resolve_iteration_series_for_operator(
        client, program_id=pid, universe_name=universe.strip()
    )
    if not sr.get("ok"):
        payload = {
            "ok": False,
            "stage": "series_resolve_failed",
            "migration_report": migration_report,
            "phase_state": phase_state,
            "program_id": pid,
            "series_resolution": sr,
            "operator_lines": lines_out + [format_guided_operator_error(sr)],
            "next_recommended_human": format_guided_operator_error(sr),
            "public_first_line": "n/a — iteration series not resolved.",
        }
        write_closeout_summary_markdown(summary_path, payload=payload)
        return {**payload, "summary_markdown": str(summary_path)}

    series_id = str(sr["series_id"])
    chooser = choose_post_patch_next_action(
        client, series_id=series_id, verify_only=verify_only
    )
    action_kind = str(chooser.get("action") or "verify_only")
    action_result: dict[str, Any] = {"kind": action_kind, "ok": True, "paths": {}}

    depth_out = stem_path / "closeout_depth_series_brief"
    repair_out = stem_path / "closeout_advance_repair"
    depth_adv_out = stem_path / "closeout_advance_public_depth"

    if action_kind == "advance_public_depth_iteration" and not verify_only:
        adv = advance_public_depth_iteration(
            settings,
            program_id=pid,
            universe_name=universe.strip(),
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
        action_result["advance_public_depth"] = {"ok": adv.get("ok")}
        if adv.get("ok"):
            action_result["paths"]["advance_json"] = str(depth_adv_out.with_suffix(".json"))
            dest = Path(depth_adv_out)
            dest.parent.mkdir(parents=True, exist_ok=True)
            json_path = dest.with_suffix(".json")
            md_path = dest.with_suffix(".md")
            json_path.write_text(
                json.dumps(
                    {
                        "operator_summary": adv.get("operator_summary"),
                        "program_id": adv.get("program_id"),
                        "universe_name": adv.get("universe_name"),
                        "series_id": adv.get("series_id"),
                        "escalation_recommendation": adv.get("escalation_recommendation"),
                        "public_depth_operator_signal": adv.get("public_depth_operator_signal"),
                        "ledger": adv.get("ledger"),
                    },
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )
            md_path.write_text(
                "\n\n".join(
                    x
                    for x in (
                        str(adv.get("depth_series_markdown") or ""),
                        str(adv.get("repair_escalation_markdown") or ""),
                    )
                    if x.strip()
                ),
                encoding="utf-8",
            )
        else:
            action_result["ok"] = False
            action_result["error"] = adv.get("error")
            action_result["raw"] = adv

    elif action_kind == "advance_repair_series" and not verify_only:
        adv = advance_public_repair_series(
            settings,
            program_id=pid,
            universe_name=universe.strip(),
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
        action_result["advance_repair_series"] = {"ok": adv.get("ok")}
        if adv.get("ok"):
            json_path = repair_out.with_suffix(".json")
            md_path = repair_out.with_suffix(".md")
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(adv.get("brief") or {}, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            md_path.write_text(str(adv.get("markdown") or ""), encoding="utf-8")
            action_result["paths"]["repair_brief_json"] = str(json_path)
            action_result["paths"]["repair_brief_md"] = str(md_path)
        else:
            action_result["ok"] = False
            action_result["error"] = adv.get("error")
            action_result["raw"] = adv

    elif action_kind in ("hold_for_plateau_review", "verify_only"):
        action_result["skipped_mutating_advance"] = True

    # Always export depth series brief (audit trail)
    brief = export_public_depth_series_brief(client, series_id=series_id)
    action_result["export_depth_series_brief_ok"] = bool(brief.get("ok"))
    if brief.get("ok"):
        dj = depth_out.with_suffix(".json")
        dm = depth_out.with_suffix(".md")
        dj.parent.mkdir(parents=True, exist_ok=True)
        dj.write_text(
            json.dumps(brief.get("brief") or {}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        dm.write_text(str(brief.get("markdown") or ""), encoding="utf-8")
        action_result["paths"]["depth_series_brief_json"] = str(dj)
        action_result["paths"]["depth_series_brief_md"] = str(dm)

    esc = str(chooser.get("escalation_recommendation") or "")
    sig = str(chooser.get("depth_operator_signal") or "")
    public_first = (
        "예 — 에스컬레이션이 `continue_public_depth` 이거나 깊이 신호가 `continue_public_depth_buildout` 입니다."
        if "continue" in esc or sig == "continue_public_depth_buildout"
        else "조건부 — 현재 권고는 수리 반복/플래토 리뷰 쪽에 가깝습니다. 브리프의 escalation/signal을 확인하세요."
    )

    if action_kind == "hold_for_plateau_review":
        next_human = "플래토·프리미엄 게이트 인근 상태입니다. 자동 전진 없이 브리프를 검토하세요."
    elif action_kind == "verify_only":
        next_human = "검증 전용 모드였습니다. 다음 루프에서 자동 전진을 허용하려면 --verify-only 를 빼고 재실행하세요."
    elif action_result.get("ok"):
        next_human = f"실행된 작업: {action_kind}. 브리프 경로를 확인하세요."
    else:
        next_human = "전진 단계가 실패했습니다. 오류 필드를 검토하고 수동 복구 후 재실행하세요."

    payload = {
        "ok": bool(action_result.get("ok")) and bool(brief.get("ok")),
        "stage": "complete",
        "migration_report": migration_report,
        "phase_state": phase_state,
        "program_id": pid,
        "universe": universe.strip(),
        "series_resolution": {
            "ok": True,
            "series_id": series_id,
            "resolved_rule": sr.get("resolved_rule"),
            "created_series": sr.get("created_series"),
        },
        "chooser": {
            "action": chooser.get("action"),
            "reason": chooser.get("reason"),
            "escalation_recommendation": chooser.get("escalation_recommendation"),
            "depth_operator_signal": chooser.get("depth_operator_signal"),
        },
        "action_taken": action_result,
        "operator_lines": lines_out
        + [
            f"[run-post-patch-closeout] series_resolved_rule={sr.get('resolved_rule')}",
            f"[run-post-patch-closeout] chooser_action={chooser.get('action')}",
            f"[run-post-patch-closeout] chooser_reason={chooser.get('reason')}",
        ],
        "next_recommended_human": next_human,
        "public_first_line": public_first,
    }
    write_closeout_summary_markdown(summary_path, payload=payload)
    out = {**payload, "summary_markdown": str(summary_path)}
    return out
