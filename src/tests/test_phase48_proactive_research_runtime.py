"""Phase 48: triggers, jobs, debate, premium, discovery, budget, cockpit outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase48_runtime.bounded_debate import DEBATE_OUTCOMES, run_bounded_debate
from phase48_runtime.budget_policy import default_budget_policy, trigger_allowed
from phase48_runtime.discovery_pipeline import append_discovery_candidate, discovery_schema, load_discovery
from phase48_runtime.job_registry import (
    append_job,
    job_with_dedupe_exists,
    load_registry,
    update_job,
)
from phase48_runtime.orchestrator import run_phase48_proactive_research_runtime
from phase48_runtime.premium_escalation import evaluate_premium_candidate
from phase48_runtime.trigger_engine import evaluate_triggers


def _p46_bundle(tmp: Path, *, gen: str, asset: str = "acohort") -> Path:
    p = tmp / "phase46.json"
    p.write_text(
        json.dumps(
            {
                "ok": True,
                "phase": "phase46_founder_decision_cockpit",
                "generated_utc": gen,
                "input_phase45_bundle_path": str(tmp / "p45.json"),
                "founder_read_model": {
                    "asset_id": asset,
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


def test_trigger_dedupe_keys_in_engine(tmp_path: Path) -> None:
    p46 = {
        "generated_utc": "g1",
        "founder_read_model": {"asset_id": "a", "closeout_status": "open"},
    }
    tr = evaluate_triggers(
        repo_root=tmp_path,
        phase46_bundle=p46,
        phase45_bundle={},
        decision_ledger_path=tmp_path / "missing.json",
        registry_metadata={"last_phase46_generated_utc": None},
    )
    dks = [t["dedupe_key"] for t in tr]
    assert len(dks) == len(set(dks))


def test_job_registry_append_and_dedupe(tmp_path: Path) -> None:
    regp = tmp_path / "reg.json"
    regp.write_text(
        json.dumps({"schema_version": 1, "metadata": {}, "jobs": []}), encoding="utf-8"
    )
    append_job(
        regp,
        job_type="evidence.refresh",
        asset_scope={"x": 1},
        trigger_source="t",
        priority=1,
        budget_class="cheap_deterministic",
        dedupe_key="dk1",
    )
    reg = load_registry(regp)
    assert job_with_dedupe_exists(reg, "dk1")
    jid = reg["jobs"][0]["job_id"]
    update_job(regp, jid, status="completed", result_summary="done")
    reg2 = load_registry(regp)
    assert reg2["jobs"][0]["status"] == "completed"


def test_bounded_debate_stopping_rules() -> None:
    ctx = {
        "authoritative_recommendation": "n",
        "primary_block_category": "deferred_due_to_proxy_limited_falsifier_substrate",
        "gate_status": "deferred",
        "closeout_status": "closed_pending_new_evidence",
    }
    out = run_bounded_debate(question="q", context=ctx, max_turns=2, max_roles=3)
    assert out["turns_used"] == 2
    assert len(out["transcript"]) == 2 * 3
    assert out["outcome"] in DEBATE_OUTCOMES


def test_premium_escalation_candidate_gate() -> None:
    prem = evaluate_premium_candidate(
        debate_outcome="unknown",
        gate_status="deferred",
        primary_block_category="deferred_due_to_proxy_limited_falsifier_substrate",
        founder_uncertainties=["a"],
        debate_transcript_len=5,
    )
    assert prem["premium_candidate"] is True
    assert prem["not_forced_into_surface_without_review"] is True
    prem2 = evaluate_premium_candidate(
        debate_outcome="no_action",
        gate_status="open",
        primary_block_category="",
        founder_uncertainties=[],
        debate_transcript_len=5,
    )
    assert prem2["premium_candidate"] is False


def test_discovery_candidate_shape(tmp_path: Path) -> None:
    p = tmp_path / "disc.json"
    p.write_text(json.dumps({"schema_version": 1, "candidates": []}), encoding="utf-8")
    rec = append_discovery_candidate(
        p,
        asset_scope={"asset_id": "x"},
        why_surfaced="test",
        triggers_fired=["t1"],
        still_uncertain="u",
        evidence_needed="e",
        debate_converged=False,
        linked_job_id="j1",
    )
    for k in discovery_schema()["required_fields"]:
        assert k in rec
    assert rec["not_a_recommendation"] is True
    assert len(load_discovery(p)["candidates"]) == 1


def test_budget_max_jobs_per_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pol = default_budget_policy()
    pol["max_jobs_per_run"] = 1
    monkeypatch.setattr(
        "phase48_runtime.orchestrator.default_budget_policy",
        lambda: pol,
    )

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
                        "timestamp": "2099-01-01T00:00:00+00:00",
                        "asset_id": "acohort",
                        "decision_type": "watch",
                        "founder_note": "n",
                        "linked_message_summary": "m",
                        "linked_authoritative_artifact": "a",
                        "linked_research_provenance": "r",
                    },
                    {
                        "timestamp": "2099-01-02T00:00:00+00:00",
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
    bpath = _p46_bundle(tmp_path, gen="2026-01-01T00:00:00+00:00")
    out = run_phase48_proactive_research_runtime(
        phase46_bundle_in=str(bpath),
        repo_root=tmp_path,
        registry_path=regp,
        discovery_path=discp,
        decision_ledger_path=decp,
        skip_alerts=True,
    )
    assert len(out["jobs_created"]) == 1


def test_full_cycle_debate_and_cockpit_outputs(tmp_path: Path) -> None:
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
    bpath = _p46_bundle(tmp_path, gen="2026-02-01T00:00:00+00:00")
    out = run_phase48_proactive_research_runtime(
        phase46_bundle_in=str(bpath),
        repo_root=tmp_path,
        registry_path=regp,
        discovery_path=discp,
        decision_ledger_path=decp,
        skip_alerts=True,
    )
    assert out["ok"] is True
    assert out["phase"] == "phase48_proactive_research_runtime"
    for k in (
        "trigger_results",
        "jobs_created",
        "jobs_executed",
        "bounded_debate_outputs",
        "premium_escalation_candidates",
        "discovery_candidates",
        "budget_policy",
        "cockpit_surface_outputs",
        "phase49",
    ):
        assert k in out
    debate_jobs = [j for j in out["jobs_created"] if j.get("job_type") == "debate.execute"]
    assert debate_jobs
    assert out["bounded_debate_outputs"]
    assert any(
        o.get("kind") == "discovery_candidate" for o in out["cockpit_surface_outputs"]
    ) or out["discovery_candidates"]
    assert out["phase49"].get("phase49_recommendation")


def test_second_cycle_no_bundle_trigger(tmp_path: Path) -> None:
    regp = tmp_path / "reg.json"
    regp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metadata": {
                    "last_phase46_generated_utc": "2026-03-01T00:00:00+00:00",
                    "last_cycle_utc": "2026-03-01T01:00:00+00:00",
                },
                "jobs": [],
            }
        ),
        encoding="utf-8",
    )
    discp = tmp_path / "disc.json"
    discp.write_text(json.dumps({"schema_version": 1, "candidates": []}), encoding="utf-8")
    decp = tmp_path / "dec.json"
    decp.write_text(json.dumps({"schema_version": 1, "decisions": []}), encoding="utf-8")
    bpath = _p46_bundle(tmp_path, gen="2026-03-01T00:00:00+00:00")
    out = run_phase48_proactive_research_runtime(
        phase46_bundle_in=str(bpath),
        repo_root=tmp_path,
        registry_path=regp,
        discovery_path=discp,
        decision_ledger_path=decp,
        skip_alerts=True,
    )
    assert not any(t["trigger_type"] == "changed_artifact_bundle" for t in out["trigger_results"])


def test_trigger_allowed_policy() -> None:
    p = default_budget_policy()
    assert trigger_allowed(p, "changed_artifact_bundle")
    p2 = {**p, "allowed_trigger_types": ["manual_watchlist"]}
    assert trigger_allowed(p2, "manual_watchlist")
    assert not trigger_allowed(p2, "changed_artifact_bundle")
