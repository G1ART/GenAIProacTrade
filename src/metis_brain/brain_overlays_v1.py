"""Pragmatic Brain Absorption v1 — Milestone C.

`brain_overlays_v1` is the first bounded, governed non-quant adjustment layer.

It is NOT a free-form AI narrative (work-order §6). Every overlay is a
structured artifact-like packet tied to an existing brain artifact or active
registry entry. The bundle loader treats overlays as optional (legacy bundles
without overlays stay valid); runtime surfaces (Today, cockpit health) cash
out the overlay's influence so founders and auditors can trace it.

Storage for v1:
  * Bundle-adjunct seed JSON (``data/mvp/brain_overlays_seed_v1.json``).
  * Bundle builder optionally merges overlays into the bundle as a top-level
    ``brain_overlays`` list without touching the Today contract surface.
  * No database migration in v1; a DB move is a later stage if operators need
    multi-tenant ingestion.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

OVERLAY_TYPES = (
    "regime_shift",
    "hazard_modifier",
    "invalidation_warning",
    "confidence_adjustment",
    "catalyst_window",
)

OverlayType = Literal[
    "regime_shift",
    "hazard_modifier",
    "invalidation_warning",
    "confidence_adjustment",
    "catalyst_window",
]

EXPECTED_DIRECTION_HINTS = (
    "",
    "position_weakens",
    "position_strengthens",
    "regime_changes",
    "risk_asymmetry_widens",
    "event_binary_pending",
)

ExpectedDirectionHint = Literal[
    "",
    "position_weakens",
    "position_strengthens",
    "regime_changes",
    "risk_asymmetry_widens",
    "event_binary_pending",
]

# Bounded Non-Quant Cash-Out v1 — Replay directional aging rule.
# Hard-coded so callers (Replay micro-brief) cannot drift the semantics.
_DIRECTIONAL_AGING_MIN_DELTA = 0.05

AgingLabel = Literal["aged_in_line", "aged_against", "neutral"]


class BrainOverlaySourceArtifactRefV1(BaseModel):
    """Structured pointer to the evidence that produced the overlay."""

    kind: str = Field(
        description="Source kind, e.g. 'earnings_transcript', 'policy_memo', 'validation_run'",
    )
    pointer: str = Field(min_length=1)
    summary: str = ""

    @field_validator("kind")
    @classmethod
    def _non_empty_kind(cls, v: str) -> str:
        v = str(v or "").strip()
        if not v:
            raise ValueError("kind required")
        return v


class BrainOverlayV1(BaseModel):
    """A single bounded non-quant adjustment attached to an artifact or registry entry.

    Exactly one of ``artifact_id`` or ``registry_entry_id`` must be present;
    the overlay always points at something existing in the bundle so it never
    becomes free-floating narrative.
    """

    overlay_id: str = Field(min_length=1)
    overlay_type: OverlayType
    artifact_id: str = ""
    registry_entry_id: str = ""
    source_artifact_refs: list[BrainOverlaySourceArtifactRefV1] = Field(default_factory=list)
    pit_timestamp_window: dict[str, str] = Field(default_factory=dict)
    awareness_lag_rule: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    counter_interpretation_present: bool = False
    reasons: list[str] = Field(default_factory=list)
    provenance_summary: str = ""
    expiry_or_recheck_rule: str = ""
    # Bounded Non-Quant Cash-Out v1 additions. All optional so legacy seed
    # files stay valid; Replay / Research surfaces treat missing values as
    # neutral / empty.
    expected_direction_hint: ExpectedDirectionHint = ""
    what_it_changes: str = Field(default="", max_length=240)
    source_artifact_refs_summary: str = Field(default="", max_length=240)

    @field_validator("overlay_type")
    @classmethod
    def _overlay_type_in_vocab(cls, v: str) -> str:
        if v not in OVERLAY_TYPES:
            raise ValueError(f"overlay_type must be one of {OVERLAY_TYPES}")
        return v

    @field_validator("expected_direction_hint")
    @classmethod
    def _direction_hint_in_vocab(cls, v: str) -> str:
        if v not in EXPECTED_DIRECTION_HINTS:
            raise ValueError(
                f"expected_direction_hint must be one of {EXPECTED_DIRECTION_HINTS}"
            )
        return v

    def bound_reference(self) -> tuple[str, str]:
        """Return (``target_kind``, ``target_id``) after exclusive-or check."""
        a = self.artifact_id.strip()
        r = self.registry_entry_id.strip()
        if (not a) and (not r):
            raise ValueError("overlay must target either artifact_id or registry_entry_id")
        if a and r:
            raise ValueError("overlay cannot target both artifact_id and registry_entry_id")
        if a:
            return ("artifact_id", a)
        return ("registry_entry_id", r)


class BrainOverlaySeedFileV1(BaseModel):
    """Seed-file schema: a list of BrainOverlayV1 plus metadata."""

    schema_version: int = 1
    contract: str = "METIS_BRAIN_OVERLAYS_SEED_V1"
    description: str = ""
    overlays: list[BrainOverlayV1] = Field(default_factory=list)


def brain_overlays_seed_path(repo_root: Path) -> Path:
    override = (os.environ.get("METIS_BRAIN_OVERLAYS_SEED") or "").strip()
    if override:
        return Path(override)
    return repo_root / "data" / "mvp" / "brain_overlays_seed_v1.json"


def load_brain_overlays_seed(repo_root: Path) -> tuple[list[BrainOverlayV1], list[str]]:
    """Return (overlays, errors). Missing file is not an error — returns ([], [])."""
    p = brain_overlays_seed_path(repo_root)
    if not p.is_file():
        return [], []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        return [], [f"overlays_read_error:{e}"]
    except json.JSONDecodeError as e:
        return [], [f"overlays_json_invalid:{e}"]
    try:
        seed = BrainOverlaySeedFileV1.model_validate(raw)
    except ValidationError as e:
        return [], [f"overlays_schema:{e}"]
    # Validate exclusive-or binding up front so bad seeds never reach runtime.
    errors: list[str] = []
    for ov in seed.overlays:
        try:
            ov.bound_reference()
        except ValueError as e:
            errors.append(f"overlays_binding:{ov.overlay_id}:{e}")
    if errors:
        return [], errors
    return list(seed.overlays), []


def validate_overlays_against_bundle(
    overlays: list[BrainOverlayV1],
    *,
    artifact_ids: set[str],
    registry_entry_ids: set[str],
) -> list[str]:
    """Ensure each overlay references an existing bundle entity."""
    errors: list[str] = []
    for ov in overlays:
        kind, target = ov.bound_reference()
        if kind == "artifact_id" and target not in artifact_ids:
            errors.append(
                f"overlay {ov.overlay_id!r}: artifact_id {target!r} not present in bundle"
            )
        if kind == "registry_entry_id" and target not in registry_entry_ids:
            errors.append(
                f"overlay {ov.overlay_id!r}: registry_entry_id {target!r} not present in bundle"
            )
    return errors


def summarize_overlays_for_runtime(
    overlays: list[dict[str, Any]] | list[BrainOverlayV1],
) -> dict[str, Any]:
    """Compact summary used by cockpit health + Today cash-out surfaces."""
    items: list[dict[str, Any]] = []
    by_type: dict[str, int] = {}
    for ov in overlays or []:
        d = ov.model_dump() if isinstance(ov, BrainOverlayV1) else dict(ov)
        otype = str(d.get("overlay_type") or "")
        by_type[otype] = by_type.get(otype, 0) + 1
        items.append(
            {
                "overlay_id": str(d.get("overlay_id") or ""),
                "overlay_type": otype,
                "artifact_id": str(d.get("artifact_id") or ""),
                "registry_entry_id": str(d.get("registry_entry_id") or ""),
                "confidence": d.get("confidence"),
                "counter_interpretation_present": bool(d.get("counter_interpretation_present")),
                "expiry_or_recheck_rule": str(d.get("expiry_or_recheck_rule") or ""),
                "expected_direction_hint": str(d.get("expected_direction_hint") or ""),
                "what_it_changes": str(d.get("what_it_changes") or ""),
            }
        )
    return {
        "contract": "METIS_BRAIN_OVERLAYS_SUMMARY_V1",
        "total": len(items),
        "count_by_type": by_type,
        "items": items,
    }


def overlay_influence_lookup(
    overlays: list[dict[str, Any]] | list[BrainOverlayV1],
) -> dict[str, list[str]]:
    """Map bundle target id → list of overlay_ids that influence it.

    Covers both artifact_id and registry_entry_id bindings. Used by runtime
    surfaces (spectrum rows, replay lineage) to flag overlay impact without
    scanning the entire overlay list per row.
    """
    out: dict[str, list[str]] = {}
    for ov in overlays or []:
        d = ov.model_dump() if isinstance(ov, BrainOverlayV1) else dict(ov)
        oid = str(d.get("overlay_id") or "")
        if not oid:
            continue
        a = str(d.get("artifact_id") or "")
        r = str(d.get("registry_entry_id") or "")
        if a:
            out.setdefault(a, []).append(oid)
        if r:
            out.setdefault(r, []).append(oid)
    return out


def overlay_decision_aging_v1(
    overlay: dict[str, Any] | BrainOverlayV1,
    snapshot_position: float | None,
    current_position: float | None,
) -> AgingLabel:
    """Pure, deterministic aging label for one overlay vs. one asset's
    spectrum_position history.

    Bounded on purpose: no price, no return, no recommendation. Only the
    spectrum_position delta (a normalized -1..+1 band value) against the
    overlay's declared ``expected_direction_hint``.

    Returns one of ``aged_in_line`` / ``aged_against`` / ``neutral``.
    Missing snapshot or missing current position always yields ``neutral``.
    Unbounded / unsupported hints (``regime_changes``,
    ``event_binary_pending``, ``risk_asymmetry_widens``, empty) also yield
    ``neutral`` — spectrum_position cannot prove those claims alone in this
    MVP, so we refuse to guess.
    """

    d = overlay.model_dump() if isinstance(overlay, BrainOverlayV1) else dict(overlay or {})
    hint = str(d.get("expected_direction_hint") or "")
    if snapshot_position is None or current_position is None:
        return "neutral"
    try:
        snap = float(snapshot_position)
        cur = float(current_position)
    except (TypeError, ValueError):
        return "neutral"
    delta = cur - snap
    if hint == "position_weakens":
        if delta <= -_DIRECTIONAL_AGING_MIN_DELTA:
            return "aged_in_line"
        if delta >= _DIRECTIONAL_AGING_MIN_DELTA:
            return "aged_against"
        return "neutral"
    if hint == "position_strengthens":
        if delta >= _DIRECTIONAL_AGING_MIN_DELTA:
            return "aged_in_line"
        if delta <= -_DIRECTIONAL_AGING_MIN_DELTA:
            return "aged_against"
        return "neutral"
    return "neutral"
