"""AGH v1 Patch 8 D2 — Production bundle graduation (v2 build + atomic write).

Builds ``data/mvp/metis_brain_bundle_v2.json`` from the canonical
``metis_brain_bundle_build_v2.json`` config (the same config that has
been driving the research branch's completed validation runs). The v2
bundle is the *production* tier of the 3-tier graduation:

    demo (built-in fallback) → sample (frozen seed pack) → production (v2)

This script is deterministic and does NOT require Supabase credentials —
when a live client is unavailable it builds from the v1 template bundle
under the same gate specs, so the script is safe to run in CI and in
copy-paste runbooks. When Supabase is available (``SUPABASE_URL`` +
``SUPABASE_SERVICE_ROLE_KEY``), it pulls the real research-branch rows
via ``build_bundle_full_from_validation_v1``.

Outputs:

* ``data/mvp/metis_brain_bundle_v2.json`` — atomically written v2 bundle
  (write to ``.tmp`` then ``os.replace``; this guarantees no half-written
  file on disk if the process dies mid-write).
* ``data/mvp/evidence/pragmatic_brain_absorption_v1_production_bundle_v2_evidence.json``
  — sha256 of the written bundle, row counts, integrity report, and the
  build mode (``live`` / ``template``) used.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from metis_brain.bundle import (  # noqa: E402
    BrainBundleV0,
    validate_active_registry_integrity,
)
from metis_brain.bundle_promotion_merge_v0 import load_bundle_json  # noqa: E402


CONFIG_PATH = REPO_ROOT / "data" / "mvp" / "metis_brain_bundle_build_v2.json"
OUTPUT_PATH = REPO_ROOT / "data" / "mvp" / "metis_brain_bundle_v2.json"
EVIDENCE_PATH = (
    REPO_ROOT
    / "data"
    / "mvp"
    / "evidence"
    / "pragmatic_brain_absorption_v1_production_bundle_v2_evidence.json"
)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> tuple[str, int]:
    """Write ``obj`` to ``path`` atomically. Returns (sha256, byte_size)."""

    raw = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return _sha256_bytes(raw), len(raw)


def _try_live_build(config: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Try to build the bundle from the live research-branch Supabase rows.

    Returns ``(merged_bundle_or_None, report)``. When credentials are
    missing or the live query fails we return ``(None, report_with_reason)``
    so the caller can fall back to the template-only build. The script
    still succeeds in that case, since the graduation script must be
    deterministic and operable offline.
    """

    report: dict[str, Any] = {"attempted": False}
    url = os.environ.get("SUPABASE_URL") or ""
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        report.update({"attempted": False, "reason": "missing_supabase_env"})
        return None, report
    try:
        report["attempted"] = True
        from supabase import create_client  # type: ignore

        client = create_client(url, key)
        from metis_brain.bundle_full_from_validation_v1 import (
            build_bundle_full_from_validation_v1,
            fetch_joined_rows_for_factor_db,
        )
        from market.promotion_gate_export import (
            export_promotion_gate_from_factor_validation_db,
        )

        template_path = REPO_ROOT / str(config["template_bundle_path"])
        template = load_bundle_json(template_path)
        specs = list(config.get("gates") or [])

        def _fetch_gate(c: Any, spec: dict[str, Any]) -> dict[str, Any]:
            return export_promotion_gate_from_factor_validation_db(
                c,
                factor_name=str(spec["factor_name"]),
                universe_name=str(spec["universe_name"]),
                horizon_type=str(spec["horizon_type"]),
                return_basis=str(spec["return_basis"]),
                artifact_id=str(spec["artifact_id"]),
            )

        merged, build_report = build_bundle_full_from_validation_v1(
            template_bundle=template,
            gate_specs=specs,
            fetch_gate=_fetch_gate,
            fetch_joined=fetch_joined_rows_for_factor_db,
            client=client,
            sync_artifact_validation_pointer=bool(
                config.get("sync_artifact_validation_pointer", True)
            ),
            spectrum_max_rows_per_horizon=config.get("spectrum_max_rows_per_horizon"),
            auto_degrade_optional_gates=list(
                config.get("auto_degrade_optional_gates") or []
            ),
            horizon_fallback_labels=dict(
                config.get("horizon_fallback_labels") or {}
            ),
            display_aliases=dict(config.get("display_aliases") or {}),
        )
        report.update({"mode": "live", "build_report": build_report})
        return merged, report
    except Exception as exc:
        report.update({"mode": "live_failed", "error": f"{exc}"})
        return None, report


def _template_build(config: dict[str, Any]) -> dict[str, Any]:
    """Fallback build: graduate the template bundle under the same gate set.

    This keeps the script deterministic and CI-runnable even when no
    Supabase credentials are present. The resulting bundle is marked
    ``build_mode='template'`` in the evidence file so operators can tell
    it apart from a live build.
    """

    template_path = REPO_ROOT / str(config["template_bundle_path"])
    template = load_bundle_json(template_path)
    graduated = dict(template)
    meta = dict(graduated.get("metadata") or {})
    meta.update(
        {
            "graduation_tier": "production",
            "graduated_from_config": str(CONFIG_PATH.relative_to(REPO_ROOT)),
            "graduated_at_utc": datetime.now(timezone.utc).isoformat(),
            "gate_spec_count": len(config.get("gates") or []),
        }
    )
    graduated["metadata"] = meta
    return graduated


def main() -> int:
    if not CONFIG_PATH.is_file():
        print(f"config missing: {CONFIG_PATH}", file=sys.stderr)
        return 2
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if str(config.get("contract", "")) != "METIS_BUNDLE_FROM_VALIDATION_CONFIG_V2":
        print(
            f"unexpected config contract: {config.get('contract')!r}",
            file=sys.stderr,
        )
        return 2

    merged, live_report = _try_live_build(config)
    build_mode = "live" if merged else "template"
    if merged is None:
        merged = _template_build(config)

    try:
        parsed_bundle = BrainBundleV0.model_validate(merged)
    except Exception as exc:
        print(f"bundle schema validation failed: {exc}", file=sys.stderr)
        return 3
    integrity_errors = validate_active_registry_integrity(parsed_bundle)
    if integrity_errors:
        print(
            "validate_active_registry_integrity FAILED:\n  "
            + "\n  ".join(integrity_errors),
            file=sys.stderr,
        )
        return 3

    sha, nbytes = _atomic_write_json(OUTPUT_PATH, merged)
    evidence = {
        "contract": "METIS_BRAIN_BUNDLE_PRODUCTION_GRADUATION_V1",
        "patch": "AGH_V1_PATCH_8_D2",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "build_mode": build_mode,
        "live_report": live_report,
        "output_path": str(OUTPUT_PATH.relative_to(REPO_ROOT)),
        "output_sha256": sha,
        "output_bytes": nbytes,
        "integrity_errors": integrity_errors,
        "gate_spec_count": len(config.get("gates") or []),
        "graduation_tier": "production",
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
