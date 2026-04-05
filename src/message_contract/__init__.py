"""Phase 8: shared message / overlay stubs (no vague free prose-only contract)."""

from __future__ import annotations

OVERLAY_FUTURE_SEAMS_DEFAULT: dict[str, str] = {
    "news": "not_available_yet",
    "ownership": "not_available_yet",
    "positioning": "not_available_yet",
    "macro_regime_overlay": "not_available_yet",
}

# Phase 9: message-layer truthfulness (docs + downstream checks; no execution language).
MESSAGE_LAYER_TRUTH_GUARDS: dict[str, str] = {
    "portfolio_execution": "forbidden_in_message_contract_outputs",
    "performance_claims": "unsupported_unless_evidence_linked",
    "casebook_scanner_missingness": "must_remain_visible_in_summaries_or_stats_json",
    "heuristic_outputs": "mark_is_heuristic_or_message_layer_heuristic_true",
}

__all__ = [
    "MESSAGE_LAYER_TRUTH_GUARDS",
    "OVERLAY_FUTURE_SEAMS_DEFAULT",
]
