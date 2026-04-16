"""Human-first runtime health payload for founder cockpit API."""

from __future__ import annotations

from typing import Any

from phase47_runtime.phase47e_user_locale import cockpit_health_public_text, normalize_lang
from phase51_runtime.runtime_health import build_runtime_health_summary


def build_cockpit_runtime_health_payload(
    *,
    repo_root,
    ingest_registry_path=None,
    audit_path=None,
    control_plane_path=None,
    lang: str | None = None,
) -> dict[str, Any]:
    from pathlib import Path

    root = Path(repo_root) if not isinstance(repo_root, Path) else repo_root
    raw = build_runtime_health_summary(
        repo_root=root,
        ingest_registry_path=ingest_registry_path,
        audit_path=audit_path,
        control_plane_path=control_plane_path,
    )
    from metis_brain.bundle import brain_bundle_path, bundle_ready_for_horizon, try_load_brain_bundle_v0

    _b, brain_errs = try_load_brain_bundle_v0(root)
    _hz = ("short", "medium", "medium_long", "long")
    horizons_ready = (
        {h: bundle_ready_for_horizon(_b, h) for h in _hz}
        if _b is not None
        else {h: False for h in _hz}
    )
    mvp_brain_gate = {
        "contract": "MVP_RUNTIME_BRAIN_GATE_V0",
        "bundle_path": str(brain_bundle_path(root)),
        "registry_bundle_ok": _b is not None,
        "bundle_errors": brain_errs if _b is None else [],
        "horizons_ready": horizons_ready,
    }
    st = raw.get("health_status") or "unknown"
    lg = normalize_lang(lang)
    headline, sub, lines = cockpit_health_public_text(lg, raw)

    skips = raw.get("recent_skip_reasons") or []
    skip_plain = [f"{s.get('why')} @ {str(s.get('timestamp') or '')[:19]}" for s in skips[:5]]

    return {
        "ok": True,
        "lang": lg,
        "headline": headline,
        "subtext": sub,
        "health_status": st,
        "plain_lines": lines,
        "recent_skips_plain": skip_plain,
        "effective_trigger_types": (raw.get("trigger_controls") or {}).get("allowed_trigger_types_effective", []),
        "mvp_brain_gate": mvp_brain_gate,
        "advanced": raw,
    }
