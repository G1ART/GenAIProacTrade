"""Deterministic operator-facing ID resolution (golden path)."""

from __future__ import annotations

import uuid
from typing import Any

from db import records as dbrec

LATEST_TOKEN = "latest"


def _is_latest(raw: str | None) -> bool:
    return str(raw or "").strip().lower() == LATEST_TOKEN


def resolve_program_id(
    client: Any,
    raw: str,
    *,
    universe_name: str | None = None,
) -> dict[str, Any]:
    if not _is_latest(raw):
        try:
            uuid.UUID(str(raw).strip())
        except ValueError:
            return {
                "ok": False,
                "error": "invalid_program_id",
                "value_preview": str(raw)[:64],
            }
        pid = str(raw).strip()
        p = dbrec.fetch_research_program(client, program_id=pid)
        if not p:
            return {"ok": False, "error": "program_not_found", "program_id": pid}
        return {
            "ok": True,
            "program_id": pid,
            "program": p,
            "resolved_rule": "explicit_uuid",
        }

    uni = (universe_name or "").strip()
    if uni:
        rows = dbrec.list_research_programs_for_universe(
            client, universe_name=uni, limit=25
        )
        rows = [r for r in rows if str(r.get("status") or "") != "archived"]
        if not rows:
            return {
                "ok": False,
                "error": "no_non_archived_program_for_universe",
                "universe_name": uni,
            }
        chosen = rows[0]
        return {
            "ok": True,
            "program_id": str(chosen["id"]),
            "program": chosen,
            "resolved_rule": "latest_created_non_archived_for_universe",
            "n_candidates_same_universe": len(rows),
        }

    recent = dbrec.fetch_research_programs_recent(client, limit=40)
    recent = [r for r in recent if str(r.get("status") or "") != "archived"]
    if not recent:
        return {"ok": False, "error": "no_non_archived_programs"}
    universes = {str(r.get("universe_name") or "") for r in recent}
    universes.discard("")
    if len(universes) > 1:
        return {
            "ok": False,
            "error": "ambiguous_latest_program_need_universe",
            "universes_seen": sorted(universes),
            "hint": "Use --program-id latest together with --universe <name>.",
        }
    chosen = recent[0]
    return {
        "ok": True,
        "program_id": str(chosen["id"]),
        "program": chosen,
        "resolved_rule": "latest_recent_implicit_single_universe_bucket",
    }


def resolve_repair_campaign_run_id(
    client: Any,
    raw: str,
    *,
    program_id: str,
    latest_success: bool = False,
) -> dict[str, Any]:
    if not _is_latest(raw):
        try:
            uuid.UUID(str(raw).strip())
        except ValueError:
            return {"ok": False, "error": "invalid_repair_campaign_run_id"}
        rid = str(raw).strip()
        row = dbrec.fetch_public_repair_campaign_run(client, run_id=rid)
        if not row:
            return {"ok": False, "error": "repair_campaign_run_not_found", "run_id": rid}
        if str(row.get("program_id") or "") != str(program_id):
            return {
                "ok": False,
                "error": "repair_campaign_program_mismatch",
                "run_id": rid,
                "expected_program_id": program_id,
            }
        return {
            "ok": True,
            "repair_campaign_run_id": rid,
            "run": row,
            "resolved_rule": "explicit_uuid",
        }

    rows = dbrec.list_public_repair_campaign_runs_for_program(
        client, program_id=program_id, limit=30
    )
    if latest_success:
        rows = [
            r
            for r in rows
            if str(r.get("status") or "") == "completed"
            and r.get("final_decision") is not None
        ]
    if not rows:
        return {
            "ok": False,
            "error": "no_matching_repair_campaign_for_program",
            "program_id": program_id,
            "latest_success": latest_success,
        }
    chosen = rows[0]
    return {
        "ok": True,
        "repair_campaign_run_id": str(chosen["id"]),
        "run": chosen,
        "resolved_rule": "latest_by_created_at"
        + ("_completed_only" if latest_success else ""),
    }
