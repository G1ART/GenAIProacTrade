"""Write Phase 47 runtime bundle + review markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase47_founder_cockpit_runtime_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p.resolve())


def write_phase47_founder_cockpit_runtime_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p48 = bundle.get("phase48") or {}
    lines = [
        "# Phase 47 — Founder cockpit runtime",
        "",
        f"- **Phase**: `{bundle.get('phase')}`",
        f"- **Generated**: `{bundle.get('generated_utc')}`",
        f"- **Phase 46 input**: `{bundle.get('input_phase46_bundle_path')}`",
        "",
        "## Runtime",
        "",
        f"- **Entry**: `{bundle.get('runtime_entrypoint')}`",
        f"- **Views**: {', '.join(bundle.get('runtime_views') or [])}",
        "",
        "## Governed conversation",
        "",
        f"- **Contract version**: `{(bundle.get('governed_conversation_contract') or {}).get('version')}`",
        f"- **Intents**: {', '.join((bundle.get('governed_conversation_contract') or {}).get('intents_supported') or [])}",
        "",
        "## Ledger actions (UI)",
        "",
        f"- **Alert actions**: {', '.join(bundle.get('alert_actions_supported') or [])}",
        f"- **Decision types**: {', '.join(bundle.get('decision_actions_supported') or [])}",
        "",
        "## Reload",
        "",
        "```json",
        json.dumps(bundle.get("reload_model") or {}, indent=2),
        "```",
        "",
        "## Deploy",
        "",
        "```json",
        json.dumps(bundle.get("deploy_target") or {}, indent=2),
        "```",
        "",
        "## Phase 48",
        "",
        f"- **`{p48.get('phase48_recommendation')}`**",
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
