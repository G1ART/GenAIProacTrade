"""Phase 53 operator-closeout markdown + bundle JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase53_signed_payload_hmac_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase53_signed_payload_hmac_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p54 = bundle.get("phase54") or {}
    lines = [
        "# Phase 53 — Signed payload HMAC, key rotation, replay guard",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **OK / smoke_metrics_ok**: `{bundle.get('ok')}` / `{bundle.get('smoke_metrics_ok')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Input Phase 52 bundle**: `{bundle.get('input_phase52_bundle_path')}`",
        "",
        "## Signed ingress",
        "",
        f"- **signed_ingress_enabled**: `{bundle.get('signed_ingress_enabled')}`",
        f"- **signature_failures_recorded** (dead-letter stage `signature`): `{bundle.get('signature_failures_recorded')}`",
        f"- **sources_with_rotation_enabled**: `{bundle.get('sources_with_rotation_enabled')}`",
        "",
        "## Replay guard",
        "",
        f"- **replay_attempts_blocked**: `{bundle.get('replay_attempts_blocked')}`",
        "",
        "## Dead-letter",
        "",
        "```json",
        json.dumps(bundle.get("dead_letter_counts") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Replay operator path",
        "",
        "```json",
        json.dumps(bundle.get("dead_letter_replay_summary") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Phase 54",
        "",
        f"- **`{p54.get('phase54_recommendation')}`**",
        f"- {p54.get('focus', '')}",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase53_dead_letter_replay_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    lines = [
        "# Phase 53 — Dead-letter registry & bounded replay",
        "",
        "Failed governed ingress events are appended to `data/research_runtime/external_dead_letter_v1.json` (smoke uses `phase53_smoke_dead_letter_v1.json`).",
        "",
        "- **Stages**: `signature`, `replay_guard`, `auth`, `routing`, `budget`, `normalize`, `queue`.",
        "- **Replay**: `replay-phase53-dead-letter --dead-letter-id …` re-submits excerpt through `process_governed_external_ingest` — still subject to signing, replay guard, budgets, and routing.",
        "- **Lineage**: audit rows may include `operator_replay_dead_letter_id` when replay succeeds.",
        "",
        "```json",
        json.dumps(bundle.get("dead_letter_replay_summary") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def write_phase53_runtime_health_parity_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    rh = bundle.get("runtime_health_summary") or {}
    lines = [
        "# Phase 53 — Runtime health parity (smoke vs prod paths)",
        "",
        "`build_runtime_health_summary` accepts optional overrides for external source registry, budget, queue, dead-letter, and replay-guard paths so **external_source_activity_v52** and **external_ingress_phase53** merge from the same files the smoke wrote.",
        "",
        "## Legacy ingest",
        "",
        "```json",
        json.dumps(rh.get("legacy_ingest_status") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## external_source_activity_v52 (excerpt)",
        "",
        "```json",
        json.dumps(rh.get("external_source_activity_v52"), indent=2, ensure_ascii=False)[:4000],
        "```",
        "",
        "## external_ingress_phase53",
        "",
        "```json",
        json.dumps(rh.get("external_ingress_phase53") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
