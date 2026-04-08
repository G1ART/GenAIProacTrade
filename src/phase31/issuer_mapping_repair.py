"""empty_cik 중 멤버십=레지스트리 CIK 일치·issuer 맵만 깨진 경우 결정적 upsert."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db import records as dbrec
from phase30.empty_cik_cleanup import report_empty_cik_gaps
from research_validation.metrics import norm_cik


def run_deterministic_empty_cik_issuer_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    symbols_limit: int = 20,
    registry_report: dict[str, Any] | None = None,
    materialization_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    client = get_supabase_client(settings)
    rep = report_empty_cik_gaps(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        registry_report=registry_report,
        materialization_report=materialization_report,
    )
    applied: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for d in rep.get("diagnoses") or []:
        if len(applied) >= symbols_limit:
            break
        diag = str(d.get("diagnosis") or "")
        if diag != "issuer_mapping_gap":
            continue
        sym = str(d.get("symbol") or "").upper().strip()
        detail = str(d.get("detail") or "")
        mem_cik = str(d.get("membership_cik") or "").strip()
        reg_cik = str(d.get("registry_cik") or "").strip()
        map_cik = str(d.get("issuer_map_cik") or "").strip()

        if detail == "no_cik_on_issuer_map_for_symbol":
            ref = mem_cik or reg_cik
            if not sym or not ref:
                blocked.append({**d, "reason": "missing_reference_cik"})
                continue
            if mem_cik and reg_cik and norm_cik(mem_cik) != norm_cik(reg_cik):
                blocked.append({**d, "reason": "membership_registry_cik_differ"})
                continue
            nc = norm_cik(ref)
        elif detail == "issuer_map_cik_mismatch":
            if not mem_cik or not map_cik:
                blocked.append({**d, "reason": "incomplete_mapping_fields"})
                continue
            if norm_cik(mem_cik) == norm_cik(map_cik):
                blocked.append({**d, "reason": "not_a_gap_after_reverify"})
                continue
            if reg_cik and norm_cik(mem_cik) != norm_cik(reg_cik):
                blocked.append(
                    {**d, "reason": "unsafe_registry_disagrees_with_membership"}
                )
                continue
            nc = norm_cik(mem_cik)
        else:
            blocked.append({**d, "reason": f"unsupported_detail:{detail}"})
            continue

        now_iso = datetime.now(timezone.utc).isoformat()
        name = sym
        dbrec.upsert_issuer_master(
            client,
            {
                "cik": nc,
                "ticker": sym,
                "company_name": name,
                "sic": None,
                "sic_description": None,
                "latest_known_exchange": None,
                "is_active": True,
                "first_seen_at": now_iso,
                "last_seen_at": now_iso,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
        )
        applied.append(
            {
                "symbol": sym,
                "cik": nc,
                "kind": "upsert_issuer_master_from_empty_cik_gap",
                "detail": detail or diag,
            }
        )

    return {
        "ok": True,
        "universe_name": universe_name,
        "repair": "deterministic_empty_cik_issuer",
        "deterministic_repairs_applied": applied,
        "blocked": blocked,
        "empty_cik_report_summary": {
            "empty_cik_row_count": rep.get("empty_cik_row_count"),
            "as_of_date": rep.get("as_of_date"),
        },
    }
