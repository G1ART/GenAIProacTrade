"""AGH v1 Patch 6 — Demo freeze HTML snapshots (F2).

Captures 4 product-surface HTML snapshots + a sha256 manifest so the
demo-freeze state is reproducibly auditable. We deliberately avoid a
live browser (no playwright / selenium dependency in this repo): each
snapshot is a self-contained ``.html`` file that embeds the canonical
API payload the SPA would render from, plus a reference to the SPA
shell files' sha256 digests.

Files written under ``data/mvp/evidence/screenshots/``:

    1. ``freeze_spa_index.html``                 — the exact SPA shell.
    2. ``freeze_today_object_detail_ko.html``    — Today detail payload (KO).
    3. ``freeze_today_object_detail_en.html``    — Today detail payload (EN).
    4. ``freeze_replay_governance_lineage_demo.html`` — replay lineage payload.
    5. ``sha256_manifest.json``                  — digest of each of the 4.

All payloads come from in-process calls against a fresh harness fixture
so this script has no network or Supabase dependency; an empty-state
surface is a valid freeze.
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


from phase47_runtime.today_spectrum import (  # noqa: E402
    build_today_object_detail_payload,
    build_today_spectrum_payload,
)


STATIC_DIR = REPO_ROOT / "src" / "phase47_runtime" / "static"
EV_DIR = REPO_ROOT / "data" / "mvp" / "evidence" / "screenshots"


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


def _render_payload_snapshot(
    *,
    title: str,
    payload: dict[str, Any],
    description: str,
) -> str:
    pretty = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    body = (
        f"<h1>{html.escape(title)}</h1>\n"
        f"<div class=\"meta\">captured_at_utc={html.escape(_now_iso())}</div>\n"
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
            "detail": "build_today_spectrum_payload returned no rows at freeze time.",
            "spectrum_ok": (sp or {}).get("ok"),
        }
    try:
        return build_today_object_detail_payload(
            repo_root=REPO_ROOT, asset_id=asset_id, horizon="short", lang=lang
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"detail_build_failed:{exc}",
            "asset_id": asset_id,
        }


def _replay_governance_lineage_demo() -> dict[str, Any]:
    # Use the harness API to render a (possibly empty) lineage payload
    # without hitting Supabase. An empty-state lineage is still valid
    # freeze evidence — it demonstrates the endpoint shape.
    try:
        from phase47_runtime.traceability_replay import (
            api_governance_lineage_for_registry_entry,
        )
        from agentic_harness.store import FixtureHarnessStore

        store = FixtureHarnessStore()
        return api_governance_lineage_for_registry_entry(
            store,
            registry_entry_id="reg_short_demo_v0",
            horizon="short",
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"governance_lineage_build_failed:{exc}",
        }


def main() -> int:
    EV_DIR.mkdir(parents=True, exist_ok=True)

    snapshots: list[Path] = []

    # (1) SPA shell snapshot — copy index.html verbatim so the freeze
    # captures the exact DOM+CSS that the demo surface used.
    src_index = STATIC_DIR / "index.html"
    snapshots.append(_write(EV_DIR / "freeze_spa_index.html", src_index.read_text(encoding="utf-8")))

    # (2) Today object detail — KO.
    detail_ko = _today_detail_safe("ko")
    snapshots.append(
        _write(
            EV_DIR / "freeze_today_object_detail_ko.html",
            _render_payload_snapshot(
                title="Today — object detail (KO) freeze snapshot",
                payload=detail_ko,
                description=(
                    "Canonical payload of GET /api/today/object_detail?lang=ko "
                    "for the top-ranked asset at freeze time. The SPA renders "
                    "the 4-block Today layout (rail / primary / decision / "
                    "evidence) + 5-section Research + governance lineage "
                    "compact from this payload."
                ),
            ),
        )
    )

    # (3) Today object detail — EN.
    detail_en = _today_detail_safe("en")
    snapshots.append(
        _write(
            EV_DIR / "freeze_today_object_detail_en.html",
            _render_payload_snapshot(
                title="Today — object detail (EN) freeze snapshot",
                payload=detail_en,
                description=(
                    "Canonical payload of GET /api/today/object_detail?lang=en. "
                    "Locale coverage is enforced by ResearchAnswerStructureV1 + "
                    "guardrails; silent degradation is rejected at source."
                ),
            ),
        )
    )

    # (4) Replay governance lineage snapshot (empty-state or live).
    lineage = _replay_governance_lineage_demo()
    snapshots.append(
        _write(
            EV_DIR / "freeze_replay_governance_lineage_demo.html",
            _render_payload_snapshot(
                title="Replay governance lineage freeze snapshot",
                payload=lineage,
                description=(
                    "Canonical payload of GET /api/replay/governance-lineage "
                    "for reg_short_demo_v0 / short horizon. The Replay "
                    "timeline plot (SVG) + step indicator + sandbox "
                    "followups are all derived from this payload."
                ),
            ),
        )
    )

    manifest = {
        "contract": "AGH_V1_PATCH_6_DEMO_FREEZE_SNAPSHOTS_MANIFEST_V1",
        "milestone": 17,
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
    print(f"wrote {len(snapshots)} demo-freeze HTML snapshots + manifest to {EV_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
