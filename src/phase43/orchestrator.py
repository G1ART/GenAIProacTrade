"""Phase 43 orchestrator — bounded backfill, audit, Phase 41/42 Supabase-fresh retest."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.client import get_supabase_client

from phase37.persistence import write_json
from phase41.pit_rerun import run_phase41_falsifier_pit
from phase42.orchestrator import run_phase42_evidence_accumulation
from phase43.before_after_audit import build_before_after_row_audit
from phase43.filing_audit import filing_evidence_snapshot
from phase43.filing_backfill import run_bounded_filing_backfill_for_cohort
from phase43.phase44_recommend import recommend_phase44_after_phase43
from phase43.sector_audit import sector_evidence_snapshot
from phase43.sector_backfill import run_bounded_sector_hydration_for_cohort
from phase43.target_cohort import load_targets_from_phase42_supabase_bundle, merge_fixture_residual_from_phase41_bundle


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_phase43_targeted_substrate_backfill(
    settings: Any,
    *,
    phase42_supabase_bundle_in: str,
    universe_name: str,
    phase41_bundle_in: str | None = None,
    state_change_scores_limit: int = 50_000,
    baseline_run_id: str = "",
    filing_index_limit: int = 200,
    max_filing_cik_repairs: int = 8,
) -> dict[str, Any]:
    p42_path = Path(phase42_supabase_bundle_in)
    bundle_in = _load_json(p42_path)
    if not bundle_in.get("ok"):
        return {
            "ok": False,
            "phase": "phase43_targeted_substrate_backfill",
            "error": "input_phase42_bundle_not_ok",
        }

    gate_before = dict(bundle_in.get("promotion_gate_phase42") or {})
    scorecard_before = dict(bundle_in.get("family_evidence_scorecard") or {})
    stable_before = str(bundle_in.get("stable_run_digest") or "")

    p41_default = bundle_in.get("phase41_bundle_path") or ""
    p41_path = Path(phase41_bundle_in.strip() or str(p41_default))
    if not p41_path.is_file():
        return {
            "ok": False,
            "phase": "phase43_targeted_substrate_backfill",
            "error": "phase41_bundle_missing",
            "path": str(p41_path),
        }
    bundle41 = _load_json(p41_path)

    targets = load_targets_from_phase42_supabase_bundle(bundle_in)
    merge_fixture_residual_from_phase41_bundle(targets, bundle41)

    client = get_supabase_client(settings)

    def _snap_filing() -> list[dict[str, Any]]:
        return [
            filing_evidence_snapshot(
                client,
                cik=str(t.get("cik") or ""),
                signal_available_date=str(t.get("signal_available_date") or ""),
                filing_index_limit=filing_index_limit,
            )
            for t in targets
        ]

    def _snap_sector() -> list[dict[str, Any]]:
        return [sector_evidence_snapshot(client, symbol=str(t.get("symbol") or "")) for t in targets]

    filing_before = _snap_filing()
    sector_before = _snap_sector()

    filing_action = run_bounded_filing_backfill_for_cohort(
        settings,
        client,
        targets,
        max_cik_repairs=max_filing_cik_repairs,
    )
    sector_action = run_bounded_sector_hydration_for_cohort(
        settings,
        universe_name=universe_name,
        targets=targets,
    )

    filing_after = _snap_filing()
    sector_after = _snap_sector()

    before_after_row_audit = build_before_after_row_audit(
        targets,
        filing_before=filing_before,
        filing_after=filing_after,
        sector_before=sector_before,
        sector_after=sector_after,
    )

    fixture_for_pit = [
        {
            "symbol": t.get("symbol"),
            "cik": t.get("cik"),
            "signal_available_date": t.get("signal_available_date"),
            "residual_join_bucket": t.get("residual_join_bucket"),
        }
        for t in targets
    ]

    pit = run_phase41_falsifier_pit(
        client,
        universe_name=universe_name,
        state_change_scores_limit=state_change_scores_limit,
        baseline_run_id=baseline_run_id.strip() or None,
        fixture_rows=fixture_for_pit,
        filing_index_limit=filing_index_limit,
    )

    phase41_rerun = {
        "ok": bool(pit.get("ok")),
        "pit_execution": pit,
        "error": pit.get("error"),
    }

    td = Path(tempfile.mkdtemp(prefix="phase43_phase42_"))
    try:
        rtemplate = Path("data/research_engine")
        for name in ("hypotheses_v1.json", "promotion_gate_v1.json"):
            src = rtemplate / name
            if src.is_file():
                shutil.copy(src, td / name)
            elif name == "hypotheses_v1.json":
                (td / name).write_text("[]", encoding="utf-8")

        minimal_p41 = {
            "ok": pit.get("ok", True),
            "phase": "phase41_falsifier_substrate",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "universe_name": universe_name,
            "pit_execution": pit,
        }
        p41_json = td / "phase41_rerun_minimal.json"
        write_json(p41_json, minimal_p41)

        p42_out = run_phase42_evidence_accumulation(
            settings,
            phase41_bundle_in=str(p41_json.resolve()),
            research_data_dir=str(td),
            use_supabase=True,
            filing_index_limit=filing_index_limit,
            bundle_out_ref="phase42_after_phase43.json",
            explanation_out=str(td / "expl_v5_tmp.md"),
            gate_history_filename="promotion_gate_history_v1.json",
        )
    finally:
        shutil.rmtree(td, ignore_errors=True)

    gate_after = dict((p42_out or {}).get("promotion_gate_phase42") or {})
    scorecard_after = dict((p42_out or {}).get("family_evidence_scorecard") or {})
    stable_after = str((p42_out or {}).get("stable_run_digest") or "")

    p44 = recommend_phase44_after_phase43(
        before_after_row_audit=before_after_row_audit,
        scorecard_before=scorecard_before,
        scorecard_after=scorecard_after,
        gate_before=gate_before,
        gate_after=gate_after,
    )

    core: dict[str, Any] = {
        "ok": bool(pit.get("ok")) and bool(p42_out.get("ok")),
        "phase": "phase43_targeted_substrate_backfill",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input_phase42_supabase_bundle_path": str(p42_path.resolve()),
        "phase41_bundle_path_used": str(p41_path.resolve()),
        "universe_name": universe_name,
        "target_cohort": targets,
        "backfill_actions": {"filing": filing_action, "sector": sector_action},
        "before_after_row_audit": before_after_row_audit,
        "phase41_rerun_after_backfill": phase41_rerun,
        "phase42_rerun_after_backfill": p42_out,
        "phase42_rerun_used_supabase_fresh": True,
        "scorecard_before": scorecard_before,
        "scorecard_after": scorecard_after,
        "gate_before": gate_before,
        "gate_after": gate_after,
        "stable_run_digest_before": stable_before,
        "stable_run_digest_after": stable_after,
        "phase44": p44,
    }
    return core
