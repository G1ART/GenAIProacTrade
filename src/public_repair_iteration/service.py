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
from public_repair_iteration.infra_noise import classify_infra_failure

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


def _governance_base(series_row: dict[str, Any]) -> dict[str, Any]:
    g = series_row.get("governance_audit_json")
    return dict(g) if isinstance(g, dict) else {}


def _record_incompatibility(
    client: Any, *, series_id: str, series_row: dict[str, Any], reason: str, run_id: str | None
) -> None:
    g = _governance_base(series_row)
    g["last_incompatibility"] = {
        "at": _now(),
        "reason": reason[:4000],
        "repair_campaign_run_id": run_id,
    }
    dbrec.update_public_repair_iteration_series(
        client,
        series_id=series_id,
        patch={"governance_audit_json": g, "updated_at": _now()},
    )


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
    other_universe = [
        s
        for s in actives
        if str(s.get("universe_name") or "") != str(universe_name)
    ]
    if other_universe:
        return {
            "ok": False,
            "error": "conflicting_active_iteration_series_other_universe",
            "blocking_series_id": str(other_universe[0]["id"]),
            "blocking_universe": other_universe[0].get("universe_name"),
            "requested_universe": universe_name,
        }

    open_slot = dbrec.list_open_public_repair_iteration_series_for_triple(
        client,
        program_id=program_id,
        universe_name=universe_name,
        policy_version=policy_version,
    )
    if len(open_slot) > 1:
        return {
            "ok": False,
            "error": "ambiguous_multiple_open_iteration_series_for_triple",
            "series_ids": [str(s["id"]) for s in open_slot],
        }
    if len(open_slot) == 1:
        s0 = open_slot[0]
        st = str(s0.get("status") or "")
        if st == "paused":
            return {
                "ok": False,
                "error": "iteration_series_paused_resume_first",
                "series_id": str(s0["id"]),
            }
        return {"ok": True, "series_id": str(s0["id"]), "created": False}

    same_uni_wrong_policy = [
        s
        for s in actives
        if str(s.get("universe_name") or "") == str(universe_name)
        and str(s.get("policy_version") or "") != str(policy_version)
    ]
    closed_ids: list[str] = []
    for s in same_uni_wrong_policy:
        sid = str(s["id"])
        dbrec.update_public_repair_iteration_series(
            client,
            series_id=sid,
            patch={"status": "closed", "updated_at": _now()},
        )
        closed_ids.append(sid)

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
    out: dict[str, Any] = {"ok": True, "series_id": sid, "created": True}
    if closed_ids:
        out["closed_prior_series"] = closed_ids
    return out


