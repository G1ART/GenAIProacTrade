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


# AGH v1 Patch 9 A1 — production-first auto-detect.
#
# Priority, top first:
#   1. ``METIS_BRAIN_BUNDLE`` env override (operator-explicit path; never
#      silently replaced).
#   2. ``data/mvp/metis_brain_bundle_v2.json`` (production tier) if the file
#      exists AND passes a cheap structural integrity gate (valid JSON +
#      root schema keys present + ``bundle_schema_version`` plausible).
#   3. ``data/mvp/metis_brain_bundle_v0.json`` (sample/demo fallback). Never
#      removed — this is the documented rollback target.
#
# The full ``validate_active_registry_integrity`` check is intentionally
# NOT run here. It is re-run downstream by ``try_load_brain_bundle_v0`` so
# the two costs don't compound on every path resolution (health poll,
# spectrum build, etc.). The quick gate is only meant to stop us handing
# back a v2 path that is structurally broken (e.g. half-written, truncated
# JSON) — in that case we silently fall back to v0 so Today keeps working,
# and the health surface separately reports the v2 integrity failure via
# ``brain_bundle_integrity_report_for_path``.
def _quick_integrity_ok(p: Path) -> bool:
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(raw, dict):
        return False
    required_root_keys = (
        "artifacts",
        "promotion_gates",
        "registry_entries",
        "spectrum_rows_by_horizon",
    )
    for k in required_root_keys:
        if k not in raw:
            return False
    schema_version = raw.get("schema_version")
    if schema_version is not None and not isinstance(schema_version, int):
        return False
    return True


def brain_bundle_path(repo_root: Path) -> Path:
    override = (os.environ.get("METIS_BRAIN_BUNDLE") or "").strip()
    if override:
        return Path(override)
    v2 = repo_root / "data" / "mvp" / "metis_brain_bundle_v2.json"
    if v2.is_file() and _quick_integrity_ok(v2):
        return v2
    return repo_root / "data" / "mvp" / "metis_brain_bundle_v0.json"


def brain_bundle_integrity_report_for_path(repo_root: Path) -> dict[str, Any]:
    """Report the resolved bundle path and whether v2 quick-integrity failed.

    AGH v1 Patch 9 A1 — surfaced by ``/api/runtime/health`` so the operator
    can see when we are running on v0 fallback because v2 is structurally
    broken (not just missing). ``v2_integrity_failed`` is emitted only
    when the v2 file physically exists but the quick gate rejects it.
    """
    override = (os.environ.get("METIS_BRAIN_BUNDLE") or "").strip()
    resolved = brain_bundle_path(repo_root)
    v2 = repo_root / "data" / "mvp" / "metis_brain_bundle_v2.json"
    v2_exists = v2.is_file()
    v2_quick_ok = v2_exists and _quick_integrity_ok(v2)
    return {
        "override_used": bool(override),
        "resolved_path": str(resolved),
        "v2_exists": v2_exists,
        "v2_quick_integrity_ok": v2_quick_ok,
        "v2_integrity_failed": v2_exists and not v2_quick_ok and not override,
        "fallback_to_v0": (not override) and (not v2_quick_ok),
    }


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
    # AGH v1 Patch 9 A2 — optional build-fingerprint block. Written by the
    # production graduation script (graduation_tier, graduated_at_utc,
    # source_run_ids, built_at_utc, gate_spec_count) so the cockpit + A2
    # integrity checks can tell apart real-graduated bundles from demo
    # templates without inspecting every artifact. Legacy bundles omit
    # this field entirely — empty dict = no claim.
    metadata: dict[str, Any] = Field(default_factory=dict)

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


