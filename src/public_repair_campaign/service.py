"""Orchestrate baseline → build-out → comparison → gated revalidation → decision."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config import Settings
from db import records as dbrec
from db.client import get_supabase_client
from public_buildout.constants import POLICY_VERSION as BUILDOUT_POLICY_VERSION
from public_buildout.orchestrator import build_public_exclusion_actions_payload
from public_buildout.orchestrator import run_targeted_public_buildout
from public_buildout.revalidation import build_revalidation_trigger
from public_depth.diagnostics import compute_substrate_coverage
from public_repair_campaign.comparisons import (
    build_improvement_interpretation,
    compare_survival_distributions,
)
from public_repair_campaign.constants import REPAIR_CAMPAIGN_POLICY_VERSION
from public_repair_campaign.decision_policy import (
    assert_final_decision,
    decide_final_repair_branch,
    substrate_improved_from_buildout,
)
from validation_campaign.service import report_program_survival_distribution, run_validation_campaign

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step(
    client: Any,
    *,
    repair_campaign_run_id: str,
    step_name: str,
    status: str,
    detail_json: dict[str, Any],
) -> None:
    dbrec.insert_public_repair_campaign_step(
        client,
        {
            "repair_campaign_run_id": repair_campaign_run_id,
            "step_name": step_name,
            "status": status,
            "detail_json": detail_json,
            "created_at": _now(),
        },
    )


def persist_universe_coverage_snapshot(
    client: Any,
    *,
    universe_name: str,
    snapshot_label: str,
    panel_limit: int,
) -> str:
    metrics, excl = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=int(panel_limit),
    )
    return dbrec.insert_public_depth_coverage_report(
        client,
        {
            "public_depth_run_id": None,
            "universe_name": universe_name,
            "snapshot_label": snapshot_label,
            "metrics_json": metrics,
            "exclusion_distribution_json": excl,
        },
    )


def run_public_repair_campaign(
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

    universe = (universe_name or "").strip() or str(prog.get("universe_name") or "")
    if not universe:
        return {"ok": False, "error": "universe_name_required", "program_id": program_id}

    run_id = dbrec.insert_public_repair_campaign_run(
        client,
        {
            "program_id": program_id,
            "universe_name": universe,
            "status": "running",
            "baseline_validation_snapshot_json": {},
            "rerun_skip_reason_json": {},
            "rationale_json": {},
            "created_at": _now(),
        },
    )

    try:
        # --- A: baseline ---
        _step(client, repair_campaign_run_id=run_id, step_name="baseline_capture", status="running", detail_json={})
        base_cov = persist_universe_coverage_snapshot(
            client,
            universe_name=universe,
            snapshot_label="before",
            panel_limit=panel_limit,
        )
        ex_payload = build_public_exclusion_actions_payload(
            client, universe_name=universe, panel_limit=panel_limit
        )
        ex_id = None
        if ex_payload.get("ok"):
            ex_id = dbrec.insert_public_exclusion_action_report(
                client,
                {
                    "universe_name": universe,
                    "policy_version": BUILDOUT_POLICY_VERSION,
                    "metrics_json": ex_payload.get("metrics") or {},
                    "exclusion_distribution_json": ex_payload.get("exclusion_distribution")
                    or {},
                    "action_queue_json": ex_payload.get("action_queue") or [],
                },
            )

        surv0 = report_program_survival_distribution(client, program_id=program_id)
        if not surv0.get("ok"):
            raise RuntimeError(surv0.get("error") or "baseline_survival_failed")

        latest_camp = dbrec.fetch_latest_validation_campaign_run_for_program(
            client, program_id=program_id
        )
        baseline_camp_id = str(latest_camp["id"]) if latest_camp else None
        baseline_rec = (
            str(latest_camp.get("recommendation") or "") if latest_camp else None
        )

        dbrec.update_public_repair_campaign_run(
            client,
            run_id=run_id,
            patch={
                "baseline_coverage_report_id": base_cov,
                "baseline_exclusion_action_report_id": ex_id,
                "baseline_campaign_run_id": baseline_camp_id,
                "baseline_validation_snapshot_json": surv0,
                "baseline_campaign_recommendation": baseline_rec,
            },
        )
        _step(
            client,
            repair_campaign_run_id=run_id,
            step_name="baseline_capture",
            status="completed",
            detail_json={
                "baseline_coverage_report_id": base_cov,
                "baseline_exclusion_action_report_id": ex_id,
                "baseline_campaign_run_id": baseline_camp_id,
            },
        )

        # --- B: targeted build-out ---
        _step(
            client,
            repair_campaign_run_id=run_id,
            step_name="targeted_buildout",
            status="running",
            detail_json={"dry_run": dry_run_buildout},
        )
        bout = run_targeted_public_buildout(
            settings,
            universe_name=universe,
            panel_limit=int(panel_limit),
            max_symbols_factor=int(max_symbols_factor),
            validation_panel_limit=int(validation_panel_limit),
            forward_panel_limit=int(forward_panel_limit),
            state_change_limit=int(state_change_limit),
            dry_run=bool(dry_run_buildout),
        )
        if not bout.get("ok"):
            _step(
                client,
                repair_campaign_run_id=run_id,
                step_name="targeted_buildout",
                status="failed",
                detail_json={"error": bout.get("error")},
            )
            dbrec.update_public_repair_campaign_run(
                client,
                run_id=run_id,
                patch={"status": "failed", "error_message": str(bout.get("error"))[:4000]},
            )
            return {**bout, "repair_campaign_run_id": run_id}

        bout_run_id = str(bout.get("public_buildout_run_id") or "")
        imp_id = bout.get("improvement_report_id")
        imp_id_s = str(imp_id) if imp_id else None
        improvement = bout.get("improvement") if isinstance(bout.get("improvement"), dict) else None

        after_cov = persist_universe_coverage_snapshot(
            client,
            universe_name=universe,
            snapshot_label="after",
            panel_limit=panel_limit,
        )

        dbrec.update_public_repair_campaign_run(
            client,
            run_id=run_id,
            patch={
                "targeted_buildout_run_id": bout_run_id or None,
                "after_coverage_report_id": after_cov,
                "improvement_report_id": imp_id_s,
            },
        )
        _step(
            client,
            repair_campaign_run_id=run_id,
            step_name="targeted_buildout",
            status="completed",
            detail_json={
                "public_buildout_run_id": bout_run_id,
                "improvement_report_id": imp_id_s,
                "after_coverage_report_id": after_cov,
            },
        )

        # --- C: improvement (persisted via buildout row; summarized in bout) ---
        _step(
            client,
            repair_campaign_run_id=run_id,
            step_name="improvement_compute",
            status="completed",
            detail_json={"improvement_summary_keys": list((improvement or {}).keys())},
        )

        # --- D: rerun gate ---
        trigger = build_revalidation_trigger(client, program_id=program_id)
        reran15 = False
        reran16 = False
        skip_json: dict[str, Any] = {}
        after_camp_id: str | None = None
        after_rec: str | None = None
        after_metrics: dict[str, Any] | None = None
        camp_out: dict[str, Any] = {}

        gate_ok = bool(
            trigger.get("ok")
            and trigger.get("recommend_rerun_phase15")
            and trigger.get("recommend_rerun_phase16")
        )

        if skip_reruns:
            skip_json = {"reason": "skip_reruns_flag"}
            _step(
                client,
                repair_campaign_run_id=run_id,
                step_name="phase15_rerun",
                status="skipped",
                detail_json=skip_json,
            )
            _step(
                client,
                repair_campaign_run_id=run_id,
                step_name="phase16_rerun",
                status="skipped",
                detail_json=skip_json,
            )
        elif not gate_ok:
            skip_json = {
                "reason": "revalidation_gate_not_met",
                "trigger": {
                    "recommend_rerun_phase15": trigger.get("recommend_rerun_phase15"),
                    "recommend_rerun_phase16": trigger.get("recommend_rerun_phase16"),
                },
            }
            _step(
                client,
                repair_campaign_run_id=run_id,
                step_name="phase15_rerun",
                status="skipped",
                detail_json=skip_json,
            )
            _step(
                client,
                repair_campaign_run_id=run_id,
                step_name="phase16_rerun",
                status="skipped",
                detail_json=skip_json,
            )
        else:
            _step(
                client,
                repair_campaign_run_id=run_id,
                step_name="phase15_rerun",
                status="running",
                detail_json={},
            )
            _step(
                client,
                repair_campaign_run_id=run_id,
                step_name="phase16_rerun",
                status="running",
                detail_json={},
            )
            camp_out = run_validation_campaign(
                client,
                program_id=program_id,
                run_mode="force_rerun",
                panel_limit=int(campaign_panel_limit),
            )
            if not camp_out.get("ok"):
                skip_json = {"reason": "campaign_failed", "detail": camp_out}
                _step(
                    client,
                    repair_campaign_run_id=run_id,
                    step_name="phase16_rerun",
                    status="failed",
                    detail_json=skip_json,
                )
                _step(
                    client,
                    repair_campaign_run_id=run_id,
                    step_name="phase15_rerun",
                    status="failed",
                    detail_json=skip_json,
                )
                dbrec.update_public_repair_campaign_run(
                    client,
                    run_id=run_id,
                    patch={
                        "rerun_skip_reason_json": skip_json,
                        "reran_phase15": False,
                        "reran_phase16": False,
                    },
                )
            else:
                after_camp_id = str(camp_out["campaign_run_id"])
                after_rec = str(camp_out.get("recommendation") or "")
                agg = camp_out.get("aggregate_metrics")
                after_metrics = agg if isinstance(agg, dict) else {}
                hyps_reran = after_metrics.get("hypotheses_reran") or []
                reran16 = True
                reran15 = bool(hyps_reran)
                _step(
                    client,
                    repair_campaign_run_id=run_id,
                    step_name="phase15_rerun",
                    status="completed",
                    detail_json={"hypotheses_reran": hyps_reran},
                )
                _step(
                    client,
                    repair_campaign_run_id=run_id,
                    step_name="phase16_rerun",
                    status="completed",
                    detail_json={"campaign_run_id": after_camp_id},
                )

        dbrec.update_public_repair_campaign_run(
            client,
            run_id=run_id,
            patch={
                "reran_phase15": reran15,
                "reran_phase16": reran16,
                "rerun_skip_reason_json": skip_json,
                "after_campaign_run_id": after_camp_id,
            },
        )

        # --- E: comparison ---
        surv1 = report_program_survival_distribution(client, program_id=program_id)
        if not surv1.get("ok"):
            surv1 = {"ok": False, "distribution": {}}

        before_dist = (surv0.get("distribution") or {}) if isinstance(surv0, dict) else {}
        after_dist = (surv1.get("distribution") or {}) if isinstance(surv1, dict) else {}
        survival_cmp = compare_survival_distributions(before_dist, after_dist)
        interp = build_improvement_interpretation(
            survival_compare=survival_cmp,
            before_rec=baseline_rec,
            after_rec=after_rec,
            after_campaign_metrics=after_metrics,
        )

        cmp_id = dbrec.upsert_public_repair_revalidation_comparison(
            client,
            {
                "repair_campaign_run_id": run_id,
                "before_survival_distribution_json": dict(before_dist),
                "after_survival_distribution_json": dict(after_dist),
                "before_campaign_recommendation": baseline_rec,
                "after_campaign_recommendation": after_rec,
                "improvement_interpretation_json": interp,
                "created_at": _now(),
            },
        )
        _step(
            client,
            repair_campaign_run_id=run_id,
            step_name="revalidation_comparison",
            status="completed",
            detail_json={"comparison_id": cmp_id},
        )

        substrate_ok = substrate_improved_from_buildout(improvement)
        reruns_executed = bool(camp_out.get("ok") and after_camp_id)

        final_decision, rationale = decide_final_repair_branch(
            substrate_improved=substrate_ok,
            reruns_executed=reruns_executed,
            improvement_summary=improvement,
            survival_compare=survival_cmp,
            before_campaign_recommendation=baseline_rec,
            after_campaign_recommendation=after_rec,
            after_campaign_metrics=after_metrics,
        )
        final_decision = assert_final_decision(final_decision)
        rationale["comparison_id"] = cmp_id
        rationale["repair_campaign_run_id"] = run_id

        dbrec.insert_public_repair_campaign_decision(
            client,
            {
                "repair_campaign_run_id": run_id,
                "decision": final_decision,
                "policy_version": REPAIR_CAMPAIGN_POLICY_VERSION,
                "rationale_json": rationale,
                "created_at": _now(),
            },
        )

        dbrec.update_public_repair_campaign_run(
            client,
            run_id=run_id,
            patch={
                "status": "completed",
                "final_decision": final_decision,
                "rationale_json": rationale,
            },
        )

        _step(
            client,
            repair_campaign_run_id=run_id,
            step_name="final_decision",
            status="completed",
            detail_json={"decision": final_decision},
        )

        return {
            "ok": True,
            "repair_campaign_run_id": run_id,
            "final_decision": final_decision,
            "rationale": rationale,
            "baseline_coverage_report_id": base_cov,
            "after_coverage_report_id": after_cov,
            "targeted_buildout_run_id": bout_run_id,
            "improvement_report_id": imp_id_s,
            "after_campaign_run_id": after_camp_id,
            "reran_phase15": reran15,
            "reran_phase16": reran16,
            "comparison_id": cmp_id,
            "improvement": improvement,
        }
    except Exception as ex:  # noqa: BLE001
        logger.exception("public repair campaign")
        from public_repair_iteration.infra_noise import annotate_failure_for_audit

        prev = dbrec.fetch_public_repair_campaign_run(client, run_id=run_id)
        rj: dict[str, Any] = dict((prev or {}).get("rationale_json") or {})
        rj["failure_audit"] = annotate_failure_for_audit(ex)
        dbrec.update_public_repair_campaign_run(
            client,
            run_id=run_id,
            patch={
                "status": "failed",
                "error_message": str(ex)[:4000],
                "rationale_json": rj,
            },
        )
        _step(
            client,
            repair_campaign_run_id=run_id,
            step_name="error",
            status="failed",
            detail_json={"error": str(ex)[:2000]},
        )
        return {"ok": False, "repair_campaign_run_id": run_id, "error": str(ex)}


def report_public_repair_campaign(client: Any, *, repair_campaign_run_id: str) -> dict[str, Any]:
    run = dbrec.fetch_public_repair_campaign_run(client, run_id=repair_campaign_run_id)
    if not run:
        return {"ok": False, "error": "repair_campaign_run_not_found"}
    steps = dbrec.fetch_public_repair_campaign_steps(
        client, repair_campaign_run_id=repair_campaign_run_id
    )
    decisions = dbrec.fetch_public_repair_campaign_decisions(
        client, repair_campaign_run_id=repair_campaign_run_id
    )
    comp = dbrec.fetch_public_repair_revalidation_comparison_for_run(
        client, repair_campaign_run_id=repair_campaign_run_id
    )
    return {
        "ok": True,
        "run": run,
        "steps": steps,
        "decisions": decisions,
        "comparison": comp,
    }


def compare_repair_revalidation_outcomes(
    client: Any, *, repair_campaign_run_id: str
) -> dict[str, Any]:
    bundle = report_public_repair_campaign(client, repair_campaign_run_id=repair_campaign_run_id)
    if not bundle.get("ok"):
        return bundle
    comp = bundle.get("comparison")
    if not comp:
        return {
            "ok": False,
            "error": "comparison_not_found",
            "repair_campaign_run_id": repair_campaign_run_id,
        }
    return {"ok": True, "comparison": comp, "run": bundle["run"]}


def export_public_repair_decision_brief(
    client: Any, *, repair_campaign_run_id: str
) -> dict[str, Any]:
    bundle = report_public_repair_campaign(client, repair_campaign_run_id=repair_campaign_run_id)
    if not bundle.get("ok"):
        return bundle
    run = bundle["run"]
    comp = bundle.get("comparison") or {}
    decisions = bundle.get("decisions") or []
    dec0 = decisions[0] if decisions else {}
    interp = comp.get("improvement_interpretation_json") or {}

    brief = {
        "version": 1,
        "repair_campaign_run_id": repair_campaign_run_id,
        "program_id": run.get("program_id"),
        "universe_name": run.get("universe_name"),
        "final_decision": run.get("final_decision"),
        "reran_phase15": run.get("reran_phase15"),
        "reran_phase16": run.get("reran_phase16"),
        "rerun_skip_reason_json": run.get("rerun_skip_reason_json"),
        "comparison": {
            "before_survival_distribution_json": comp.get("before_survival_distribution_json"),
            "after_survival_distribution_json": comp.get("after_survival_distribution_json"),
            "before_campaign_recommendation": comp.get("before_campaign_recommendation"),
            "after_campaign_recommendation": comp.get("after_campaign_recommendation"),
            "improvement_interpretation_json": interp,
        },
        "latest_decision_row": dec0,
        "rationale_json": run.get("rationale_json"),
    }
    lines = [
        "# Public repair campaign decision brief",
        "",
        f"- **Run**: `{repair_campaign_run_id}`",
        f"- **Program**: `{run.get('program_id')}`",
        f"- **Universe**: `{run.get('universe_name')}`",
        "",
        "## Final decision",
        "",
        f"`{run.get('final_decision')}`",
        "",
        "## Reruns",
        "",
        f"- reran_phase15: {run.get('reran_phase15')}",
        f"- reran_phase16: {run.get('reran_phase16')}",
        "",
        "## Survival (before → after)",
        "",
        f"- before: `{comp.get('before_survival_distribution_json')}`",
        f"- after: `{comp.get('after_survival_distribution_json')}`",
        "",
        "## Campaign recommendation",
        "",
        f"- before: `{comp.get('before_campaign_recommendation')}`",
        f"- after: `{comp.get('after_campaign_recommendation')}`",
        "",
        "## Interpretation",
        "",
        "```json",
        json.dumps(interp, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    return {"ok": True, "brief": brief, "markdown": "\n".join(lines)}


def list_repair_campaigns(client: Any, *, program_id: str, limit: int = 20) -> dict[str, Any]:
    rows = dbrec.list_public_repair_campaign_runs_for_program(
        client, program_id=program_id, limit=limit
    )
    return {"ok": True, "program_id": program_id, "runs": rows}
