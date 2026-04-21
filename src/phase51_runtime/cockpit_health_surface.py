"""Human-first runtime health payload for founder cockpit API."""

from __future__ import annotations

from typing import Any

from phase47_runtime.phase47e_user_locale import cockpit_health_public_text, normalize_lang
from phase51_runtime.runtime_health import build_runtime_health_summary


# AGH v1 Patch 8 E2 — canonical runtime-health status vocabulary exposed
# to the cockpit. `ok` means all subsystems are healthy; `degraded` means
# at least one non-fatal subsystem is missing / failed but the operator
# can still navigate; `down` is reserved for truly broken responses
# (process-level exception). The HTTP layer turns only `down` into 503.
RUNTIME_HEALTH_STATUS_VALUES = ("ok", "degraded", "down")


# Bounded Non-Quant Cash-Out v1 — BNCO-6. Canonical 4-value vocabulary for
# horizon state exposed on mvp_brain_gate.horizon_state_v1.
HORIZON_STATE_V1_VALUES = (
    "real_derived",
    "real_derived_with_degraded_challenger",
    "template_fallback",
    "insufficient_evidence",
)


def _horizon_state_v1_from_provenance(
    horizon_provenance: dict[str, Any],
    horizons: tuple[str, ...],
) -> dict[str, str]:
    """Project ``horizon_provenance.source`` into the canonical 4-value state.

    Any horizon not present in provenance, or carrying an unexpected source
    label, is degraded to ``insufficient_evidence`` — we refuse to let
    runtime surface confidence that provenance cannot justify.
    """
    out: dict[str, str] = {}
    for hz in horizons:
        prov = horizon_provenance.get(hz) if isinstance(horizon_provenance, dict) else None
        src = str((prov or {}).get("source") or "") if isinstance(prov, dict) else ""
        if src in HORIZON_STATE_V1_VALUES:
            out[hz] = src
        else:
            out[hz] = "insufficient_evidence"
    return out


# AGH v1 Patch 8 D3 — 3-tier brain bundle graduation vocabulary:
#   demo        : built-in fallback artifacts only (no DB-derived evidence)
#   sample      : frozen investor seed pack (canonical v1 bundle)
#   production  : graduated from R-branch Supabase completed runs (v2 bundle)
#
# The tier is inferred from the bundle file path + provenance. It is
# exposed via /api/runtime/health so the UI can render a bundle-tier
# badge without re-deriving the rule client-side.
BRAIN_BUNDLE_TIERS = ("demo", "sample", "production")


