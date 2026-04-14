"""Phase 52: governed webhook auth, budgets, routing, queue, health merge."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState

from phase52_runtime.event_queue import (
    default_event_queue_path,
    enqueue_event,
    pop_next_pending,
    queue_depth_pending,
    save_queue,
)
from phase52_runtime.governed_ingress import flush_one_queued_event_to_registry, process_governed_external_ingest
from phase52_runtime.health_merge import merge_phase52_into_summary
from phase52_runtime.orchestrator import run_phase52_governed_webhook_auth_routing_smoke
from phase52_runtime.routing_rules import routing_allows_event
from phase52_runtime.source_budgets import check_and_consume_budget, default_budget_state_path, load_budget_state, save_budget_state
from phase52_runtime.source_registry import save_source_registry
from phase52_runtime.webhook_auth import hash_shared_secret, verify_webhook_secret


def test_verify_webhook_secret_timing_safe() -> None:
    h = hash_shared_secret("correct")
    assert verify_webhook_secret(stored_hash=h, presented_secret="correct")
    assert not verify_webhook_secret(stored_hash=h, presented_secret="wrong")


def test_routing_allows_and_rejects() -> None:
    src = {
        "allowed_raw_event_types": ["watchlist_submit"],
        "normalized_trigger_allowlist": ["manual_watchlist"],
    }
    ok, _ = routing_allows_event(source=src, raw_event_type="watchlist_submit", normalized_trigger_type="manual_watchlist")
    assert ok
    bad, r = routing_allows_event(source=src, raw_event_type="named_source_registration", normalized_trigger_type="named_source_signal")
    assert not bad
    assert "raw_event_type" in r


def test_rate_limit_per_minute(tmp_path: Path) -> None:
    bud = tmp_path / "bud.json"
    save_budget_state(bud, {"schema_version": 1, "by_source_id": {}})
    src = {"rate_limit_per_minute": 2, "max_events_per_window": 100, "window_seconds": 3600}
    t0 = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    a, _ = check_and_consume_budget(source=src, source_id="s1", budget_path=bud, now=t0)
    b, _ = check_and_consume_budget(source=src, source_id="s1", budget_path=bud, now=t0)
    c, r = check_and_consume_budget(source=src, source_id="s1", budget_path=bud, now=t0)
    assert a and b
    assert not c and r == "rate_limit_per_minute"


def test_queue_enqueue_dedupe(tmp_path: Path) -> None:
    q = tmp_path / "q.json"
    body = {"x": 1}
    r1 = enqueue_event(path=q, body=body, dedupe_key="dk1", source_id="src")
    r2 = enqueue_event(path=q, body=body, dedupe_key="dk1", source_id="src")
    assert r1["ok"]
    assert not r2["ok"]
    assert queue_depth_pending(q) == 1


def test_pop_next_pending_order(tmp_path: Path) -> None:
    q = tmp_path / "q2.json"
    enqueue_event(path=q, body={"a": 1}, dedupe_key="a", source_id="s")
    enqueue_event(path=q, body={"b": 1}, dedupe_key="b", source_id="s")
    first = pop_next_pending(q)
    second = pop_next_pending(q)
    assert first and first.get("body") == {"a": 1}
    assert second and second.get("body") == {"b": 1}


def test_health_merge_requires_non_empty_sources(tmp_path: Path) -> None:
    summary: dict = {"health_status": "healthy"}
    root = tmp_path
    default_reg = root / "data" / "research_runtime" / "external_source_registry_v1.json"
    default_reg.parent.mkdir(parents=True, exist_ok=True)
    default_reg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_name": "t",
                        "source_type": "webhook",
                        "source_id": "t1",
                        "enabled": True,
                        "shared_secret_hash": hash_shared_secret("x"),
                        "allowed_raw_event_types": ["watchlist_submit"],
                        "normalized_trigger_allowlist": ["manual_watchlist"],
                        "rate_limit_per_minute": 99,
                        "max_events_per_window": 99,
                        "window_seconds": 3600,
                        "queue_mode": "direct",
                        "notes": "",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    merge_phase52_into_summary(summary, root)
    assert "external_source_activity_v52" in summary


def test_process_governed_auth_failure_no_registry_row(tmp_path: Path) -> None:
    ing = tmp_path / "ing.json"
    aud = tmp_path / "aud.json"
    cp = tmp_path / "cp.json"
    cp.write_text(
        json.dumps(
            {
                "enabled": True,
                "maintenance_mode": False,
                "max_cycles_per_window": 10,
                "window_seconds": 3600,
                "disabled_trigger_types": [],
                "allowed_trigger_types": ["manual_watchlist"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    src_reg = tmp_path / "src.json"
    save_source_registry(
        src_reg,
        {
            "schema_version": 1,
            "sources": [
                {
                    "source_name": "x",
                    "source_type": "webhook",
                    "source_id": "gw1",
                    "enabled": True,
                    "shared_secret_hash": hash_shared_secret("sekret"),
                    "allowed_raw_event_types": ["watchlist_submit"],
                    "normalized_trigger_allowlist": ["manual_watchlist"],
                    "rate_limit_per_minute": 50,
                    "max_events_per_window": 500,
                    "window_seconds": 3600,
                    "queue_mode": "direct",
                    "notes": "",
                }
            ],
        },
    )
    bud = tmp_path / "bud.json"
    save_budget_state(bud, {"schema_version": 1, "by_source_id": {}})
    q = tmp_path / "q.json"
    save_queue(q, {"schema_version": 1, "max_depth": 500, "items": []})
    ev = {
        "source_type": "webhook",
        "source_id": "gw1",
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": "a1"},
        "payload": {"note": "n", "suggested_job_type": "debate.execute"},
    }
    out = process_governed_external_ingest(
        ev,
        source_id_header="gw1",
        webhook_secret="bad",
        repo_root=tmp_path,
        source_registry_path=src_reg,
        budget_state_path=bud,
        queue_path=q,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp,
    )
    assert not out.get("ok")
    assert out.get("error") == "auth_failed"
    if ing.is_file():
        reg = json.loads(ing.read_text(encoding="utf-8"))
        assert len(reg.get("entries") or []) == 0


def test_dispatch_authenticated_endpoint(tmp_path: Path) -> None:
    bpath = tmp_path / "b46.json"
    bpath.write_text(
        json.dumps(
            {
                "ok": True,
                "phase": "phase46_founder_decision_cockpit",
                "generated_utc": "2026-01-01T00:00:00+00:00",
                "founder_read_model": {"asset_id": "dispatch_asset"},
                "cockpit_state": {"cohort_aggregate": {"decision_card": {}}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ap = tmp_path / "a.json"
    dp = tmp_path / "d.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)

    dr = tmp_path / "data" / "research_runtime"
    dr.mkdir(parents=True, exist_ok=True)
    src_reg = dr / "external_source_registry_v1.json"
    sec = "dispatch-secret"
    save_source_registry(
        src_reg,
        {
            "schema_version": 1,
            "sources": [
                {
                    "source_name": "d",
                    "source_type": "webhook",
                    "source_id": "dispatch_src",
                    "enabled": True,
                    "shared_secret_hash": hash_shared_secret(sec),
                    "allowed_raw_event_types": ["watchlist_submit"],
                    "normalized_trigger_allowlist": ["manual_watchlist"],
                    "rate_limit_per_minute": 50,
                    "max_events_per_window": 500,
                    "window_seconds": 3600,
                    "queue_mode": "direct",
                    "notes": "",
                }
            ],
        },
    )
    cp_path = dr / "control_plane.json"
    cp_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "maintenance_mode": False,
                "max_cycles_per_window": 10,
                "window_seconds": 3600,
                "disabled_trigger_types": [],
                "allowed_trigger_types": ["manual_watchlist"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    from shutil import copyfile

    from phase50_runtime.control_plane import default_control_plane_path

    real_cp = default_control_plane_path(tmp_path)
    real_cp.parent.mkdir(parents=True, exist_ok=True)
    copyfile(cp_path, real_cp)

    ing_path = dr / "external_trigger_ingest_v1.json"
    ing_path.write_text(json.dumps({"schema_version": 1, "entries": []}, ensure_ascii=False), encoding="utf-8")
    aud_path = dr / "external_trigger_audit_log_v1.json"
    aud_path.write_text(json.dumps({"schema_version": 1, "entries": []}, ensure_ascii=False), encoding="utf-8")
    save_budget_state(default_budget_state_path(tmp_path), {"schema_version": 1, "by_source_id": {}})
    save_queue(default_event_queue_path(tmp_path), {"schema_version": 1, "max_depth": 500, "items": []})

    ev = {
        "source_type": "webhook",
        "source_id": "dispatch_src",
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": "dispatch_asset"},
        "payload": {"note": "via http", "suggested_job_type": "debate.execute"},
    }
    body = json.dumps(ev, ensure_ascii=False).encode("utf-8")
    code, obj = dispatch_json(
        st,
        method="POST",
        path="/api/runtime/external-ingest/authenticated",
        body=body,
        headers={"X-Source-Id": "dispatch_src", "X-Webhook-Secret": sec},
    )
    assert code == 200
    assert obj.get("ok")
    assert (obj.get("registry_entry") or {}).get("status") == "accepted"


def test_phase52_smoke_metrics(tmp_path: Path) -> None:
    p46 = Path(__file__).resolve().parents[2] / "docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json"
    p50 = Path(__file__).resolve().parents[2] / "docs/operator_closeout/phase50_registry_controls_and_operator_timing_bundle.json"
    p51 = Path(__file__).resolve().parents[2] / "docs/operator_closeout/phase51_external_trigger_ingest_bundle.json"
    if not p46.is_file() or not p50.is_file() or not p51.is_file():
        pytest.skip("anchor bundles missing")
    out = run_phase52_governed_webhook_auth_routing_smoke(
        phase46_bundle_in=str(p46),
        phase50_control_bundle_in=str(p50),
        input_phase51_bundle_path=str(p51),
        repo_root=tmp_path,
        persist_health_summary=False,
    )
    assert out.get("smoke_metrics_ok") is True
    assert out.get("auth_results_summary", {}).get("auth_failures_recorded", 0) >= 1
    assert out.get("queue_summary", {}).get("queued_events", 0) >= 1


def test_flush_queue_to_registry(tmp_path: Path) -> None:
    cp = tmp_path / "cp.json"
    cp.write_text(
        json.dumps(
            {
                "enabled": True,
                "maintenance_mode": False,
                "max_cycles_per_window": 10,
                "window_seconds": 3600,
                "disabled_trigger_types": [],
                "allowed_trigger_types": ["manual_watchlist"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ing = tmp_path / "ing.json"
    ing.write_text(json.dumps({"schema_version": 1, "entries": []}, ensure_ascii=False), encoding="utf-8")
    aud = tmp_path / "aud.json"
    aud.write_text(json.dumps({"schema_version": 1, "entries": []}, ensure_ascii=False), encoding="utf-8")
    q = tmp_path / "q.json"
    ev = {
        "source_type": "webhook",
        "source_id": "qsrc",
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": "aflush"},
        "payload": {"note": "flush me", "suggested_job_type": "debate.execute"},
    }
    enqueue_event(path=q, body=ev, dedupe_key="dkflush", source_id="qsrc")
    out = flush_one_queued_event_to_registry(
        repo_root=tmp_path,
        queue_path=q,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp,
    )
    assert out.get("ok")
    assert (out.get("registry_entry") or {}).get("status") == "accepted"
