"""End-to-end public-core operator cycle (no premium dependency)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import PROJECT_ROOT


def default_cycle_out_dir() -> Path:
    return PROJECT_ROOT / "docs" / "public_core_cycle" / "latest"


def build_operator_plain_language_packet(
    *,
    state_change_run_id: str,
    universe_name: str,
    stages: list[dict[str, Any]],
    overlay_summary: dict[str, Any],
) -> dict[str, Any]:
    wl_st = next((s for s in stages if s.get("name") == "scanner_watchlist"), {})
    wl_out = wl_st.get("out") or {}
    return {
        "what_changed": (
            f"Public-core cycle for universe={universe_name} anchored at state_change_run_id={state_change_run_id}. "
            "Ran: harness inputs → investigation memos → outlier casebook → daily watchlist snapshot."
        ),
        "why_this_matters": (
            "Produces one auditable chain from deterministic state-change signals to review-oriented messages "
            "without using premium overlays in ranking or scores."
        ),
        "what_remains_unknown": (
            "Premium transcript/estimates paths are optional seams; memo wording depends on model/config; "
            "an empty watchlist is valid when priority gates exclude all candidates."
        ),
        "watchlist_entries": wl_out.get("watchlist_entries"),
        "scanner_run_id": wl_out.get("scanner_run_id"),
        "premium_overlay_snapshot": overlay_summary,
    }


def run_public_core_cycle(
    client: Any,
    settings: Any,
    *,
    universe: str,
    state_change_run_id: Optional[str] = None,
    ensure_state_change: bool = False,
    factor_version: str = "v1",
    state_change_limit: int = 200,
    harness_limit: int = 500,
    memo_limit: int = 500,
    casebook_candidate_limit: int = 600,
    scanner_candidate_limit: int = 500,
    scanner_top_n: int = 15,
    min_priority_score: float = 20.0,
    max_candidate_rank: int = 60,
    as_of_calendar_date: Optional[str] = None,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    from casebook.build_run import run_outlier_casebook_build
    from db import records as dbrec
    from harness.input_materializer import materialize_inputs_for_run
    from harness.run_batch import generate_memos_for_run
    from scanner.daily_build import run_daily_scanner_build
    from sources.reporting import build_source_registry_report
    from sources.transcripts_ingest import report_transcripts_overlay_status
    from state_change.reports import build_state_change_run_report
    from state_change.runner import run_state_change

    _ = settings  # reserved for future OPENAI / rate limits
    dest = out_dir or default_cycle_out_dir()
    dest.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    stages: list[dict[str, Any]] = []
    warnings: list[str] = []

    rid = state_change_run_id or dbrec.fetch_latest_state_change_run_id(
        client, universe_name=universe
    )

    if not rid and ensure_state_change:
        sc_out = run_state_change(
            client,
            universe_name=universe,
            factor_version=factor_version,
            limit=state_change_limit,
            dry_run=False,
            include_nullable_overlays=False,
        )
        stages.append(
            {"name": "state_change_build", "status": sc_out.get("status"), "out": sc_out}
        )
        if sc_out.get("status") == "completed":
            rid = str(sc_out.get("run_id") or "")
        else:
            warnings.append(f"state_change_build:{sc_out.get('status')}")

    if not rid:
        summary = {
            "ok": False,
            "error": "no_state_change_run",
            "hint": "Pass --state-change-run-id or use --ensure-state-change (requires factor panels)",
            "universe": universe,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stages": stages,
            "warnings": warnings,
        }
        (dest / "cycle_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return summary

    sc_report = build_state_change_run_report(
        client, run_id=rid, candidates_limit=30
    )
    stages.append(
        {
            "name": "state_change_report",
            "status": "success" if sc_report.get("ok") else "warning",
            "out": {"ok": sc_report.get("ok"), "run_id": rid},
        }
    )

    def _safe(name: str, fn: Any) -> Any:
        try:
            out = fn()
            st = "success"
            if isinstance(out, dict) and out.get("errors"):
                st = "warning"
            if isinstance(out, dict) and out.get("error"):
                st = "failed"
            stages.append({"name": name, "status": st, "out": out})
            return out
        except Exception as e:  # noqa: BLE001
            stages.append({"name": name, "status": "failed", "error": str(e)})
            warnings.append(f"{name}:{e}")
            return None

    _safe(
        "harness_inputs",
        lambda: materialize_inputs_for_run(client, run_id=rid, limit=harness_limit),
    )
    _safe(
        "investigation_memos",
        lambda: generate_memos_for_run(
            client,
            run_id=rid,
            limit=memo_limit,
            force_new_memo_version=False,
        ),
    )
    _safe(
        "outlier_casebook",
        lambda: run_outlier_casebook_build(
            client,
            state_change_run_id=rid,
            universe_name=universe,
            candidate_limit=casebook_candidate_limit,
        ),
    )
    as_of = as_of_calendar_date or datetime.now(timezone.utc).date().isoformat()
    _safe(
        "scanner_watchlist",
        lambda: run_daily_scanner_build(
            client,
            state_change_run_id=rid,
            universe_name=universe,
            as_of_calendar_date=as_of,
            candidate_scan_limit=scanner_candidate_limit,
            top_n=scanner_top_n,
            min_priority_score=min_priority_score,
            max_candidate_rank=max_candidate_rank,
        ),
    )

    overlay = {
        "transcripts_overlay": report_transcripts_overlay_status(client),
        "source_registry_report": build_source_registry_report(client),
    }
    packet = build_operator_plain_language_packet(
        state_change_run_id=rid,
        universe_name=universe,
        stages=stages,
        overlay_summary=overlay,
    )
    op_health = {"operational_runs_recent": dbrec.fetch_operational_runs_recent(client, limit=15)}

    scanner_failed = any(
        s.get("name") == "scanner_watchlist" and s.get("status") == "failed"
        for s in stages
    )
    ok = bool(rid) and not scanner_failed

    summary = {
        "ok": ok,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "universe": universe,
        "state_change_run_id": rid,
        "stages": stages,
        "warnings": warnings,
        "operator_plain_language": packet,
        "overlay_and_registry_summary": overlay,
        "run_health_operational_runs_sample": op_health,
    }
    (dest / "cycle_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    md_lines = [
        "# Public-core operator cycle",
        "",
        f"- Universe: `{universe}`",
        f"- State change run: `{rid}`",
        "",
        "## Stages",
        "",
    ]
    for s in stages:
        md_lines.append(f"- **{s.get('name')}**: {s.get('status')}")
    md_lines.extend(
        [
            "",
            "## Plain-language packet",
            "",
            f"- **What changed**: {packet['what_changed']}",
            f"- **Why this matters**: {packet['why_this_matters']}",
            f"- **What remains unknown**: {packet['what_remains_unknown']}",
            "",
            "## Premium overlay",
            "",
            "Transcript and other premium overlays are optional seams and are not used in deterministic scoring.",
            "",
        ]
    )
    (dest / "operator_packet.md").write_text("\n".join(md_lines), encoding="utf-8")
    return summary


def load_latest_cycle_summary(base: Optional[Path] = None) -> Optional[dict[str, Any]]:
    p = (base or default_cycle_out_dir()) / "cycle_summary.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
