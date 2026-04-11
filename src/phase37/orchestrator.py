"""Phase 37 orchestrator — assemble backlog sprint bundle (no DB, no broad repair)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase37.adversarial_review import default_adversarial_reviews
from phase37.casebook import seed_casebook_entries
from phase37.constitution import constitution_bundle_payload
from phase37.explanation_surface import render_explanation_prototype_md
from phase37.hypothesis_registry import default_hypothesis_registry
from phase37.phase38_recommend import recommend_phase38_after_phase37
from phase37.persistence import ensure_research_data_dir, write_json
from phase37.pit_experiment import (
    default_pit_spec_for_join_mismatch_fixture,
    fixture_join_key_mismatch_rows,
    run_pit_experiment_scaffold,
)


def _load_phase36_1_ground_truth(bundle_path: str) -> dict[str, Any]:
    p = Path(bundle_path)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def run_phase37_research_engine_backlog_sprint(
    *,
    phase36_1_bundle_path: str = "",
    research_data_dir: str = "data/research_engine",
    explanation_out_path: str = "docs/operator_closeout/phase37_explanation_prototype.md",
) -> dict[str, Any]:
    gt = _load_phase36_1_ground_truth(phase36_1_bundle_path.strip())
    closeout = (gt.get("closeout_summary") or {}) if gt else {}
    if not closeout and gt.get("after"):
        # tolerate shape without closeout_summary
        a = gt["after"]
        closeout = {
            "joined_recipe_substrate_row_count": a.get("joined_recipe_substrate_row_count"),
            "joined_market_metadata_flagged_count": a.get("joined_market_metadata_flagged_count"),
            "no_state_change_join": (a.get("exclusion_distribution") or {}).get(
                "no_state_change_join"
            ),
            "missing_excess_return_1q": a.get("missing_excess_return_1q"),
            "missing_validation_symbol_count": a.get("missing_validation_symbol_count"),
        }

    hypotheses = default_hypothesis_registry()
    casebook = seed_casebook_entries()
    reviews = default_adversarial_reviews()
    spec = default_pit_spec_for_join_mismatch_fixture()
    exp = run_pit_experiment_scaffold(
        hypothesis_id=hypotheses[0]["hypothesis_id"],
        spec=spec,
    )
    fixture = fixture_join_key_mismatch_rows()
    explanation_md = render_explanation_prototype_md(
        hypothesis=hypotheses[0],
        signal_case=fixture[0],
    )

    exp_path = Path(explanation_out_path)
    exp_path.parent.mkdir(parents=True, exist_ok=True)
    exp_path.write_text(explanation_md, encoding="utf-8")

    rdir = ensure_research_data_dir(research_data_dir)
    artifact_paths = {
        "hypotheses_v1": write_json(rdir / "hypotheses_v1.json", hypotheses),
        "casebook_v1": write_json(rdir / "casebook_v1.json", casebook),
        "pit_experiments_v1": write_json(
            rdir / "pit_experiments_v1.json", [exp.to_json_dict()]
        ),
        "adversarial_reviews_v1": write_json(
            rdir / "adversarial_reviews_v1.json", reviews
        ),
    }

    phase38 = recommend_phase38_after_phase37()
    now = datetime.now(timezone.utc).isoformat()

    return {
        "ok": True,
        "phase": "phase37_research_engine_backlog_sprint_1",
        "generated_utc": now,
        "ground_truth_phase36_1": closeout
        or {
            "joined_recipe_substrate_row_count": 266,
            "joined_market_metadata_flagged_count": 0,
            "no_state_change_join": 8,
            "missing_excess_return_1q": 78,
            "missing_validation_symbol_count": 151,
            "substrate_freeze_recommendation": "freeze_public_core_and_shift_to_research_engine",
            "phase37_recommendation": "execute_research_engine_backlog_sprint",
            "note": "fallback_defaults_when_bundle_missing",
        },
        "research_engine_constitution": constitution_bundle_payload(),
        "executable_vs_conceptual": {
            "executable_now": [
                "JSON hypothesis objects (hypotheses_v1.json)",
                "JSON casebook entries (casebook_v1.json)",
                "PIT experiment scaffold record (pit_experiments_v1.json) — inputs/alternates only",
                "Adversarial review records (adversarial_reviews_v1.json)",
                "Explanation prototype markdown (phase37_explanation_prototype.md)",
            ],
            "conceptual_phase38": [
                "DB-bound PIT replay comparing alternate as_of / run specs",
                "Promotion gate checklist persistence and enforcement hooks",
                "User-facing app surface wiring (API/UI) beyond static MD",
            ],
        },
        "hypothesis_registry_v1": {"hypotheses": hypotheses},
        "pit_lab": {
            "fixture_join_key_mismatch_rows": fixture,
            "default_spec": spec.to_json_dict(),
            "experiments": [exp.to_json_dict()],
        },
        "adversarial_reviews_v1": reviews,
        "casebook_v1": casebook,
        "explanation_prototype": {
            "format": "markdown",
            "path": str(exp_path.resolve()),
            "hypothesis_id": hypotheses[0]["hypothesis_id"],
            "signal_symbol": fixture[0]["symbol"],
        },
        "persistent_artifact_paths": artifact_paths,
        "phase38": phase38,
    }
