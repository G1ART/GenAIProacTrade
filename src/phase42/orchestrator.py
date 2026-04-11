"""Phase 42 orchestrator — evidence accumulation from Phase 41 bundle + optional Supabase refresh."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db import records as dbrec
from db.client import get_supabase_client

from phase37.persistence import ensure_research_data_dir, write_json
from phase39.lifecycle import normalize_hypothesis_lifecycle_fields
from phase42.blocker_taxonomy import classify_filing_blocker_cause, classify_sector_blocker_cause
from phase42.evidence_accumulation import (
    build_discrimination_summary,
    build_evidence_density_by_family,
    build_family_evidence_scorecard,
    build_row_level_blockers_from_phase41_substrate,
    extract_fixture_rows_from_phase41_bundle,
    stable_run_digest,
    unchanged_vs_prior_run_digest,
)
from phase42.explanation_v5 import render_phase42_explanation_v5_md
from phase42.hypothesis_narrowing import narrow_families_for_phase42
from phase42.phase43_recommend import recommend_phase43_after_phase42
from phase42.promotion_gate_phase42 import append_gate_history_phase42, build_promotion_gate_phase42

from research_validation.metrics import norm_cik, norm_signal_date

DEFAULT_BUNDLE_OUT_REF = "docs/operator_closeout/phase42_evidence_accumulation_bundle.json"


def _load_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_hypotheses(rdir: Path) -> list[dict[str, Any]]:
    data = _load_json(rdir / "hypotheses_v1.json")
    if not isinstance(data, list):
        return []
    return [normalize_hypothesis_lifecycle_fields(dict(h)) for h in data if isinstance(h, dict)]


def build_row_blockers_supabase(
    client: Any,
    *,
    fixture_rows: list[dict[str, Any]],
    filing_index_limit: int,
) -> list[dict[str, Any]]:
    ciks = sorted({norm_cik(r.get("cik")) for r in fixture_rows})
    filings_by_cik: dict[str, list[dict[str, Any]]] = {}
    for cik in ciks:
        filings_by_cik[cik] = dbrec.fetch_filing_index_rows_for_cik(
            client, cik=cik, limit=filing_index_limit
        )
    symbols = [str(r.get("symbol") or "").upper().strip() for r in fixture_rows]
    meta_by_sym = dbrec.fetch_market_metadata_latest_rows_for_symbols(client, symbols)
    out: list[dict[str, Any]] = []
    for fr in fixture_rows:
        cik = norm_cik(fr.get("cik"))
        sig = norm_signal_date(fr.get("signal_available_date")) or ""
        sym = str(fr.get("symbol") or "").upper().strip()
        meta_row = meta_by_sym.get(sym)
        fc = classify_filing_blocker_cause(
            signal_available_date=sig,
            filing_index_rows=filings_by_cik.get(cik, []),
        )
        sc = classify_sector_blocker_cause(metadata_row=meta_row)
        fc_extra = {k: v for k, v in fc.items() if k != "phase41_equivalent"}
        sc_extra = {k: v for k, v in sc.items() if k != "phase41_equivalent"}
        out.append(
            {
                "symbol": sym,
                "cik": cik,
                "signal_available_date": sig,
                "blocker_replay_source": "supabase_fresh",
                **fc_extra,
                **sc_extra,
            }
        )
    return out


def run_phase42_evidence_accumulation(
    settings: Any,
    *,
    phase41_bundle_in: str,
    research_data_dir: str = "data/research_engine",
    use_supabase: bool = True,
    filing_index_limit: int = 200,
    bundle_out_ref: str = DEFAULT_BUNDLE_OUT_REF,
    explanation_out: str = "docs/operator_closeout/phase42_explanation_surface_v5.md",
    gate_history_filename: str = "promotion_gate_history_v1.json",
) -> dict[str, Any]:
    p41_path = Path(phase41_bundle_in)
    raw41 = _load_json(p41_path)
    if not isinstance(raw41, dict):
        return {
            "ok": False,
            "phase": "phase42_evidence_accumulation",
            "error": "phase41_bundle_missing_or_invalid",
            "path": str(p41_path),
        }

    pit = raw41.get("pit_execution") or {}
    if not pit.get("ok", True):
        return {
            "ok": False,
            "phase": "phase42_evidence_accumulation",
            "error": pit.get("error") or "phase41_pit_not_ok",
            "pit_execution": pit,
        }

    families = pit.get("families_executed") or []
    fixture_rows = extract_fixture_rows_from_phase41_bundle(raw41)

    if use_supabase:
        client = get_supabase_client(settings)
        if not fixture_rows:
            return {
                "ok": False,
                "phase": "phase42_evidence_accumulation",
                "error": "no_fixture_rows_in_phase41_bundle_for_supabase_path",
            }
        row_blockers = build_row_blockers_supabase(
            client, fixture_rows=fixture_rows, filing_index_limit=filing_index_limit
        )
    else:
        row_blockers = build_row_level_blockers_from_phase41_substrate(pit)
        if not row_blockers:
            return {
                "ok": False,
                "phase": "phase42_evidence_accumulation",
                "error": "no_substrate_per_row_in_phase41_pit_use_supabase_or_rerun_phase41",
            }

    disc = build_discrimination_summary(families_executed=families)
    density = build_evidence_density_by_family(
        families_executed=families,
        row_level_blockers=row_blockers,
    )
    scorecard = build_family_evidence_scorecard(
        phase41_pit=pit,
        row_level_blockers=row_blockers,
        discrimination_summary=disc,
    )
    narrowing = narrow_families_for_phase42(
        families_executed=families,
        discrimination_summary=disc,
        row_level_blockers=row_blockers,
        evidence_density=density,
    )

    rdir = Path(research_data_dir)
    ensure_research_data_dir(rdir)
    hypotheses = _load_hypotheses(rdir)

    prior_gate_path = rdir / "promotion_gate_v1.json"
    prior_gate = _load_json(prior_gate_path)
    if not isinstance(prior_gate, dict):
        prior_gate = {}

    new_gate = build_promotion_gate_phase42(
        prior_gate=prior_gate,
        phase41_pit=pit,
        scorecard=scorecard,
        discrimination_summary=disc,
        narrowing=narrowing,
        hypotheses=hypotheses,
    )

    hist_path = str((rdir / gate_history_filename).resolve())
    append_gate_history_phase42(hist_path, prior_record=prior_gate, new_record=new_gate)
    write_json(prior_gate_path, new_gate)

    partial_for_p43: dict[str, Any] = {"promotion_gate_phase42": new_gate}
    p43 = recommend_phase43_after_phase42(bundle=partial_for_p43)

    core_for_digest = {
        "family_evidence_scorecard": scorecard,
        "discrimination_summary": disc,
        "promotion_gate_phase42": new_gate,
    }
    digest = stable_run_digest(bundle_core=core_for_digest)

    core: dict[str, Any] = {
        "ok": True,
        "phase": "phase42_evidence_accumulation",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase41_bundle_path": str(p41_path.resolve()),
        "bundle_out_ref": bundle_out_ref.strip() or DEFAULT_BUNDLE_OUT_REF,
        "pit_execution": pit,
        "row_level_blockers": row_blockers,
        "family_evidence_scorecard": scorecard,
        "evidence_density_by_family": density,
        "discrimination_summary": disc,
        "hypothesis_narrowing": narrowing,
        "family_rerun_unchanged_digest": unchanged_vs_prior_run_digest(raw41),
        "stable_run_digest": digest,
        "promotion_gate_phase42": new_gate,
        "promotion_gate_primary_block_category": new_gate.get("primary_block_category"),
        "phase43": p43,
        "promotion_gate_history_path": hist_path,
        "persistent_writes": {
            "promotion_gate_v1": str(prior_gate_path.resolve()),
            "promotion_gate_history_v1": hist_path,
        },
    }

    expl_path = Path(explanation_out)
    expl_path.parent.mkdir(parents=True, exist_ok=True)
    core["explanation_v5"] = {"format": "markdown", "path": str(expl_path.resolve())}
    expl_path.write_text(render_phase42_explanation_v5_md(bundle=core), encoding="utf-8")
    return core
