"""Phase 46 bundle JSON, cockpit review MD, founder pitch MD."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase46_founder_decision_cockpit_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def _bullets(lines: list[str], items: list[Any], *, empty: str) -> None:
    if items:
        for x in items:
            lines.append(f"- {x}")
    else:
        lines.append(empty)


def write_phase46_founder_decision_cockpit_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rm = bundle.get("founder_read_model") or {}
    pitch = bundle.get("representative_pitch") or {}
    cs = bundle.get("cockpit_state") or {}
    agg = cs.get("cohort_aggregate") or {}

    lines: list[str] = [
        "# Phase 46 — Founder decision cockpit (preview)",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Phase 45 input**: `{bundle.get('input_phase45_bundle_path')}`",
        f"- **Phase 44 input**: `{bundle.get('input_phase44_bundle_path')}`",
        "",
        "## Decision layer",
        "",
        f"- **Asset / cohort id**: `{rm.get('asset_id')}`",
        f"- **Founder decision status**: `{rm.get('decision_status')}`",
        f"- **Authoritative phase**: `{rm.get('authoritative_phase')}`",
        f"- **Authoritative recommendation (key)**: `{rm.get('authoritative_recommendation')}`",
        f"- **Phase 46 engine stance (from Phase 45 block)**: `{rm.get('current_stance')}`",
        "",
        "### Headline",
        "",
        rm.get("headline_message") or "",
        "",
        "### What changed / did not",
        "",
        "**Changed**",
        "",
    ]
    _bullets(lines, rm.get("what_changed") or [], empty="- _(none)_")
    lines.extend(["", "**Did not change (high level)**", ""])
    _bullets(lines, rm.get("what_did_not_change") or [], empty="- _(none)_")
    lines.extend(
        [
            "",
            "## Message layer (representative agent — governed)",
            "",
            pitch.get("top_level_pitch") or "",
            "",
            "### Why this matters",
            "",
            pitch.get("why_this_matters") or "",
            "",
            "## Information layer",
            "",
            "### Uncertainties",
            "",
        ]
    )
    _bullets(lines, rm.get("current_uncertainties") or [], empty="- _(none)_")
    lines.extend(["", "### Watchpoints", ""])
    _bullets(lines, rm.get("next_watchpoints") or [], empty="- _(none)_")
    lines.extend(
        [
            "",
            "## Cockpit cards (cohort aggregate)",
            "",
            f"- **Primary founder status**: `{agg.get('founder_primary_status')}`",
            "",
            "### Information card bullets",
            "",
        ]
    )
    _bullets(lines, (agg.get("information_card") or {}).get("bullets") or [], empty="- _(none)_")
    lines.extend(["", "## Research & provenance", ""])
    _bullets(lines, (agg.get("research_provenance_card") or {}).get("bullets") or [], empty="- _(none)_")
    lines.extend(["", "### Trace links", ""])
    for k, v in (rm.get("trace_links") or {}).items():
        lines.append(f"- `{k}`: {v}")
    if not (rm.get("trace_links") or {}):
        lines.append("- _(none)_")
    lines.extend(
        [
            "",
            "## Drill-down contract (examples in bundle JSON)",
            "",
            "Layers: `decision`, `message`, `information`, `research`, `provenance`, `closeout`.",
            "",
            "## Ledgers",
            "",
            f"- **Alert ledger file**: `{bundle.get('alert_ledger_path')}`",
            f"- **Decision trace file**: `{bundle.get('decision_trace_ledger_path')}`",
            f"- **Alerts on file**: {len((bundle.get('alert_ledger_snapshot') or {}).get('alerts') or [])}",
            f"- **Decisions on file**: {len((bundle.get('decision_trace_ledger_snapshot') or {}).get('decisions') or [])}",
            "",
            "## Phase 47",
            "",
            f"- **`{(bundle.get('phase47') or {}).get('phase47_recommendation')}`**",
            "",
            "---",
            "",
            "_Phase 46: product surface only; no substrate work._",
            "",
        ]
    )
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase46_founder_pitch_surface_md(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pitch = bundle.get("representative_pitch") or {}
    lines: list[str] = [
        "# Founder pitch surface — Phase 46 (governed spokesperson)",
        "",
        "_Tone: chief of staff / research lead — bounded, explicit about uncertainty._",
        "",
        "## Pitch",
        "",
        pitch.get("top_level_pitch") or "",
        "",
        "## Why this matters",
        "",
        pitch.get("why_this_matters") or "",
        "",
        "## What changed",
        "",
    ]
    wc = pitch.get("what_changed") or []
    if wc:
        for x in wc:
            lines.append(f"- {x}")
    else:
        lines.append("- _(see canonical closeout)_")
    lines.extend(
        [
            "",
            "## What remains unproven",
            "",
            pitch.get("what_remains_unproven") or "",
            "",
            "## What to watch next",
            "",
            pitch.get("what_to_watch_next") or "",
            "",
            "## Default next engine stance",
            "",
            str(pitch.get("phase46_default") or ""),
            "",
        ]
    )
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
