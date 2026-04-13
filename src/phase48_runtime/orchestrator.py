"""Single-cycle proactive research orchestrator (idempotent, budgeted)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase46.alert_ledger import append_alert, default_ledger_path as default_alert_ledger_path

from phase48_runtime.bounded_debate import run_bounded_debate
from phase48_runtime.budget_policy import default_budget_policy
from phase48_runtime.discovery_pipeline import append_discovery_candidate, default_discovery_path
from phase48_runtime.job_registry import (
    JOB_TYPES,
    append_job,
    default_registry_path,
    job_with_dedupe_exists,
    load_registry,
    update_job,
    update_metadata,
)
from phase48_runtime.premium_escalation import evaluate_premium_candidate
from phase48_runtime.phase49_recommend import recommend_phase49
from phase48_runtime.trigger_engine import clear_manual_triggers_file, evaluate_triggers


def _resolve_path(stored: str, repo_root: Path) -> Path | None:
    p = Path(stored)
    if p.is_file():
        return p
    cand = repo_root / "docs" / "operator_closeout" / p.name
    return cand if cand.is_file() else None


def _read_json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def run_phase48_proactive_research_runtime(
    *,
    phase46_bundle_in: str,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
    discovery_path: Path | None = None,
    decision_ledger_path: Path | None = None,
    skip_alerts: bool = False,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    p46_path = Path(phase46_bundle_in)
    if not p46_path.is_absolute():
        p46_path = (root / p46_path).resolve()
    phase46_bundle = _read_json(p46_path)

    p45_path = _resolve_path(str(phase46_bundle.get("input_phase45_bundle_path") or ""), root)
    phase45_bundle: dict[str, Any] | None = _read_json(p45_path) if p45_path else None

    reg_path = registry_path or default_registry_path(root)
    disc_path = discovery_path or default_discovery_path(root)
    dec_path = decision_ledger_path
    if dec_path is None:
        lp = phase46_bundle.get("decision_trace_ledger_path")
        if isinstance(lp, str):
            r = _resolve_path(lp, root)
            dec_path = r if r else default_decision_path_fallback(root)
        else:
            dec_path = default_decision_path_fallback(root)

    policy = default_budget_policy()
    max_jobs = int(policy.get("max_jobs_per_run") or 5)
    max_debate_turns = int(policy.get("max_debate_turns") or 3)
    max_roles = int(policy.get("max_participating_roles") or 5)
    max_candidates = int(policy.get("max_candidate_publishes_per_cycle") or 3)
    max_alerts = int(policy.get("max_alerts_per_cycle") or 2)

    registry = load_registry(reg_path)
    meta = dict(registry.get("metadata") or {})

    triggers = evaluate_triggers(
        repo_root=root,
        phase46_bundle=phase46_bundle,
        phase45_bundle=phase45_bundle,
        decision_ledger_path=dec_path,
        registry_metadata=meta,
        policy=policy,
    )

    jobs_created: list[dict[str, Any]] = []
    created_dedupes: set[str] = set()
    cycle_now = datetime.now(timezone.utc).isoformat()

    for t in triggers:
        if len(jobs_created) >= max_jobs:
            break
        dk = str(t.get("dedupe_key") or "")
        if not dk or dk in created_dedupes:
            continue
        reg = load_registry(reg_path)
        if job_with_dedupe_exists(reg, dk):
            continue
        jt = str(t.get("suggested_job_type") or "evidence.refresh")
        if jt not in JOB_TYPES:
            jt = "evidence.refresh"
        asset_scope = {"asset_id": str((phase46_bundle.get("founder_read_model") or {}).get("asset_id") or "unknown")}
        budget_class = (
            "bounded_debate"
            if jt == "debate.execute"
            else "cheap_deterministic"
            if jt == "evidence.refresh"
            else "moderate_refresh"
        )
        job = append_job(
            reg_path,
            job_type=jt,
            asset_scope=asset_scope,
            trigger_source=str(t.get("trigger_type") or "unknown"),
            priority=int(t.get("priority") or 10),
            budget_class=budget_class,
            dedupe_key=dk,
            trigger_payload={"trigger": t},
        )
        created_dedupes.add(dk)
        jobs_created.append(job)

    jobs_executed: list[dict[str, Any]] = []
    last_debate_job_id = ""
    bounded_debate_outputs: list[dict[str, Any]] = []
    premium_escalation_candidates: list[dict[str, Any]] = []
    discovery_candidates: list[dict[str, Any]] = []
    cockpit_surface_outputs: list[dict[str, Any]] = []
    alerts_written = 0
    manual_cleared: list[str] = []

    rm = phase46_bundle.get("founder_read_model") or {}
    gs = rm.get("gate_summary") or {}
    uncertainties = rm.get("current_uncertainties") or []

    for job in jobs_created:
        jid = job["job_id"]
        update_job(reg_path, jid, status="running", increment_attempt=True)
        jt = job["job_type"]
        out_art: list[Any] = []
        summary = ""

        if jt == "evidence.refresh":
            summary = (
                f"Static evidence refresh against bundle `generated_utc={phase46_bundle.get('generated_utc')}`; "
                f"no substrate mutation. Gate: {gs.get('gate_status')} / {gs.get('primary_block_category')}."
            )
            out_art.append({"kind": "bundle_pointer", "phase46_path": str(p46_path)})
        elif jt == "hypothesis.check":
            summary = (
                f"Hypothesis posture unchanged vs authoritative `{rm.get('authoritative_recommendation')}` "
                f"under `{rm.get('authoritative_phase')}`."
            )
            out_art.append({"kind": "authoritative_check", "ok": True})
        elif jt == "debate.execute":
            trig = (job.get("trigger_payload") or {}).get("trigger") or {}
            hint = ""
            if trig.get("trigger_type") in ("closeout_reopen_candidate", "named_source_signal"):
                hint = "reopen"
            ctx = {
                "authoritative_recommendation": rm.get("authoritative_recommendation"),
                "primary_block_category": gs.get("primary_block_category"),
                "gate_status": gs.get("gate_status"),
                "closeout_status": rm.get("closeout_status"),
                "debate_hint": hint,
            }
            debate = run_bounded_debate(
                question=f"Governed check: {trig.get('trigger_type', 'signal')}",
                context=ctx,
                max_turns=max_debate_turns,
                max_roles=max_roles,
            )
            bounded_debate_outputs.append(debate)
            last_debate_job_id = jid
            summary = f"Bounded debate outcome={debate.get('outcome')}; turns={debate.get('turns_used')}."
            out_art.append({"kind": "bounded_debate", "ref": debate})
            prem = evaluate_premium_candidate(
                debate_outcome=str(debate.get("outcome") or ""),
                gate_status=str(gs.get("gate_status") or ""),
                primary_block_category=str(gs.get("primary_block_category") or ""),
                founder_uncertainties=uncertainties,
                debate_transcript_len=len(debate.get("transcript") or []),
            )
            premium_escalation_candidates.append(prem)
            cockpit_surface_outputs.append({"kind": "premium_escalation_candidate", "payload": prem})
            if prem.get("premium_candidate"):
                cockpit_surface_outputs.append(
                    {"kind": "cockpit_message", "severity": "info", "text": prem.get("justification", "")[:500]}
                )
        elif jt == "premium.escalation_candidate":
            prem = evaluate_premium_candidate(
                debate_outcome="unknown",
                gate_status=str(gs.get("gate_status") or ""),
                primary_block_category=str(gs.get("primary_block_category") or ""),
                founder_uncertainties=uncertainties,
                debate_transcript_len=1,
            )
            premium_escalation_candidates.append(prem)
            summary = "Premium candidate evaluation (standalone job)."
            out_art.append({"kind": "premium_evaluation", "payload": prem})
        else:
            summary = f"Job type {jt} acknowledged; no extra action in MVP cycle."
            out_art.append({"kind": "noop", "job_type": jt})

        update_job(
            reg_path,
            jid,
            status="completed",
            result_summary=summary,
            output_artifacts=out_art,
        )
        jobs_executed.append(
            {
                "job_id": jid,
                "job_type": jt,
                "result_summary": summary,
            }
        )

    publishes = 0
    for deb in bounded_debate_outputs:
        if publishes >= max_candidates:
            break
        oc = str(deb.get("outcome") or "")
        if oc not in ("reopen_candidate", "unknown", "premium_required"):
            continue
        trig_types = [t.get("trigger_type") for t in triggers]
        rec = append_discovery_candidate(
            disc_path,
            asset_scope={"asset_id": rm.get("asset_id")},
            why_surfaced=f"Bounded debate outcome `{oc}` under proactive cycle.",
            triggers_fired=[str(x) for x in trig_types[:5]],
            still_uncertain="; ".join(str(u) for u in uncertainties[:3])[:800],
            evidence_needed="Named dispositive path or premium ROI-reviewed dataset (candidate only).",
            debate_converged=oc in ("supported", "unsupported"),
            linked_job_id=last_debate_job_id or (jobs_created[0]["job_id"] if jobs_created else ""),
        )
        discovery_candidates.append(rec)
        cockpit_surface_outputs.append({"kind": "discovery_candidate", "payload": rec})
        publishes += 1

    ap_path = default_alert_ledger_path(root)
    if not skip_alerts and alerts_written < max_alerts:
        for deb in bounded_debate_outputs:
            if alerts_written >= max_alerts:
                break
            if deb.get("outcome") == "reopen_candidate":
                append_alert(
                    ap_path,
                    asset_id=str(rm.get("asset_id") or "cohort"),
                    alert_class="reopen_candidate_runtime",
                    message_summary="Phase 48 debate surfaced a reopen candidate — requires governance review.",
                    triggering_source_artifact="phase48_proactive_research_runtime",
                    requires_attention=True,
                )
                cockpit_surface_outputs.append({"kind": "alert_ledger_append", "class": "reopen_candidate_runtime"})
                alerts_written += 1

    for job in jobs_created:
        tp = (job.get("trigger_payload") or {}).get("trigger") or {}
        if tp.get("trigger_type") == "manual_watchlist" and tp.get("manual_file"):
            mf = Path(str(tp["manual_file"]))
            if mf.is_file():
                clear_manual_triggers_file(mf)
                manual_cleared.append(str(mf))

    new_meta = {
        "last_phase46_generated_utc": phase46_bundle.get("generated_utc"),
        "last_cycle_utc": cycle_now,
    }
    update_metadata(reg_path, **new_meta)

    gen = datetime.now(timezone.utc).isoformat()
    return {
        "ok": True,
        "phase": "phase48_proactive_research_runtime",
        "generated_utc": gen,
        "input_phase46_bundle_path": str(p46_path),
        "trigger_results": triggers,
        "jobs_created": jobs_created,
        "jobs_executed": jobs_executed,
        "bounded_debate_outputs": bounded_debate_outputs,
        "premium_escalation_candidates": premium_escalation_candidates,
        "discovery_candidates": discovery_candidates,
        "budget_policy": policy,
        "cockpit_surface_outputs": cockpit_surface_outputs,
        "manual_triggers_cleared": manual_cleared,
        "phase49": recommend_phase49(),
    }


def default_decision_path_fallback(root: Path) -> Path:
    return root / "data" / "product_surface" / "decision_trace_ledger_v1.json"