def _infer_brain_bundle_tier(
    bundle_path: str,
    horizon_provenance: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    meta_tier = str((metadata or {}).get("graduation_tier") or "").lower()
    if meta_tier in BRAIN_BUNDLE_TIERS:
        return meta_tier
    p = str(bundle_path or "").lower()
    if p.endswith("metis_brain_bundle_v2.json"):
        return "production"
    if p.endswith("metis_brain_bundle_v0.json"):
        return "sample"
    any_real = False
    any_missing = False
    for _hz, prov in (horizon_provenance or {}).items():
        src = str((prov or {}).get("source") or "")
        if src.startswith("real_derived"):
            any_real = True
        elif src in ("", "template_fallback", "insufficient_evidence"):
            any_missing = True
    if any_real and not any_missing:
        return "production"
    if any_real:
        return "sample"
    return "demo"


def build_cockpit_runtime_health_payload(
    *,
    repo_root,
    ingest_registry_path=None,
    audit_path=None,
    control_plane_path=None,
    lang: str | None = None,
) -> dict[str, Any]:
    """Assemble the cockpit runtime-health payload.

    AGH v1 Patch 8 E2: never raise to the HTTP layer for recoverable
    sub-failures. If any of the independent sub-steps (advanced summary,
    brain bundle, overlays summary, spec survey) fail, capture the reason
    into ``degraded_reasons`` and return a 200-shaped payload with
    ``health_status='degraded'``. Only a total process-level failure
    surfaces ``health_status='down'`` — that is what the HTTP layer
    translates into 503.
    """
    from pathlib import Path

    root = Path(repo_root) if not isinstance(repo_root, Path) else repo_root
    degraded_reasons: list[str] = []
    try:
        raw = build_runtime_health_summary(
            repo_root=root,
            ingest_registry_path=ingest_registry_path,
            audit_path=audit_path,
            control_plane_path=control_plane_path,
        )
    except Exception as exc:  # pragma: no cover — guarded path
        raw = {"health_status": "degraded"}
        degraded_reasons.append(f"runtime_health_summary_failed: {type(exc).__name__}")
    from metis_brain.bundle import brain_bundle_path, bundle_ready_for_horizon, try_load_brain_bundle_v0

    try:
        _b, brain_errs = try_load_brain_bundle_v0(root)
    except Exception as exc:  # pragma: no cover — guarded path
        _b, brain_errs = None, [f"brain_bundle_exception: {type(exc).__name__}"]
        degraded_reasons.append(f"brain_bundle_load_failed: {type(exc).__name__}")
    _hz = ("short", "medium", "medium_long", "long")
    horizons_ready = (
        {h: bundle_ready_for_horizon(_b, h) for h in _hz}
        if _b is not None
        else {h: False for h in _hz}
    )
    bundle_as_of_utc = str(getattr(_b, "as_of_utc", "") or "") if _b is not None else ""
    # horizon_provenance is the canonical real-derived / template_fallback
    # / degraded truth emitted by build_bundle_full_from_validation_v1.
    horizon_provenance = (
        dict(getattr(_b, "horizon_provenance", {}) or {}) if _b is not None else {}
    )
    # Founder-facing: active artifact per horizon with display alias when present.
    active_artifact_by_horizon: dict[str, dict[str, Any]] = {}
    if _b is not None:
        art_by_id = {a.artifact_id: a for a in _b.artifacts}
        for ent in _b.registry_entries:
            if str(getattr(ent, "status", "") or "") != "active":
                continue
            aid = str(getattr(ent, "active_artifact_id", "") or "")
            art = art_by_id.get(aid)
            active_artifact_by_horizon[str(ent.horizon)] = {
                "registry_entry_id": ent.registry_entry_id,
                "active_artifact_id": aid,
                "active_model_family_name": ent.active_model_family_name,
                "display_id": (
                    (getattr(art, "display_id", "") if art else "")
                    or getattr(ent, "display_id", "")
                    or ""
                ),
                "display_family_name_ko": (
                    (getattr(art, "display_family_name_ko", "") if art else "")
                    or getattr(ent, "display_family_name_ko", "")
                    or ""
                ),
                "display_family_name_en": (
                    (getattr(art, "display_family_name_en", "") if art else "")
                    or getattr(ent, "display_family_name_en", "")
                    or ""
                ),
                "challenger_artifact_ids": list(ent.challenger_artifact_ids or []),
            }
    # Pragmatic Brain Absorption v1 — Milestone C cash-out. Surfacing the
    # bounded brain_overlays list lets Today / Research / Replay flag overlay
    # influence without duplicating the full overlay payload per row.
    from metis_brain.brain_overlays_v1 import summarize_overlays_for_runtime

    try:
        brain_overlays_summary = summarize_overlays_for_runtime(
            list(getattr(_b, "brain_overlays", []) or []) if _b is not None else []
        )
    except Exception as exc:  # pragma: no cover — guarded path
        brain_overlays_summary = []
        degraded_reasons.append(f"brain_overlays_summary_failed: {type(exc).__name__}")
    # Bounded Non-Quant Cash-Out v1 — BNCO-6. horizon_state_v1 is the
    # canonical 4-value projection of ``horizon_provenance`` that runtime
    # surfaces + health gates can rely on without parsing nested gates.
    horizon_state_v1 = _horizon_state_v1_from_provenance(horizon_provenance, _hz)
    bundle_metadata = (
        dict(getattr(_b, "metadata", {}) or {})
        if _b is not None and hasattr(_b, "metadata")
        else {}
    )
    brain_bundle_tier = _infer_brain_bundle_tier(
        str(brain_bundle_path(root)),
        horizon_provenance,
        bundle_metadata,
    )
    mvp_brain_gate = {
        "contract": "MVP_RUNTIME_BRAIN_GATE_V1",
        "bundle_path": str(brain_bundle_path(root)),
        "bundle_as_of_utc": bundle_as_of_utc,
        "registry_bundle_ok": _b is not None,
        "bundle_errors": brain_errs if _b is None else [],
        "horizons_ready": horizons_ready,
        "horizon_provenance": horizon_provenance,
        "horizon_state_v1": horizon_state_v1,
        "active_artifact_by_horizon": active_artifact_by_horizon,
        "brain_overlays_summary": brain_overlays_summary,
        # AGH v1 Patch 8 D3 — production graduation tier surfaced to the
        # UI so the tier badge can render without duplicating the rule.
        "brain_bundle_tier": brain_bundle_tier,
    }
    from metis_brain.mvp_spec_survey_v0 import build_mvp_spec_survey_v0

    try:
        mvp_spec_survey = build_mvp_spec_survey_v0(root)
    except Exception as exc:  # pragma: no cover — guarded path
        mvp_spec_survey = {"ok": False, "error": type(exc).__name__}
        degraded_reasons.append(f"mvp_spec_survey_failed: {type(exc).__name__}")
    # Brain-bundle absence is a real degradation signal the operator needs
    # to see — surface it through the same reasons list.
    if _b is None:
        degraded_reasons.append("brain_bundle_missing")
    raw_status = raw.get("health_status") or "unknown"
    if degraded_reasons and raw_status in ("ok", "healthy", "unknown"):
        st = "degraded"
    else:
        st = raw_status
    lg = normalize_lang(lang)
    try:
        headline, sub, lines = cockpit_health_public_text(lg, raw)
    except Exception as exc:  # pragma: no cover — guarded path
        headline, sub, lines = ("", "", [])
        degraded_reasons.append(f"cockpit_health_text_failed: {type(exc).__name__}")

    skips = raw.get("recent_skip_reasons") or []
    skip_plain = [f"{s.get('why')} @ {str(s.get('timestamp') or '')[:19]}" for s in skips[:5]]

    return {
        "ok": True,
        "lang": lg,
        "headline": headline,
        "subtext": sub,
        "health_status": st,
        "degraded_reasons": sorted(set(degraded_reasons)),
        "plain_lines": lines,
        "recent_skips_plain": skip_plain,
        "effective_trigger_types": (raw.get("trigger_controls") or {}).get("allowed_trigger_types_effective", []),
        "mvp_brain_gate": mvp_brain_gate,
        "mvp_product_spec_survey_v0": mvp_spec_survey,
        "advanced": raw,
    }
