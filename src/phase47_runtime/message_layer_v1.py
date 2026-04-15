"""Message Layer v1 — first-class message objects on Today spectrum rows (MVP Sprint 2 contract, stub).

Field names align with PLAN_MODE / MVP roadmap. Optional `message` block in spectrum seed
fills gaps; otherwise we derive a minimal message from rationale + what_changed.
"""

from __future__ import annotations

from typing import Any

# Contract keys returned per row under `message` (subset of full MVP object).
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


def build_message_layer_v1_for_row(
    *,
    row: dict[str, Any],
    horizon: str,
    lang: str,
    active_model_family: str,
    rationale_summary: str,
    what_changed: str,
    confidence_band: str | None,
) -> dict[str, Any]:
    m = row.get("message") if isinstance(row.get("message"), dict) else {}
    aid = str(row.get("asset_id") or "")
    mid = str(m.get("message_id") or "").strip() or f"demo_{horizon}_{aid}".replace(" ", "_")

    headline = _pick_lang(m.get("headline"), lang) or (rationale_summary[:100] + ("…" if len(rationale_summary) > 100 else ""))
    one_line = _pick_lang(m.get("one_line_take"), lang) or rationale_summary[:220]
    why_now = _pick_lang(m.get("why_now"), lang) or (one_line[:160] if one_line else rationale_summary[:160])
    wchg = _pick_lang(m.get("what_changed"), lang) or what_changed
    unproven = _pick_lang(m.get("what_remains_unproven"), lang)
    watch = _pick_lang(m.get("what_to_watch"), lang)
    action = _pick_lang(m.get("action_frame"), lang)
    evidence = _pick_lang(m.get("linked_evidence_summary"), lang)

    cb = str(m.get("confidence_band") or confidence_band or "").strip()

    return {
        "message_id": mid,
        "asset_id": aid,
        "horizon": horizon,
        "headline": headline,
        "one_line_take": one_line,
        "why_now": why_now,
        "what_changed": wchg,
        "what_remains_unproven": unproven,
        "what_to_watch": watch,
        "action_frame": action,
        "confidence_band": cb,
        "linked_model_family": str(m.get("linked_model_family") or active_model_family or ""),
        "linked_evidence_summary": evidence,
    }
