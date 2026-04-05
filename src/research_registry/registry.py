"""Insert / idempotent sample rows for governance demos (Phase 9)."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from research_registry.promotion_rules import describe_production_boundary


def ensure_sample_hypotheses(client: Any) -> dict[str, Any]:
    """Two fixed titles: sandbox review + blocked/rejected; idempotent by title."""
    out: dict[str, Any] = {"created": [], "skipped": []}

    def one(
        *,
        title: str,
        status: str,
        source_scope: str,
        intended_use: str,
        leakage: str,
        promotion: str,
        rejection: str | None,
        event_type: str,
        decision_summary: str,
        rationale: str,
    ) -> None:
        if dbrec.hypothesis_exists_by_title(client, title=title):
            out["skipped"].append(title)
            return
        hid = dbrec.insert_research_hypothesis(
            client,
            title=title,
            research_item_status=status,
            source_scope=source_scope,
            intended_use=intended_use,
            leakage_review_status=leakage,
            promotion_decision=promotion,
            rejection_reason=rejection,
            linked_artifacts=[{"kind": "note", "ref": "phase9_sample"}],
        )
        eid = dbrec.insert_promotion_gate_event(
            client,
            hypothesis_id=hid,
            event_type=event_type,
            decision_summary=decision_summary,
            rationale=rationale,
            actor="phase9_seed",
        )
        out["created"].append(
            {"hypothesis_id": hid, "promotion_gate_event_id": eid, "title": title}
        )

    one(
        title="[Phase9 sample] Alt momentum window (sandbox review)",
        status="sandbox_only",
        source_scope="internal_experiment / non-production",
        intended_use="offline factor shape exploration only",
        leakage="not_reviewed",
        promotion="none",
        rejection=None,
        event_type="status_set",
        decision_summary="Remain sandbox until leakage review completes",
        rationale="No panel data path wired; operator holds in sandbox_only.",
    )
    one(
        title="[Phase9 sample] Social sentiment overlay (blocked)",
        status="rejected",
        source_scope="external_unverified_feed_hypothetical",
        intended_use="was proposed as message overlay; not in truth spine",
        leakage="blocked_pending_review",
        promotion="denied",
        rejection="Unverified third-party feed; leakage and staleness risk unacceptable.",
        event_type="rejection",
        decision_summary="Not approved for experiment",
        rationale="blocked_leakage_risk; stays out of production candidate logic.",
    )
    return out


def build_registry_report_payload(client: Any, *, limit: int = 200) -> dict[str, Any]:
    hypos = dbrec.fetch_research_hypotheses(client, limit=limit)
    events = dbrec.fetch_promotion_gate_events_recent(client, limit=min(limit, 100))
    return {
        "hypothesis_count": len(hypos),
        "hypotheses": hypos,
        "recent_promotion_gate_events": events,
        "boundary": describe_production_boundary(),
    }
