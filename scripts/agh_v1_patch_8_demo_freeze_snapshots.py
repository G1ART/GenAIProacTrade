"""AGH v1 Patch 8 — production-graduation freeze HTML snapshots (F2).

Captures the product-surface HTML snapshots + a sha256 manifest so the
Patch 8 state is reproducibly auditable. Same philosophy as Patch 7:
no live browser, each snapshot is a self-contained ``.html`` file that
either mirrors the SPA shell verbatim or embeds the canonical API
payload the SPA would render from.

Patch 8 snapshots emphasise **graduation** (demo → sample → production
vocabulary, v2 bundle tier badge, Research 4-stack incl. what_changed,
Today hero stack with why_now / confidence / caveat / next, bundle-tier
chip, /api/runtime/health degraded envelope, lineage step note + gap
annotation).

Files written under ``data/mvp/evidence/screenshots_patch_8/``:

    1. ``freeze_spa_index_patch_8.html``                        — SPA shell (Patch 8 DOM+CSS: tier chip, contract state slot).
    2. ``freeze_today_object_detail_ko_patch_8.html``           — Today detail payload (KO).
    3. ``freeze_today_object_detail_en_patch_8.html``           — Today detail payload (EN).
    4. ``freeze_replay_governance_lineage_sample_patch_8.html`` — replay lineage payload.
    5. ``freeze_runtime_health_ko_patch_8.html``                — /api/runtime/health (KO).
    6. ``freeze_runtime_health_en_patch_8.html``                — /api/runtime/health (EN).
    7. ``freeze_research_answer_structure_contract_patch_8.html`` — Pydantic contract JSON schema (what_changed_bullets).
    8. ``sha256_manifest.json``                                 — digest of every snapshot + SPA shell.

All payloads come from in-process calls against a fresh harness
fixture. No network, no Supabase, no LLM. Empty-state / degraded
surfaces are valid freezes.
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
from phase51_runtime.cockpit_health_surface import (  # noqa: E402
    build_cockpit_runtime_health_payload,
)


STATIC_DIR = REPO_ROOT / "src" / "phase47_runtime" / "static"
EV_DIR = REPO_ROOT / "data" / "mvp" / "evidence" / "screenshots_patch_8"


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
    pretty = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    body = (
        f"<h1>{html.escape(title)}</h1>\n"
        f"<div class=\"meta\">captured_at_utc={html.escape(_now_iso())} · patch=8</div>\n"
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
            "spectrum_total_rows": (sp or {}).get("total_rows"),
            "spectrum_truncated": (sp or {}).get("truncated"),
            "spectrum_rows_limit": (sp or {}).get("rows_limit"),
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


def _replay_governance_lineage_sample() -> dict[str, Any]:
    try:
        from agentic_harness.store import FixtureHarnessStore
        from phase47_runtime.traceability_replay import (
            api_governance_lineage_for_registry_entry,
        )

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


def _research_contract_schema() -> dict[str, Any]:
    try:
        from agentic_harness.llm.contract import ResearchAnswerStructureV1

        return ResearchAnswerStructureV1.model_json_schema()
    except Exception as exc:
        return {"ok": False, "error": f"contract_schema_failed:{exc}"}


def main() -> int:
    EV_DIR.mkdir(parents=True, exist_ok=True)

    snapshots: list[Path] = []

    src_index = STATIC_DIR / "index.html"
    snapshots.append(
        _write(
            EV_DIR / "freeze_spa_index_patch_8.html",
            src_index.read_text(encoding="utf-8"),
        )
    )

    detail_ko = _today_detail_safe("ko")
    snapshots.append(
        _write(
            EV_DIR / "freeze_today_object_detail_ko_patch_8.html",
            _render_payload_snapshot(
                title="Today — object detail (KO) · Patch 8 production-graduation freeze",
                payload=detail_ko,
                description=(
                    "Canonical payload of GET /api/today/object_detail?lang=ko. "
                    "The SPA renders the Patch 8 Today hero stack (why_now / "
                    "confidence / caveat / next_step) + Research 4-stack "
                    "(what_changed on top of why_it_matters) from this payload."
                ),
            ),
        )
    )

    detail_en = _today_detail_safe("en")
    snapshots.append(
        _write(
            EV_DIR / "freeze_today_object_detail_en_patch_8.html",
            _render_payload_snapshot(
                title="Today — object detail (EN) · Patch 8 production-graduation freeze",
                payload=detail_en,
                description=(
                    "Canonical payload of GET /api/today/object_detail?lang=en. "
                    "Locale coverage is enforced by ResearchAnswerStructureV1 "
                    "guardrails; Patch 8 adds what_changed_bullets_ko/en with "
                    "the same non-empty-both-or-empty-both invariant."
                ),
            ),
        )
    )

    lineage = _replay_governance_lineage_sample()
    snapshots.append(
        _write(
            EV_DIR / "freeze_replay_governance_lineage_sample_patch_8.html",
            _render_payload_snapshot(
                title="Replay governance lineage · Patch 8 production-graduation freeze",
                payload=lineage,
                description=(
                    "Canonical payload of GET /api/replay/governance-lineage "
                    "for reg_short_demo_v0 / short horizon. The Patch 8 Replay "
                    "surface renders the same 3-lane SVG timeline + a new "
                    "step-note ('N of 4 complete · current frontier: X') + "
                    "30-day+ gap annotations from this payload."
                ),
            ),
        )
    )

    for lang in ("ko", "en"):
        payload = build_cockpit_runtime_health_payload(repo_root=REPO_ROOT, lang=lang)
        snapshots.append(
            _write(
                EV_DIR / f"freeze_runtime_health_{lang}_patch_8.html",
                _render_payload_snapshot(
                    title=(
                        f"/api/runtime/health ({lang.upper()}) · Patch 8 graduation freeze"
                    ),
                    payload=payload,
                    description=(
                        "Hardened health envelope: ok=True + health_status ∈ "
                        "{ok, degraded, down}, degraded_reasons[], "
                        "mvp_brain_gate.brain_bundle_tier ∈ {demo, sample, "
                        "production}. The UI tier chip hydrates from this "
                        "payload; Railway's healthcheckPath targets this URL."
                    ),
                ),
            )
        )

    contract_schema = _research_contract_schema()
    snapshots.append(
        _write(
            EV_DIR / "freeze_research_answer_structure_contract_patch_8.html",
            _render_payload_snapshot(
                title=(
                    "ResearchAnswerStructureV1 JSON schema · Patch 8 graduation freeze"
                ),
                payload=contract_schema,
                description=(
                    "Pydantic JSON schema for the LLM research response contract. "
                    "Patch 8 adds ``what_changed_bullets_ko`` / "
                    "``what_changed_bullets_en`` with max_length + locale "
                    "consistency validators and an orchestrator prompt + "
                    "guardrail pair that refuse responses missing this field."
                ),
            ),
        )
    )

    manifest = {
        "contract": "AGH_V1_PATCH_8_PRODUCTION_GRADUATION_SNAPSHOTS_MANIFEST_V1",
        "milestone": 19,
        "patch_nature": "production_graduation_ux_ai_wow_scale_closure",
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
        f"wrote {len(snapshots)} Patch 8 graduation freeze snapshots + manifest to {EV_DIR}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
