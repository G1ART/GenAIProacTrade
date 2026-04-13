"""Phase 51: external ingest, normalization, dedupe, control plane, health, positive-path smoke."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase48_runtime.trigger_engine import evaluate_triggers
from phase50_runtime.control_plane import default_control_plane_state, save_control_plane
from phase50_runtime.trigger_controls import effective_budget_policy

from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState

from phase51_runtime.external_ingest_adapters import process_external_payload, process_events_from_file
from phase51_runtime.external_trigger_ingest import (
    default_ingest_registry_path,
    ingest_external_event,
    load_ingest_registry,
    supplemental_triggers_from_registry,
)
from phase51_runtime.orchestrator import run_phase51_external_positive_path_smoke
from phase51_runtime.runtime_health import build_runtime_health_summary
from phase51_runtime.trigger_normalizer import compute_dedupe_key, normalize_raw_event


def _raw_ev(**kwargs) -> dict:
    base = {
        "source_type": "test",
        "source_id": "t1",
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": "a1"},
        "payload": {"note": "n1", "suggested_job_type": "debate.execute"},
    }
    base.update(kwargs)
    return base


def test_normalize_known_and_unknown() -> None:
    r = normalize_raw_event(_raw_ev())
    assert r["ok"] and r["normalized_trigger_type"] == "manual_watchlist"
    bad = normalize_raw_event(_raw_ev(raw_event_type="totally_unknown"))
    assert not bad["ok"]


def test_dedupe_key_deterministic() -> None:
    a = compute_dedupe_key(
        source_type="s",
        source_id="i",
        raw_event_type="watchlist_submit",
        payload={"note": "x"},
    )
    b = compute_dedupe_key(
        source_type="s",
        source_id="i",
        raw_event_type="watchlist_submit",
        payload={"note": "x"},
    )
    assert a == b


def test_ingest_rejects_disabled_trigger_type(tmp_path: Path) -> None:
    cp_path = tmp_path / "cp.json"
    st = default_control_plane_state()
    st["disabled_trigger_types"] = ["manual_watchlist"]
    save_control_plane(cp_path, st)
    ing = tmp_path / "ing.json"
    ent = ingest_external_event(
        _raw_ev(),
        ingest_registry_path=ing,
        control_plane=st,
    )
    assert ent["status"] == "rejected"
    assert ent.get("accepted_or_rejected_reason") == "trigger_type_disabled_or_not_allowed"


def test_ingest_maintenance_suppressed(tmp_path: Path) -> None:
    cp = default_control_plane_state()
    cp["maintenance_mode"] = True
    ing = tmp_path / "ing.json"
    ent = ingest_external_event(
        _raw_ev(),
        ingest_registry_path=ing,
        control_plane=cp,
        maintenance_blocks_accept=True,
    )
    assert ent["accepted_or_rejected_reason"] == "maintenance_mode_ingest_suppressed"


def test_dedupe_second_identical(tmp_path: Path) -> None:
    cp = default_control_plane_state()
    ing = tmp_path / "ing.json"
    e1 = ingest_external_event(_raw_ev(source_id="dup"), ingest_registry_path=ing, control_plane=cp)
    assert e1["status"] == "accepted"
    e2 = ingest_external_event(_raw_ev(source_id="dup"), ingest_registry_path=ing, control_plane=cp)
    assert e2["status"] == "deduped"


def test_supplemental_from_registry(tmp_path: Path) -> None:
    cp = default_control_plane_state()
    ing = tmp_path / "ing.json"
    ingest_external_event(_raw_ev(), ingest_registry_path=ing, control_plane=cp)
    sup = supplemental_triggers_from_registry(ing)
    assert len(sup) == 1
    assert sup[0]["trigger_type"] == "manual_watchlist"


def test_evaluate_triggers_merges_supplemental(tmp_path: Path) -> None:
    p46 = {
        "generated_utc": "2026-01-01T00:00:00+00:00",
        "founder_read_model": {"asset_id": "x"},
    }
    dec = tmp_path / "d.json"
    dec.write_text(json.dumps({"schema_version": 1, "decisions": []}), encoding="utf-8")
    pol = effective_budget_policy(default_control_plane_state())
    sup = [
        {
            "trigger_type": "manual_watchlist",
            "dedupe_key": "ext:sup:1",
            "priority": 15,
            "payload": {"asset_id": "x", "note": "s", "suggested_job_type": "debate.execute"},
            "suggested_job_type": "debate.execute",
        }
    ]
    tr = evaluate_triggers(
        repo_root=tmp_path,
        phase46_bundle=p46,
        phase45_bundle=None,
        decision_ledger_path=dec,
        registry_metadata={"last_phase46_generated_utc": "2026-01-01T00:00:00+00:00"},
        policy=pol,
        manual_triggers_path=None,
        supplemental_triggers=sup,
    )
    types = [t["trigger_type"] for t in tr]
    assert "manual_watchlist" in types


def test_runtime_health_summary_shape(tmp_path: Path) -> None:
    ing = tmp_path / "ing.json"
    ing.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    h = build_runtime_health_summary(repo_root=tmp_path, ingest_registry_path=ing)
    assert h.get("health_status")
    assert "external_ingest_counts" in h
    assert "audit_tail_summary" in h


def test_process_external_payload_writes_registry_and_audit(tmp_path: Path) -> None:
    cp_path = tmp_path / "cp.json"
    save_control_plane(cp_path, default_control_plane_state())
    ing = tmp_path / "ing.json"
    aud = tmp_path / "aud.json"
    out = process_external_payload(
        _raw_ev(source_id="file_drop_test"),
        repo_root=tmp_path,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp_path,
    )
    assert out["ok"]
    reg = load_ingest_registry(ing)
    assert len(reg["entries"]) == 1
    log = json.loads(aud.read_text(encoding="utf-8"))
    assert len(log["entries"]) >= 1


def test_phase51_external_positive_path_smoke_nonzero(tmp_path: Path) -> None:
    p46 = tmp_path / "p46.json"
    p46.write_text(
        json.dumps(
            {
                "ok": True,
                "phase": "phase46_founder_decision_cockpit",
                "generated_utc": "2026-01-02T00:00:00+00:00",
                "founder_read_model": {
                    "asset_id": "t_cohort",
                    "closeout_status": "closed_pending_new_evidence",
                    "gate_summary": {
                        "gate_status": "deferred",
                        "primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate",
                    },
                    "current_uncertainties": ["u1"],
                },
            }
        ),
        encoding="utf-8",
    )
    p50 = tmp_path / "p50.json"
    p50.write_text(
        json.dumps({"ok": True, "phase": "phase50", "generated_utc": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    out = run_phase51_external_positive_path_smoke(
        phase46_bundle_in=str(p46),
        phase50_control_bundle_in=str(p50),
        repo_root=tmp_path,
        registry_path=tmp_path / "reg.json",
        discovery_path=tmp_path / "disc.json",
        ingest_registry_path=tmp_path / "ing.json",
        external_audit_path=tmp_path / "ext_aud.json",
        decision_ledger_path=tmp_path / "dec.json",
        manual_triggers_path=tmp_path / "man.json",
        lease_path=tmp_path / "lease.json",
    )
    assert out.get("smoke_metrics_ok") is True
    assert out.get("external_events_accepted", 0) >= 1
    assert out.get("cycles_consuming_external_events")
    assert len(out.get("jobs_created") or []) >= 1
    assert len(out.get("bounded_debate_outputs") or []) >= 1


def test_dispatch_runtime_health_and_oversized_ingest(tmp_path: Path) -> None:
    bpath = tmp_path / "b46.json"
    bpath.write_text(
        json.dumps(
            {
                "ok": True,
                "phase": "phase46_founder_decision_cockpit",
                "generated_utc": "2026-01-01T00:00:00+00:00",
                "founder_read_model": {"asset_id": "x"},
                "cockpit_state": {"cohort_aggregate": {"decision_card": {}}},
            }
        ),
        encoding="utf-8",
    )
    ap = tmp_path / "a.json"
    dp = tmp_path / "d.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    code, obj = dispatch_json(st, method="GET", path="/api/runtime/health", body=None)
    assert code == 200
    assert obj.get("headline")

    big = b'{"x":"' + b"y" * 40000 + b'"}'
    code2, obj2 = dispatch_json(
        st,
        method="POST",
        path="/api/runtime/external-ingest",
        body=big,
    )
    assert code2 == 413
    assert obj2.get("error") == "body_too_large"


def test_repo_phase50_bundle_path_exists() -> None:
    repo = Path(__file__).resolve().parents[2]
    p50 = repo / "docs/operator_closeout/phase50_registry_controls_and_operator_timing_bundle.json"
    if not p50.is_file():
        pytest.skip("phase50 bundle missing")
    assert p50.is_file()


def test_default_ingest_path_under_data() -> None:
    repo = Path(__file__).resolve().parents[2]
    p = default_ingest_registry_path(repo)
    assert "external_trigger_ingest_v1.json" in str(p)
