"""Message Object v1 — Product Spec §6.4 (Patch Bundle B: schema + generation + rationale + evidence)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Seed / legacy path: explicit non-registry linkage (Today still contract-shaped).
SEED_UNLINKED_REGISTRY_ID = "seed:unlinked_registry_v0"
SEED_UNLINKED_ARTIFACT_ID = "seed:unlinked_artifact_v0"


class LinkedEvidenceItemV1(BaseModel):
    """Structured evidence pointer (not free memo)."""

    pointer: str = Field(min_length=1, description="Stable reference, e.g. validation bundle id or pit pointer")
    summary: str = ""
    kind: str = Field(default="support", description="support | risk | validation")


class MessageObjectV1(BaseModel):
    """Product Spec §6.4 — all required fields as resolved single-language strings.

    Pragmatic Brain Absorption v1 — Milestone B adds optional residual-score-
    semantics fields (see docs/plan/METIS_Residual_Score_Semantics_v1.md). They
    default to empty strings so survey Q1–Q10 remain green and persisted
    snapshots stay backwards compatible.
    """

    headline: str = Field(min_length=1)
    why_now: str
    what_changed: str
    what_remains_unproven: str
    what_to_watch: str
    action_frame: str
    confidence_band: str
    linked_evidence: list[LinkedEvidenceItemV1]
    linked_registry_entry_id: str = Field(min_length=1)
    linked_artifact_id: str = Field(min_length=1)
    residual_score_semantics_version: str = ""
    invalidation_hint: str = ""
    recheck_cadence: str = ""


def rationale_summary_contract_v1(*, text: str, max_chars: int = 520) -> str:
    """Deterministic rationale string for cards/detail (non-empty when input has content)."""
    s = " ".join(str(text or "").split()).strip()
    if not s:
        return ""
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def _pick_lang(obj: Any, lg: str) -> str:
    if isinstance(obj, dict):
        return str(obj.get(lg) or obj.get("en") or obj.get("ko") or "").strip()
    if obj is None:
        return ""
    return str(obj).strip()


def _linked_evidence_from_row(
    *,
    row: dict[str, Any],
    horizon: str,
    lang: str,
    rationale_summary: str,
) -> list[LinkedEvidenceItemV1]:
    m = row.get("message") if isinstance(row.get("message"), dict) else {}
    raw = m.get("linked_evidence")
    out: list[LinkedEvidenceItemV1] = []
    if isinstance(raw, list):
        for it in raw:
            if not isinstance(it, dict):
                continue
            ptr = str(it.get("pointer") or "").strip()
            if not ptr:
                continue
            out.append(
                LinkedEvidenceItemV1(
                    pointer=ptr,
                    summary=str(it.get("summary") or "").strip(),
                    kind=str(it.get("kind") or "support").strip() or "support",
                )
            )
    if out:
        return out
    ev_text = _pick_lang(m.get("linked_evidence_summary"), lang)
    aid = str(row.get("asset_id") or "").strip() or "unknown"
    summary = ev_text or rationale_summary_contract_v1(text=rationale_summary, max_chars=240)
    if not summary:
        summary = f"spectrum_row:{aid}:{horizon}"
    return [
        LinkedEvidenceItemV1(
            pointer=f"spectrum_row:{aid}:{horizon}:v1",
            summary=summary,
            kind="validation",
        )
    ]


def format_linked_evidence_summary_v1(items: list[LinkedEvidenceItemV1], *, max_chars: int = 400) -> str:
    """Single-line / short block for legacy UI (`linked_evidence_summary`)."""
    parts: list[str] = []
    for it in items:
        chunk = it.summary.strip() or it.pointer
        if chunk:
            parts.append(chunk)
    s = " · ".join(parts).strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def build_message_object_v1_for_today_row(
    *,
    row: dict[str, Any],
    horizon: str,
    lang: str,
    rationale_summary: str,
    what_changed_plain: str,
    confidence_band: str | None,
    linked_registry_entry_id: str,
    linked_artifact_id: str,
) -> MessageObjectV1:
    """Build §6.4 object from spectrum row (+ optional nested `message` overrides)."""
    m = row.get("message") if isinstance(row.get("message"), dict) else {}
    rs = rationale_summary_contract_v1(text=rationale_summary)

    headline = _pick_lang(m.get("headline"), lang) or (rs[:100] + ("…" if len(rs) > 100 else "") if rs else "—")
    why_now = _pick_lang(m.get("why_now"), lang) or (rs[:200] if rs else headline[:160])
    wchg = _pick_lang(m.get("what_changed"), lang) or what_changed_plain
    unproven = _pick_lang(m.get("what_remains_unproven"), lang)
    watch = _pick_lang(m.get("what_to_watch"), lang)
    action = _pick_lang(m.get("action_frame"), lang)
    cb = str(m.get("confidence_band") or confidence_band or "").strip()

    ev = _linked_evidence_from_row(row=row, horizon=horizon, lang=lang, rationale_summary=rationale_summary)

    residual_version = str(
        m.get("residual_score_semantics_version")
        or row.get("residual_score_semantics_version")
        or ""
    ).strip()
    invalidation_hint = str(
        m.get("invalidation_hint") or row.get("invalidation_hint") or ""
    ).strip()
    recheck_cadence = str(
        m.get("recheck_cadence") or row.get("recheck_cadence") or ""
    ).strip()

    return MessageObjectV1(
        headline=headline or "—",
        why_now=why_now,
        what_changed=wchg,
        what_remains_unproven=unproven,
        what_to_watch=watch,
        action_frame=action,
        confidence_band=cb,
        linked_evidence=ev,
        linked_registry_entry_id=linked_registry_entry_id,
        linked_artifact_id=linked_artifact_id,
        residual_score_semantics_version=residual_version,
        invalidation_hint=invalidation_hint,
        recheck_cadence=recheck_cadence,
    )
