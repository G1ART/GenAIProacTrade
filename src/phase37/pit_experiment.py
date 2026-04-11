"""PIT experiment runner scaffold — bind hypothesis to deterministic run spec, record outcomes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class PITRunSpecV1:
    """Deterministic experiment boundary (scaffold — DB binding is Phase 38+)."""

    spec_id: str
    hypothesis_id: str
    as_of_policy: str
    state_change_run_mode: str
    join_key_variant: str
    notes: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PITExperimentRecordV1:
    experiment_id: str
    hypothesis_id: str
    spec: dict[str, Any]
    inputs_snapshot: dict[str, Any]
    outputs: dict[str, Any]
    failure_modes: list[str]
    compared_alternates: list[dict[str, Any]]
    created_utc: str
    status: str

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def fixture_join_key_mismatch_rows() -> list[dict[str, Any]]:
    """Canonical PIT-lab fixture (aligned with Phase 36.1 bundle)."""
    return [
        {
            "symbol": "BBY",
            "cik": "0000764478",
            "signal_available_date": "2025-12-08",
            "residual_join_bucket": "state_change_built_but_join_key_mismatch",
            "blocked_reason": "earliest_state_change_as_of_after_signal_no_pit_match",
            "first_state_change_as_of_in_run": "2026-09-28",
        },
        {
            "symbol": "ADSK",
            "cik": "0000769397",
            "signal_available_date": "2025-11-27",
            "residual_join_bucket": "state_change_built_but_join_key_mismatch",
            "blocked_reason": "earliest_state_change_as_of_after_signal_no_pit_match",
            "first_state_change_as_of_in_run": "2026-09-28",
        },
        {
            "symbol": "CRM",
            "cik": "0001108524",
            "signal_available_date": "2025-12-04",
            "residual_join_bucket": "state_change_built_but_join_key_mismatch",
            "blocked_reason": "earliest_state_change_as_of_after_signal_no_pit_match",
            "first_state_change_as_of_in_run": "2026-09-28",
        },
        {
            "symbol": "CRWD",
            "cik": "0001535527",
            "signal_available_date": "2025-12-03",
            "residual_join_bucket": "state_change_built_but_join_key_mismatch",
            "blocked_reason": "earliest_state_change_as_of_after_signal_no_pit_match",
            "first_state_change_as_of_in_run": "2026-09-28",
        },
        {
            "symbol": "DELL",
            "cik": "0001571996",
            "signal_available_date": "2025-12-10",
            "residual_join_bucket": "state_change_built_but_join_key_mismatch",
            "blocked_reason": "earliest_state_change_as_of_after_signal_no_pit_match",
            "first_state_change_as_of_in_run": "2026-09-28",
        },
        {
            "symbol": "DUK",
            "cik": "0001326160",
            "signal_available_date": "2025-11-10",
            "residual_join_bucket": "state_change_built_but_join_key_mismatch",
            "blocked_reason": "earliest_state_change_as_of_after_signal_no_pit_match",
            "first_state_change_as_of_in_run": "2026-03-28",
        },
        {
            "symbol": "NVDA",
            "cik": "0001045810",
            "signal_available_date": "2025-11-20",
            "residual_join_bucket": "state_change_built_but_join_key_mismatch",
            "blocked_reason": "earliest_state_change_as_of_after_signal_no_pit_match",
            "first_state_change_as_of_in_run": "2026-09-28",
        },
        {
            "symbol": "WMT",
            "cik": "0000104169",
            "signal_available_date": "2025-12-04",
            "residual_join_bucket": "state_change_built_but_join_key_mismatch",
            "blocked_reason": "earliest_state_change_as_of_after_signal_no_pit_match",
            "first_state_change_as_of_in_run": "2026-09-28",
        },
    ]


def run_pit_experiment_scaffold(
    *,
    hypothesis_id: str,
    spec: PITRunSpecV1,
    fixture_rows: list[dict[str, Any]] | None = None,
) -> PITExperimentRecordV1:
    """
    Execute first scaffold pass: records inputs and placeholder outputs.
    Does not call DB or re-run state_change — binding is explicit Phase 38 work.
    """
    rows = fixture_rows if fixture_rows is not None else fixture_join_key_mismatch_rows()
    now = datetime.now(timezone.utc).isoformat()
    # Placeholder: alternate boundary comparison slots for future harness
    alternates = [
        {
            "label": "baseline_phase36_run_reference",
            "state_change_run_mode": "fixed_run_id_from_substrate_audit",
            "expected": "join_key_mismatch_for_fixture_set",
        },
        {
            "label": "alternate_not_yet_executed",
            "state_change_run_mode": "earlier_as_of_run_or_explicit_lag_shim",
            "expected": "TBD_phase38_db_bound_runner",
        },
    ]
    return PITExperimentRecordV1(
        experiment_id=str(uuid4()),
        hypothesis_id=hypothesis_id,
        spec=spec.to_json_dict(),
        inputs_snapshot={
            "fixture_row_count": len(rows),
            "fixture_symbols": [r["symbol"] for r in rows],
            "rows": rows,
        },
        outputs={
            "runner": "phase37_pit_experiment_scaffold_v1",
            "engine_result": "scaffold_only_no_db_execution",
            "summary": (
                "Recorded deterministic fixture and spec; compare_alternates reserved for Phase 38 "
                "runner that replays join under alternate as-of assumptions."
            ),
        },
        failure_modes=[],
        compared_alternates=alternates,
        created_utc=now,
        status="recorded_scaffold",
    )


def default_pit_spec_for_join_mismatch_fixture() -> PITRunSpecV1:
    return PITRunSpecV1(
        spec_id="pit_spec_join_mismatch_fixture_v1",
        hypothesis_id="hyp_pit_join_key_mismatch_as_of_boundary_v1",
        as_of_policy="signal_available_date_strict_pit",
        state_change_run_mode="reference_run_from_phase36_audit",
        join_key_variant="pick_state_change_at_or_before_signal_default",
        notes="Baseline spec mirrors production join; alternate specs to be executed in Phase 38.",
    )
