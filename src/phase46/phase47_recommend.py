"""Phase 47 fork after founder cockpit surface."""

from __future__ import annotations

from typing import Any


def recommend_phase47() -> dict[str, Any]:
    return {
        "phase47_recommendation": "wire_alert_and_decision_ledgers_to_ui_and_notification_hooks_v1",
        "rationale": (
            "Consume the Phase 46 UI surface contract in a thin web or ops dashboard: alert feed, "
            "decision trace, drill-down panels, and optional notifications — still governed by bundles, "
            "no new substrate work."
        ),
    }
