"""Iteration series lifecycle, trend snapshots, escalation persistence."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config import Settings
from db import records as dbrec
from db.client import get_supabase_client
from public_buildout.revalidation import build_revalidation_trigger
from public_repair_campaign.service import run_public_repair_campaign
from public_repair_iteration.constants import ITERATION_POLICY_VERSION
from public_repair_iteration.escalation_policy import (
    assert_escalation_recommendation,
    decide_escalation_recommendation,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_trend_snapshot_json(
    client: Any, *, program_id: str, run_row: dict[str, Any]
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    excl: dict[str, Any] = {}
    after_cov = run_row.get("after_coverage_report_id")
    if after_cov:
        rep = dbrec.fetch_public_depth_coverage_report(
            client, report_id=str(after_cov)
        )
        if rep:
            mj = rep.get("metrics_json")
            metrics = mj if isinstance(mj, dict) else {}
            ej = rep.get("exclusion_distribution_json")
            excl = ej if isinstance(ej, dict) else {}
    comp = dbrec.fetch_public_repair_revalidation_comparison_for_run(
        client, repair_campaign_run_id=str(run_row["id"])
    )
    interp: dict[str, Any] = {}
    surv_after: dict[str, Any] = {}
    if comp:
        ij = comp.get("improvement_interpretation_json")
        interp = ij if isinstance(ij, dict) else {}
        sa = comp.get("after_survival_distribution_json")
        surv_after = sa if isinstance(sa, dict) else {}
    totals = interp.get("after_campaign_failure_totals") or {}
    prem = totals.get("premium_share") if isinstance(totals, dict) else None
    trig = build_revalidation_trigger(client, program_id=program_id)
    top_excl = sorted(
        ((str(k), int(v)) for k, v in excl.items()),
        key=lambda x: -x[1],
    )[:8]
    return {
        "repair_campaign_run_id": str(run_row["id"]),
        "final_decision": run_row.get("final_decision"),
        "joined_recipe_substrate_row_count": metrics.get(
            "joined_recipe_substrate_row_count"
        ),
        "thin_input_share": metrics.get("thin_input_share"),
        "reran_phase15": run_row.get("reran_phase15"),
        "reran_phase16": run_row.get("reran_phase16"),
        "recommend_rerun_phase15": trig.get("recommend_rerun_phase15"),
        "recommend_rerun_phase16": trig.get("recommend_rerun_phase16"),
        "survival_after_distribution": dict(surv_after),
        "premium_share_from_interp": prem,
        "top_exclusion_keys": [k for k, _ in top_excl],
    }


def get_or_create_iteration_series(
    client: Any,
    *,
    program_id: str,
    universe_name: str,
    policy_version: str = ITERATION_POLICY_VERSION,
) -> dict[str, Any]:
    actives = dbrec.list_active_public_repair_iteration_series_for_program(
        client, program_id=program_id
    )
    if len(actives) > 1:
        return {
            "ok": False,
            "error": "ambiguous_multiple_active_iteration_series",
            "series_ids": [str(s["id"]) for s in actives],
        }
    if not actives:
        sid = dbrec.insert_public_repair_iteration_series(
            client,
            {
                "program_id": program_id,
                "universe_name": universe_name,
                "policy_version": policy_version,
                "status": "active",
                "created_at": _now(),
                "updated_at": _now(),
            },
        )
        return {"ok": True, "series_id": sid, "created": True}
    s0 = actives[0]
    if str(s0.get("policy_version") or "") == policy_version:
        return {"ok": True, "series_id": str(s0["id"]), "created": False}
    dbrec.update_public_repair_iteration_series(
        client, series_id=str(s0["id"]), patch={"status": "closed", "updated_at": _now()}
    )
    sid = dbrec.insert_public_repair_iteration_series(
        client,
        {
            "program_id": program_id,
            "universe_name": universe_name,
            "policy_version": policy_version,
            "status": "active",
            "created_at": _now(),
            "updated_at": _now(),
        },
    )
    return {"ok": True, "series_id": sid, "created": True, "closed_prior_series": str(s0["id"])}


def run_public_repair_iteration(
    settings: Settings,
    *,
    program_id: str,
    universe_name: str | None = None,
    dry_run_buildout: bool = False,
    skip_reruns: bool = False,
    panel_limit: int = 8000,
    campaign_panel_limit: int = 6000,
    max_symbols_factor: int = 50,
    validation_panel_limit: int = 2000,
    forward_panel_limit: int = 2000,
    state_change_limit: int = 400,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    uni = (universe_name or "").strip() or str(prog.get("universe_name") or "")
    if not uni:
        return {"ok": False, "error": "universe_name_required"}

    ser = get_or_create_iteration_series(
        client, program_id=program_id, universe_name=uni
    )
    if not ser.get("ok"):
        return ser
    series_id = str(ser["series_id"])

    camp = run_public_repair_campaign(
        settings,
        program_id=program_id,
        universe_name=uni,
        dry_run_buildout=dry_run_buildout,
        skip_reruns=skip_reruns,
        panel_limit=panel_limit,
        campaign_panel_limit=campaign_panel_limit,
        max_symbols_factor=max_symbols_factor,
        validation_panel_limit=validation_panel_limit,
        forward_panel_limit=forward_panel_limit,
        state_change_limit=state_change_limit,
    )
    out: dict[str, Any] = {
        "ok": camp.get("ok", False),
        "series_id": series_id,
        "repair_campaign": camp,
        "iteration_member_added": False,
    }
    if not camp.get("ok"):
        dbrec.update_public_repair_iteration_series(
            client, series_id=series_id, patch={"updated_at": _now()}
        )
        return out

    rid = str(camp.get("repair_campaign_run_id") or "")
    run_row = dbrec.fetch_public_repair_campaign_run(client, run_id=rid)
    if not run_row:
        dbrec.update_public_repair_iteration_series(
            client, series_id=series_id, patch={"updated_at": _now()}
        )
        return {**out, "error": "repair_run_row_missing_after_campaign"}

    if str(run_row.get("status") or "") != "completed" or not run_row.get(
        "final_decision"
    ):
        dbrec.update_public_repair_iteration_series(
            client, series_id=series_id, patch={"updated_at": _now()}
        )
        return {
            **out,
            "warning": "campaign_not_completed_or_no_final_decision_skip_member",
            "run_status": run_row.get("status"),
        }

    snap = build_trend_snapshot_json(client, program_id=program_id, run_row=run_row)
    seq = dbrec.fetch_max_sequence_public_repair_iteration_member(
        client, series_id=series_id
    ) + int(1)
    dbrec.insert_public_repair_iteration_member(
        client,
        {
            "series_id": series_id,
            "repair_campaign_run_id": rid,
            "sequence_number": seq,
            "trend_snapshot_json": snap,
            "created_at": _now(),
        },
    )

    members = dbrec.list_public_repair_iteration_members_for_series(
        client, series_id=series_id
    )
    snapshots = [dict(m.get("trend_snapshot_json") or {}) for m in members]
    rec, rat, plateau, cf = decide_escalation_recommendation(snapshots)
    rec = assert_escalation_recommendation(rec)
    rationale_text = f"{rec}: {rat.get('rule', '')}"
    dbrec.insert_public_repair_escalation_decision(
        client,
        {
            "series_id": series_id,
            "recommendation": rec,
            "rationale": rationale_text[:8000],
            "plateau_metrics_json": {**plateau, "rationale_struct": rat},
            "counterfactual_json": cf,
            "created_at": _now(),
        },
    )
    dbrec.update_public_repair_iteration_series(
        client, series_id=series_id, patch={"updated_at": _now()}
    )

    out["iteration_member_added"] = True
    out["sequence_number"] = seq
    out["escalation_recommendation"] = rec
    out["escalation_rationale"] = rat
    out["plateau_metrics"] = plateau
    return out


def report_public_repair_iteration_history(
    client: Any, *, series_id: str
) -> dict[str, Any]:
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    members = dbrec.list_public_repair_iteration_members_for_series(
        client, series_id=series_id
    )
    esc = dbrec.list_public_repair_escalation_decisions_for_series(
        client, series_id=series_id, limit=50
    )
    return {
        "ok": True,
        "series": s,
        "members": members,
        "escalation_decisions": esc,
    }


def report_public_repair_iteration_history_for_program(
    client: Any, *, program_id: str
) -> dict[str, Any]:
    series_list = dbrec.list_public_repair_iteration_series_for_program(
        client, program_id=program_id, limit=10
    )
    if not series_list:
        return {"ok": True, "program_id": program_id, "series": [], "members_by_series": {}}
    out_series = []
    by_sid: dict[str, Any] = {}
    for s in series_list:
        sid = str(s["id"])
        out_series.append(s)
        by_sid[sid] = {
            "members": dbrec.list_public_repair_iteration_members_for_series(
                client, series_id=sid
            ),
            "escalation_decisions": dbrec.list_public_repair_escalation_decisions_for_series(
                client, series_id=sid, limit=20
            ),
        }
    return {
        "ok": True,
        "program_id": program_id,
        "series": out_series,
        "detail_by_series_id": by_sid,
    }


def compute_public_repair_plateau(
    client: Any, *, series_id: str
) -> dict[str, Any]:
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    members = dbrec.list_public_repair_iteration_members_for_series(
        client, series_id=series_id
    )
    snapshots = [dict(m.get("trend_snapshot_json") or {}) for m in members]
    rec, rat, plateau, cf = decide_escalation_recommendation(snapshots)
    rec = assert_escalation_recommendation(rec)
    return {
        "ok": True,
        "series": s,
        "n_members": len(members),
        "escalation_recommendation": rec,
        "rationale": rat,
        "plateau_metrics": plateau,
        "counterfactual": cf,
        "ephemeral": True,
        "note": "Computed from current members; last persisted row may differ until next run-public-repair-iteration.",
    }


def export_public_repair_escalation_brief(
    client: Any, *, series_id: str
) -> dict[str, Any]:
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    decisions = dbrec.list_public_repair_escalation_decisions_for_series(
        client, series_id=series_id, limit=5
    )
    plateau_bundle = compute_public_repair_plateau(client, series_id=series_id)
    latest = decisions[0] if decisions else None
    brief = {
        "version": 1,
        "series_id": series_id,
        "program_id": s.get("program_id"),
        "universe_name": s.get("universe_name"),
        "policy_version": s.get("policy_version"),
        "series_status": s.get("status"),
        "latest_persisted_escalation": latest,
        "recomputed_from_members": {
            "recommendation": plateau_bundle.get("escalation_recommendation"),
            "rationale": plateau_bundle.get("rationale"),
            "plateau_metrics": plateau_bundle.get("plateau_metrics"),
            "counterfactual": plateau_bundle.get("counterfactual"),
        },
    }
    lines = [
        "# Public repair escalation brief (Phase 20)",
        "",
        f"- **Series**: `{series_id}`",
        f"- **Program**: `{brief.get('program_id')}`",
        f"- **Universe**: `{brief.get('universe_name')}`",
        "",
        "## Latest persisted recommendation",
        "",
        f"`{(latest or {}).get('recommendation')}`",
        "",
        str((latest or {}).get("rationale") or ""),
        "",
        "## Recomputed from all iteration members (ephemeral check)",
        "",
        f"`{plateau_bundle.get('escalation_recommendation')}`",
        "",
        "```json",
        json.dumps(plateau_bundle.get("rationale") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    return {"ok": True, "brief": brief, "markdown": "\n".join(lines)}


def report_latest_repair_state(
    client: Any, *, program_id: str
) -> dict[str, Any]:
    runs = dbrec.list_public_repair_campaign_runs_for_program(
        client, program_id=program_id, limit=5
    )
    actives = dbrec.list_active_public_repair_iteration_series_for_program(
        client, program_id=program_id
    )
    series_id = str(actives[0]["id"]) if actives else None
    plateau = None
    if series_id:
        plateau = compute_public_repair_plateau(client, series_id=series_id)
    return {
        "ok": True,
        "program_id": program_id,
        "latest_repair_campaign_runs": runs,
        "active_iteration_series": actives,
        "plateau_report": plateau,
    }


def list_public_repair_series(
    client: Any, *, program_id: str, limit: int = 30
) -> dict[str, Any]:
    rows = dbrec.list_public_repair_iteration_series_for_program(
        client, program_id=program_id, limit=limit
    )
    return {"ok": True, "program_id": program_id, "series": rows}


def resolve_active_series_for_program(
    client: Any, *, program_id: str
) -> dict[str, Any]:
    actives = dbrec.list_active_public_repair_iteration_series_for_program(
        client, program_id=program_id
    )
    if not actives:
        return {"ok": False, "error": "no_active_iteration_series", "program_id": program_id}
    if len(actives) > 1:
        return {
            "ok": False,
            "error": "ambiguous_multiple_active_series",
            "series_ids": [str(s["id"]) for s in actives],
        }
    return {"ok": True, "series_id": str(actives[0]["id"]), "series": actives[0]}
