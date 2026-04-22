"""AGH v1 Patch 9 — productionize / self-serve / scale freeze snapshots (F2).

Freezes the Patch 9 product state as self-contained HTML + a sha256
manifest. Same philosophy as Patch 6–8: no live browser, each snapshot
either mirrors the SPA shell verbatim or embeds the canonical API
payload the SPA would render from.

Patch 9 snapshots emphasise:

* v2-first bundle resolution (``/api/runtime/health`` surfaces
  ``brain_bundle_path_resolved``, ``brain_bundle_v2_integrity_failed``,
  ``brain_bundle_fallback_to_v0``).
* Self-serve recent-request drawer + worker-tick hint (in SPA shell).
* Contract-card 2-column grid (in SPA shell).
* Snapshot lazy-generation (Today spectrum freeze is snapshot-IO free;
  the detail freeze triggers the lazy persist).

Files written under ``data/mvp/evidence/screenshots_patch_9/``:

    1. ``freeze_spa_index_patch_9.html``                       — SPA shell (Patch 9 CSS additions).
    2. ``freeze_today_spectrum_short_patch_9.html``            — Today spectrum canonical payload.
    3. ``freeze_today_object_detail_ko_patch_9.html``          — Today detail (KO).
    4. ``freeze_today_object_detail_en_patch_9.html``          — Today detail (EN).
    5. ``freeze_runtime_health_ko_patch_9.html``               — /api/runtime/health (KO).
    6. ``freeze_runtime_health_en_patch_9.html``               — /api/runtime/health (EN).
    7. ``freeze_bundle_integrity_report_patch_9.html``         — integrity report payload.
    8. ``sha256_manifest.json``                                — digest of every snapshot + SPA shell.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


from metis_brain.bundle import brain_bundle_integrity_report_for_path  # noqa: E402
from phase47_runtime.today_spectrum import (  # noqa: E402
    build_today_object_detail_payload,
    build_today_spectrum_payload,
)
from phase51_runtime.cockpit_health_surface import (  # noqa: E402
    build_cockpit_runtime_health_payload,
)


STATIC_DIR = REPO_ROOT / "src" / "phase47_runtime" / "static"
EV_DIR = REPO_ROOT / "data" / "mvp" / "evidence" / "screenshots_patch_9"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _shell_template(title: str, body_html: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"ko\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\" />\n"
        f"<title>{html.escape(title)}</title>\n"
        "<style>\n"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;"
        "margin:0;padding:1.5rem;background:#0f1115;color:#e6e6e6;line-height:1.5;}\n"
        "h1{font-size:1.1rem;margin:0 0 0.6rem;color:#fff;}\n"
        "h2{font-size:0.9rem;margin:1.4rem 0 0.4rem;color:#8ab4f8;text-transform:uppercase;"
        "letter-spacing:0.08em;}\n"
        ".meta{font-size:0.8rem;color:#9aa0a6;margin-bottom:1rem;}\n"
        "pre{background:#1a1d23;border:1px solid #2a2f39;border-radius:6px;padding:0.8rem;"
        "overflow:auto;font-size:0.78rem;white-space:pre-wrap;word-break:break-word;}\n"
        ".note{color:#b9b9b9;font-size:0.82rem;margin-top:0.8rem;}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body_html}\n"
        "</body>\n"
        "</html>\n"
    )


def _render_payload_snapshot(*, title: str, payload: dict[str, Any], description: str) -> str:
    pretty = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    body = (
        f"<h1>{html.escape(title)}</h1>\n"
        f"<div class=\"meta\">captured_at_utc={html.escape(_now_iso())} · patch=9</div>\n"
        f"<div class=\"note\">{html.escape(description)}</div>\n"
        "<h2>canonical payload</h2>\n"
        f"<pre>{html.escape(pretty)}</pre>\n"
    )
    return _shell_template(title, body)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _today_detail_safe(lang: str) -> dict[str, Any]:
    os.environ["METIS_TODAY_SOURCE"] = "registry"
    sp = build_today_spectrum_payload(repo_root=REPO_ROOT, horizon="short", lang=lang)
    asset_id = None
    if isinstance(sp, dict):
        for row in sp.get("rows") or []:
            if isinstance(row, dict) and row.get("asset_id"):
                asset_id = row["asset_id"]
                break
    if not asset_id:
        return {
            "ok": False,
            "error": "no_asset_id_available",
            "spectrum_ok": (sp or {}).get("ok"),
            "spectrum_total_rows": (sp or {}).get("total_rows"),
        }
    try:
        return build_today_object_detail_payload(
            repo_root=REPO_ROOT, asset_id=asset_id, horizon="short", lang=lang
        )
    except Exception as exc:
        return {"ok": False, "error": f"detail_build_failed:{exc}", "asset_id": asset_id}


def main() -> int:
    EV_DIR.mkdir(parents=True, exist_ok=True)
    snapshots: list[Path] = []

    src_index = STATIC_DIR / "index.html"
    snapshots.append(
        _write(
            EV_DIR / "freeze_spa_index_patch_9.html",
            src_index.read_text(encoding="utf-8"),
        )
    )

    os.environ["METIS_TODAY_SOURCE"] = "registry"
    sp = build_today_spectrum_payload(repo_root=REPO_ROOT, horizon="short", lang="ko")
    snapshots.append(
        _write(
            EV_DIR / "freeze_today_spectrum_short_patch_9.html",
            _render_payload_snapshot(
                title="Today spectrum (short, KO) · Patch 9 scale-closure freeze",
                payload=sp,
                description=(
                    "Canonical payload of GET /api/today/spectrum?horizon=short. "
                    "Patch 9 C·C: this build path no longer pre-persists message "
                    "snapshots; snapshot IO moves to the object-detail entry."
                ),
            ),
        )
    )

    snapshots.append(
        _write(
            EV_DIR / "freeze_today_object_detail_ko_patch_9.html",
            _render_payload_snapshot(
                title="Today — object detail (KO) · Patch 9 freeze",
                payload=_today_detail_safe("ko"),
                description=(
                    "Canonical payload of GET /api/today/object_detail?lang=ko. "
                    "Opening this view is what triggers lazy message snapshot "
                    "persistence under Patch 9 C·C."
                ),
            ),
        )
    )
    snapshots.append(
        _write(
            EV_DIR / "freeze_today_object_detail_en_patch_9.html",
            _render_payload_snapshot(
                title="Today — object detail (EN) · Patch 9 freeze",
                payload=_today_detail_safe("en"),
                description=(
                    "English locale of the Patch 9 Today detail. Self-serve "
                    "copy (enqueue / worker / approval) remains operator-gated."
                ),
            ),
        )
    )

    for lang in ("ko", "en"):
        payload = build_cockpit_runtime_health_payload(repo_root=REPO_ROOT, lang=lang)
        snapshots.append(
            _write(
                EV_DIR / f"freeze_runtime_health_{lang}_patch_9.html",
                _render_payload_snapshot(
                    title=(
                        f"/api/runtime/health ({lang.upper()}) · Patch 9 freeze"
                    ),
                    payload=payload,
                    description=(
                        "Patch 9 A1 adds brain_bundle_path_resolved, "
                        "brain_bundle_v2_exists, brain_bundle_v2_integrity_failed, "
                        "brain_bundle_fallback_to_v0, brain_bundle_override_used "
                        "so the tier chip can honestly render a fallback "
                        "variant when v2 exists but fails the quick integrity gate."
                    ),
                ),
            )
        )

    integrity = brain_bundle_integrity_report_for_path(REPO_ROOT)
    snapshots.append(
        _write(
            EV_DIR / "freeze_bundle_integrity_report_patch_9.html",
            _render_payload_snapshot(
                title="brain_bundle_integrity_report_for_path · Patch 9 freeze",
                payload=integrity,
                description=(
                    "Patch 9 A1 observability helper. Reports which bundle path "
                    "was resolved (env override > v2 > v0) and whether v2 failed "
                    "the quick integrity gate."
                ),
            ),
        )
    )

    manifest = {
        "contract": "AGH_V1_PATCH_9_PRODUCTIONIZE_SELF_SERVE_SCALE_SNAPSHOTS_MANIFEST_V1",
        "milestone": 20,
        "patch_nature": "productionize_self_serve_scale_closure",
        "generated_at_utc": _now_iso(),
        "snapshot_count": len(snapshots),
        "snapshots": [
            {
                "path": str(p.relative_to(REPO_ROOT)),
                "sha256": _sha256(p),
                "bytes": p.stat().st_size,
            }
            for p in snapshots
        ],
        "spa_shell_source_sha256": {
            "index.html": _sha256(STATIC_DIR / "index.html"),
            "app.js": _sha256(STATIC_DIR / "app.js"),
        },
    }
    (EV_DIR / "sha256_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {len(snapshots)} Patch 9 freeze snapshots + manifest to {EV_DIR}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
