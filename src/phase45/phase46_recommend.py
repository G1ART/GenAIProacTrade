"""Phase 46 fork: default hold closeout; optional surface when new source registration exists."""

from __future__ import annotations

from typing import Any


def recommend_phase46(
    *,
    operator_registered_new_named_source: bool = False,
) -> dict[str, Any]:
    if operator_registered_new_named_source:
        return {
            "phase46_recommendation": "register_new_source_then_authorize_one_bounded_reopen_v1",
            "rationale": (
                "Operator registered a concrete named filing and/or sector path distinct from "
                "Phase 43; authorize at most one bounded cohort retest under documented cap — "
                "still no broad substrate work."
            ),
        }
    return {
        "phase46_recommendation": "hold_closeout_until_named_new_source_or_new_evidence_v1",
        "rationale": (
            "Default stance after Phase 45 canonical closeout: remain closed until a new named "
            "source/path or other dispositive new evidence is recorded; do not infer reopening "
            "from legacy optimistic bundle strings."
        ),
    }
