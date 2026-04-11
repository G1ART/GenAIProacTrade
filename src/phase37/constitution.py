"""Research engine constitution — pillars mapped to code artifacts and queueable work units."""

from __future__ import annotations

from typing import Any

# Each pillar: executable module(s), on-disk artifacts, work-unit kinds (for queues / JSONL / future DB).
RESEARCH_ENGINE_ARTIFACTS: list[dict[str, Any]] = [
    {
        "pillar_id": "hypothesis_forge",
        "summary": "Turn substrate-stable signals into testable hypotheses with explicit falsifiers.",
        "python_modules": [
            "phase37.hypothesis_registry",
            "phase39.hypothesis_seeds",
            "phase39.lifecycle",
            "phase40.lifecycle_phase40",
        ],
        "persistent_artifacts": ["data/research_engine/hypotheses_v1.json"],
        "work_unit_types": ["hypothesis.create", "hypothesis.attach_metrics", "hypothesis.transition_status"],
    },
    {
        "pillar_id": "pit_validation_lab",
        "summary": "Deterministic PIT replay under explicit as-of / join / lag boundaries.",
        "python_modules": [
            "phase37.pit_experiment",
            "phase38.pit_runner",
            "phase39.pit_family_contract",
            "phase40.pit_engine",
            "phase40.family_execution",
            "phase40.contract_manifest",
            "phase41.pit_rerun",
            "phase42.evidence_accumulation",
        ],
        "persistent_artifacts": [
            "data/research_engine/pit_experiments_v1.json",
            "data/research_engine/governance_join_policy_registry_v1.json",
        ],
        "work_unit_types": ["pit.bind_spec", "pit.execute_scaffold", "pit.compare_alternate_boundary"],
    },
    {
        "pillar_id": "adversarial_peer_review",
        "summary": "Structured challenges to thesis, mechanism, and data lineage — queryable, not chat logs.",
        "python_modules": ["phase37.adversarial_review", "phase39.adversarial_batch", "phase40.adversarial_family"],
        "persistent_artifacts": ["data/research_engine/adversarial_reviews_v1.json"],
        "work_unit_types": ["review.submit", "review.resolve", "review.record_impact"],
    },
    {
        "pillar_id": "promotion_gate",
        "summary": "Explicit criteria before a hypothesis influences product surfaces (no auto-promotion).",
        "python_modules": [
            "phase37.hypothesis_registry",
            "phase39.promotion_gate_phase39",
            "phase40.promotion_gate_phase40",
            "phase41.promotion_gate_phase41",
            "phase42.promotion_gate_phase42",
        ],
        "persistent_artifacts": [
            "data/research_engine/promotion_gate_v1.json",
            "data/research_engine/promotion_gate_history_v1.json",
        ],
        "work_unit_types": ["gate.checklist", "gate.block", "gate.record_decision"],
    },
    {
        "pillar_id": "residual_memory_casebook",
        "summary": "Deferred substrate tails as first-class cases with reopen conditions.",
        "python_modules": ["phase37.casebook"],
        "persistent_artifacts": ["data/research_engine/casebook_v1.json"],
        "work_unit_types": ["casebook.upsert", "casebook.reassess_trigger"],
    },
    {
        "pillar_id": "user_facing_explanation_layer",
        "summary": "Judgment-augmenting narratives tied to evidence, not buy/sell simplification.",
        "python_modules": [
            "phase37.explanation_surface",
            "phase38.explanation_phase38",
            "phase39.explanation_v2",
            "phase40.explanation_v3",
            "phase41.explanation_v4",
            "phase42.explanation_v5",
        ],
        "persistent_artifacts": [
            "docs/operator_closeout/phase37_explanation_prototype.md",
            "docs/operator_closeout/phase39_explanation_surface_v2.md",
            "docs/operator_closeout/phase40_explanation_surface_v3.md",
            "docs/operator_closeout/phase41_explanation_surface_v4.md",
            "docs/operator_closeout/phase42_explanation_surface_v5.md",
        ],
        "work_unit_types": ["explain.render_hypothesis", "explain.render_signal_case"],
    },
]


def constitution_bundle_payload() -> dict[str, Any]:
    return {
        "version": 1,
        "pillars": RESEARCH_ENGINE_ARTIFACTS,
        "non_goals": [
            "broad_substrate_repair_as_headline",
            "auto_promote_hypothesis",
            "production_scoring_rewrite_without_governance",
            "generic_ai_stock_picker_ux",
        ],
    }
