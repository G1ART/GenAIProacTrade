"""Phase 41 orchestrator — falsifier substrate PIT, lifecycle evidence, gate v4, explanation v4."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.client import get_supabase_client

from phase37.persistence import ensure_research_data_dir, write_json
from phase39.lifecycle import normalize_hypothesis_lifecycle_fields
from phase41.adversarial_phase41 import merge_phase41_adversarial, phase41_substrate_reviews
from phase41.explanation_v4 import render_phase41_explanation_v4_md
from phase41.lifecycle_phase41 import apply_phase41_substrate_evidence
from phase41.phase42_recommend import recommend_phase42_after_phase41
from phase41.pit_rerun import run_phase41_falsifier_pit
from phase41.promotion_gate_phase41 import append_gate_history_phase41, build_promotion_gate_phase41

DEFAULT_BUNDLE_OUT = "docs/operator_closeout/phase41_falsifier_substrate_bundle.json"


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


def _extract_family(pit: dict[str, Any], family_id: str) -> dict[str, Any] | None:
    for f in pit.get("families_executed") or []:
        if str(f.get("family_id") or "") == family_id:
            return dict(f)
    return None


def _compare_outcome_digests(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    if not before or not after:
        return {"note": "missing before or after family payload"}
    bspec = before.get("summary_counts_by_spec") or {}
    aspec = after.get("summary_counts_by_spec") or {}
    return {
        "before_summary_counts_by_spec": bspec,
        "after_summary_counts_by_spec": aspec,
        "spec_keys_before": before.get("spec_keys_executed"),
        "spec_keys_after": after.get("spec_keys_executed"),
        "unchanged_rollups": bspec == aspec,
    }


def build_before_after_payload(
    *,
    phase40_bundle_path: str | None,
    phase41_pit: dict[str, Any],
) -> dict[str, Any]:
    if not (phase40_bundle_path or "").strip():
        return {"note": "no phase40 bundle path provided"}
    p = Path(phase40_bundle_path)
    b = _load_json(p)
    if not isinstance(b, dict):
        return {"note": "phase40 bundle missing or invalid", "path": str(p)}
    pit40 = b.get("pit_execution") or {}
    out: dict[str, Any] = {}
    for fid in ("signal_filing_boundary_v1", "issuer_sector_reporting_cadence_v1"):
        bf = _extract_family(pit40, fid)
        af = _extract_family(phase41_pit, fid)
        out[fid] = _compare_outcome_digests(bf, af)
    return out


def run_phase41_falsifier_substrate(
    settings: Any,
    *,
    universe_name: str,
    state_change_scores_limit: int = 50_000,
    baseline_run_id: str = "",
    research_data_dir: str = "data/research_engine",
    phase40_bundle_in: str = "",
    bundle_out_ref: str = DEFAULT_BUNDLE_OUT,
    explanation_out: str = "docs/operator_closeout/phase41_explanation_surface_v4.md",
    gate_history_filename: str = "promotion_gate_history_v1.json",
    filing_index_limit: int = 200,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    pit = run_phase41_falsifier_pit(
        client,
        universe_name=universe_name,
        state_change_scores_limit=state_change_scores_limit,
        baseline_run_id=baseline_run_id.strip() or None,
        filing_index_limit=filing_index_limit,
    )

    rdir = Path(research_data_dir)
    ensure_research_data_dir(rdir)
    hypotheses = _load_hypotheses(rdir)
    if not hypotheses:
        return {
            "ok": False,
            "phase": "phase41_falsifier_substrate",
            "error": "hypotheses_v1.json missing or empty",
            "pit_execution": pit,
        }

    if not pit.get("ok"):
        return {
            "ok": False,
            "phase": "phase41_falsifier_substrate",
            "pit_execution": pit,
            "error": pit.get("error"),
        }

    evidence_ref = bundle_out_ref.strip() or DEFAULT_BUNDLE_OUT
    apply_phase41_substrate_evidence(
        hypotheses,
        pit_result=pit,
        evidence_ref=evidence_ref,
    )

    adv_path = rdir / "adversarial_reviews_v1.json"
    adv_raw = _load_json(adv_path)
    adv_list = adv_raw if isinstance(adv_raw, list) else []
    new_rev = phase41_substrate_reviews(pit_result=pit)
    adv_merged = merge_phase41_adversarial(adv_list, new_rev)

    prior_gate_path = rdir / "promotion_gate_v1.json"
    prior_gate = _load_json(prior_gate_path)
    if not isinstance(prior_gate, dict):
        prior_gate = {}

    new_gate = build_promotion_gate_phase41(
        prior_gate=prior_gate,
        pit_result=pit,
        hypotheses=hypotheses,
    )

    hist_path = str((rdir / gate_history_filename).resolve())
    append_gate_history_phase41(hist_path, prior_record=prior_gate, new_record=new_gate)

    write_json(rdir / "hypotheses_v1.json", hypotheses)
    write_json(adv_path, adv_merged)
    write_json(prior_gate_path, new_gate)

    p42 = recommend_phase42_after_phase41(bundle={})
    before_after = build_before_after_payload(
        phase40_bundle_path=phase40_bundle_in.strip() or None,
        phase41_pit=pit,
    )

    life_after = {str(h.get("hypothesis_id") or ""): str(h.get("status") or "") for h in hypotheses}
    core: dict[str, Any] = {
        "ok": True,
        "phase": "phase41_falsifier_substrate",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "universe_name": universe_name,
        "pit_execution": pit,
        "family_rerun_before_after": before_after,
        "lifecycle_after": life_after,
        "lifecycle_status_distribution": dict(Counter(life_after.values())),
        "promotion_gate_phase41": new_gate,
        "phase42": p42,
        "promotion_gate_history_path": hist_path,
        "persistent_writes": {
            "hypotheses_v1": str((rdir / "hypotheses_v1.json").resolve()),
            "adversarial_reviews_v1": str(adv_path.resolve()),
            "promotion_gate_v1": str(prior_gate_path.resolve()),
            "promotion_gate_history_v1": hist_path,
        },
    }

    expl_path = Path(explanation_out)
    expl_path.parent.mkdir(parents=True, exist_ok=True)
    core["explanation_v4"] = {"format": "markdown", "path": str(expl_path.resolve())}
    expl_path.write_text(render_phase41_explanation_v4_md(bundle=core), encoding="utf-8")
    return core
