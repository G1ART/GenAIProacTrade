"""Map heuristic outlier rows to Phase 13 residual triage buckets (non-causal, review-oriented)."""

from __future__ import annotations

from typing import Any

# Triage taxonomy — not causal claims; for operator routing and future premium ROI hooks.
RESIDUAL_TRIAGE_BUCKETS: tuple[str, ...] = (
    "data_missingness_dominated",
    "regime_mismatch",
    "delayed_market_recognition",
    "likely_exogenous_event",
    "contradictory_public_signal",
    "unresolved_residual",
)

OVERLAY_HINT_BY_BUCKET: dict[str, str] = {
    "data_missingness_dominated": (
        "Optional premium: earnings call transcript or estimate context may clarify sparse factor coverage "
        "(does not change deterministic scores)."
    ),
    "regime_mismatch": (
        "Optional premium: macro/regime overlay may contextualize component vs headline tension "
        "(does not change deterministic scores)."
    ),
    "delayed_market_recognition": (
        "Optional premium: longer forward window or price-quality overlay may test delayed recognition "
        "(does not change deterministic scores)."
    ),
    "likely_exogenous_event": (
        "Optional premium: news / ownership / positioning seams may explain gaps public core cannot see "
        "(does not change deterministic scores)."
    ),
    "contradictory_public_signal": (
        "Optional premium: additional filings or estimate reconciliation may reduce memo vs signal tension "
        "(does not change deterministic scores)."
    ),
    "unresolved_residual": (
        "Optional premium: transcript or estimate detail may resolve classification vs score tension "
        "(does not change deterministic scores)."
    ),
}


def assign_residual_triage_fields(entry: dict[str, Any]) -> None:
    """Mutates entry with residual_triage_bucket and premium_overlay_suggestion."""
    ot = str(entry.get("outlier_type") or "")
    st = entry.get("source_trace") if isinstance(entry.get("source_trace"), dict) else {}
    if ot == "reaction_gap":
        bucket = (
            "likely_exogenous_event"
            if not st.get("validation_panel_id")
            else "delayed_market_recognition"
        )
    elif ot == "persistence_failure":
        bucket = "regime_mismatch"
    elif ot == "contamination_override":
        bucket = "data_missingness_dominated"
    elif ot == "regime_mismatch":
        bucket = "regime_mismatch"
    elif ot == "thesis_challenge_divergence":
        bucket = "contradictory_public_signal"
    elif ot == "unexplained_residual":
        bucket = "unresolved_residual"
    else:
        bucket = "unresolved_residual"
    entry["residual_triage_bucket"] = bucket
    entry["premium_overlay_suggestion"] = OVERLAY_HINT_BY_BUCKET.get(
        bucket, OVERLAY_HINT_BY_BUCKET["unresolved_residual"]
    )
