"""Phase 52: authenticated ingest, budgets, routing, queue — authoritative smoke."""

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
from phase51_runtime.external_trigger_audit import append_external_audit, default_external_trigger_audit_path
from phase51_runtime.external_trigger_ingest import (
    default_ingest_registry_path,
    link_events_to_cycle,
    load_ingest_registry,
    save_ingest_registry,
    supplemental_triggers_from_registry,
)
from phase51_runtime.runtime_health import build_runtime_health_summary, refresh_and_persist_runtime_health

from phase52_runtime.event_queue import default_event_queue_path, load_queue, save_queue
from phase52_runtime.governed_ingress import flush_one_queued_event_to_registry, process_governed_external_ingest
from phase52_runtime.phase53_recommend import recommend_phase53
from phase52_runtime.source_budgets import default_budget_state_path, load_budget_state, save_budget_state
from phase52_runtime.source_registry import default_external_source_registry_path, save_source_registry
from phase52_runtime.webhook_auth import hash_shared_secret


def _read_json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _watchlist_event(*, source_id: str, asset_id: str, note: str) -> dict[str, Any]:
    return {
        "source_type": "webhook",
        "source_id": source_id,
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": asset_id},
        "payload": {"note": note, "suggested_job_type": "debate.execute"},
    }


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
    path.write_text(json.dumps({"schema_version": 1, "candidates": []}, indent=2, ensure_ascii=False), encoding="utf-8")


def _empty_manual(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "pending": []}, indent=2, ensure_ascii=False), encoding="utf-8")


def _base_source(
    *,
    source_id: str,
    secret: str,
    queue_mode: str,
    rate_per_minute: int = 120,
    allowed_raw: list[str] | None = None,
    allowed_nt: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_name": f"source_{source_id}",
        "source_type": "webhook",
        "source_id": source_id,
        "enabled": True,
        "shared_secret_hash": hash_shared_secret(secret),
        "allowed_raw_event_types": allowed_raw or ["watchlist_submit"],
        "normalized_trigger_allowlist": allowed_nt or ["manual_watchlist"],
        "rate_limit_per_minute": rate_per_minute,
        "max_events_per_window": 500,
        "window_seconds": 3600,
        "queue_mode": queue_mode,
        "notes": "phase52 smoke",
    }


