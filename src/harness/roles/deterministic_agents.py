"""Thesis / Challenge / Synthesis — deterministic skeleton (no LLM numerics)."""

from __future__ import annotations

from typing import Any


def signal_summary_block(inp: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_class": inp.get("candidate_class"),
        "candidate_rank": inp.get("candidate_rank"),
        "state_change_score": inp.get("state_change_score"),
        "state_change_direction": inp.get("state_change_direction"),
        "confidence_band": inp.get("confidence_band"),
        "dominant_change_type": inp.get("dominant_change_type"),
        "top_driver_signals_json": inp.get("top_driver_signals_json"),
        "component_breakdown_preview": (inp.get("component_breakdown") or [])[:8],
    }


def run_thesis_agent(inp: dict[str, Any]) -> dict[str, Any]:
    """Strongest supportable reading of the deterministic signal (no new numbers)."""
    score = inp.get("state_change_score")
    direction = inp.get("state_change_direction") or "unknown"
    cc = inp.get("candidate_class") or "unknown"
    text = (
        f"Deterministic state-change layer classifies this issuer-date as `{cc}` with "
        f"direction `{direction}`"
        + (f" and score `{score}`." if score is not None else " (score row missing).")
    )
    text += (
        " A constructive reading: the recorded component pattern is consistent with "
        "an internal narrative of shifting fundamentals or reporting context as encoded "
        "in Phase 6 signals — subject to data gaps below."
    )
    return {
        "text": text,
        "uncertainty_label": "plausible_hypothesis",
        "anchors": signal_summary_block(inp),
    }


def run_challenge_agent(inp: dict[str, Any]) -> dict[str, Any]:
    """Mandatory counter-case — must not be optional."""
    miss = inp.get("missing_data_indicators") or []
    cov = inp.get("coverage_flags") or []
    val = inp.get("validation_panel_join") or {}
    return {
        "alternate_interpretation": (
            "The same numeric pattern could reflect stale filings, partial component "
            "coverage, or regime mismatch rather than an economically meaningful shift. "
            "Correlation in research summaries does not imply issuer-level predictive "
            "validity."
        ),
        "data_insufficiency_risk": (
            "Missing or thin inputs: "
            + (", ".join(str(x) for x in miss) if miss else "none flagged")
            + ". Coverage notes: "
            + (", ".join(str(x) for x in cov[:6]) if cov else "none")
        ),
        "contamination_regime_risk": (
            "Component-level contamination/regime scores may be null or weak; "
            "interpretation should not assume clean regime alignment."
        ),
        "why_change_may_not_matter": (
            "Market prices and forward outcomes are not evaluated here; the signal is "
            "a documentation-time state snapshot, not proof of subsequent performance."
        ),
        "what_would_falsify_thesis": (
            "Future restatements, revised filings, or reconciled fundamentals that remove "
            "the driver signals; or demonstration that drivers were data artifacts."
        ),
        "validation_context_note": val,
        "uncertainty_label": "plausible_hypothesis",
    }


def run_synthesis_agent(
    inp: dict[str, Any], thesis: dict[str, Any], challenge: dict[str, Any]
) -> dict[str, Any]:
    """Preserves both thesis and challenge; does not collapse to single verdict."""
    return {
        "text": (
            "Thesis highlights what the deterministic spine asserts for this issuer-date. "
            "Challenge lists interpretive and data risks that can overturn a naive reading. "
            "Both remain simultaneously tenable; the operator must judge under uncertainty."
        ),
        "thesis_preserved": True,
        "challenge_preserved": True,
        "explicit_disagreement_note": (
            "No forced consensus: thesis (" + (thesis.get("uncertainty_label") or "") + ") "
            "and challenge (" + (challenge.get("uncertainty_label") or "") + ") coexist."
        ),
        "uncertainty_label": "unverifiable",
    }
