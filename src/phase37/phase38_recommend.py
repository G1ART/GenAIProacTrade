"""Phase 38 entry recommendation after research engine sprint 1."""

from __future__ import annotations

from typing import Any


def recommend_phase38_after_phase37() -> dict[str, Any]:
    return {
        "phase38_recommendation": (
            "bind_pit_experiment_runner_to_db_and_execute_alternate_as_of_specs"
        ),
        "rationale": (
            "Hypothesis registry, casebook, and scaffold experiments exist; the next increment is a "
            "deterministic DB-bound PIT runner that replays join logic under alternate specs, persists "
            "results, and feeds adversarial review resolution — without broad substrate repair campaigns."
        ),
    }
