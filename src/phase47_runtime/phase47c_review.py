"""Write Phase 47c bundle + review markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase47c_traceability_replay_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase47c_traceability_replay_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p47d = bundle.get("phase47d") or {}
    lines = [
        "# Phase 47c — Traceability & decision replay",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Design sources**: {bundle.get('design_sources') or []}",
        "",
        "## Traceability views",
        "",
        "```json",
        json.dumps(bundle.get("traceability_views"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Plot grammar (contract)",
        "",
        "```json",
        json.dumps(bundle.get("plot_grammar"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Event grammar (markers)",
        "",
        "```json",
        json.dumps(bundle.get("event_grammar"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Replay vs counterfactual",
        "",
        "### Replay rules",
        "",
        "\n".join(f"- {x}" for x in (bundle.get("replay_rules") or [])),
        "",
        "### Counterfactual rules",
        "",
        "\n".join(f"- {x}" for x in (bundle.get("counterfactual_rules") or [])),
        "",
        "## Decision quality vs outcome quality",
        "",
        "\n".join(f"- {x}" for x in (bundle.get("decision_quality_vs_outcome_quality_rules") or [])),
        "",
        "## Counterfactual scaffold",
        "",
        "```json",
        json.dumps(bundle.get("counterfactual_scaffold"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Phase 47d recommendation",
        "",
        f"- **`{p47d.get('phase47d_recommendation')}`**",
        f"- {p47d.get('focus', '')}",
        "",
        "## Runtime API",
        "",
        "- `GET /api/replay/timeline` — events + synthetic series + portfolio stub.",
        "- `GET /api/replay/micro-brief?event_id=…` — hover/select payload.",
        "- `GET /api/replay/contract` — views + counterfactual scaffold summary.",
        "",
        "## UI",
        "",
        "- Top nav **Replay** (not under Advanced); sub-mode **Replay** vs **Counterfactual Lab**.",
        "- Implementation: `src/phase47_runtime/static/`, logic: `traceability_replay.py`.",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
