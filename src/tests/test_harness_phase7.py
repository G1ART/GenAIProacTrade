"""Phase 7 harness: contracts, referee, memo disagreement (no DB)."""

from __future__ import annotations

import pytest

from harness.memo_builder.pipeline import generate_investigation_memo_v1
from harness.referee.gate import referee_gate_scan
from harness.roles.deterministic_agents import (
    run_challenge_agent,
    run_synthesis_agent,
    run_thesis_agent,
)


def _minimal_input() -> dict:
    return {
        "contract_version": "ai_harness_input_v1",
        "payload_hash": "testhash",
        "candidate_id": "00000000-0000-0000-0000-000000000001",
        "issuer_id": None,
        "ticker": "TEST",
        "company_name": "Test Co",
        "as_of_date": "2025-01-15",
        "cik": "0000000000",
        "state_change_run_id": "00000000-0000-0000-0000-000000000002",
        "universe_name": "sp500_current",
        "factor_version": "v1",
        "candidate_rank": 1,
        "candidate_class": "investigate_now",
        "candidate_reason_json": {},
        "dominant_change_type": "signal_shift",
        "confidence_band": "medium",
        "state_change_score": 1.25,
        "state_change_direction": "increase",
        "score_gating_status": "ok",
        "top_driver_signals_json": [{"name": "velocity"}],
        "component_breakdown": [],
        "key_factor_deltas": {"accruals": 0.1},
        "validation_context_summary": {"summaries": []},
        "validation_panel_join": {},
        "filing_source_handles": [{"kind": "sec_accession", "accession_no": "0000320193-24-000001"}],
        "coverage_flags": [],
        "missing_data_indicators": [],
        "contamination_indicators": [],
        "regime_context_flags": [],
    }


def test_thesis_challenge_both_non_empty() -> None:
    inp = _minimal_input()
    th = run_thesis_agent(inp)
    ch = run_challenge_agent(inp)
    sy = run_synthesis_agent(inp, th, ch)
    assert th.get("text")
    assert ch.get("alternate_interpretation")
    assert sy.get("challenge_preserved") is True
    assert sy.get("thesis_preserved") is True


def test_referee_default_passes_clean_memo() -> None:
    memo = generate_investigation_memo_v1(_minimal_input(), memo_version=1)
    assert memo.get("strongest_counter_argument", {}).get("alternate_interpretation")
    assert memo.get("referee_result", {}).get("passed") is True


def test_referee_blocks_buy_language() -> None:
    memo = generate_investigation_memo_v1(_minimal_input(), memo_version=1)
    memo["thesis_interpretation"]["text"] = "You should buy this stock now."
    r = referee_gate_scan(memo)
    assert r["passed"] is False
    assert any(
        x.get("code") == "forbidden_execution_or_promotion_language" for x in r["flags"]
    )


def test_referee_requires_counter_argument() -> None:
    memo = generate_investigation_memo_v1(_minimal_input(), memo_version=1)
    memo["strongest_counter_argument"] = {}
    r = referee_gate_scan(memo)
    assert r["passed"] is False


def test_cli_help_harness_commands() -> None:
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    env = {**__import__("os").environ, "PYTHONPATH": str(root / "src")}
    for cmd in (
        "smoke-harness",
        "build-ai-harness-inputs",
        "generate-investigation-memos",
        "report-review-queue",
        "set-review-queue-status",
        "export-phase7-evidence-bundle",
    ):
        r = subprocess.run(
            [sys.executable, str(root / "src" / "main.py"), cmd, "-h"],
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
        )
        assert r.returncode == 0, (cmd, r.stderr)
