"""Phase 51: external ingest + governed cycle + health (authoritative smoke)."""

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
    save_control_plane,
)
from phase50_runtime.cycle_lease import default_lease_path, release_lease, try_acquire_lease
from phase50_runtime.runtime_audit_log import append_audit_entry, build_audit_entry, count_cycles_started_in_window, default_audit_log_path, last_cycle_timestamp
from phase50_runtime.timing_policy import should_run_cycle_now
from phase50_runtime.trigger_controls import effective_budget_policy, trigger_controls_summary

from phase51_runtime.cockpit_health_surface import build_cockpit_runtime_health_payload
from phase51_runtime.external_ingest_adapters import process_events_from_file
from phase51_runtime.external_trigger_audit import append_external_audit, default_external_trigger_audit_path
from phase51_runtime.external_trigger_ingest import (
    default_ingest_registry_path,
    link_events_to_cycle,
    load_ingest_registry,
    save_ingest_registry,
    supplemental_triggers_from_registry,
)
from phase51_runtime.phase52_recommend import recommend_phase52
from phase51_runtime.runtime_health import build_runtime_health_summary, refresh_and_persist_runtime_health


def _read_json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def default_phase51_smoke_registry_path(repo_root: Path) -> Path:
    return repo_root / "data" / "research_runtime" / "phase51_external_smoke_registry_v1.json"


def default_phase51_smoke_discovery_path(repo_root: Path) -> Path:
    return repo_root / "data" / "research_runtime" / "phase51_external_smoke_discovery_v1.json"


def default_phase51_smoke_ingest_path(repo_root: Path) -> Path:
    return repo_root / "data" / "research_runtime" / "phase51_external_smoke_ingest_v1.json"


def default_phase51_smoke_external_audit_path(repo_root: Path) -> Path:
    return repo_root / "data" / "research_runtime" / "phase51_external_smoke_audit_v1.json"


def _reset_registry(path: Path, *, phase46_generated_utc: str | None) -> None:
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