def collect_plateau_snapshots_for_series(
    client: Any,
    *,
    series_id: str,
    exclude_infra_default: bool = True,
) -> dict[str, Any]:
    """Build ordered snapshots for escalation; quarantine infra / malformed runs by default."""
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    members = dbrec.list_public_repair_iteration_members_for_series(
        client, series_id=series_id
    )
    program_id = str(s.get("program_id") or "")
    if not exclude_infra_default:
        included_snaps = [dict(m.get("trend_snapshot_json") or {}) for m in members]
        return {
            "ok": True,
            "series": s,
            "snapshots": included_snaps,
            "excluded_runs": [],
            "included_run_count": len(included_snaps),
            "excluded_infra_failure_count": 0,
            "excluded_other_count": 0,
            "n_iteration_members_total": len(members),
            "exclude_infra_default": False,
        }
    included_snaps: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    infra_excluded = 0
    for m in members:
        mk = str(m.get("member_kind") or "repair_campaign")
        pdepth_id = m.get("public_depth_run_id")
        if mk == "public_depth" or pdepth_id:
            drid = str(pdepth_id or "")
            if not drid:
                excluded.append(
                    {
                        "public_depth_run_id": "",
                        "reason": "missing_public_depth_run_id",
                    }
                )
                continue
            drow = dbrec.fetch_public_depth_run(client, run_id=drid)
            if not drow:
                excluded.append(
                    {"public_depth_run_id": drid, "reason": "depth_run_row_missing"}
                )
                continue
            msg = str(drow.get("error_message") or "")
            st = str(drow.get("status") or "")
            if exclude_infra_default:
                if st == "failed":
                    cat = classify_infra_failure(msg)
                    reason = f"failed_depth_run:{cat or 'non_infra'}"
                    excluded.append(
                        {
                            "public_depth_run_id": drid,
                            "reason": reason,
                            "error_preview": msg[:240],
                        }
                    )
                    if cat:
                        infra_excluded += 1
                    continue
                if st != "completed":
                    excluded.append(
                        {
                            "public_depth_run_id": drid,
                            "reason": "depth_run_not_completed",
                            "status": st,
                        }
                    )
                    continue
                if classify_infra_failure(msg):
                    excluded.append(
                        {
                            "public_depth_run_id": drid,
                            "reason": "infra_echo_on_completed_depth_run",
                            "error_preview": msg[:240],
                        }
                    )
                    infra_excluded += 1
                    continue
            snap = dict(m.get("trend_snapshot_json") or {})
            if snap:
                included_snaps.append(snap)
            else:
                excluded.append(
                    {
                        "public_depth_run_id": drid,
                        "reason": "missing_trend_snapshot_on_member",
                    }
                )
            continue

        rid = str(m.get("repair_campaign_run_id") or "")
        run_row = dbrec.fetch_public_repair_campaign_run(client, run_id=rid)
        if not run_row:
            excluded.append(
                {"repair_campaign_run_id": rid, "reason": "run_row_missing"}
            )
            continue
        msg = str(run_row.get("error_message") or "")
        st = str(run_row.get("status") or "")
        if exclude_infra_default:
            if st == "failed":
                cat = classify_infra_failure(msg)
                reason = f"failed_run:{cat or 'non_infra'}"
                excluded.append(
                    {"repair_campaign_run_id": rid, "reason": reason, "error_preview": msg[:240]}
                )
                if cat:
                    infra_excluded += 1
                continue
            if st != "completed" or not run_row.get("final_decision"):
                excluded.append(
                    {
                        "repair_campaign_run_id": rid,
                        "reason": "not_completed_or_missing_final_decision",
                        "status": st,
                    }
                )
                continue
            if classify_infra_failure(msg):
                excluded.append(
                    {
                        "repair_campaign_run_id": rid,
                        "reason": "infra_echo_on_completed_run",
                        "error_preview": msg[:240],
                    }
                )
                infra_excluded += 1
                continue
        snap = dict(m.get("trend_snapshot_json") or {})
        if not snap:
            snap = build_trend_snapshot_json(
                client, program_id=program_id, run_row=run_row
            )
        included_snaps.append(snap)

    n_ex = len(excluded)
    return {
        "ok": True,
        "series": s,
        "snapshots": included_snaps,
        "excluded_runs": excluded,
        "included_run_count": len(included_snaps),
        "excluded_infra_failure_count": infra_excluded,
        "excluded_other_count": max(0, n_ex - infra_excluded),
        "n_iteration_members_total": len(members),
        "exclude_infra_default": exclude_infra_default,
    }


def recompute_escalation_from_series_members(
    client: Any,
    *,
    series_id: str,
    persist: bool = True,
    exclude_infra_default: bool = True,
) -> dict[str, Any]:
    bundle = collect_plateau_snapshots_for_series(
        client,
        series_id=series_id,
        exclude_infra_default=exclude_infra_default,
    )
    if not bundle.get("ok"):
        return bundle
    snapshots = bundle["snapshots"]
    rec, rat, plateau, cf = decide_escalation_recommendation(snapshots)
    rec = assert_escalation_recommendation(rec)
    plateau_out = {
        **plateau,
        "included_run_count": bundle["included_run_count"],
        "excluded_infra_failure_count": bundle["excluded_infra_failure_count"],
        "excluded_other_count": bundle["excluded_other_count"],
        "n_iteration_members_total": bundle["n_iteration_members_total"],
    }
    if persist:
        rationale_text = f"{rec}: {rat.get('rule', '')}"
        dbrec.insert_public_repair_escalation_decision(
            client,
            {
                "series_id": series_id,
                "recommendation": rec,
                "rationale": rationale_text[:8000],
                "plateau_metrics_json": {
                    **plateau_out,
                    "rationale_struct": rat,
                    "excluded_runs": bundle["excluded_runs"],
                },
                "counterfactual_json": cf,
                "created_at": _now(),
            },
        )
        dbrec.update_public_repair_iteration_series(
            client, series_id=series_id, patch={"updated_at": _now()}
        )
    return {
        "ok": True,
        "escalation_recommendation": rec,
        "escalation_rationale": rat,
        "plateau_metrics": plateau_out,
        "counterfactual": cf,
        "excluded_runs": bundle["excluded_runs"],
        "included_run_ids_order": [
            str(x.get("repair_campaign_run_id") or "") for x in snapshots
        ],
    }


