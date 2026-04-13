"""Phase 49: multi-cycle scheduler wraps Phase 48 and aggregates metrics."""

from __future__ import annotations

import json
from pathlib import Path

from phase49_runtime.orchestrator import run_phase49_daemon_scheduler_multi_cycle


def _p46_bundle(tmp: Path, *, gen: str) -> Path:
    p = tmp / "phase46.json"
    p.write_text(
        json.dumps(
            {
                "ok": True,
                "phase": "phase46_founder_decision_cockpit",
                "generated_utc": gen,
                "input_phase45_bundle_path": str(tmp / "p45.json"),
                "founder_read_model": {
                    "asset_id": "acohort",
                    "closeout_status": "closed_pending_new_evidence",
                    "reopen_requires_named_source": True,
                    "authoritative_recommendation": "narrow_x",
                    "authoritative_phase": "phase44",
                    "current_uncertainties": ["u1", "u2"],
                    "gate_summary": {
                        "gate_status": "deferred",
                        "primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp / "p45.json").write_text(
        json.dumps(
            {
                "ok": True,
                "future_reopen_protocol": {"future_reopen_allowed_with_named_source": True},
            }
        ),
        encoding="utf-8",
    )
    return p


def test_phase49_two_cycles_aggregate_metrics(tmp_path: Path) -> None:
    regp = tmp_path / "reg.json"
    regp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metadata": {"last_phase46_generated_utc": None, "last_cycle_utc": None},
                "jobs": [],
            }
        ),
        encoding="utf-8",
    )
    discp = tmp_path / "disc.json"
    discp.write_text(json.dumps({"schema_version": 1, "candidates": []}), encoding="utf-8")
    decp = tmp_path / "dec.json"
    decp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "decisions": [
                    {
                        "timestamp": "2099-03-01T00:00:00+00:00",
                        "asset_id": "acohort",
                        "decision_type": "reopen_request",
                        "founder_note": "n",
                        "linked_message_summary": "m",
                        "linked_authoritative_artifact": "a",
                        "linked_research_provenance": "r",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    bpath = _p46_bundle(tmp_path, gen="2026-04-01T00:00:00+00:00")
    out = run_phase49_daemon_scheduler_multi_cycle(
        phase46_bundle_in=str(bpath),
        repo_root=tmp_path,
        cycles=2,
        sleep_seconds=0.0,
        registry_path=regp,
        discovery_path=discp,
        decision_ledger_path=decp,
        skip_alerts=True,
    )
    assert out["ok"] is True
    assert out["phase"] == "phase49_daemon_scheduler_multi_cycle_triggers_and_metrics_v1"
    agg = out["aggregate_metrics"]
    assert agg["cycles_completed"] == 2
    assert len(out["cycle_summaries"]) == 2
    assert len(out["phase48_cycles"]) == 2
    assert out["last_phase48_cycle"].get("phase") == "phase48_proactive_research_runtime"
    p50 = out.get("phase50") or {}
    assert p50.get("phase50_recommendation")
