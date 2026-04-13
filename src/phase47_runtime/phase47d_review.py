"""Write Phase 47d bundle + review markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase47d_thick_slice_home_feed_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase47d_thick_slice_home_feed_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p47e = bundle.get("phase47e") or {}
    lines = [
        "# Phase 47d — Thick-slice Home feed & decision copilot shell",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Design source**: `{bundle.get('design_source_path')}`",
        "",
        "## DESIGN_V3 alignment",
        "",
        "- Home-first blocks (Today, Watchlist, Research in progress, Alerts preview, Journal preview, Ask AI brief, portfolio stub).",
        "- Top nav matches user mental model: Home, Watchlist, Research, Replay, Journal, Ask AI, Advanced.",
        "- Raw JSON and full alert tooling are confined to **Research → Advanced** cohort tab and **Advanced** top-level panel.",
        "- Closed research fixtures are de-prioritized on Home: Today explains archive context and points to Watchlist / Research / Alerts.",
        "",
        "## Blockers / deviations",
        "",
        "_None recorded._ If a future change conflicts with `docs/DESIGN_V3_MINIMAL_AND_STRONG.md`, list it here.",
        "",
        "## Home blocks (catalog)",
        "",
        "```json",
        json.dumps(bundle.get("home_blocks"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Navigation shell",
        "",
        "```json",
        json.dumps(bundle.get("navigation_shell"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Closed fixture repositioning",
        "",
        "\n".join(f"- {x}" for x in (bundle.get("closed_fixture_repositioning") or [])),
        "",
        "## Ask AI brief contract",
        "",
        "```json",
        json.dumps(bundle.get("ask_ai_brief_contract"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Empty-state rules",
        "",
        "\n".join(f"- {x}" for x in (bundle.get("empty_state_rules_applied") or [])),
        "",
        "## Phase 47e recommendation",
        "",
        f"- **`{p47e.get('phase47e_recommendation')}`**",
        f"- {p47e.get('focus', '')}",
        "",
        "## Runtime API",
        "",
        "- `GET /api/home/feed` — composed Home blocks for UI + tests.",
        "- `GET /api/overview` — includes `user_first.navigation` with Phase 47d primary nav.",
        "",
        "## UI",
        "",
        "- `src/phase47_runtime/static/index.html`, `app.js` — Home grid, relocated alerts manager, Journal cards.",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