def validate_active_registry_integrity(
    bundle: BrainBundleV0,
    *,
    tier: str | None = None,
) -> list[str]:
    """Return human-readable errors; empty list means Today may consume this bundle.

    AGH v1 Patch 9 A2 — when ``tier='production'`` is passed explicitly,
    additional checks run (active/challenger consistency, spectrum rows
    per horizon, tier metadata coherence, write-evidence coherence). Under
    the default ``tier=None`` / ``tier='sample'`` / ``tier='demo'`` the
    historical (Patch 8 and earlier) minimum-check behaviour is preserved,
    so legacy callers that call this unconditionally (e.g. overlay
    loaders) keep their existing semantics.
    """
    errors: list[str] = []
    tier_norm = (tier or "").strip().lower()
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

    if tier_norm == "production":
        errors.extend(_production_tier_integrity_checks(bundle))

    return errors


# AGH v1 Patch 9 A2 — production tier integrity hardening.
#
# These checks run in addition to the universal checks above, but only
# when a caller opts in by passing ``tier='production'``. They encode the
# extra invariants we promise to operators whenever the cockpit claims a
# bundle is at production tier (vs. sample / demo). Each check appends
# plain-language reasons; no check raises.
_PRODUCTION_HORIZONS = ("short", "medium", "medium_long", "long")


