"""Phase 16: orchestrate validation across eligible hypotheses, persist campaign + brief."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from db import records as dbrec
from research_validation.service import run_recipe_validation
from validation_campaign.compatibility import is_recipe_validation_run_compatible
from validation_campaign.constants import CAMPAIGN_POLICY_VERSION, STRONG_USABLE_QUALITY
from validation_campaign.decision_gate import assert_bounded_recommendation, decide_strategic_recommendation


def _program_quality_class(program: dict[str, Any]) -> str:
    qctx = program.get("linked_quality_context_json") or {}
    return str(qctx.get("quality_class") or "unknown")


def hypothesis_campaign_eligible(
    hypothesis: dict[str, Any],
    program: dict[str, Any],
    reviews: list[dict[str, Any]],
    referee_rows: list[dict[str, Any]],
) -> tuple[bool, str]:
    if str(program.get("status") or "") == "archived":
        return False, "program_archived"
    st = str(hypothesis.get("status") or "")
    if st not in ("candidate_recipe", "sandboxed"):
        return False, "status_not_candidate_or_sandboxed"
    if not reviews:
        return False, "reviews_required"
    if not referee_rows:
        return False, "referee_decision_required"
    return True, ""


def list_eligible_hypotheses_for_campaign(
    client: Any, *, program_id: str
) -> dict[str, Any]:
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found"}
    hyps = dbrec.fetch_research_hypotheses_for_program(client, program_id=program_id)
    eligible: list[dict[str, Any]] = []
    for h in hyps:
        hid = str(h["id"])
        rev = dbrec.fetch_research_reviews_for_hypothesis(client, hypothesis_id=hid)
        ref = dbrec.fetch_research_referee_decisions_for_hypothesis(
            client, hypothesis_id=hid
        )
        ok, reason = hypothesis_campaign_eligible(h, prog, rev, ref)
        if ok:
            eligible.append(
                {
                    "hypothesis_id": hid,
                    "hypothesis_title": h.get("hypothesis_title"),
                    "status": h.get("status"),
                }
            )
    return {
        "ok": True,
        "program_id": program_id,
        "n_eligible": len(eligible),
        "eligible": eligible,
    }


def _summarize_baselines(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    lost_to: list[str] = []
    beats: dict[str, bool] = {}
    for c in comparisons:
        if str(c.get("comparison_type") or "") != "spread_vs_baseline":
            continue
        name = str(c.get("baseline_name") or "")
        interp = c.get("interpretation_json") or {}
        b = bool(interp.get("beats"))
        beats[name] = b
        if not b:
            lost_to.append(name)
    return {"lost_to": lost_to, "beats": beats}


def _summarize_premium_hints(failures: list[dict[str, Any]]) -> dict[str, Any]:
    hints = [str(f.get("premium_overlay_hint") or "").strip() for f in failures]
    nonempty = [h for h in hints if h]
    return {
        "n_nonempty": len(nonempty),
        "top_hints": Counter(nonempty).most_common(8),
    }


def _build_member_row(
    *,
    campaign_run_id: str,
    hypothesis_id: str,
    validation_run_id: str,
    survival: dict[str, Any],
    comparisons: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    now: str,
) -> dict[str, Any]:
    fj = survival.get("fragility_json") or {}
    return {
        "campaign_run_id": campaign_run_id,
        "hypothesis_id": hypothesis_id,
        "validation_run_id": validation_run_id,
        "survival_status": str(survival.get("survival_status") or ""),
        "baseline_summary_json": _summarize_baselines(comparisons),
        "fragility_summary_json": {
            "window_stability_ratio": fj.get("window_stability_ratio"),
            "program_quality_class": fj.get("program_quality_class"),
            "contradiction_residual_count": fj.get("contradiction_residual_count"),
            "rationale": survival.get("rationale"),
        },
        "premium_hint_summary_json": _summarize_premium_hints(failures),
        "created_at": now,
    }


def _aggregate_from_members(
    members: list[dict[str, Any]],
    failures_by_hypothesis: dict[str, list[dict[str, Any]]],
    program_qc: str,
) -> dict[str, Any]:
    survival_counts: Counter[str] = Counter()
    baseline_loss: Counter[str] = Counter()
    failure_reasons: Counter[str] = Counter()
    premium_nonempty = 0
    contradictory = 0
    thin_fail = 0
    degraded_ctx_fail = 0
    strong_usable_ctx = 0

    for m in members:
        survival_counts[str(m.get("survival_status") or "")] += 1
        bsum = m.get("baseline_summary_json") or {}
        for name in bsum.get("lost_to") or []:
            baseline_loss[name] += 1
        fj = m.get("fragility_summary_json") or {}
        pqc = str(fj.get("program_quality_class") or "")
        if pqc in STRONG_USABLE_QUALITY:
            strong_usable_ctx += 1
        hid = str(m.get("hypothesis_id") or "")
        fails = failures_by_hypothesis.get(hid, [])
        for f in fails:
            fr = str(f.get("failure_reason") or "")
            failure_reasons[fr] += 1
            if fr == "contradictory_residual_link":
                contradictory += 1
            if fr == "thin_input_program_context_dependence":
                thin_fail += 1
            if "degraded" in fr or "failed" in fr:
                degraded_ctx_fail += 1
            ph = str(f.get("premium_overlay_hint") or "").strip()
            if ph:
                premium_nonempty += 1

    total_f = sum(failure_reasons.values())
    return {
        "n_validated": len(members),
        "survives": survival_counts.get("survives", 0),
        "weak_survival": survival_counts.get("weak_survival", 0),
        "demote_to_sandbox": survival_counts.get("demote_to_sandbox", 0),
        "archive_failed": survival_counts.get("archive_failed", 0),
        "baseline_loss_distribution": dict(baseline_loss),
        "failure_reason_counts": dict(failure_reasons),
        "total_failure_cases_across_members": total_f,
        "n_contradictory_failure_cases": contradictory,
        "n_failure_cases_with_nonempty_premium_hint": premium_nonempty,
        "thin_input_failure_share": (thin_fail / total_f) if total_f else 0.0,
        "degraded_or_failed_context_failure_share": (degraded_ctx_fail / total_f)
        if total_f
        else 0.0,
        "n_members_strong_or_usable_context": strong_usable_ctx,
        "dominant_program_quality_class": program_qc,
    }


def run_validation_campaign(
    client: Any,
    *,
    program_id: str,
    run_mode: str = "reuse_or_run",
    panel_limit: int = 6000,
) -> dict[str, Any]:
    if run_mode not in ("reuse_only", "reuse_or_run", "force_rerun"):
        return {"ok": False, "error": "invalid_run_mode"}

    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found"}

    elig = list_eligible_hypotheses_for_campaign(client, program_id=program_id)
    if not elig.get("ok"):
        return elig

    eligible_list = elig["eligible"]
    n_eligible = len(eligible_list)
    program_qc = _program_quality_class(prog)

    now = datetime.now(timezone.utc).isoformat()
    members_payload: list[dict[str, Any]] = []
    failures_by_hypothesis: dict[str, list[dict[str, Any]]] = {}
    skipped: list[dict[str, str]] = []
    reran: list[str] = []

    for item in eligible_list:
        hid = item["hypothesis_id"]
        validation_run_id: Optional[str] = None

        if run_mode != "force_rerun":
            existing = dbrec.fetch_latest_recipe_validation_run_for_hypothesis(
                client, hypothesis_id=hid, status="completed"
            )
            if existing and is_recipe_validation_run_compatible(
                existing, program_quality_class=program_qc
            ):
                validation_run_id = str(existing["id"])

        if validation_run_id is None:
            if run_mode == "reuse_only":
                skipped.append({"hypothesis_id": hid, "reason": "no_compatible_completed_run"})
                continue
            out = run_recipe_validation(
                client, hypothesis_id=hid, panel_limit=int(panel_limit)
            )
            if not out.get("ok"):
                skipped.append(
                    {
                        "hypothesis_id": hid,
                        "reason": "validation_failed",
                        "detail": str(out.get("error") or out),
                    }
                )
                continue
            validation_run_id = str(out["validation_run_id"])
            reran.append(hid)

        surv = dbrec.fetch_recipe_survival_for_run(
            client, validation_run_id=validation_run_id
        )
        if not surv:
            skipped.append({"hypothesis_id": hid, "reason": "survival_row_missing"})
            continue
        comps = dbrec.fetch_recipe_validation_comparisons_for_run(
            client, validation_run_id=validation_run_id
        )
        fails = dbrec.fetch_recipe_failure_cases_for_run(
            client, validation_run_id=validation_run_id
        )
        failures_by_hypothesis[hid] = fails

        members_payload.append(
            _build_member_row(
                campaign_run_id="",  # filled after insert
                hypothesis_id=hid,
                validation_run_id=validation_run_id,
                survival=surv,
                comparisons=comps,
                failures=fails,
                now=now,
            )
        )

    metrics = _aggregate_from_members(members_payload, failures_by_hypothesis, program_qc)
    metrics["n_eligible"] = n_eligible
    metrics["n_skipped"] = len(skipped)
    metrics["hypotheses_reran"] = reran

    rec, rec_detail = decide_strategic_recommendation(metrics)
    rec = assert_bounded_recommendation(rec)

    selection_json = {
        "criteria": "candidate_recipe_or_sandboxed_with_reviews_and_referee",
        "program_not_archived": True,
        "skipped": skipped,
    }

    rationale_json = {
        "recommendation": rec,
        "decision_detail": rec_detail,
        "aggregate_metrics": metrics,
        "what_would_change": _counterfactual_hints(rec, metrics),
    }

    run_row = {
        "program_id": program_id,
        "policy_version": CAMPAIGN_POLICY_VERSION,
        "run_mode": run_mode,
        "hypothesis_selection_json": selection_json,
        "aggregate_metrics_json": metrics,
        "recommendation": rec,
        "rationale_json": rationale_json,
        "created_at": now,
    }
    campaign_id = dbrec.insert_validation_campaign_run(client, run_row)

    for m in members_payload:
        m["campaign_run_id"] = campaign_id
    dbrec.insert_validation_campaign_members_batch(client, members_payload)

    rationale_text = (
        f"{rec}: {rec_detail.get('rule')} "
        f"(validated={metrics['n_validated']}, eligible={n_eligible})"
    )
    decision_row = {
        "campaign_run_id": campaign_id,
        "recommendation": rec,
        "rationale": rationale_text,
        "evidence_thresholds_json": {
            "min_eligible_hypotheses": 2,
            "min_validated_hypotheses": 2,
            "premium_share_for_seam": 0.35,
            "thin_degraded_failure_share_tilt": 0.35,
        },
        "counterfactual_next_step_json": rationale_json["what_would_change"],
        "created_at": now,
    }
    dbrec.insert_validation_campaign_decision(client, decision_row)

    return {
        "ok": True,
        "campaign_run_id": campaign_id,
        "recommendation": rec,
        "n_eligible": n_eligible,
        "n_validated": metrics["n_validated"],
        "skipped": skipped,
        "aggregate_metrics": metrics,
    }


def _counterfactual_hints(rec: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "if_more_strong_usable_and_contradictions": (
            "Could move toward targeted_premium_seam_first if contradictory_public_signal "
            "failure share rises in strong/usable substrate."
        ),
        "if_eligible_below_threshold": "Re-run campaign after more hypotheses reach referee.",
        "if_thin_input_resolved": (
            "Re-run public-core cycle to lift quality_class; then repeat campaign."
        ),
        "current_recommendation": rec,
        "snapshot": {
            "n_validated": metrics.get("n_validated"),
            "weak_survival": metrics.get("weak_survival"),
            "dominant_program_qc": metrics.get("dominant_program_quality_class"),
        },
    }


def report_validation_campaign(client: Any, *, campaign_run_id: str) -> dict[str, Any]:
    run = dbrec.fetch_validation_campaign_run(client, campaign_run_id=campaign_run_id)
    if not run:
        return {"ok": False, "error": "campaign_run_not_found"}
    members = dbrec.fetch_validation_campaign_members(
        client, campaign_run_id=campaign_run_id
    )
    decisions = dbrec.fetch_validation_campaign_decisions(
        client, campaign_run_id=campaign_run_id
    )
    prog = dbrec.fetch_research_program(
        client, program_id=str(run["program_id"])
    )
    return {
        "ok": True,
        "campaign_run": run,
        "program": prog,
        "members": members,
        "decisions": decisions,
    }


def report_program_survival_distribution(
    client: Any, *, program_id: str
) -> dict[str, Any]:
    prog = dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found"}
    hyps = dbrec.fetch_research_hypotheses_for_program(client, program_id=program_id)
    counts: Counter[str] = Counter()
    missing = 0
    per_hypothesis: list[dict[str, Any]] = []
    for h in hyps:
        hid = str(h["id"])
        run = dbrec.fetch_latest_recipe_validation_run_for_hypothesis(
            client, hypothesis_id=hid, status="completed"
        )
        if not run:
            missing += 1
            per_hypothesis.append({"hypothesis_id": hid, "survival_status": None})
            continue
        surv = dbrec.fetch_recipe_survival_for_run(
            client, validation_run_id=str(run["id"])
        )
        if not surv:
            missing += 1
            per_hypothesis.append({"hypothesis_id": hid, "survival_status": None})
            continue
        st = str(surv.get("survival_status") or "")
        counts[st] += 1
        per_hypothesis.append(
            {
                "hypothesis_id": hid,
                "validation_run_id": str(run["id"]),
                "survival_status": st,
            }
        )
    return {
        "ok": True,
        "program_id": program_id,
        "distribution": dict(counts),
        "n_hypotheses": len(hyps),
        "n_without_completed_validation": missing,
        "per_hypothesis": per_hypothesis,
    }


def build_decision_brief(
    client: Any, *, campaign_run_id: str
) -> dict[str, Any]:
    bundle = report_validation_campaign(client, campaign_run_id=campaign_run_id)
    if not bundle.get("ok"):
        return bundle
    run = bundle["campaign_run"]
    prog = bundle["program"] or {}
    members = bundle["members"]
    decisions = bundle["decisions"]
    decision0 = decisions[0] if decisions else {}

    top_failures = Counter()
    top_hints: Counter[str] = Counter()
    surviving: list[dict[str, Any]] = []
    for m in members:
        st = str(m.get("survival_status") or "")
        if st == "survives":
            surviving.append(
                {
                    "hypothesis_id": m.get("hypothesis_id"),
                    "validation_run_id": m.get("validation_run_id"),
                }
            )
        fj = m.get("fragility_summary_json") or {}
        if fj.get("rationale"):
            top_failures[str(fj["rationale"])] += 1
        ph = m.get("premium_hint_summary_json") or {}
        for hint, cnt in ph.get("top_hints") or []:
            top_hints[hint] += int(cnt)

    metrics = run.get("aggregate_metrics_json") or {}
    brief = {
        "version": 1,
        "campaign_run_id": campaign_run_id,
        "program": {
            "id": prog.get("id"),
            "title": prog.get("title"),
            "research_question": prog.get("research_question"),
            "horizon_type": prog.get("horizon_type"),
        },
        "recommendation": run.get("recommendation"),
        "rationale_text": decision0.get("rationale"),
        "rationale_json": run.get("rationale_json"),
        "hypotheses_included": [
            {
                "hypothesis_id": m.get("hypothesis_id"),
                "validation_run_id": m.get("validation_run_id"),
                "survival_status": m.get("survival_status"),
            }
            for m in members
        ],
        "survival_distribution": {
            "survives": metrics.get("survives", 0),
            "weak_survival": metrics.get("weak_survival", 0),
            "demote_to_sandbox": metrics.get("demote_to_sandbox", 0),
            "archive_failed": metrics.get("archive_failed", 0),
        },
        "top_failure_rationales": top_failures.most_common(10),
        "top_premium_hint_tokens": top_hints.most_common(10),
        "top_surviving_recipes": surviving,
        "evidence_thresholds": (decision0.get("evidence_thresholds_json") or {}),
        "counterfactual_next_step": (decision0.get("counterfactual_next_step_json") or {}),
    }
    return {"ok": True, "brief": brief}


def render_decision_brief_markdown(brief: dict[str, Any]) -> str:
    prog = brief.get("program") or {}
    lines = [
        "# Validation decision brief",
        "",
        f"- **Program**: {prog.get('title')}",
        f"- **Locked question**: {prog.get('research_question')}",
        f"- **Campaign run**: `{brief.get('campaign_run_id')}`",
        "",
        "## Recommendation",
        "",
        f"`{brief.get('recommendation')}`",
        "",
        brief.get("rationale_text") or "",
        "",
        "## Survival distribution (campaign members)",
        "",
        f"- survives: {brief.get('survival_distribution', {}).get('survives')}",
        f"- weak_survival: {brief.get('survival_distribution', {}).get('weak_survival')}",
        f"- demote_to_sandbox: {brief.get('survival_distribution', {}).get('demote_to_sandbox')}",
        f"- archive_failed: {brief.get('survival_distribution', {}).get('archive_failed')}",
        "",
        "## Hypotheses included",
        "",
    ]
    for h in brief.get("hypotheses_included") or []:
        lines.append(
            f"- `{h.get('hypothesis_id')}` → `{h.get('survival_status')}` "
            f"(run `{h.get('validation_run_id')}`)"
        )
    lines.extend(
        [
            "",
            "## Top failure rationales (fragility / survival)",
            "",
        ]
    )
    for r, n in brief.get("top_failure_rationales") or []:
        lines.append(f"- {r}: {n}")
    lines.extend(["", "## Top premium-overlay hints (from failure cases)", ""])
    for r, n in brief.get("top_premium_hint_tokens") or []:
        lines.append(f"- {r}: {n}")
    lines.extend(
        [
            "",
            "## What would change the call",
            "",
        ]
    )
    cf = brief.get("counterfactual_next_step") or {}
    for k, v in cf.items():
        if k == "current_recommendation":
            continue
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    return "\n".join(lines)