def append_completed_run_to_iteration_series(
    client: Any,
    *,
    series_id: str,
    program_id: str,
    run_row: dict[str, Any],
) -> dict[str, Any]:
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    if str(s.get("program_id") or "") != str(program_id):
        return {
            "ok": False,
            "error": "iteration_series_program_mismatch",
            "series_id": series_id,
        }
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
        _record_incompatibility(
            client,
            series_id=series_id,
            series_row=s,
            reason="series_policy_version_mismatch",
            run_id=str(run_row.get("id") or ""),
        )
        return {
            "ok": False,
            "error": "iteration_series_policy_version_mismatch",
            "series_policy_version": s.get("policy_version"),
            "expected": ITERATION_POLICY_VERSION,
        }
    rid = str(run_row.get("id") or "")
    if str(run_row.get("program_id") or "") != str(program_id):
        _record_incompatibility(
            client,
            series_id=series_id,
            series_row=s,
            reason="repair_run_program_mismatch",
            run_id=rid,
        )
        return {"ok": False, "error": "repair_run_program_mismatch"}
    if str(run_row.get("universe_name") or "") != str(s.get("universe_name") or ""):
        _record_incompatibility(
            client,
            series_id=series_id,
            series_row=s,
            reason="repair_run_universe_mismatch",
            run_id=rid,
        )
        return {
            "ok": False,
            "error": "repair_run_universe_incompatible_with_series",
            "run_universe": run_row.get("universe_name"),
            "series_universe": s.get("universe_name"),
        }
    if str(run_row.get("status") or "") != "completed" or not run_row.get(
        "final_decision"
    ):
        return {
            "ok": False,
            "error": "repair_run_not_completed_or_missing_final_decision",
            "status": run_row.get("status"),
        }

    existing = dbrec.fetch_public_repair_iteration_member_by_run_id(
        client, repair_campaign_run_id=rid
    )
    if existing:
        esc = recompute_escalation_from_series_members(
            client, series_id=series_id, persist=True
        )
        return {
            "ok": True,
            "idempotent": True,
            "iteration_member_id": str(existing["id"]),
            "repair_campaign_run_id": rid,
            "escalation_recommendation": esc.get("escalation_recommendation"),
            "plateau_metrics": esc.get("plateau_metrics"),
        }

    snap = build_trend_snapshot_json(
        client, program_id=program_id, run_row=run_row
    )
    seq = dbrec.fetch_max_sequence_public_repair_iteration_member(
        client, series_id=series_id
    ) + int(1)
    dbrec.insert_public_repair_iteration_member(
        client,
        {
            "series_id": series_id,
            "member_kind": "repair_campaign",
            "repair_campaign_run_id": rid,
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
        "repair_campaign_run_id": rid,
        "escalation_recommendation": esc.get("escalation_recommendation"),
        "escalation_rationale": esc.get("escalation_rationale"),
        "plateau_metrics": esc.get("plateau_metrics"),
        "counterfactual": esc.get("counterfactual"),
        "excluded_runs": esc.get("excluded_runs"),
    }


def pause_public_repair_series(
    client: Any, *, series_id: str, reason: str
) -> dict[str, Any]:
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    if str(s.get("status") or "") != "active":
        return {
            "ok": False,
            "error": "iteration_series_not_active_cannot_pause",
            "status": s.get("status"),
        }
    g = _governance_base(s)
    g["pause"] = {"at": _now(), "reason": str(reason)[:4000]}
    dbrec.update_public_repair_iteration_series(
        client,
        series_id=series_id,
        patch={
            "status": "paused",
            "governance_audit_json": g,
            "updated_at": _now(),
        },
    )
    return {"ok": True, "series_id": series_id, "status": "paused"}


def resume_public_repair_series(
    client: Any, *, series_id: str, audit_note: str = ""
) -> dict[str, Any]:
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    if str(s.get("status") or "") != "paused":
        return {
            "ok": False,
            "error": "iteration_series_not_paused_cannot_resume",
            "status": s.get("status"),
        }
    g = _governance_base(s)
    resumes = list(g.get("resumes") or [])
    resumes.append({"at": _now(), "note": str(audit_note)[:4000]})
    g["resumes"] = resumes
    dbrec.update_public_repair_iteration_series(
        client,
        series_id=series_id,
        patch={
            "status": "active",
            "governance_audit_json": g,
            "updated_at": _now(),
        },
    )
    return {"ok": True, "series_id": series_id, "status": "active"}


def close_public_repair_series(
    client: Any, *, series_id: str, reason: str
) -> dict[str, Any]:
    s = dbrec.fetch_public_repair_iteration_series(client, series_id=series_id)
    if not s:
        return {"ok": False, "error": "iteration_series_not_found"}
    st = str(s.get("status") or "")
    if st not in ("active", "paused"):
        return {
            "ok": False,
            "error": "iteration_series_already_closed_or_invalid",
            "status": st,
        }
    g = _governance_base(s)
    g["closure"] = {"at": _now(), "reason": str(reason)[:4000]}
    dbrec.update_public_repair_iteration_series(
        client,
        series_id=series_id,
        patch={
            "status": "closed",
            "governance_audit_json": g,
            "updated_at": _now(),
        },
    )
    return {"ok": True, "series_id": series_id, "status": "closed"}


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

    app = append_completed_run_to_iteration_series(
        client,
        series_id=series_id,
        program_id=program_id,
        run_row=run_row,
    )
    if not app.get("ok"):
        return {**out, **app}
    out["iteration_member_added"] = not bool(app.get("idempotent"))
    out["iteration_append"] = app
    if app.get("sequence_number") is not None:
        out["sequence_number"] = app["sequence_number"]
    out["escalation_recommendation"] = app.get("escalation_recommendation")
    out["escalation_rationale"] = app.get("escalation_rationale")
    out["plateau_metrics"] = app.get("plateau_metrics")
    out["counterfactual"] = app.get("counterfactual")
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
    client: Any,
    *,
    series_id: str,
    exclude_infra_default: bool = True,
) -> dict[str, Any]:
    bundle = collect_plateau_snapshots_for_series(
        client,
        series_id=series_id,
        exclude_infra_default=exclude_infra_default,
    )
    if not bundle.get("ok"):
        return bundle
    snapshots = bundle["snapshots"]
    rec, rat, plateau, cf = decide_escalation_recommendation(snapshots)
    rec = assert_escalation_recommendation(rec)
    plateau_out = {
        **plateau,
        "included_run_count": bundle["included_run_count"],
        "excluded_infra_failure_count": bundle["excluded_infra_failure_count"],
        "excluded_other_count": bundle["excluded_other_count"],
        "n_iteration_members_total": bundle["n_iteration_members_total"],
    }
    return {
        "ok": True,
        "series": bundle["series"],
        "n_members": bundle["n_iteration_members_total"],
        "escalation_recommendation": rec,
        "rationale": rat,
        "plateau_metrics": plateau_out,
        "counterfactual": cf,
        "excluded_runs": bundle["excluded_runs"],
        "ephemeral": True,
        "note": "Computed from iteration members with Phase 21 infra quarantine defaults.",
    }