def _production_tier_integrity_checks(bundle: BrainBundleV0) -> list[str]:
    out: list[str] = []

    # Check 1: active / challenger consistency. Every active registry
    # entry's ``active_artifact_id`` must be in ``artifacts``, AND every
    # referenced challenger id must also be in ``artifacts``, AND no
    # challenger may point to its own active_artifact_id (would be a
    # self-promotion loop).
    art_ids = {a.artifact_id for a in bundle.artifacts}
    for ent in bundle.registry_entries:
        if ent.status != "active":
            continue
        aid = str(getattr(ent, "active_artifact_id", "") or "")
        if aid and aid not in art_ids:
            out.append(
                f"production: registry {ent.registry_entry_id!r} active_artifact_id {aid!r} absent from artifacts"
            )
        seen_challengers: set[str] = set()
        for cid in (ent.challenger_artifact_ids or []):
            c = str(cid or "")
            if not c:
                continue
            if c in seen_challengers:
                out.append(
                    f"production: registry {ent.registry_entry_id!r} duplicate challenger {c!r}"
                )
            seen_challengers.add(c)
            if c == aid:
                out.append(
                    f"production: registry {ent.registry_entry_id!r} challenger_artifact_id equals active_artifact_id {c!r}"
                )
            if c not in art_ids:
                out.append(
                    f"production: registry {ent.registry_entry_id!r} challenger_artifact_id {c!r} absent from artifacts"
                )

    # Check 2: spectrum rows per horizon. Production bundles must ship
    # at least one spectrum row for each of the four MVP horizons. A
    # sample/demo bundle is allowed to be partial; a production bundle
    # that claims a horizon via registry_entries but ships zero rows is
    # misleading to Today.
    for hz in _PRODUCTION_HORIZONS:
        rows = bundle.spectrum_rows_by_horizon.get(hz)
        has_active_for_hz = any(
            ent.status == "active" and ent.horizon == hz for ent in bundle.registry_entries
        )
        if has_active_for_hz and not rows:
            out.append(
                f"production: horizon {hz!r} has an active registry entry but zero spectrum rows"
            )
        if rows is not None and not isinstance(rows, list):  # pragma: no cover — schema guard
            out.append(f"production: spectrum_rows_by_horizon[{hz!r}] is not a list")

    # Check 3: tier metadata coherence. If the bundle carries a
    # ``graduation_tier`` hint in its metadata block, that hint must be
    # ``production`` when we are being asked to validate at production
    # tier. And every active artifact's ``validation_pointer`` + ``created_by``
    # must look production-shaped (not the demo/stub fingerprints). This
    # closes "v2 file exists, loads fine, but internally still points at
    # ``pit:demo:*`` / ``stub_feature_set`` / ``deterministic_kernel``".
    meta = getattr(bundle, "metadata", None)
    if isinstance(meta, dict):
        mt = str(meta.get("graduation_tier") or "").strip().lower()
        if mt and mt != "production":
            out.append(
                f"production: bundle.metadata.graduation_tier={mt!r} contradicts production-tier check"
            )
    # Map each active/challenger artifact to the horizon(s) it serves so
    # that horizons whose provenance is *honestly degraded* (template_fallback
    # or insufficient_evidence) can legitimately ship demo-shaped artifacts
    # without being treated as a production violation. This matches the
    # Pragmatic Brain Absorption v1 Milestone A contract: gates marked under
    # ``auto_degrade_optional_gates`` in the build config fall through to
    # template/insufficient-evidence, and their honesty is already surfaced
    # via ``horizon_provenance.source``. The check below therefore only
    # rejects demo-shaped artifacts on horizons that claim to be
    # ``real_derived`` (or whose provenance is missing entirely).
    _DEGRADED_PROVENANCE_SOURCES = {"template_fallback", "insufficient_evidence"}
    horizon_provenance = getattr(bundle, "horizon_provenance", {}) or {}
    artifact_to_horizons: dict[str, set[str]] = {}
    active_artifact_ids: set[str] = set()
    for ent in bundle.registry_entries:
        if ent.status != "active":
            continue
        aid = str(getattr(ent, "active_artifact_id", "") or "")
        hz = str(getattr(ent, "horizon", "") or "")
        if aid:
            active_artifact_ids.add(aid)
            if hz:
                artifact_to_horizons.setdefault(aid, set()).add(hz)
        for c in (ent.challenger_artifact_ids or []):
            c_str = str(c or "")
            if not c_str:
                continue
            active_artifact_ids.add(c_str)
            if hz:
                artifact_to_horizons.setdefault(c_str, set()).add(hz)

    def _all_horizons_intentionally_degraded(aid: str) -> bool:
        horizons = artifact_to_horizons.get(aid) or set()
        if not horizons:
            return False
        for hz in horizons:
            prov = horizon_provenance.get(hz)
            if not isinstance(prov, dict):
                return False
            src = str(prov.get("source") or "").strip()
            if src not in _DEGRADED_PROVENANCE_SOURCES:
                return False
        return True

    for art in bundle.artifacts:
        if art.artifact_id not in active_artifact_ids:
            continue
        if _all_horizons_intentionally_degraded(art.artifact_id):
            continue
        vp = str(getattr(art, "validation_pointer", "") or "")
        cb = str(getattr(art, "created_by", "") or "")
        fs = str(getattr(art, "feature_set", "") or "")
        if vp.startswith("pit:demo:") or vp.startswith("demo:") or vp == "":
            out.append(
                f"production: artifact {art.artifact_id!r} has non-production validation_pointer={vp!r}"
            )
        if cb in ("deterministic_kernel", "stub", "") or cb.startswith("demo"):
            out.append(
                f"production: artifact {art.artifact_id!r} has non-production created_by={cb!r}"
            )
        if fs in ("stub_feature_set", "") or fs.startswith("demo"):
            out.append(
                f"production: artifact {art.artifact_id!r} has non-production feature_set={fs!r}"
            )

    # Check 4: hash / write-evidence coherence. Production bundles should
    # carry a non-empty ``as_of_utc`` and, when metadata is present, a
    # ``source_run_ids`` or equivalent build fingerprint so the graduation
    # runbook can point a rollback at the prior build. Missing fingerprints
    # are reported but never block (we still return the bundle) — the
    # health surface will flag them.
    if not str(bundle.as_of_utc or "").strip():
        out.append("production: bundle.as_of_utc is empty")
    if isinstance(meta, dict):
        src_runs = meta.get("source_run_ids")
        if src_runs is None or (isinstance(src_runs, list) and not src_runs):
            out.append("production: bundle.metadata.source_run_ids missing or empty")
        built_at = str(meta.get("built_at_utc") or "").strip()
        if not built_at:
            out.append("production: bundle.metadata.built_at_utc missing")

    return out


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
