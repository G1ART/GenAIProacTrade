"""Phase 52 operator closeout artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase52_webhook_auth_routing_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase52_webhook_auth_routing_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p53 = bundle.get("phase53") or {}
    lines = [
        "# Phase 52 — Governed webhook auth, budgets, routing, optional queue",
        "",
        f"- **OK / metrics**: `{bundle.get('ok')}` / `smoke_metrics_ok={bundle.get('smoke_metrics_ok')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Phase 51 bundle (input anchor)**: `{bundle.get('input_phase51_bundle_path')}`",
        "",
        "## Source registry",
        "",
        f"- **Sources registered**: {bundle.get('sources_registered')}",
        "",
        "## Summaries",
        "",
        "```json",
        json.dumps(
            {
                "auth_results_summary": bundle.get("auth_results_summary"),
                "rate_limit_results_summary": bundle.get("rate_limit_results_summary"),
                "routing_results_summary": bundle.get("routing_results_summary"),
                "queue_summary": bundle.get("queue_summary"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        "```",
        "",
        "## Runtime health (excerpt)",
        "",
        "```json",
        json.dumps(
            {
                "health_status": (bundle.get("runtime_health_summary") or {}).get("health_status"),
                "external_ingest_counts": (bundle.get("runtime_health_summary") or {}).get("external_ingest_counts"),
                "external_source_activity_v52": (bundle.get("runtime_health_summary") or {}).get(
                    "external_source_activity_v52"
                ),
            },
            indent=2,
            ensure_ascii=False,
        ),
        "```",
        "",
        "## Phase 53",
        "",
        f"- **`{p53.get('phase53_recommendation')}`**",
        f"- {p53.get('focus', '')}",
        "",
        "## HTTP",
        "",
        "- `POST /api/runtime/external-ingest/authenticated` — headers `X-Source-Id`, `X-Webhook-Secret` (TLS required in production).",
        "- Legacy `POST /api/runtime/external-ingest` unchanged (no Phase 52 gates).",
        "",
        "## Persistent files",
        "",
        "- `data/research_runtime/external_source_registry_v1.json`",
        "- `data/research_runtime/external_source_budget_state_v1.json`",
        "- `data/research_runtime/external_event_queue_v1.json`",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase52_runtime_health_surface_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    rh = bundle.get("runtime_health_summary") or {}
    lines = [
        "# Phase 52 — Runtime health surface (source + queue visibility)",
        "",
        f"- **Bundle phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        "",
        "## Health status",
        "",
        f"- `{rh.get('health_status')}`",
        "",
        "## External ingest counts (registry)",
        "",
        "```json",
        json.dumps(rh.get("external_ingest_counts"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Phase 52 per-source activity (`external_source_activity_v52`)",
        "",
        "```json",
        json.dumps(rh.get("external_source_activity_v52"), indent=2, ensure_ascii=False),
        "```",
        "",
        "## Cockpit preview (human lines)",
        "",
        "```json",
        json.dumps((bundle.get("cockpit_runtime_health_preview") or {}).get("plain_lines"), indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