def _delta_num(a: Any, b: Any) -> Any:
    try:
        if a is None or b is None:
            return None
        return float(a) - float(b)
    except (TypeError, ValueError):
        return None


def _premium_discovery_gate_checklist(plateau_bundle: dict[str, Any]) -> dict[str, Any]:
    rec = str(plateau_bundle.get("escalation_recommendation") or "")
    rat = plateau_bundle.get("rationale") or {}
    pm = plateau_bundle.get("plateau_metrics") or {}
    rule = str(rat.get("rule") or "")
    return {
        "recommendation_matches_open_premium": rec == "open_targeted_premium_discovery",
        "rule": rule,
        "n_iterations_used": pm.get("n_iterations"),
        "included_run_count": pm.get("included_run_count"),
        "joined_delta_first_last": pm.get("joined_delta_first_last"),
        "thin_latest": pm.get("thin_series", [None])[-1]
        if isinstance(pm.get("thin_series"), list)
        else None,
        "premium_share_latest": pm.get("premium_share_latest"),
        "infra_quarantine_applied_default": True,
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
    prev = decisions[1] if len(decisions) > 1 else None
    trend_deltas: dict[str, Any] = {}
    if latest and prev:
        try:
            lj = latest.get("plateau_metrics_json") or {}
            pj = prev.get("plateau_metrics_json") or {}
            if isinstance(lj, dict) and isinstance(pj, dict):
                trend_deltas = {
                    "included_run_count_delta": _delta_num(
                        lj.get("included_run_count"), pj.get("included_run_count")
                    ),
                    "n_iterations_delta": _delta_num(
                        lj.get("n_iterations"), pj.get("n_iterations")
                    ),
                }
        except Exception:  # noqa: BLE001
            trend_deltas = {}

    compatibility_basis = {
        "series_universe": s.get("universe_name"),
        "series_policy_version": s.get("policy_version"),
        "iteration_policy_expected": ITERATION_POLICY_VERSION,
        "series_status": s.get("status"),
        "governance_audit": s.get("governance_audit_json"),
    }
    brief = {
        "version": 2,
        "series_id": series_id,
        "program_id": s.get("program_id"),
        "universe_name": s.get("universe_name"),
        "policy_version": s.get("policy_version"),
        "series_status": s.get("status"),
        "compatibility_basis": compatibility_basis,
        "included_runs": {},
        "latest_persisted_escalation": latest,
        "recomputed_from_members": {
            "recommendation": plateau_bundle.get("escalation_recommendation"),
            "rationale": plateau_bundle.get("rationale"),
            "plateau_metrics": plateau_bundle.get("plateau_metrics"),
            "counterfactual": plateau_bundle.get("counterfactual"),
            "excluded_runs": plateau_bundle.get("excluded_runs"),
            "trend_deltas_vs_prior_persisted": trend_deltas,
        },
        "final_recommendation": plateau_bundle.get("escalation_recommendation"),
        "counterfactual_summary": plateau_bundle.get("counterfactual"),
        "premium_discovery_gate_checklist": _premium_discovery_gate_checklist(
            plateau_bundle
        ),
    }
    snaps = collect_plateau_snapshots_for_series(
        client, series_id=series_id, exclude_infra_default=True
    )
    if snaps.get("ok"):
        brief["included_runs"] = {
            "repair_campaign_run_ids_in_order": [
                str(x.get("repair_campaign_run_id") or "")
                for x in snaps["snapshots"]
            ],
            "public_depth_run_ids_in_order": [
                str(x.get("public_depth_run_id") or "")
                for x in snaps["snapshots"]
            ],
            "member_kinds_in_order": [
                str(x.get("member_kind") or "repair_campaign")
                for x in snaps["snapshots"]
            ],
            "included_run_count": snaps["included_run_count"],
        }
        brief["excluded_runs_with_reasons"] = snaps["excluded_runs"]

    lines = [
        "# Public repair escalation brief (Phase 21)",
        "",
        f"- **Series**: `{series_id}`",
        f"- **Program**: `{brief.get('program_id')}`",
        f"- **Universe**: `{brief.get('universe_name')}`",
        f"- **Compatibility**: policy `{s.get('policy_version')}` (expected `{ITERATION_POLICY_VERSION}`), status `{s.get('status')}`",
        "",
        "## Final recommendation (recomputed, infra-quarantine default)",
        "",
        f"`{plateau_bundle.get('escalation_recommendation')}`",
        "",
        "## Included runs",
        "",
        "```json",
        json.dumps(brief.get("included_runs") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Excluded runs (audit)",
        "",
        "```json",
        json.dumps(
            brief.get("excluded_runs_with_reasons") or [], indent=2, ensure_ascii=False
        ),
        "```",
        "",
        "## Trend deltas vs prior persisted decision",
        "",
        "```json",
        json.dumps(trend_deltas, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Counterfactual summary",
        "",
        "```json",
        json.dumps(
            plateau_bundle.get("counterfactual") or {}, indent=2, ensure_ascii=False
        ),
        "```",
        "",
        "## Premium discovery gate checklist",
        "",
        "```json",
        json.dumps(
            brief.get("premium_discovery_gate_checklist") or {},
            indent=2,
            ensure_ascii=False,
        ),
        "```",
        "",
        "## Latest persisted recommendation (DB row)",
        "",
        f"`{(latest or {}).get('recommendation')}`",
        "",
        str((latest or {}).get("rationale") or ""),
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
        # Top-level UUID for operators (avoid digging into active_iteration_series[0].id).
        "active_series_id": series_id,
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
    row = actives[0]
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if prog and str(prog.get("status") or "").lower() == "archived":
        return {
            "ok": False,
            "error": "program_archived_active_series_resolution_blocked",
            "program_id": program_id,
        }
    if prog and str(row.get("universe_name") or "") != str(
        prog.get("universe_name") or ""
    ):
        return {
            "ok": False,
            "error": "active_series_universe_incompatible_with_program",
            "series_universe": row.get("universe_name"),
            "program_universe": prog.get("universe_name"),
        }
    if str(row.get("policy_version") or "") != ITERATION_POLICY_VERSION:
        return {
            "ok": False,
            "error": "active_series_policy_version_incompatible",
            "series_policy_version": row.get("policy_version"),
            "expected_policy_version": ITERATION_POLICY_VERSION,
        }
    return {"ok": True, "series_id": str(row["id"]), "series": row}


def advance_public_repair_series(
    settings: Settings,
    *,
    program_id: str,
    universe_name: str | None = None,
    series_id_override: str | None = None,
    attach_repair_run_id: str | None = None,
    run_new_campaign: bool = True,
    dry_run_buildout: bool = False,
    skip_reruns: bool = False,
    panel_limit: int = 8000,
    campaign_panel_limit: int = 6000,
    max_symbols_factor: int = 50,
    validation_panel_limit: int = 2000,
    forward_panel_limit: int = 2000,
    state_change_limit: int = 400,
) -> dict[str, Any]:
    """
    Golden path: compatible active series → campaign or attach → append → plateau/escalation → brief.
    """
    from public_repair_iteration.resolver import (
        resolve_iteration_series_id,
        resolve_repair_campaign_run_id,
    )

    client = get_supabase_client(settings)
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    uni = (universe_name or "").strip() or str(prog.get("universe_name") or "")

    if series_id_override:
        sr = resolve_iteration_series_id(
            client,
            series_id_override,
            program_id=program_id,
            program=prog,
        )
    else:
        sr = resolve_iteration_series_id(
            client,
            "latest-active-series",
            program_id=program_id,
            program=prog,
        )
    if not sr.get("ok"):
        return sr
    series_id = str(sr["series_id"])
    series_row = sr["series"]

    run_row: dict[str, Any] | None = None
    camp_out: dict[str, Any] | None = None
    if run_new_campaign:
        if attach_repair_run_id:
            return {
                "ok": False,
                "error": "attach_repair_run_id_incompatible_with_run_new_campaign",
            }
        camp_out = run_public_repair_campaign(
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
        if not camp_out.get("ok"):
            return {
                "ok": False,
                "error": "repair_campaign_failed",
                "repair_campaign": camp_out,
                "series_id": series_id,
            }
        rid = str(camp_out.get("repair_campaign_run_id") or "")
        run_row = dbrec.fetch_public_repair_campaign_run(client, run_id=rid)
    else:
        if not attach_repair_run_id:
            return {
                "ok": False,
                "error": "attach_repair_run_id_required_when_skipping_campaign",
            }
        rc = resolve_repair_campaign_run_id(
            client,
            attach_repair_run_id.strip(),
            program_id=program_id,
            series=series_row,
            program=prog,
        )
        if not rc.get("ok"):
            return {**rc, "series_id": series_id}
        run_row = rc.get("run")
        if not isinstance(run_row, dict):
            return {"ok": False, "error": "repair_run_row_missing", "series_id": series_id}

    assert run_row is not None
    app = append_completed_run_to_iteration_series(
        client,
        series_id=series_id,
        program_id=program_id,
        run_row=run_row,
    )
    if not app.get("ok"):
        return {**app, "repair_campaign": camp_out, "series_id": series_id}

    brief_bundle = export_public_repair_escalation_brief(client, series_id=series_id)
    rec = str(app.get("escalation_recommendation") or "")
    summary = (
        f"[advance-public-repair-series] program={program_id} series={series_id} "
        f"run={run_row.get('id')} recommendation={rec} "
        f"included_runs={app.get('plateau_metrics', {}).get('included_run_count')} "
        f"excluded_infra={app.get('plateau_metrics', {}).get('excluded_infra_failure_count')}"
    )
    return {
        "ok": True,
        "program_id": program_id,
        "universe_name": uni,
        "series_id": series_id,
        "repair_campaign": camp_out,
        "iteration_append": app,
        "escalation_recommendation": rec,
        "operator_summary": summary,
        "brief": brief_bundle.get("brief"),
        "markdown": brief_bundle.get("markdown"),
    }
