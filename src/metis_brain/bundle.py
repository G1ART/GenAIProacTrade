"""Load and validate `metis_brain_bundle_v0.json` (artifact + gate + registry + spectrum rows)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from metis_brain.schemas_v0 import (
    ActiveHorizonRegistryEntryV0,
    ModelArtifactPacketV0,
    PromotionGateRecordV0,
)


def brain_bundle_path(repo_root: Path) -> Path:
    override = (os.environ.get("METIS_BRAIN_BUNDLE") or "").strip()
    if override:
        return Path(override)
    return repo_root / "data" / "mvp" / "metis_brain_bundle_v0.json"


class BrainBundleV0(BaseModel):
    """Root document: artifacts, gates, registry entries, spectrum rows keyed by horizon."""

    schema_version: int = 1
    as_of_utc: str = ""
    price_layer_note: str = ""
    artifacts: list[ModelArtifactPacketV0]
    promotion_gates: list[PromotionGateRecordV0]
    registry_entries: list[ActiveHorizonRegistryEntryV0]
    spectrum_rows_by_horizon: dict[str, list[dict[str, Any]]]
    # Optional per-horizon provenance block. Emitted by the DB-derived bundle
    # builder so Today/Research/Replay can distinguish real-derived artifacts
    # from template fallbacks without silent carryover. Legacy bundles omit
    # this field (empty dict = no claim).
    horizon_provenance: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # Pragmatic Brain Absorption v1 — Milestone C. Optional bounded non-quant
    # adjustments; each item is a ``BrainOverlayV1`` packet bound to either an
    # artifact_id or registry_entry_id in this bundle. Legacy bundles omit
    # this field entirely (empty list = no overlays).
    brain_overlays: list[dict[str, Any]] = Field(default_factory=list)
    # AGH v1 Patch 3 (Artifact Promotion Bridge Closure). Bounded FIFO trail
    # (<=20) of recent governed operator-approved apply events. Written
    # atomically by ``registry_patch_executor`` and consumed by Today to
    # surface horizon-scoped "governed apply" badges without adding a new
    # worker/queue. The list element shape is intentionally loose so that
    # future target vocab extensions remain backward compatible; the element
    # keys emitted today are:
    #   ``target``, ``horizon``, ``registry_entry_id``, ``proposal_packet_id``,
    #   ``decision_packet_id``, ``applied_packet_id``,
    #   ``from_active_artifact_id`` (optional), ``to_active_artifact_id``
    #   (optional), ``applied_at_utc``, ``spectrum_refresh_needs_db_rebuild``
    #   (bool, optional).
    recent_governed_applies: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_spectrum_horizon_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("spectrum_rows_by_horizon")
        if isinstance(raw, dict):
            norm: dict[str, list[dict[str, Any]]] = {}
            allowed = frozenset({"short", "medium", "medium_long", "long"})
            for k, v in raw.items():
                nk = str(k).strip().lower().replace("-", "_")
                if nk not in allowed:
                    raise ValueError(f"invalid horizon key in spectrum_rows_by_horizon: {k!r}")
                if not isinstance(v, list):
                    raise ValueError(f"spectrum_rows_by_horizon[{k!r}] must be a list")
                norm[nk] = v
            data["spectrum_rows_by_horizon"] = norm
        return data

    @model_validator(mode="after")
    def _artifact_ids_unique(self) -> BrainBundleV0:
        ids = [a.artifact_id for a in self.artifacts]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate artifact_id in artifacts")
        return self


def load_brain_bundle_v0(repo_root: Path) -> BrainBundleV0 | None:
    b, _errs = try_load_brain_bundle_v0(repo_root)
    return b


def try_load_brain_bundle_v0(repo_root: Path) -> tuple[BrainBundleV0 | None, list[str]]:
    """Parse bundle JSON. On structural parse failure or integrity failure, returns (None, errors)."""
    p = brain_bundle_path(repo_root)
    if not p.is_file():
        return None, []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        return None, [f"bundle_read_error:{e}"]
    except json.JSONDecodeError as e:
        return None, [f"bundle_json_invalid:{e}"]
    try:
        bundle = BrainBundleV0.model_validate(raw)
    except ValidationError as e:
        return None, [f"bundle_schema:{e}"]
    errs = validate_active_registry_integrity(bundle)
    if errs:
        return None, errs
    return bundle, []


def validate_active_registry_integrity(bundle: BrainBundleV0) -> list[str]:
    """Return human-readable errors; empty list means Today may consume this bundle."""
    errors: list[str] = []
    by_art = {a.artifact_id: a for a in bundle.artifacts}
    gates_by_artifact: dict[str, list[PromotionGateRecordV0]] = {}
    for g in bundle.promotion_gates:
        gates_by_artifact.setdefault(g.artifact_id, []).append(g)

    for ent in bundle.registry_entries:
        if ent.status != "active":
            continue
        if ent.active_artifact_id not in by_art:
            errors.append(
                f"registry {ent.registry_entry_id!r}: active_artifact_id {ent.active_artifact_id!r} not in artifacts"
            )
            continue
        art = by_art[ent.active_artifact_id]
        if art.horizon != ent.horizon:
            errors.append(
                f"registry {ent.registry_entry_id!r}: horizon {ent.horizon!r} != artifact.horizon {art.horizon!r}"
            )
        gs = gates_by_artifact.get(ent.active_artifact_id) or []
        if not gs:
            errors.append(f"registry {ent.registry_entry_id!r}: no promotion_gate for artifact {ent.active_artifact_id!r}")
            continue
        ok = any(
            g.pit_pass and g.coverage_pass and g.monotonicity_pass and str(g.approved_by_rule or "").strip()
            for g in gs
        )
        if not ok:
            errors.append(
                f"registry {ent.registry_entry_id!r}: no passing promotion gate for artifact {ent.active_artifact_id!r}"
            )
        for cid in ent.challenger_artifact_ids:
            if cid not in by_art:
                errors.append(
                    f"registry {ent.registry_entry_id!r}: challenger_artifact_id {cid!r} not in artifacts"
                )
        rows = bundle.spectrum_rows_by_horizon.get(ent.horizon)
        if not rows:
            errors.append(f"registry {ent.registry_entry_id!r}: no spectrum_rows for horizon {ent.horizon!r}")
        for i, r in enumerate(rows):
            if not isinstance(r, dict):
                errors.append(f"spectrum row {ent.horizon!r}[{i}] is not an object")
                continue
            if str(r.get("asset_id") or "").strip() == "":
                errors.append(f"spectrum row {ent.horizon!r}[{i}] missing asset_id")
            if r.get("spectrum_position") is None:
                errors.append(f"spectrum row {ent.horizon!r}[{i}] missing spectrum_position")

    # one active registry per horizon (v0 contract)
    active_by_h: dict[str, list[str]] = {}
    for ent in bundle.registry_entries:
        if ent.status == "active":
            active_by_h.setdefault(ent.horizon, []).append(ent.registry_entry_id)
    for hz, ids in active_by_h.items():
        if len(ids) > 1:
            errors.append(f"multiple active registry entries for horizon {hz!r}: {ids}")

    # Pragmatic Brain Absorption v1 — Milestone C. Overlays must bind to an
    # existing artifact_id or registry_entry_id so they never become
    # free-floating narrative.
    if bundle.brain_overlays:
        from metis_brain.brain_overlays_v1 import (
            BrainOverlayV1,
            validate_overlays_against_bundle,
        )

        artifact_ids = {a.artifact_id for a in bundle.artifacts}
        registry_entry_ids = {e.registry_entry_id for e in bundle.registry_entries}
        parsed: list[BrainOverlayV1] = []
        for i, raw in enumerate(bundle.brain_overlays):
            try:
                parsed.append(BrainOverlayV1.model_validate(raw))
            except Exception as e:  # noqa: BLE001
                errors.append(f"brain_overlays[{i}] invalid: {e}")
        if parsed:
            errors.extend(
                validate_overlays_against_bundle(
                    parsed,
                    artifact_ids=artifact_ids,
                    registry_entry_ids=registry_entry_ids,
                )
            )

    return errors


def bundle_ready_for_horizon(bundle: BrainBundleV0, horizon: str) -> bool:
    hz = horizon.strip().lower().replace("-", "_")
    errs = validate_active_registry_integrity(bundle)
    if errs:
        return False
    active = [e for e in bundle.registry_entries if e.status == "active" and e.horizon == hz]
    if len(active) != 1:
        return False
    rows = bundle.spectrum_rows_by_horizon.get(hz)
    return bool(rows)
