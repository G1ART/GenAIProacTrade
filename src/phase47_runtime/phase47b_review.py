"""Write Phase 47b bundle + review markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase47b_user_first_ux_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase47b_user_first_ux_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p47c = bundle.get("phase47c") or {}
    lines = [
        "# Phase 47b — User-first information architecture & UX",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Design source**: `{bundle.get('design_source_path')}`",
        "",
        "## Primary navigation (user-first)",
        "",
        "```json",
        json.dumps(bundle.get("primary_navigation"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Object detail sections (replaces internal tabs in default view)",
        "",
        "```json",
        json.dumps(bundle.get("object_detail_sections"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Object hierarchy",
        "",
        "```json",
        json.dumps(bundle.get("object_hierarchy"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Status translation (sample)",
        "",
        "```json",
        json.dumps((bundle.get("status_translation_examples") or [])[:6], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Advanced boundary rules",
        "",
        "\n".join(f"- {x}" for x in (bundle.get("advanced_boundary_rules") or [])),
        "",
        "## Phase 47c recommendation",
        "",
        f"- **`{p47c.get('phase47c_recommendation')}`**",
        f"- {p47c.get('focus', '')}",
        "",
        "## Section naming map (old → new)",
        "",
        "| Internal (retired from top tabs) | User-first section |",
        "|-----------------------------------|----------------------|",
        "| decision / message (split) | **Brief** |",
        "| message / what_changed | **Why now** |",
        "| closeout / next_watchpoints | **What could change** |",
        "| information / research | **Evidence** |",
        "| (scattered) | **History** (alerts + decisions panels) |",
        "| governed prompts | **Ask AI** |",
        "| provenance / closeout / raw | **Advanced** |",
        "",
        "## Runtime",
        "",
        "- UI: `src/phase47_runtime/static/` — Brief-first layout, object badge, detail tabs, copilot shortcuts.",
        "- API: `GET /api/overview` includes `user_first`; `GET /api/user-first/section/{id}`.",
        "- Copy layer: `src/phase47_runtime/ui_copy.py`.",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
