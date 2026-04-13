"""Phase 47 runtime metadata bundle (no HTTP — use app.py to serve)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase46.decision_trace_ledger import DECISION_TYPES

from phase47_runtime.governed_conversation import build_governed_conversation_contract
from phase47_runtime.phase48_recommend import recommend_phase48


def run_phase47_founder_cockpit_runtime(
    *,
    phase46_bundle_in: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    p46 = Path(phase46_bundle_in).resolve()
    gen = datetime.now(timezone.utc).isoformat()
    return {
        "ok": True,
        "phase": "phase47_founder_cockpit_runtime",
        "generated_utc": gen,
        "input_phase46_bundle_path": str(p46),
        "runtime_entrypoint": "PYTHONPATH=src python3 src/phase47_runtime/app.py",
        "runtime_views": [
            "home_overview",
            "cohort_detail_drilldown",
            "alerts_panel",
            "decision_log",
            "governed_conversation",
        ],
        "governed_conversation_contract": build_governed_conversation_contract(),
        "alert_actions_supported": ["acknowledge", "resolve", "supersede", "dismiss"],
        "decision_actions_supported": sorted(DECISION_TYPES),
        "reload_model": {
            "kind": "explicit_http_post_reload",
            "path": "/api/reload",
            "staleness": "GET /api/meta exposes bundle_stale vs phase46 bundle mtime",
        },
        "deploy_target": {
            "primary": "internal_https_reverse_proxy",
            "notes_path": "docs/operator_closeout/phase47_runtime_deploy_notes.md",
            "example_hosts": ["127.0.0.1 (dev)", "corp VPN static host behind nginx"],
        },
        "phase48": recommend_phase48(),
    }
