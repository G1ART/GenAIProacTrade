"""Deterministic operator-facing ID resolution (golden path)."""

from __future__ import annotations

import uuid
from typing import Any

from db import records as dbrec
from public_repair_iteration.constants import (
    ITERATION_POLICY_VERSION,
    REPAIR_CAMPAIGN_SELECTORS,
    SELECTOR_FROM_LATEST_PAIR,
    SELECTOR_LATEST,
    SELECTOR_LATEST_ACTIVE_SERIES,
    SELECTOR_LATEST_COMPATIBLE,
    SELECTOR_LATEST_FOR_PROGRAM,
    SELECTOR_LATEST_SUCCESS,
)
from public_repair_iteration.infra_noise import call_with_transient_retry


def _norm_token(raw: str | None) -> str:
    s = str(raw or "").strip().lower().replace("_", "-")
    return s


def _is_latest_token(raw: str | None) -> bool:
    return _norm_token(raw) == SELECTOR_LATEST


def repair_campaign_selector_token(raw: str | None) -> str | None:
    """Return canonical selector token if `raw` is a known selector (not a UUID)."""
    t = _norm_token(raw)
    if t in REPAIR_CAMPAIGN_SELECTORS:
        return t
    return None


def _list_runs_for_program(client: Any, *, program_id: str, limit: int = 40) -> list[dict[str, Any]]:
    return call_with_transient_retry(
        lambda: dbrec.list_public_repair_campaign_runs_for_program(
            client, program_id=program_id, limit=limit
        )
    )


def _program_archived(program: dict[str, Any] | None) -> bool:
    if not program:
        return False
    return str(program.get("status") or "").lower() == "archived"


def _run_success_eligible(row: dict[str, Any]) -> bool:
    return str(row.get("status") or "") == "completed" and row.get("final_decision") is not None


def _run_compatible_with_series(
    row: dict[str, Any],
    *,
    program_id: str,
    series: dict[str, Any],
) -> bool:
    if str(row.get("program_id") or "") != str(program_id):
        return False
    if str(row.get("universe_name") or "") != str(series.get("universe_name") or ""):
        return False
    if str(series.get("policy_version") or "") != ITERATION_POLICY_VERSION:
        return False
    return _run_success_eligible(row)


def resolve_program_id(
    client: Any,
    raw: str,
    *,
    universe_name: str | None = None,
) -> dict[str, Any]:
    if not _is_latest_token(raw):
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


