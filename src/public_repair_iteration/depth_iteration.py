"""Phase 22: public-depth iterations under repair iteration series governance."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config import Settings
from db import records as dbrec
from db.client import get_supabase_client
from public_buildout.revalidation import build_revalidation_trigger
from public_depth.expansion import run_public_depth_expansion
from public_depth.readiness import build_research_readiness_summary
from public_repair_iteration.constants import ITERATION_POLICY_VERSION
from public_repair_iteration.depth_signal import compute_public_depth_operator_signal
from public_repair_iteration.marginal_policy import classify_public_depth_improvement
from public_repair_iteration.service import (
    collect_plateau_snapshots_for_series,
    compute_public_repair_plateau,
    export_public_repair_escalation_brief,
    get_or_create_iteration_series,
    recompute_escalation_from_series_members,
    resolve_active_series_for_program,
)

logger = logging.getLogger(__name__)


def resolve_iteration_series_for_operator(
    client: Any,
    *,
    program_id: str,
    universe_name: str | None = None,
) -> dict[str, Any]:
    """
    Operator mode: resolve a compatible active iteration series without passing UUID.
    Creates an open slot when none exists (same rules as depth advance).
    """
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    uni = (universe_name or "").strip() or str(prog.get("universe_name") or "")
    if not uni:
        return {"ok": False, "error": "universe_name_required_for_operator_series_resolve"}
    rs = resolve_active_series_for_program(client, program_id=program_id)
    if rs.get("ok"):
        row = rs["series"]
        if str(row.get("universe_name") or "") != uni:
            return {
                "ok": False,
                "error": "operator_universe_active_series_mismatch",
                "operator_hint": (
                    "다음 중 하나를 선택하세요: (1) --universe 를 활성 시리즈 유니버스와 맞추기 "
                    f"({row.get('universe_name')}) (2) 해당 유니버스용 시리즈 거버넌스 정리."
                ),
                "series_universe": row.get("universe_name"),
                "requested_universe": uni,
            }
        return {
            "ok": True,
            "series_id": rs["series_id"],
            "series": row,
            "resolved_rule": "active_compatible_series",
        }
    err = str(rs.get("error") or "")
    if err == "no_active_iteration_series":
        cr = get_or_create_iteration_series(
            client, program_id=program_id, universe_name=uni
        )
        if not cr.get("ok"):
            return cr
        sid = str(cr["series_id"])
        row = dbrec.fetch_public_repair_iteration_series(client, series_id=sid)
        return {
            "ok": True,
            "series_id": sid,
            "series": row or {},
            "resolved_rule": "get_or_created_iteration_series_open_slot",
            "created_series": bool(cr.get("created")),
        }
    if err == "ambiguous_multiple_active_series":
        return {
            "ok": False,
            "error": "ambiguous_multiple_active_series",
            "operator_hint": (
                "동일 프로그램에 active 시리즈가 여러 개입니다. pause/close 로 하나만 남기고 재시도하세요."
            ),
            "series_ids": rs.get("series_ids") or [],
        }
    return rs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _top_exclusion_keys(dist: dict[str, Any], *, limit: int = 8) -> list[str]:
    items = sorted(
        ((str(k), int(v)) for k, v in dist.items() if v is not None),
        key=lambda x: -x[1],
    )[:limit]
    return [k for k, _ in items]


def _count_ops_succeeded(operations: list[dict[str, Any]]) -> int:
    n = 0
    for op in operations:
        r = op.get("result")
        if not isinstance(r, dict):
            continue
        if r.get("ok") is True:
            n += 1
            continue
        if str(r.get("status") or "") == "completed":
            n += 1
    return n


def build_public_depth_iteration_ledger(
    *,
    expansion_result: dict[str, Any],
    readiness_before: dict[str, Any],
    readiness_after: dict[str, Any],
    trig_before: dict[str, Any],
    trig_after: dict[str, Any],
) -> dict[str, Any]:
    """Assemble Phase 22 trend ledger fields from expansion + readiness + revalidation triggers."""
    ok = bool(expansion_result.get("ok"))
    before_m = expansion_result.get("before_metrics") or {}
    after_m = expansion_result.get("after_metrics") or {}
    if not isinstance(before_m, dict):
        before_m = {}
    if not isinstance(after_m, dict):
        after_m = {}

    before_ex = expansion_result.get("before_exclusion_distribution") or {}
    after_ex = expansion_result.get("after_exclusion_distribution") or {}
    if not isinstance(before_ex, dict):
        before_ex = {}
    if not isinstance(after_ex, dict):
        after_ex = {}

    thin_b = before_m.get("thin_input_share")
    thin_a = after_m.get("thin_input_share")
    joined_b = before_m.get("joined_recipe_substrate_row_count")
    joined_a = after_m.get("joined_recipe_substrate_row_count")

    def _delta(a: Any, b: Any) -> float | None:
        try:
            if a is None or b is None:
                return None
            return float(a) - float(b)
        except (TypeError, ValueError):
            return None

    summary = expansion_result.get("expansion_summary_json")
    if not isinstance(summary, dict) and ok:
        # completed runs persist summary on row; caller may pass row slice
        summary = {}
    if not isinstance(summary, dict):
        summary = {}
    ops = summary.get("operations")
    if not isinstance(ops, list):
        ops = []

    # Bounded expansion: before/after coverage (+ uplift row) count as core actions.
    base_attempted = 2 if ok else 1
    base_succeeded = 2 if ok else 0
    attempted = base_attempted + len(ops)
    succeeded = base_succeeded + _count_ops_succeeded(ops)

    ledger: dict[str, Any] = {
        "expansion_ok": ok,
        "error_message": expansion_result.get("error")
        or expansion_result.get("error_message"),
        "thin_input_share_before": thin_b,
        "thin_input_share_after": thin_a,
        "thin_input_share_delta": _delta(thin_a, thin_b),
        "joined_recipe_substrate_row_count_before": joined_b,
        "joined_recipe_substrate_row_count_after": joined_a,
        "joined_recipe_substrate_row_count_delta": _delta(joined_a, joined_b),
        "dominant_exclusion_keys_before": _top_exclusion_keys(before_ex),
        "dominant_exclusion_keys_after": _top_exclusion_keys(after_ex),
        "research_readiness_before": readiness_before.get(
            "recommend_rerun_phase_15_16"
        ),
        "research_readiness_after": readiness_after.get(
            "recommend_rerun_phase_15_16"
        ),
        "rerun_gate_before": {
            "phase15": trig_before.get("recommend_rerun_phase15"),
            "phase16": trig_before.get("recommend_rerun_phase16"),
        },
        "rerun_gate_after": {
            "phase15": trig_after.get("recommend_rerun_phase15"),
            "phase16": trig_after.get("recommend_rerun_phase16"),
        },
        "buildout_actions_attempted": attempted,
        "buildout_actions_succeeded": succeeded,
        "public_depth_run_id": expansion_result.get("public_depth_run_id"),
        "before_report_id": expansion_result.get("before_report_id"),
        "after_report_id": expansion_result.get("after_report_id"),
        "uplift_report_id": expansion_result.get("uplift_report_id"),
    }
    ic = classify_public_depth_improvement(ledger)
    ledger["improvement_classification"] = ic
    return ledger


def build_trend_snapshot_for_public_depth(ledger: dict[str, Any]) -> dict[str, Any]:
    """Trend snapshot compatible with plateau math + phase22_ledger."""
    ra = ledger.get("rerun_gate_after") or {}
    if not isinstance(ra, dict):
        ra = {}
    rid = str(ledger.get("public_depth_run_id") or "")
    return {
        "member_kind": "public_depth",
        "public_depth_run_id": rid,
        "repair_campaign_run_id": None,
        "final_decision": "public_depth_iteration",
        "joined_recipe_substrate_row_count": ledger.get(
            "joined_recipe_substrate_row_count_after"
        ),
        "thin_input_share": ledger.get("thin_input_share_after"),
        "reran_phase15": None,
        "reran_phase16": None,
        "recommend_rerun_phase15": ra.get("phase15"),
        "recommend_rerun_phase16": ra.get("phase16"),
        "survival_after_distribution": {},
        "premium_share_from_interp": None,
        "top_exclusion_keys": ledger.get("dominant_exclusion_keys_after") or [],
        "phase22_ledger": ledger,
        "improvement_classification": ledger.get("improvement_classification"),
    }


def append_public_depth_expansion_to_iteration_series(
    client: Any,
    *,
    series_id: str,
    program_id: str,
    ledger: dict[str, Any],
    depth_run_row: dict[str, Any],
) -> dict[str, Any]:
    """Append one public_depth run to series (idempotent on public_depth_run_id)."""
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    st = str(s.get("status") or "")
    if st == "paused":
        return {
            "ok": False,
            "error": "cannot_append_iteration_series_paused",
            "series_id": series_id,
        }
    if st == "closed":
        return {
            "ok": False,
            "error": "cannot_append_iteration_series_closed",
            "series_id": series_id,
        }
    if st != "active":
        return {
            "ok": False,
            "error": "cannot_append_iteration_series_bad_status",
            "status": st,
        }
    if str(s.get("policy_version") or "") != ITERATION_POLICY_VERSION:
        return {
            "ok": False,
            "error": "iteration_series_policy_version_mismatch",
            "series_policy_version": s.get("policy_version"),
            "expected": ITERATION_POLICY_VERSION,
        }
    drid = str(depth_run_row.get("id") or "")
    if not drid:
        return {"ok": False, "error": "public_depth_run_id_missing"}

    uni_series = str(s.get("universe_name") or "")
    uni_run = str(depth_run_row.get("universe_name") or "")
    if uni_run and uni_series and uni_run != uni_series:
        return {
            "ok": False,
            "error": "public_depth_run_universe_mismatch",
            "run_universe": uni_run,
            "series_universe": uni_series,
        }

    existing = dbrec.fetch_public_repair_iteration_member_by_depth_run_id(
        client, public_depth_run_id=drid
    )
    if existing:
        esc = recompute_escalation_from_series_members(
            client, series_id=series_id, persist=True
        )
        return {
            "ok": True,
            "idempotent": True,
            "iteration_member_id": str(existing["id"]),
            "public_depth_run_id": drid,
            "escalation_recommendation": esc.get("escalation_recommendation"),
            "plateau_metrics": esc.get("plateau_metrics"),
        }

    snap = build_trend_snapshot_for_public_depth(ledger)
    seq = dbrec.fetch_max_sequence_public_repair_iteration_member(
        client, series_id=series_id
    ) + int(1)
    dbrec.insert_public_repair_iteration_member(
        client,
        {
            "series_id": series_id,
            "member_kind": "public_depth",
            "repair_campaign_run_id": None,
            "public_depth_run_id": drid,
            "sequence_number": seq,
            "trend_snapshot_json": snap,
            "created_at": _now(),
        },
    )
    esc = recompute_escalation_from_series_members(
        client, series_id=series_id, persist=True
    )
    return {
        "ok": True,
        "idempotent": False,
        "sequence_number": seq,
        "public_depth_run_id": drid,
        "escalation_recommendation": esc.get("escalation_recommendation"),
        "escalation_rationale": esc.get("escalation_rationale"),
        "plateau_metrics": esc.get("plateau_metrics"),
        "counterfactual": esc.get("counterfactual"),
        "excluded_runs": esc.get("excluded_runs"),
    }


def advance_public_depth_iteration(
    settings: Settings,
    *,
    program_id: str,
    universe_name: str | None = None,
    series_id_override: str | None = None,
    panel_limit: int = 8000,
    run_validation_panels: bool = False,
    run_forward_returns: bool = False,
    validation_panel_limit: int = 2000,
    forward_panel_limit: int = 2000,
    max_universe_factor_builds: int = 0,
    execute_phase15_16_revalidation: bool = False,
    validation_campaign_panel_limit: int = 6000,
) -> dict[str, Any]:
    """
    Resolve active series → baseline readiness → bounded public-depth expansion →
    ledger append → escalation → operator signal + repair escalation brief + depth brief.
    """
    from public_repair_iteration.resolver import resolve_iteration_series_id

    from validation_campaign.service import run_validation_campaign

    client = get_supabase_client(settings)
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    uni = (universe_name or "").strip() or str(prog.get("universe_name") or "")
    if not uni:
        return {"ok": False, "error": "universe_name_required"}

    if series_id_override:
        sr = resolve_iteration_series_id(
            client,
            series_id_override.strip(),
            program_id=program_id,
            program=prog,
        )
    else:
        rs = resolve_active_series_for_program(client, program_id=program_id)
        if rs.get("ok"):
            sr = {
                "ok": True,
                "series_id": rs["series_id"],
                "series": rs["series"],
            }
        else:
            if rs.get("error") == "no_active_iteration_series":
                cr = get_or_create_iteration_series(
                    client, program_id=program_id, universe_name=uni
                )
                if not cr.get("ok"):
                    return cr
                srow = dbrec.fetch_public_repair_iteration_series(
                    client, series_id=str(cr["series_id"])
                )
                sr = {
                    "ok": True,
                    "series_id": str(cr["series_id"]),
                    "series": srow or {},
                }
            else:
                return rs
    if not sr.get("ok"):
        return sr
    series_id = str(sr["series_id"])
    srow = sr.get("series") or {}
    if str(srow.get("universe_name") or "") != uni:
        return {
            "ok": False,
            "error": "series_universe_mismatch_use_matching_universe",
            "series_universe": srow.get("universe_name"),
            "requested_universe": uni,
        }

    readiness_before = build_research_readiness_summary(
        client, program_id=program_id
    )
    trig_before = build_revalidation_trigger(client, program_id=program_id)

    exp = run_public_depth_expansion(
        settings,
        universe_name=uni,
        panel_limit=panel_limit,
        run_validation_panels=run_validation_panels,
        run_forward_returns=run_forward_returns,
        validation_panel_limit=validation_panel_limit,
        forward_panel_limit=forward_panel_limit,
        max_universe_factor_builds=max_universe_factor_builds,
    )

    drid = str(exp.get("public_depth_run_id") or "")
    if not drid:
        return {
            "ok": False,
            "error": "public_depth_run_id_missing_after_expansion",
            "expansion": exp,
        }
    drow = dbrec.fetch_public_depth_run(client, run_id=drid)
    if not drow:
        return {
            "ok": False,
            "error": "public_depth_run_row_missing",
            "expansion": exp,
        }
    esj = drow.get("expansion_summary_json")
    if isinstance(esj, dict):
        exp = {**exp, "expansion_summary_json": esj}
    if not exp.get("ok"):
        exp = {**exp, "error": exp.get("error") or drow.get("error_message")}

    readiness_after = build_research_readiness_summary(
        client, program_id=program_id
    )
    trig_after = build_revalidation_trigger(client, program_id=program_id)

    rb = readiness_before if readiness_before.get("ok") else {}
    ra = readiness_after if readiness_after.get("ok") else {}
    tb = trig_before if trig_before.get("ok") else {}
    ta = trig_after if trig_after.get("ok") else {}

    ledger = build_public_depth_iteration_ledger(
        expansion_result=exp,
        readiness_before=rb,
        readiness_after=ra,
        trig_before=tb,
        trig_after=ta,
    )

    app = append_public_depth_expansion_to_iteration_series(
        client,
        series_id=series_id,
        program_id=program_id,
        ledger=ledger,
        depth_run_row=drow,
    )
    if not app.get("ok"):
        return {**app, "expansion": exp, "ledger": ledger}

    plateau = compute_public_repair_plateau(client, series_id=series_id)
    esc = str(plateau.get("escalation_recommendation") or "")

    depth_bundle = export_public_depth_series_brief(client, series_id=series_id)
    ledgers_nf = depth_bundle.get("depth_ledgers_newest_first") or []

    sig, sig_r = compute_public_depth_operator_signal(
        escalation_recommendation=esc,
        depth_ledgers_newest_first=ledgers_nf,
    )

    reval_out: dict[str, Any] | None = None
    if execute_phase15_16_revalidation:
        gate_open = bool(ta.get("recommend_rerun_phase15")) or bool(
            ta.get("recommend_rerun_phase16")
        )
        gate_was_closed = not (
            bool(tb.get("recommend_rerun_phase15"))
            or bool(tb.get("recommend_rerun_phase16"))
        )
        if gate_open and gate_was_closed:
            reval_out = run_validation_campaign(
                client,
                program_id=program_id,
                run_mode="reuse_or_run",
                panel_limit=validation_campaign_panel_limit,
            )
        else:
            reval_out = {
                "ok": True,
                "skipped": True,
                "reason": "revalidation_gate_not_newly_open",
                "rerun_gate_after": ta,
                "rerun_gate_before": tb,
            }

    repair_brief = export_public_repair_escalation_brief(
        client, series_id=series_id
    )

    summary = (
        f"[advance-public-depth-iteration] program={program_id} series={series_id} "
        f"depth_run={drow.get('id')} improvement={ledger.get('improvement_classification')} "
        f"escalation={esc} depth_signal={sig} "
        f"included_runs={plateau.get('plateau_metrics', {}).get('included_run_count')}"
    )

    out: dict[str, Any] = {
        "ok": True,
        "program_id": program_id,
        "universe_name": uni,
        "series_id": series_id,
        "expansion": exp,
        "ledger": ledger,
        "iteration_append": app,
        "escalation_recommendation": esc,
        "public_depth_operator_signal": sig,
        "public_depth_signal_rationale": sig_r,
        "plateau": plateau,
        "depth_series_brief": depth_bundle.get("brief"),
        "depth_series_markdown": depth_bundle.get("markdown"),
        "repair_escalation_brief": repair_brief.get("brief"),
        "repair_escalation_markdown": repair_brief.get("markdown"),
        "operator_summary": summary,
    }
    if reval_out is not None:
        out["phase15_16_revalidation"] = reval_out
    return out


def export_public_depth_series_brief(
    client: Any, *, series_id: str
) -> dict[str, Any]:
    """Multi-run evidence export for public-depth + repair members (Phase 22)."""
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}

    members = dbrec.list_public_repair_iteration_members_for_series(
        client, series_id=series_id
    )
    plateau = compute_public_repair_plateau(client, series_id=series_id)
    esc = str(plateau.get("escalation_recommendation") or "")

    coll = collect_plateau_snapshots_for_series(
        client, series_id=series_id, exclude_infra_default=True
    )

    depth_ledgers_ordered: list[dict[str, Any]] = []
    classifications_ordered: list[str] = []
    for m in members:
        snap = dict(m.get("trend_snapshot_json") or {})
        if str(m.get("member_kind") or "repair_campaign") == "public_depth" or snap.get(
            "member_kind"
        ) == "public_depth":
            led = snap.get("phase22_ledger")
            if isinstance(led, dict):
                depth_ledgers_ordered.append(led)
                classifications_ordered.append(
                    str(led.get("improvement_classification") or "")
                )

    ledgers_nf = list(reversed(depth_ledgers_ordered))

    sig, sig_r = compute_public_depth_operator_signal(
        escalation_recommendation=esc,
        depth_ledgers_newest_first=ledgers_nf,
    )

    esc_rows = dbrec.list_public_repair_escalation_decisions_for_series(
        client, series_id=series_id, limit=50
    )
    branch_counts: dict[str, int] = {}
    for row in esc_rows:
        r = str(row.get("recommendation") or "")
        branch_counts[r] = branch_counts.get(r, 0) + 1

    cls_counts: dict[str, int] = {}
    for c in classifications_ordered:
        if not c:
            continue
        cls_counts[c] = cls_counts.get(c, 0) + 1

    latest_dom_after: list[str] = []
    if ledgers_nf:
        latest_dom_after = list(ledgers_nf[0].get("dominant_exclusion_keys_after") or [])

    brief: dict[str, Any] = {
        "version": 1,
        "series_id": series_id,
        "program_id": s.get("program_id"),
        "universe_name": s.get("universe_name"),
        "member_count_total": len(members),
        "included_run_count": coll.get("included_run_count")
        if coll.get("ok")
        else None,
        "excluded_runs": coll.get("excluded_runs") if coll.get("ok") else [],
        "improvement_classifications_in_order": classifications_ordered,
        "improvement_classification_counts": cls_counts,
        "persisted_escalation_branch_counts": branch_counts,
        "escalation_recommendation_current": esc,
        "public_depth_operator_signal": sig,
        "public_depth_signal_rationale": sig_r,
        "dominant_exclusions_latest_after": latest_dom_after,
        "trend_deltas_last_depth": ledgers_nf[0] if ledgers_nf else None,
        "plateau_metrics": plateau.get("plateau_metrics"),
    }

    lines = [
        "# Public depth series brief (Phase 22)",
        "",
        f"- **Series**: `{series_id}`",
        f"- **Members (total)**: {len(members)}",
        f"- **Included in plateau (default quarantine)**: {brief.get('included_run_count')}",
        f"- **Current escalation**: `{esc}`",
        f"- **Public-depth operator signal**: `{sig}`",
        "",
        "## Improvement classifications (public-depth members, chronological)",
        "",
        "```json",
        json.dumps(classifications_ordered, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Classification counts",
        "",
        "```json",
        json.dumps(cls_counts, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Persisted escalation branch counts (history)",
        "",
        "```json",
        json.dumps(branch_counts, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Excluded runs (audit)",
        "",
        "```json",
        json.dumps(brief.get("excluded_runs") or [], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Latest dominant exclusions (after snapshot)",
        "",
        "```json",
        json.dumps(latest_dom_after, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Signal rationale",
        "",
        "```json",
        json.dumps(sig_r, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    return {
        "ok": True,
        "brief": brief,
        "markdown": "\n".join(lines),
        "depth_ledgers_newest_first": ledgers_nf,
    }
