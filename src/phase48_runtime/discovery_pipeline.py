"""Research discovery candidates — not recommendations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_discovery_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "data" / "research_runtime" / "discovery_candidates_v1.json"


def load_discovery(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "candidates": []}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def save_discovery(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_discovery_candidate(
    path: Path,
    *,
    asset_scope: dict[str, Any],
    why_surfaced: str,
    triggers_fired: list[str],
    still_uncertain: str,
    evidence_needed: str,
    debate_converged: bool | None,
    linked_job_id: str,
) -> dict[str, Any]:
    data = load_discovery(path)
    cands = list(data.get("candidates") or [])
    rec = {
        "candidate_id": f"dc_{len(cands)+1}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "asset_scope": asset_scope,
        "why_it_surfaced": why_surfaced,
        "triggers_fired": triggers_fired,
        "what_is_still_uncertain": still_uncertain,
        "additional_evidence_needed": evidence_needed,
        "debate_converged_or_unresolved": debate_converged,
        "linked_job_id": linked_job_id,
        "not_a_recommendation": True,
    }
    cands.append(rec)
    data["candidates"] = cands
    save_discovery(path, data)
    return rec


def discovery_schema() -> dict[str, Any]:
    return {
        "version": 1,
        "description": "Structured discovery candidates for cockpit; never buy/sell advice.",
        "required_fields": [
            "asset_scope",
            "why_it_surfaced",
            "triggers_fired",
            "what_is_still_uncertain",
            "additional_evidence_needed",
            "not_a_recommendation",
        ],
    }
