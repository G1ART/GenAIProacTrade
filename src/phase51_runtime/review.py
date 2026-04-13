"""Write Phase 51 operator closeout artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase51_external_trigger_ingest_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase51_external_trigger_ingest_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p52 = bundle.get("phase52") or {}
    lines = [
        "# Phase 51 — External trigger ingest & governed cycle",
        "",
        f"- **OK / metrics**: `{bundle.get('ok')}` / `smoke_metrics_ok={bundle.get('smoke_metrics_ok')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Phase 50 control bundle (input)**: `{bundle.get('input_phase50_control_bundle_path')}`",
        "",
        "## External events",
        "",
        f"- Received: **{bundle.get('external_events_received')}**",
        f"- Accepted: **{bundle.get('external_events_accepted')}**",
        f"- Rejected (incl. dedupe): **{bundle.get('external_events_rejected')}**",
        f"- Deduped only: **{bundle.get('external_events_deduped', '—')}**",
        "",
        "## Normalization results",
        "",
        "```json",
        json.dumps(bundle.get("normalized_trigger_results") or [], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Cycles consuming external events",
        "",
        "```json",
        json.dumps(bundle.get("cycles_consuming_external_events") or [], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Runtime health summary (excerpt)",
        "",
        "```json",
        json.dumps(
            {
                "health_status": (bundle.get("runtime_health_summary") or {}).get("health_status"),
                "external_ingest_counts": (bundle.get("runtime_health_summary") or {}).get(
                    "external_ingest_counts"
                ),
            },
            indent=2,
            ensure_ascii=False,
        ),
        "```",
        "",
        "## Phase 52",
        "",
        f"- **`{p52.get('phase52_recommendation')}`**",
        f"- {p52.get('focus', '')}",
        "",
        "## Adapters (MVP)",
        "",
        "- File drop JSON (`phase51_runtime.external_ingest_adapters.load_events_from_file`)",
        "- `POST /api/runtime/external-ingest` (bounded JSON body)",
        "- CLI `submit-external-trigger-json`",
        "",
        "## Persistent files",
        "",
        "- `data/research_runtime/external_trigger_ingest_v1.json`",
        "- `data/research_runtime/external_trigger_audit_log_v1.json`",
        "- `data/research_runtime/runtime_health_summary_v1.json` (refreshed via CLI / health builder)",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase51_runtime_health_surface_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    prev = bundle.get("cockpit_runtime_health_preview") or {}
    lines = [
        "# Phase 51 — Runtime health surface (cockpit)",
        "",
        f"- **Bundle ref**: `phase51_external_trigger_ingest_bundle.json` (`generated_utc`: {bundle.get('generated_utc')})",
        "",
        "## Founder-facing preview (API shape)",
        "",
        f"- **headline**: {prev.get('headline', '')}",
        f"- **subtext**: {prev.get('subtext', '')}",
        "",
        "### Plain lines",
        "",
        "\n".join(f"- {x}" for x in (prev.get("plain_lines") or [])),
        "",
        "### Recent skips (plain)",
        "",
        "\n".join(f"- {x}" for x in (prev.get("recent_skips_plain") or [])) or "- (none)",
        "",
        "## API",
        "",
        "- `GET /api/runtime/health` — human-first card + `advanced` machine block",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