def _reset_discovery(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "candidates": []}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _empty_manual(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 1, "pending": []}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_smoke_external_event(path: Path, *, asset_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ev = {
        "source_type": "file_drop",
        "source_id": "phase51_external_positive_path",
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": asset_id},
        "payload": {
            "note": "Governed external ingest (not operator manual_triggers_v1 seed).",
            "suggested_job_type": "debate.execute",
        },
    }
    path.write_text(json.dumps([ev], indent=2, ensure_ascii=False), encoding="utf-8")


def run_phase51_external_positive_path_smoke(
    *,
    phase46_bundle_in: str,
    phase50_control_bundle_in: str,
    repo_root: Path | None = None,
    registry_path: Path | None = None,
    discovery_path: Path | None = None,
    ingest_registry_path: Path | None = None,
    external_audit_path: Path | None = None,
    decision_ledger_path: Path | None = None,
    manual_triggers_path: Path | None = None,
    lease_path: Path | None = None,
    skip_alerts: bool = True,
    persist_health_summary: bool = False,
) -> dict[str, Any]:
    """
    External file-drop event -> ingest registry -> supplemental trigger -> bounded Phase 48 cycle.
    Does not seed manual_triggers_v1.json (empty manual file).
    """
    root = repo_root or Path(__file__).resolve().parents[2]
    p46 = Path(phase46_bundle_in)
    if not p46.is_absolute():
        p46 = (root / p46).resolve()
    phase46_bundle = _read_json(p46)
    rm = phase46_bundle.get("founder_read_model") or {}
    asset_id = str(rm.get("asset_id") or "phase51_cohort")

    p50 = Path(phase50_control_bundle_in)
    if not p50.is_absolute():
        p50 = (root / p50).resolve()
    _read_json(p50)

    reg_path = registry_path or default_phase51_smoke_registry_path(root)
    disc_path = discovery_path or default_phase51_smoke_discovery_path(root)
    ing_path = ingest_registry_path or default_phase51_smoke_ingest_path(root)
    ext_audit_path = external_audit_path or default_phase51_smoke_external_audit_path(root)
    lease_path = lease_path or default_lease_path(root)
    audit_path = default_audit_log_path(root)
    cp_path = default_control_plane_path(root)
    manual_path = manual_triggers_path or (root / "data" / "research_runtime" / "phase51_smoke_empty_manual_v1.json")
    dec_path = decision_ledger_path
    if dec_path is None:
        dec_path = root / "data" / "research_runtime" / "phase51_smoke_empty_decisions_v1.json"
        dec_path.parent.mkdir(parents=True, exist_ok=True)
        dec_path.write_text(
            json.dumps({"schema_version": 1, "decisions": []}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    save_ingest_registry(ing_path, {"schema_version": 1, "entries": []})
    if ext_audit_path.is_file():
        ext_audit_path.write_text(
            json.dumps({"schema_version": 1, "entries": []}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    drop = root / "data" / "research_runtime" / "phase51_external_drop_smoke_v1.json"
    _write_smoke_external_event(drop, asset_id=asset_id)

    ensure_control_plane_file(cp_path)
    cp_disk = load_control_plane(cp_path)
    cp_run = {
        **cp_disk,
        "enabled": True,
        "maintenance_mode": False,
        "default_cycle_profile": "manual_debug",
        "disabled_trigger_types": [x for x in (cp_disk.get("disabled_trigger_types") or []) if x != "manual_watchlist"],
    }
    cp_smoke_path = root / "data" / "research_runtime" / "phase51_smoke_control_plane_v1.json"
    save_control_plane(cp_smoke_path, cp_run)

    win_sec = int(cp_run.get("window_seconds") or 3600)
    cycles_in_win = count_cycles_started_in_window(audit_path, window_seconds=win_sec)
    timing = should_run_cycle_now(
        control_plane=cp_run,
        profile_name="manual_debug",
        last_cycle_started_at=last_cycle_timestamp(audit_path),
        cycles_in_current_window=cycles_in_win,
    )
    timing = {"run": True, "reason": "phase51_smoke_bypass_timing", "detail": "external_positive_path", "profile": "manual_debug"}

    received = process_events_from_file(
        drop,
        repo_root=root,
        ingest_registry_path=ing_path,
        audit_path=ext_audit_path,
        control_plane_path=cp_smoke_path,
        maintenance_blocks_accept=False,
    )

    reg = load_ingest_registry(ing_path)
    entries = list(reg.get("entries") or [])
    n_acc = sum(1 for e in entries if e.get("status") == "accepted")
    n_rej = sum(1 for e in entries if e.get("status") == "rejected")
    n_dedup = sum(1 for e in entries if e.get("status") == "deduped")
    n_rej_total = n_rej + n_dedup
    norm_results = [
        {
            "event_id": e.get("event_id"),
            "normalized_trigger_type": e.get("normalized_trigger_type"),
            "status": e.get("status"),
            "reason": e.get("accepted_or_rejected_reason"),
        }
        for e in entries
    ]

    supplemental = supplemental_triggers_from_registry(ing_path)
    ext_ids = [str(t.get("external_event_id")) for t in supplemental if t.get("external_event_id")]

    cycle_id = str(uuid.uuid4())
    lease = try_acquire_lease(lease_path)
    if not lease["ok"]:
        return {
            "ok": False,
            "phase": "phase51_external_trigger_ingest",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "input_phase50_control_bundle_path": str(p50),
            "error": "lease_not_acquired",
            "external_events_received": len(received),
            "external_events_accepted": n_acc,
            "external_events_rejected": n_rej_total,
            "external_events_deduped": n_dedup,
            "normalized_trigger_results": norm_results,
            "cycles_consuming_external_events": [],
            "runtime_health_summary": build_runtime_health_summary(repo_root=root, ingest_registry_path=ing_path),
            "phase52": recommend_phase52(),
        }

    cycle_id = str(lease.get("cycle_id") or cycle_id)
    _reset_registry(reg_path, phase46_generated_utc=str(phase46_bundle.get("generated_utc") or "") or None)
    _reset_discovery(disc_path)
    _empty_manual(manual_path)

    eff_policy = effective_budget_policy(cp_run)
    p48_out: dict[str, Any] = {}
    try:
        p48_out = run_phase48_proactive_research_runtime(
            phase46_bundle_in=str(p46),
            repo_root=root,
            registry_path=reg_path,
            discovery_path=disc_path,
            decision_ledger_path=dec_path,
            skip_alerts=skip_alerts,
            budget_policy=eff_policy,
            manual_triggers_path=manual_path,
            supplemental_triggers=supplemental,
        )
    finally:
        release_lease(lease_path, cycle_id=cycle_id)

    if ext_ids and supplemental:
        link_events_to_cycle(ing_path, ext_ids, cycle_id)
        for eid in ext_ids:
            append_external_audit(
                ext_audit_path,
                {
                    "kind": "external_consumed",
                    "event_id": eid,
                    "linked_cycle_id": cycle_id,
                },
            )

    triggers = p48_out.get("trigger_results") or []
    jobs_c = p48_out.get("jobs_created") or []
    jobs_e = p48_out.get("jobs_executed") or []
    debates = p48_out.get("bounded_debate_outputs") or []
    disc_out = p48_out.get("discovery_candidates") or []
    cockpit = p48_out.get("cockpit_surface_outputs") or []

    append_audit_entry(
        audit_path,
        build_audit_entry(
            cycle_id=cycle_id,
            why_started="phase51_external_positive_path",
            lease_acquired=True,
            controls_applied={
                "timing": timing,
                "trigger_controls": trigger_controls_summary(cp_run),
                "external_supplemental_count": len(supplemental),
            },
            triggers_evaluated=len(triggers),
            jobs_created=len(jobs_c),
            jobs_executed=len(jobs_e),
            why_stopped="phase48_completed" if jobs_e else "no_jobs_executed",
            skipped=False,
        ),
    )

    extra_ok = len(debates) > 0 or len(disc_out) > 0 or len(cockpit) > 0
    metrics_ok = len(supplemental) >= 1 and len(jobs_c) >= 1 and len(jobs_e) >= 1 and extra_ok

    health = build_runtime_health_summary(repo_root=root, ingest_registry_path=ing_path)
    if persist_health_summary:
        refresh_and_persist_runtime_health(root)

    gen = datetime.now(timezone.utc).isoformat()
    return {
        "ok": metrics_ok,
        "phase": "phase51_external_trigger_ingest",
        "generated_utc": gen,
        "input_phase50_control_bundle_path": str(p50),
        "external_events_received": len(received),
        "external_events_accepted": n_acc,
        "external_events_rejected": n_rej_total,
        "external_events_deduped": n_dedup,
        "normalized_trigger_results": norm_results,
        "cycles_consuming_external_events": [cycle_id] if metrics_ok else [],
        "runtime_health_summary": health,
        "cockpit_runtime_health_preview": build_cockpit_runtime_health_payload(repo_root=root, ingest_registry_path=ing_path),
        "phase48_generated_utc": p48_out.get("generated_utc"),
        "trigger_results": triggers,
        "jobs_created": jobs_c,
        "jobs_executed": jobs_e,
        "bounded_debate_outputs": debates,
        "discovery_candidates": disc_out,
        "cockpit_surface_outputs": cockpit,
        "smoke_metrics_ok": metrics_ok,
        "isolated_registry_path": str(reg_path),
        "isolated_ingest_registry_path": str(ing_path),
        "isolated_external_audit_path": str(ext_audit_path),
        "external_drop_file": str(drop),
        "phase52": recommend_phase52(),
    }
