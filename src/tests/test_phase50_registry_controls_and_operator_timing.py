"""Phase 50: control plane, lease, timing, audit, trigger overrides, positive-path smoke."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase48_runtime.budget_policy import default_budget_policy
from phase48_runtime.orchestrator import run_phase48_proactive_research_runtime
from phase48_runtime.trigger_engine import evaluate_triggers
from phase50_runtime.control_plane import (
    default_control_plane_path,
    load_control_plane,
    save_control_plane,
)
from phase50_runtime.cycle_lease import default_lease_path, release_lease, try_acquire_lease
from phase50_runtime.orchestrator import (
    run_phase50_positive_path_smoke,
    run_phase50_registry_controls_and_operator_timing,
)
from phase50_runtime.runtime_audit_log import append_audit_entry, load_audit_log
from phase50_runtime.timing_policy import should_run_cycle_now
from phase50_runtime.trigger_controls import effective_budget_policy


def _minimal_p46() -> dict:
    return {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-01T00:00:00+00:00",
        "founder_read_model": {
            "asset_id": "t_cohort",
            "closeout_status": "closed_pending_new_evidence",
            "gate_summary": {"gate_status": "deferred", "primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate"},
            "current_uncertainties": ["u1"],
        },
        "input_phase45_bundle_path": "",
    }


def test_lease_acquire_release(tmp_path: Path) -> None:
    lp = tmp_path / "lease.json"
    a = try_acquire_lease(lp, ttl_seconds=60)
    assert a["ok"] is True
    b = try_acquire_lease(lp, ttl_seconds=60)
    assert b["ok"] is False
    release_lease(lp, cycle_id=a["cycle_id"])
    c = try_acquire_lease(lp, ttl_seconds=60)
    assert c["ok"] is True


def test_stale_lease_allows_reacquire(tmp_path: Path) -> None:
    lp = tmp_path / "lease.json"
    lp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "active",
                "cycle_id": "x",
                "holder": "old",
                "acquired_at": "2020-01-01T00:00:00+00:00",
                "expires_at": "2020-01-01T00:01:00+00:00",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    a = try_acquire_lease(lp, ttl_seconds=60)
    assert a["ok"] is True


def test_trigger_disable_override(tmp_path: Path) -> None:
    cp = {
        "allowed_trigger_types": ["manual_watchlist"],
        "disabled_trigger_types": ["changed_artifact_bundle"],
    }
    pol = effective_budget_policy(cp)
    assert "changed_artifact_bundle" not in pol["allowed_trigger_types"]
    assert "manual_watchlist" in pol["allowed_trigger_types"]


def test_timing_skip_maintenance() -> None:
    cp = {"enabled": True, "maintenance_mode": True, "max_cycles_per_window": 10, "window_seconds": 60}
    r = should_run_cycle_now(
        control_plane=cp,
        profile_name="manual_debug",
        last_cycle_started_at=None,
        cycles_in_current_window=0,
    )
    assert r["run"] is False
    assert r["reason"] == "maintenance_mode"


def test_runtime_audit_append(tmp_path: Path) -> None:
    ap = tmp_path / "audit.json"
    append_audit_entry(
        ap,
        {
            "timestamp": "t",
            "cycle_id": "c1",
            "why_cycle_started": "test",
            "lease_acquired": True,
            "controls_applied": {},
            "triggers_evaluated_count": 0,
            "jobs_created_count": 0,
            "jobs_executed_count": 0,
            "why_cycle_stopped": "skip",
            "cycle_skipped": True,
            "operator_override": None,
        },
    )
    log = load_audit_log(ap)
    assert len(log["entries"]) == 1


def test_positive_path_smoke_nonzero(tmp_path: Path) -> None:
    p46 = tmp_path / "p46.json"
    b = _minimal_p46()
    p46.write_text(json.dumps(b), encoding="utf-8")
    out = run_phase50_positive_path_smoke(
        phase46_bundle_in=str(p46),
        repo_root=tmp_path,
        skip_alerts=True,
        bypass_timing_for_smoke=True,
    )
    assert out.get("smoke_metrics_ok") is True
    assert out.get("ok") is True
    assert len(out.get("trigger_results") or []) >= 1
    assert len(out.get("jobs_created") or []) >= 1
    assert len(out.get("jobs_executed") or []) >= 1
    extra = (
        len(out.get("bounded_debate_outputs") or [])
        + len(out.get("premium_escalation_candidates") or [])
        + len(out.get("discovery_candidates") or [])
        + len(out.get("cockpit_surface_outputs") or [])
    )
    assert extra >= 1


def test_maintenance_blocks_smoke(tmp_path: Path) -> None:
    p46 = tmp_path / "p46.json"
    p46.write_text(json.dumps(_minimal_p46()), encoding="utf-8")
    cp = default_control_plane_path(tmp_path)
    save_control_plane(
        cp,
        {
            **load_control_plane(cp),
            "maintenance_mode": True,
            "enabled": True,
        },
    )
    out = run_phase50_positive_path_smoke(
        phase46_bundle_in=str(p46),
        repo_root=tmp_path,
        bypass_timing_for_smoke=False,
        honor_maintenance_mode=True,
    )
    assert out.get("ok") is False
    assert out.get("error") == "timing_blocked"


def test_registry_controls_bundle(tmp_path: Path) -> None:
    p49 = tmp_path / "p49.json"
    p49.write_text(
        json.dumps({"ok": True, "phase": "phase49", "generated_utc": "t"}),
        encoding="utf-8",
    )
    out = run_phase50_registry_controls_and_operator_timing(
        phase49_bundle_in=str(p49),
        repo_root=tmp_path,
    )
    assert out["ok"] is True
    for k in (
        "control_plane_state",
        "timing_profiles",
        "lease_behavior",
        "trigger_controls",
        "runtime_audit_summary",
        "phase51",
    ):
        assert k in out


def test_evaluate_triggers_respects_effective_policy(tmp_path: Path) -> None:
    dec = tmp_path / "dec.json"
    dec.write_text(json.dumps({"schema_version": 1, "decisions": []}), encoding="utf-8")
    b = _minimal_p46()
    pol = default_budget_policy()
    pol["allowed_trigger_types"] = ["manual_watchlist"]
    manual = tmp_path / "manual.json"
    manual.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pending": [{"asset_id": "x", "note": "n", "suggested_job_type": "debate.execute"}],
            }
        ),
        encoding="utf-8",
    )
    tr = evaluate_triggers(
        repo_root=tmp_path,
        phase46_bundle=b,
        phase45_bundle=None,
        decision_ledger_path=dec,
        registry_metadata={"last_phase46_generated_utc": None, "last_cycle_utc": None},
        policy=pol,
        manual_triggers_path=manual,
    )
    assert len(tr) == 1
    assert tr[0]["suggested_job_type"] == "debate.execute"


def test_phase48_accepts_budget_and_manual_path(tmp_path: Path) -> None:
    p46 = tmp_path / "p46.json"
    bundle = _minimal_p46()
    bundle["alert_ledger_path"] = str(tmp_path / "a.json")
    bundle["decision_trace_ledger_path"] = str(tmp_path / "d.json")
    (tmp_path / "a.json").write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    (tmp_path / "d.json").write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    p46.write_text(json.dumps(bundle), encoding="utf-8")
    reg = tmp_path / "reg.json"
    reg.write_text(
        json.dumps(
            {"schema_version": 1, "metadata": {"last_phase46_generated_utc": None, "last_cycle_utc": None}, "jobs": []},
            indent=2,
        ),
        encoding="utf-8",
    )
    disc = tmp_path / "disc.json"
    disc.write_text('{"schema_version":1,"candidates":[]}', encoding="utf-8")
    manual = tmp_path / "manual.json"
    manual.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pending": [{"asset_id": "t_cohort", "note": "x", "suggested_job_type": "debate.execute"}],
            }
        ),
        encoding="utf-8",
    )
    pol = default_budget_policy()
    pol["allowed_trigger_types"] = ["manual_watchlist"]
    out = run_phase48_proactive_research_runtime(
        phase46_bundle_in=str(p46),
        repo_root=tmp_path,
        registry_path=reg,
        discovery_path=disc,
        skip_alerts=True,
        budget_policy=pol,
        manual_triggers_path=manual,
    )
    assert len(out.get("jobs_executed") or []) >= 1


def test_repo_phase49_registry_bundle_smoke() -> None:
    repo = Path(__file__).resolve().parents[2]
    p49 = repo / "docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_bundle.json"
    if not p49.is_file():
        pytest.skip("phase49 bundle missing")
    out = run_phase50_registry_controls_and_operator_timing(
        phase49_bundle_in=str(p49),
        repo_root=repo,
    )
    assert out["ok"] is True