def run_phase52_governed_webhook_auth_routing_smoke(
    *,
    phase46_bundle_in: str,
    phase50_control_bundle_in: str,
    input_phase51_bundle_path: str,
    repo_root: Path | None = None,
    persist_health_summary: bool = False,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    p46 = Path(phase46_bundle_in)
    if not p46.is_absolute():
        p46 = (root / p46).resolve()
    phase46_bundle = _read_json(p46)
    rm = phase46_bundle.get("founder_read_model") or {}
    asset_id = str(rm.get("asset_id") or "phase52_cohort")

    p50 = Path(phase50_control_bundle_in)
    if not p50.is_absolute():
        p50 = (root / p50).resolve()
    _read_json(p50)
    p51 = Path(input_phase51_bundle_path)
    if not p51.is_absolute():
        p51 = (root / p51).resolve()

    secret = "phase52-smoke-secret-v1"
    dr = "phase52_direct"
    qu = "phase52_queue"
    rt = "phase52_rate"
    data_rt = root / "data" / "research_runtime"
    data_rt.mkdir(parents=True, exist_ok=True)

    reg_path = root / "data" / "research_runtime" / "phase52_smoke_job_registry_v1.json"
    disc_path = root / "data" / "research_runtime" / "phase52_smoke_discovery_v1.json"
    ing_path = root / "data" / "research_runtime" / "phase52_smoke_ingest_v1.json"
    ext_audit_path = root / "data" / "research_runtime" / "phase52_smoke_audit_v1.json"
    # Isolated paths so smoke does not overwrite operator defaults under data/research_runtime/.
    src_reg_path = root / "data" / "research_runtime" / "phase52_external_smoke_source_registry_v1.json"
    bud_path = root / "data" / "research_runtime" / "phase52_external_smoke_budget_v1.json"
    q_path = root / "data" / "research_runtime" / "phase52_external_smoke_queue_v1.json"
    lease_path = default_lease_path(root)
    audit_path = default_audit_log_path(root)
    cp_path = default_control_plane_path(root)
    manual_path = root / "data" / "research_runtime" / "phase52_smoke_empty_manual_v1.json"
    dec_path = root / "data" / "research_runtime" / "phase52_smoke_empty_decisions_v1.json"
    dec_path.parent.mkdir(parents=True, exist_ok=True)
    dec_path.write_text(json.dumps({"schema_version": 1, "decisions": []}, indent=2, ensure_ascii=False), encoding="utf-8")

    ensure_control_plane_file(cp_path)
    cp_disk = load_control_plane(cp_path)
    cp_run = {
        **cp_disk,
        "enabled": True,
        "maintenance_mode": False,
        "default_cycle_profile": "manual_debug",
        "disabled_trigger_types": [x for x in (cp_disk.get("disabled_trigger_types") or []) if x != "manual_watchlist"],
    }
    cp_smoke_path = root / "data" / "research_runtime" / "phase52_smoke_control_plane_v1.json"
    save_control_plane(cp_smoke_path, cp_run)

    save_ingest_registry(ing_path, {"schema_version": 1, "entries": []})
    ext_audit_path.write_text(json.dumps({"schema_version": 1, "entries": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    save_budget_state(bud_path, {"schema_version": 1, "by_source_id": {}})
    save_queue(q_path, {"schema_version": 1, "max_depth": 500, "items": []})

    sources = [
        _base_source(source_id=dr, secret=secret, queue_mode="direct", rate_per_minute=200),
        _base_source(source_id=qu, secret=secret, queue_mode="enqueue_before_cycle", rate_per_minute=200),
        _base_source(source_id=rt, secret=secret, queue_mode="direct", rate_per_minute=1),
    ]
    save_source_registry(src_reg_path, {"schema_version": 1, "sources": sources})

    dl_smoke = data_rt / "phase53_smoke_external_dead_letter_v1.json"
    rg_smoke = data_rt / "phase53_smoke_external_replay_guard_v1.json"
    dl_smoke.write_text(json.dumps({"schema_version": 1, "entries": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    rg_smoke.write_text(json.dumps({"schema_version": 1, "entries": []}, indent=2, ensure_ascii=False), encoding="utf-8")

    auth_failures = 0
    routing_failures = 0
    rate_hits = 0
    accepted_direct = 0
    queued_events = 0

    r0 = process_governed_external_ingest(
        _watchlist_event(source_id=dr, asset_id=asset_id, note="n0"),
        source_id_header=dr,
        webhook_secret="wrong-secret",
        repo_root=root,
        source_registry_path=src_reg_path,
        budget_state_path=bud_path,
        queue_path=q_path,
        ingest_registry_path=ing_path,
        audit_path=ext_audit_path,
        control_plane_path=cp_smoke_path,
        dead_letter_path=dl_smoke,
        replay_guard_path=rg_smoke,
    )
    if not r0.get("ok") and r0.get("error") == "auth_failed":
        auth_failures += 1

    bad_route = {
        "source_type": "webhook",
        "source_id": dr,
        "raw_event_type": "named_source_registration",
        "asset_scope": {"asset_id": asset_id},
        "payload": {"note": "x", "source_name": "s"},
    }
    r1 = process_governed_external_ingest(
        bad_route,
        source_id_header=dr,
        webhook_secret=secret,
        repo_root=root,
        source_registry_path=src_reg_path,
        budget_state_path=bud_path,
        queue_path=q_path,
        ingest_registry_path=ing_path,
        audit_path=ext_audit_path,
        control_plane_path=cp_smoke_path,
        dead_letter_path=dl_smoke,
        replay_guard_path=rg_smoke,
    )
    if not r1.get("ok") and r1.get("error") == "routing_rejected":
        routing_failures += 1

    r2a = process_governed_external_ingest(
        _watchlist_event(source_id=rt, asset_id=asset_id, note="rate-a"),
        source_id_header=rt,
        webhook_secret=secret,
        repo_root=root,
        source_registry_path=src_reg_path,
        budget_state_path=bud_path,
        queue_path=q_path,
        ingest_registry_path=ing_path,
        audit_path=ext_audit_path,
        control_plane_path=cp_smoke_path,
        dead_letter_path=dl_smoke,
        replay_guard_path=rg_smoke,
    )
    r2b = process_governed_external_ingest(
        _watchlist_event(source_id=rt, asset_id=asset_id, note="rate-b"),
        source_id_header=rt,
        webhook_secret=secret,
        repo_root=root,
        source_registry_path=src_reg_path,
        budget_state_path=bud_path,
        queue_path=q_path,
        ingest_registry_path=ing_path,
        audit_path=ext_audit_path,
        control_plane_path=cp_smoke_path,
        dead_letter_path=dl_smoke,
        replay_guard_path=rg_smoke,
    )
    if r2a.get("ok") and (r2a.get("registry_entry") or {}).get("status") == "accepted":
        accepted_direct += 1
    if not r2b.get("ok") and r2b.get("error") == "rate_limited":
        rate_hits += 1

    r3 = process_governed_external_ingest(
        _watchlist_event(source_id=dr, asset_id=asset_id, note="direct-primary"),
        source_id_header=dr,
        webhook_secret=secret,
        repo_root=root,
        source_registry_path=src_reg_path,
        budget_state_path=bud_path,
        queue_path=q_path,
        ingest_registry_path=ing_path,
        audit_path=ext_audit_path,
        control_plane_path=cp_smoke_path,
        dead_letter_path=dl_smoke,
        replay_guard_path=rg_smoke,
    )
    if r3.get("ok") and r3.get("ingest_mode") == "direct":
        accepted_direct += 1

    r4 = process_governed_external_ingest(
        _watchlist_event(source_id=qu, asset_id=asset_id, note="queued-item-1"),
        source_id_header=qu,
        webhook_secret=secret,
        repo_root=root,
        source_registry_path=src_reg_path,
        budget_state_path=bud_path,
        queue_path=q_path,
        ingest_registry_path=ing_path,
        audit_path=ext_audit_path,
        control_plane_path=cp_smoke_path,
        dead_letter_path=dl_smoke,
        replay_guard_path=rg_smoke,
    )
    if r4.get("ok") and r4.get("ingest_mode") == "queued":
        queued_events += 1

    flush_out = flush_one_queued_event_to_registry(
        repo_root=root,
        queue_path=q_path,
        ingest_registry_path=ing_path,
        audit_path=ext_audit_path,
        control_plane_path=cp_smoke_path,
    )

    win_sec = int(cp_run.get("window_seconds") or 3600)
    cycles_in_win = count_cycles_started_in_window(audit_path, window_seconds=win_sec)
    timing = should_run_cycle_now(
        control_plane=cp_run,
        profile_name="manual_debug",
        last_cycle_started_at=last_cycle_timestamp(audit_path),
        cycles_in_current_window=cycles_in_win,
    )
    timing = {"run": True, "reason": "phase52_smoke_bypass_timing", "detail": "governed_webhook", "profile": "manual_debug"}

    supplemental = supplemental_triggers_from_registry(ing_path)
    ext_ids = [str(t.get("external_event_id")) for t in supplemental if t.get("external_event_id")]

    cycle_id = str(uuid.uuid4())
    lease = try_acquire_lease(lease_path)
    if not lease["ok"]:
        gen = datetime.now(timezone.utc).isoformat()
        health = build_runtime_health_summary(
            repo_root=root,
            ingest_registry_path=ing_path,
            external_source_registry_path=src_reg_path,
            external_budget_state_path=bud_path,
            external_event_queue_path=q_path,
            dead_letter_path=dl_smoke,
            replay_guard_path=rg_smoke,
        )
        return {
            "ok": False,
            "phase": "phase52_webhook_auth_routing",
            "generated_utc": gen,
            "input_phase51_bundle_path": str(p51),
            "sources_registered": len(sources),
            "auth_results_summary": {"auth_failures": auth_failures, "routing_failures": routing_failures},
            "rate_limit_results_summary": {"rate_limited_events": rate_hits},
            "routing_results_summary": {"disallowed_raw_rejected": routing_failures},
            "queue_summary": {"queued": queued_events, "flush_ok": flush_out.get("ok"), "pending_depth": len([x for x in (load_queue(q_path).get("items") or []) if x.get("status") == "pending"])},
            "runtime_health_summary": health,
            "phase53": recommend_phase53(),
            "error": "lease_not_acquired",
            "smoke_metrics_ok": False,
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
            skip_alerts=True,
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
                {"kind": "external_consumed", "event_id": eid, "linked_cycle_id": cycle_id},
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
            why_started="phase52_governed_webhook_smoke",
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
    metrics_ok = (
        auth_failures >= 1
        and routing_failures >= 1
        and rate_hits >= 1
        and queued_events >= 1
        and flush_out.get("ok")
        and len(supplemental) >= 1
        and len(jobs_c) >= 1
        and len(jobs_e) >= 1
        and extra_ok
    )

    health = build_runtime_health_summary(
        repo_root=root,
        ingest_registry_path=ing_path,
        external_source_registry_path=src_reg_path,
        external_budget_state_path=bud_path,
        external_event_queue_path=q_path,
        dead_letter_path=dl_smoke,
        replay_guard_path=rg_smoke,
    )
    cockpit_preview = build_cockpit_runtime_health_payload(repo_root=root, ingest_registry_path=ing_path)
    if persist_health_summary:
        refresh_and_persist_runtime_health(root)

    gen = datetime.now(timezone.utc).isoformat()
    reg = load_ingest_registry(ing_path)
    entries = list(reg.get("entries") or [])
    n_acc = sum(1 for e in entries if e.get("status") == "accepted")
    n_con = sum(1 for e in entries if e.get("status") == "consumed")

    return {
        "ok": metrics_ok,
        "smoke_metrics_ok": metrics_ok,
        "phase": "phase52_webhook_auth_routing",
        "generated_utc": gen,
        "input_phase51_bundle_path": str(p51),
        "sources_registered": len(sources),
        "auth_results_summary": {
            "auth_failures_recorded": auth_failures,
            "expected_min": 1,
        },
        "rate_limit_results_summary": {
            "rate_limited_events": rate_hits,
            "expected_min": 1,
        },
        "routing_results_summary": {
            "disallowed_raw_rejected": routing_failures,
            "expected_min": 1,
        },
        "queue_summary": {
            "queued_events": queued_events,
            "flush_registry_ok": flush_out.get("ok"),
            "flush_registry_entry_status": (flush_out.get("registry_entry") or {}).get("status"),
            "pending_after_flush": sum(1 for x in (load_queue(q_path).get("items") or []) if x.get("status") == "pending"),
        },
        "runtime_health_summary": health,
        "cockpit_runtime_health_preview": cockpit_preview,
        "ingest_registry_accepted_rows": n_acc,
        "ingest_registry_consumed_rows": n_con,
        "phase48_generated_utc": p48_out.get("generated_utc"),
        "trigger_results": triggers,
        "jobs_created": jobs_c,
        "jobs_executed": jobs_e,
        "bounded_debate_outputs": debates,
        "discovery_candidates": disc_out,
        "cockpit_surface_outputs": cockpit,
        "isolated_ingest_registry_path": str(ing_path),
        "isolated_external_audit_path": str(ext_audit_path),
        "external_source_registry_path": str(src_reg_path),
        "external_source_budget_state_path": str(bud_path),
        "external_event_queue_path": str(q_path),
        "production_registry_paths_note": (
            "Operator defaults: external_source_registry_v1.json, "
            "external_source_budget_state_v1.json, external_event_queue_v1.json under data/research_runtime/."
        ),
        "phase53": recommend_phase53(),
    }
