"""Seed hypotheses for the locked Phase 14 program (deterministic templates)."""

from __future__ import annotations

from typing import Any

from research_engine.constants import DEFAULT_PHASE14_RESEARCH_QUESTION

SEED_HYPOTHESES: list[dict[str, Any]] = [
    {
        "hypothesis_title": "Liquidity and attention frictions delay price recognition",
        "economic_rationale": (
            "For issuers with lower depth and slower institutional attention, the same deterministic "
            "state-change signal may take longer to embed in prices over a quarter horizon. "
            "This is a testable claim about information diffusion speed, not trading advice."
        ),
        "mechanism_json": {
            "primary_mechanism": "Slower price discovery when marginal traders are scarce.",
            "transmission": "Order flow absorbs signal more slowly for less liquid symbols.",
        },
        "feature_definition_json": {
            "families": ["liquidity_proxy", "state_change_score", "forward_excess_next_quarter"],
        },
        "scope_limits_json": {"universe": "sp500_current"},
        "expected_effect_json": {"direction": "conditional_speed_of_recognition"},
        "failure_modes_json": {"macro_shock_confound": "Macro weeks dominate Q horizon."},
        "claims_to_explain": "delayed_market_recognition",
    },
    {
        "hypothesis_title": "Information complexity slows consensus formation",
        "economic_rationale": (
            "Complex disclosures lengthen the time for investors to map state-change components "
            "into a coherent narrative versus simpler peers with similar headline scores."
        ),
        "mechanism_json": {
            "primary_mechanism": "Higher due-diligence costs delay consensus updates.",
            "transmission": "Analyst workflows need more time to verify complex filings.",
        },
        "feature_definition_json": {
            "families": ["disclosure_complexity_proxy", "state_change_score"],
        },
        "scope_limits_json": {"universe": "sp500_current"},
        "expected_effect_json": {"direction": "slower_recognition_when_complexity_high"},
        "failure_modes_json": {"thin_coverage": "Complexity metrics sparse."},
        "claims_to_explain": "delayed_market_recognition",
    },
    {
        "hypothesis_title": "Gating and missingness artifacts masquerade as delayed recognition",
        "economic_rationale": (
            "When gating and component missingness are high, headline scores may misalign with "
            "forwards because the public measurement layer is thin, not because markets are slow."
        ),
        "mechanism_json": {
            "primary_mechanism": "Sparse components inflate tension without price counterpart.",
            "transmission": "Validation joins inherit missingness-driven noise.",
        },
        "feature_definition_json": {
            "families": ["missing_component_count", "gating_status", "state_change_score"],
        },
        "scope_limits_json": {"requires_quality_context": True},
        "expected_effect_json": {"direction": "misalignment_when_missingness_high"},
        "failure_modes_json": {"false_signal": "Scores near threshold with empty components."},
        "claims_to_explain": "unresolved_residual",
    },
]


def program_question_matches_lock(program_question: str) -> bool:
    return program_question.strip() == DEFAULT_PHASE14_RESEARCH_QUESTION.strip()