def resolve_iteration_series_id(
    client: Any,
    raw: str,
    *,
    program_id: str,
    program: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve `latest-active-series` or explicit series UUID for a program."""
    t = _norm_token(raw)
    if t != SELECTOR_LATEST_ACTIVE_SERIES:
        try:
            uuid.UUID(str(raw).strip())
        except ValueError:
            return {
                "ok": False,
                "error": "invalid_iteration_series_id",
                "value_preview": str(raw)[:64],
            }
        sid = str(raw).strip()
        row = dbrec.fetch_public_repair_iteration_series(client, series_id=sid)
        if not row:
            return {"ok": False, "error": "iteration_series_not_found", "series_id": sid}
        if str(row.get("program_id") or "") != str(program_id):
            return {
                "ok": False,
                "error": "iteration_series_program_mismatch",
                "series_id": sid,
                "expected_program_id": program_id,
            }
        if str(row.get("status") or "") != "active":
            return {
                "ok": False,
                "error": "iteration_series_not_active",
                "series_id": sid,
                "status": row.get("status"),
            }
        prog = program or dbrec.fetch_research_program(client, program_id=program_id)
        if not prog:
            return {"ok": False, "error": "program_not_found", "program_id": program_id}
        if _program_archived(prog):
            return {
                "ok": False,
                "error": "program_archived_series_resolution_blocked",
                "program_id": program_id,
            }
        if str(row.get("universe_name") or "") != str(prog.get("universe_name") or ""):
            return {
                "ok": False,
                "error": "iteration_series_universe_incompatible_with_program",
                "series_universe": row.get("universe_name"),
                "program_universe": prog.get("universe_name"),
            }
        if str(row.get("policy_version") or "") != ITERATION_POLICY_VERSION:
            return {
                "ok": False,
                "error": "iteration_series_policy_version_incompatible",
                "series_policy_version": row.get("policy_version"),
                "expected_policy_version": ITERATION_POLICY_VERSION,
            }
        return {
            "ok": True,
            "series_id": sid,
            "series": row,
            "resolved_rule": "explicit_uuid",
        }

    actives = dbrec.list_active_public_repair_iteration_series_for_program(
        client, program_id=program_id
    )
    if not actives:
        return {
            "ok": False,
            "error": "no_active_iteration_series",
            "program_id": program_id,
        }
    if len(actives) > 1:
        return {
            "ok": False,
            "error": "ambiguous_multiple_active_iteration_series",
            "series_ids": [str(s["id"]) for s in actives],
        }
    row = actives[0]
    prog = program or dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    if _program_archived(prog):
        return {
            "ok": False,
            "error": "program_archived_series_resolution_blocked",
            "program_id": program_id,
        }
    if str(row.get("universe_name") or "") != str(prog.get("universe_name") or ""):
        return {
            "ok": False,
            "error": "iteration_series_universe_incompatible_with_program",
            "series_universe": row.get("universe_name"),
            "program_universe": prog.get("universe_name"),
        }
    if str(row.get("policy_version") or "") != ITERATION_POLICY_VERSION:
        return {
            "ok": False,
            "error": "iteration_series_policy_version_incompatible",
            "series_policy_version": row.get("policy_version"),
            "expected_policy_version": ITERATION_POLICY_VERSION,
        }
    return {
        "ok": True,
        "series_id": str(row["id"]),
        "series": row,
        "resolved_rule": "latest_active_series_for_program",
    }


def resolve_repair_campaign_run_id(
    client: Any,
    raw: str,
    *,
    program_id: str,
    latest_success: bool = False,
    series: dict[str, Any] | None = None,
    program: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Resolve repair campaign run id from explicit UUID or selector tokens.

    Tokens: latest, latest-success, latest-for-program, latest-compatible.
    `latest_success` is legacy; if True and raw is `latest`, same as latest-success.
    """
    token = repair_campaign_selector_token(raw)
    if token is None:
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
        prog = program or dbrec.fetch_research_program(client, program_id=program_id)
        if not prog:
            return {"ok": False, "error": "program_not_found", "program_id": program_id}
        if _program_archived(prog):
            return {
                "ok": False,
                "error": "program_archived_run_resolution_blocked",
                "program_id": program_id,
            }
        if latest_success:
            if not _run_success_eligible(row):
                return {
                    "ok": False,
                    "error": "repair_campaign_run_not_success_eligible",
                    "run_id": rid,
                    "status": row.get("status"),
                }
        return {
            "ok": True,
            "repair_campaign_run_id": rid,
            "run": row,
            "resolved_rule": "explicit_uuid",
        }

    eff = _norm_token(raw)
    if eff == SELECTOR_LATEST and latest_success:
        eff = SELECTOR_LATEST_SUCCESS

    if eff == SELECTOR_LATEST:
        rows = _list_runs_for_program(client, program_id=program_id)
        if not rows:
            return {
                "ok": False,
                "error": "no_matching_repair_campaign_for_program",
                "program_id": program_id,
                "selector": eff,
            }
        chosen = rows[0]
        return {
            "ok": True,
            "repair_campaign_run_id": str(chosen["id"]),
            "run": chosen,
            "resolved_rule": "latest_by_created_at",
        }

    prog = program or dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    if _program_archived(prog):
        return {
            "ok": False,
            "error": "program_archived_run_resolution_blocked",
            "program_id": program_id,
        }

    if eff in (SELECTOR_LATEST_SUCCESS, SELECTOR_LATEST_FOR_PROGRAM):
        rows = _list_runs_for_program(client, program_id=program_id)
        rows = [r for r in rows if _run_success_eligible(r)]
        if not rows:
            return {
                "ok": False,
                "error": "no_matching_repair_campaign_for_program",
                "program_id": program_id,
                "selector": eff,
            }
        chosen = rows[0]
        return {
            "ok": True,
            "repair_campaign_run_id": str(chosen["id"]),
            "run": chosen,
            "resolved_rule": f"{eff}_by_created_at",
        }

    if eff == SELECTOR_LATEST_COMPATIBLE:
        if not series:
            return {
                "ok": False,
                "error": "series_context_required_for_latest_compatible",
                "hint": "Resolve an active iteration series first or pass series row.",
            }
        rows = _list_runs_for_program(client, program_id=program_id)
        compat = [
            r
            for r in rows
            if _run_compatible_with_series(r, program_id=program_id, series=series)
        ]
        if not compat:
            return {
                "ok": False,
                "error": "no_compatible_repair_campaign_for_program",
                "program_id": program_id,
                "selector": eff,
                "series_id": str(series.get("id") or ""),
            }
        chosen = compat[0]
        return {
            "ok": True,
            "repair_campaign_run_id": str(chosen["id"]),
            "run": chosen,
            "resolved_rule": "latest_compatible_completed_with_final_decision",
        }

    if eff == SELECTOR_FROM_LATEST_PAIR:
        return {
            "ok": False,
            "error": "use_resolve_repair_campaign_latest_pair",
            "selector": eff,
        }

    return {"ok": False, "error": "unsupported_repair_campaign_selector", "selector": eff}


def resolve_repair_campaign_latest_pair(
    client: Any,
    *,
    program_id: str,
    series: dict[str, Any] | None = None,
    compatible: bool = True,
    program: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Two most recent eligible runs, oldest first (for trend / diff tooling)."""
    prog = program or dbrec.fetch_research_program(client, program_id=program_id)
    if not prog:
        return {"ok": False, "error": "program_not_found", "program_id": program_id}
    if _program_archived(prog):
        return {
            "ok": False,
            "error": "program_archived_run_resolution_blocked",
            "program_id": program_id,
        }
    rows = _list_runs_for_program(client, program_id=program_id)
    if compatible:
        if not series:
            return {
                "ok": False,
                "error": "series_context_required_for_compatible_pair",
            }
        rows = [
            r
            for r in rows
            if _run_compatible_with_series(r, program_id=program_id, series=series)
        ]
    else:
        rows = [r for r in rows if _run_success_eligible(r)]
    if len(rows) < 2:
        return {
            "ok": False,
            "error": "insufficient_runs_for_pair",
            "n_found": len(rows),
            "program_id": program_id,
        }
    newer, older = rows[0], rows[1]
    return {
        "ok": True,
        "repair_campaign_run_ids": [str(older["id"]), str(newer["id"])],
        "runs": [older, newer],
        "resolved_rule": "from_latest_pair"
        + ("_compatible" if compatible else "_success_only"),
    }
