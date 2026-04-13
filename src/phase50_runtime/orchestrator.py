"""Phase 50 orchestrators: control-plane closeout bundle + governed positive-path smoke."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase48_runtime.orchestrator import run_phase48_proactive_research_runtime

from phase50_runtime.control_plane import (
    default_control_plane_path,
    ensure_control_plane_file,
    load_control_plane,
)
from phase50_runtime.cycle_lease import (
    default_lease_path,
    lease_behavior_doc,
    release_lease,
    try_acquire_lease,
)
from phase50_runtime.phase51_recommend import recommend_phase51
from phase50_runtime.runtime_audit_log import (
    append_audit_entry,
    build_audit_entry,
    count_cycles_started_in_window,
    default_audit_log_path,
    last_cycle_timestamp,
    summarize_audit_tail,
)
from phase50_runtime.timing_policy import TIMING_PROFILES, should_run_cycle_now
from phase50_runtime.trigger_controls import effective_budget_policy, trigger_controls_summary


def _read_json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def default_smoke_registry_path(repo_root: Path) -> Path:
    return repo_root / "data" / "research_runtime" / "phase50_positive_path_smoke_registry_v1.json"


def default_smoke_discovery_path(repo_root: Path) -> Path:
    return repo_root / "data" / "research_runtime" / "phase50_positive_path_smoke_discovery_v1.json"


def default_smoke_manual_path(repo_root: Path) -> Path:
    return repo_root / "data" / "research_runtime" / "phase50_positive_path_smoke_manual_v1.json"


def _reset_smoke_registry(path: Path, *, phase46_generated_utc: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metadata": {
                    "last_phase46_generated_utc": phase46_generated_utc,
                    "last_cycle_utc": "1970-01-01T00:00:00+00:00",
                },
                "jobs": [],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _reset_smoke_discovery(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "candidates": []}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_smoke_manual(path: Path, *, asset_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pending": [
                    {
                        "asset_id": asset_id,
                        "note": "phase50 positive path smoke (operator-seeded, governed job type)",
                        "suggested_job_type": "debate.execute",
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _clear_manual(path: Path) -> None:
    if path.is_file():
        path.write_text(
            json.dumps({"schema_version": 1, "pending": []}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def run_phase50_registry_controls_and_operator_timing(
    *,
    phase49_bundle_in: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    p49 = Path(phase49_bundle_in)
    if not p49.is_absolute():
        p49 = (root / p49).resolve()
    phase49_bundle = _read_json(p49)
    cp_path = default_control_plane_path(root)
    cp = ensure_control_plane_file(cp_path)
    audit_path = default_audit_log_path(root)
    gen = datetime.now(timezone.utc).isoformat()
    return {
        "ok": True,
        "phase": "phase50_registry_controls_and_operator_timing_v1",
        "generated_utc": gen,
        "input_phase49_bundle_path": str(p49),
        "control_plane_state": cp,
        "control_plane_path": str(cp_path),
        "timing_profiles": TIMING_PROFILES,
        "lease_behavior": lease_behavior_doc(),
        "trigger_controls": trigger_controls_summary(cp),
        "runtime_audit_summary": summarize_audit_tail(audit_path, last_n=40),
        "phase51": recommend_phase51(),
    }


def run_phase50_positive_path_smoke(
    *,
    phase46_bundle_in: str,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
    discovery_path: Path | None = None,
    decision_ledger_path: Path | None = None,
    skip_alerts: bool = True,
    bypass_timing_for_smoke: bool = True,
    honor_maintenance_mode: bool = False,
) -> dict[str, Any]:
    """
    Operator-seeded governed smoke: manual trigger file with debate.execute,
    isolated registry/discovery, lease + audit, non-empty cycle outputs.
    """
    root = repo_root or Path(__file__).resolve().parents[2]
    p46 = Path(phase46_bundle_in)
    if not p46.is_absolute():
        p46 = (root / p46).resolve()
    phase46_bundle = _read_json(p46)
    rm = phase46_bundle.get("founder_read_model") or {}
    asset_id = str(rm.get("asset_id") or "smoke_cohort")

    reg_path = registry_path or default_smoke_registry_path(root)
    disc_path = discovery_path or default_smoke_discovery_path(root)
    manual_path = default_smoke_manual_path(root)
    cp_path = default_control_plane_path(root)
    lease_path = default_lease_path(root)
    audit_path = default_audit_log_path(root)

    ensure_control_plane_file(cp_path)
    cp_disk = load_control_plane(cp_path)
    cp_run = {
        **cp_disk,
        "enabled": True,
        "default_cycle_profile": "manual_debug",
        "disabled_trigger_types": [
            x for x in (cp_disk.get("disabled_trigger_types") or []) if x != "manual_watchlist"
        ],
    }
    if not honor_maintenance_mode:
        cp_run["maintenance_mode"] = False

    win_sec = int(cp_run.get("window_seconds") or 3600)
    cycles_in_win = count_cycles_started_in_window(audit_path, window_seconds=win_sec)
    timing = should_run_cycle_now(
        control_plane=cp_run,
        profile_name="manual_debug",
        last_cycle_started_at=last_cycle_timestamp(audit_path),
        cycles_in_current_window=cycles_in_win,
    )
    if bypass_timing_for_smoke:
        timing = {"run": True, "reason": "smoke_bypass_timing", "detail": "positive_path_smoke", "profile": "manual_debug"}

    cycle_id = str(uuid.uuid4())
    if not timing["run"]:
        append_audit_entry(
            audit_path,
            build_audit_entry(
                cycle_id=cycle_id,
                why_started="positive_path_smoke",
                lease_acquired=False,
                controls_applied={"timing": timing, "control_plane_excerpt": {"enabled": cp_run.get("enabled")}},
                triggers_evaluated=0,
                jobs_created=0,
                jobs_executed=0,
                why_stopped=timing.get("reason", "timing_blocked"),
                skipped=True,
            ),
        )
        return {
            "ok": False,
            "phase": "phase50_positive_path_smoke",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "error": "timing_blocked",
            "timing_decision": timing,
            "seeded_trigger_source": None,
            "trigger_results": [],
            "jobs_created": [],
            "jobs_executed": [],
            "bounded_debate_outputs": [],
            "premium_escalation_candidates": [],
            "discovery_candidates": [],
            "cockpit_surface_outputs": [],
            "phase51": recommend_phase51(),
        }

    lease = try_acquire_lease(lease_path)
    if not lease["ok"]:
        append_audit_entry(
            audit_path,
            build_audit_entry(
                cycle_id=cycle_id,
                why_started="positive_path_smoke",
                lease_acquired=False,
                controls_applied={"lease_denied": lease},
                triggers_evaluated=0,
                jobs_created=0,
                jobs_executed=0,
                why_stopped="lease_not_acquired",
                skipped=True,
            ),
        )
        return {
            "ok": False,
            "phase": "phase50_positive_path_smoke",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "error": "lease_not_acquired",
            "lease_denied": lease,
            "seeded_trigger_source": None,
            "trigger_results": [],
            "jobs_created": [],
            "jobs_executed": [],
            "bounded_debate_outputs": [],
            "premium_escalation_candidates": [],
            "discovery_candidates": [],
            "cockpit_surface_outputs": [],
            "phase51": recommend_phase51(),
        }

    cycle_id = str(lease.get("cycle_id") or cycle_id)
    _reset_smoke_registry(reg_path, phase46_generated_utc=str(phase46_bundle.get("generated_utc") or "") or None)
    _reset_smoke_discovery(disc_path)
    _write_smoke_manual(manual_path, asset_id=asset_id)

    eff_policy = effective_budget_policy(cp_run)
    p48_out: dict[str, Any] = {}
    try:
        p48_out = run_phase48_proactive_research_runtime(
            phase46_bundle_in=str(p46),
            repo_root=root,
            registry_path=reg_path,
            discovery_path=disc_path,
            decision_ledger_path=decision_ledger_path,
            skip_alerts=skip_alerts,
            budget_policy=eff_policy,
            manual_triggers_path=manual_path,
        )
    finally:
        release_lease(lease_path, cycle_id=cycle_id)
        _clear_manual(manual_path)

    triggers = p48_out.get("trigger_results") or []
    jobs_c = p48_out.get("jobs_created") or []
    jobs_e = p48_out.get("jobs_executed") or []
    debates = p48_out.get("bounded_debate_outputs") or []
    prem = p48_out.get("premium_escalation_candidates") or []
    disc = p48_out.get("discovery_candidates") or []
    cockpit = p48_out.get("cockpit_surface_outputs") or []

    why_stopped = "phase48_completed"
    if not triggers:
        why_stopped = "no_triggers"
    elif not jobs_c:
        why_stopped = "no_jobs_enqueued"

    append_audit_entry(
        audit_path,
        build_audit_entry(
            cycle_id=cycle_id,
            why_started="positive_path_smoke_governed",
            lease_acquired=True,
            controls_applied={
                "timing": timing,
                "trigger_controls": trigger_controls_summary(cp_run),
                "budget_policy_allowed": eff_policy.get("allowed_trigger_types"),
            },
            triggers_evaluated=len(triggers),
            jobs_created=len(jobs_c),
            jobs_executed=len(jobs_e),
            why_stopped=why_stopped,
            skipped=False,
        ),
    )

    extra_ok = (
        len(debates) > 0
        or len(prem) > 0
        or len(disc) > 0
        or len(cockpit) > 0
    )
    metrics_ok = len(triggers) >= 1 and len(jobs_c) >= 1 and len(jobs_e) >= 1 and extra_ok

    gen = datetime.now(timezone.utc).isoformat()
    return {
        "ok": metrics_ok,
        "phase": "phase50_positive_path_smoke",
        "generated_utc": gen,
        "input_phase46_bundle_path": str(p46),
        "seeded_trigger_source": "manual_watchlist",
        "seeded_job_type": "debate.execute",
        "smoke_metrics_ok": metrics_ok,
        "trigger_results": triggers,
        "jobs_created": jobs_c,
        "jobs_executed": jobs_e,
        "bounded_debate_outputs": debates,
        "premium_escalation_candidates": prem,
        "discovery_candidates": disc,
        "cockpit_surface_outputs": cockpit,
        "phase48_generated_utc": p48_out.get("generated_utc"),
        "isolated_registry_path": str(reg_path),
        "isolated_discovery_path": str(disc_path),
        "phase51": recommend_phase51(),
    }

