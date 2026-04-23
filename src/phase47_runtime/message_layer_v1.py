"""Message Layer v1 — Today spectrum row message (UI) + Metis Product Spec §6.4 object (Patch Bundle B).

Legacy keys (`one_line_take`, `linked_model_family`, `linked_evidence_summary`) remain for `app.js`.
`linked_registry_entry_id`, `linked_artifact_id`, `linked_evidence` satisfy the unified product contract.

Patch 11 (Brain Bundle v3, 2026-04-23) also exposes residual-score
semantics from the spectrum row so the Product Shell view-model layer
can translate them into customer-facing ``residual_freshness`` labels
without touching the raw engineering slugs
(``residual_semantics_v1`` / ``monthly_after_new_filing_or_21_trading_days``
/ ``spectrum_position_crosses_midline`` etc.). See
``docs/plan/METIS_Residual_Score_Semantics_v1.md``.
"""

from __future__ import annotations

from typing import Any

from metis_brain.message_object_v1 import (
    MessageObjectV1,
    build_message_object_v1_for_today_row,
    format_linked_evidence_summary_v1,
)

# Keys returned per row under `message` (UI + contract).
MESSAGE_LAYER_V1_KEYS: tuple[str, ...] = (
    "message_id",
    "asset_id",
    "horizon",
    "headline",
    "one_line_take",
    "why_now",
    "what_changed",
    "what_remains_unproven",
    "what_to_watch",
    "action_frame",
    "confidence_band",
    "linked_model_family",
    "linked_evidence_summary",
    "linked_registry_entry_id",
    "linked_artifact_id",
    "linked_evidence",
    # Patch 11 — residual-score semantics (raw engineering slugs; view-models
    # translate these into customer-facing labels before exposing them).
    "residual_score_semantics_version",
    "invalidation_hint",
    "recheck_cadence",
)


def _pick_lang(obj: Any, lg: str) -> str:
    if isinstance(obj, dict):
        return str(obj.get(lg) or obj.get("en") or obj.get("ko") or "").strip()
    if obj is None:
        return ""
    return str(obj).strip()


def spectrum_band_from_position(position: float | None) -> str:
    """Ternary band for UI color: left = lower spectrum index, right = higher."""
    if position is None:
        return "center"
    try:
        p = float(position)
    except (TypeError, ValueError):
        return "center"
    if p < 0.34:
        return "left"
    if p > 0.66:
        return "right"
    return "center"


def spectrum_quintile_from_position(position: float | None) -> str:
    """Product Spec §5.1 — five-way valuation band (0–1 spectrum index, higher = more stretched)."""
    if position is None:
        return "neutral"
    try:
        p = float(position)
    except (TypeError, ValueError):
        return "neutral"
    p = max(0.0, min(1.0, p))
    if p < 0.15:
        return "extreme_underpriced"
    if p < 0.35:
        return "underpriced"
    if p <= 0.65:
        return "neutral"
    if p < 0.85:
        return "overpriced"
    return "extreme_overpriced"


def build_message_layer_v1_for_row(
    *,
    row: dict[str, Any],
    horizon: str,
    lang: str,
    active_model_family: str,
    rationale_summary: str,
    what_changed: str,
    confidence_band: str | None,
    linked_registry_entry_id: str,
    linked_artifact_id: str,
) -> dict[str, Any]:
    obj: MessageObjectV1 = build_message_object_v1_for_today_row(
        row=row,
        horizon=horizon,
        lang=lang,
        rationale_summary=rationale_summary,
        what_changed_plain=what_changed,
        confidence_band=confidence_band,
        linked_registry_entry_id=linked_registry_entry_id,
        linked_artifact_id=linked_artifact_id,
    )
    m = row.get("message") if isinstance(row.get("message"), dict) else {}
    aid = str(row.get("asset_id") or "")
    mid = str(m.get("message_id") or "").strip() or f"demo_{horizon}_{aid}".replace(" ", "_")

    one_line = _pick_lang(m.get("one_line_take"), lang) or obj.headline[:220]
    evidence_summary = format_linked_evidence_summary_v1(obj.linked_evidence)

    # Patch 11 — residual semantics passthrough. The MessageObjectV1 layer
    # already picks these up from either the row or row["message"], but the
    # dict return previously dropped them so the Product Shell view-models
    # could never see them. We re-expose the raw slugs here; all customer-
    # facing DTOs translate them via residual_freshness_block() and never
    # surface the raw value.
    residual_version = str(
        getattr(obj, "residual_score_semantics_version", "")
        or row.get("residual_score_semantics_version")
        or (m.get("residual_score_semantics_version") if isinstance(m, dict) else "")
        or ""
    )
    invalidation_hint = str(
        getattr(obj, "invalidation_hint", "")
        or row.get("invalidation_hint")
        or (m.get("invalidation_hint") if isinstance(m, dict) else "")
        or ""
    )
    recheck_cadence = str(
        getattr(obj, "recheck_cadence", "")
        or row.get("recheck_cadence")
        or (m.get("recheck_cadence") if isinstance(m, dict) else "")
        or ""
    )

    return {
        "message_id": mid,
        "asset_id": aid,
        "horizon": horizon,
        "headline": obj.headline,
        "one_line_take": one_line,
        "why_now": obj.why_now,
        "what_changed": obj.what_changed,
        "what_remains_unproven": obj.what_remains_unproven,
        "what_to_watch": obj.what_to_watch,
        "action_frame": obj.action_frame,
        "confidence_band": obj.confidence_band,
        "linked_model_family": str(m.get("linked_model_family") or active_model_family or ""),
        "linked_evidence_summary": evidence_summary,
        "linked_registry_entry_id": obj.linked_registry_entry_id,
        "linked_artifact_id": obj.linked_artifact_id,
        "linked_evidence": [x.model_dump() for x in obj.linked_evidence],
        "residual_score_semantics_version": residual_version,
        "invalidation_hint": invalidation_hint,
        "recheck_cadence": recheck_cadence,
    }
