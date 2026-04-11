"""Phase 40 orchestrator — DB PIT families, lifecycle, adversarial, gate, explanation v3."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.client import get_supabase_client

from phase37.persistence import ensure_research_data_dir, write_json
from phase39.lifecycle import normalize_hypothesis_lifecycle_fields
from phase40.adversarial_family import BATCH_TAG, family_execution_reviews, merge_family_adversarial
from phase40.contract_manifest import build_phase40_contract_manifest
from phase40.explanation_v3 import render_phase40_explanation_v3_md
from phase40.family_execution import run_phase40_pit_families
from phase40.lifecycle_phase40 import apply_phase40_hypothesis_lifecycle
from phase40.phase41_recommend import recommend_phase41_after_phase40
from phase40.promotion_gate_phase40 import append_gate_history_phase40, build_promotion_gate_phase40

DEFAULT_PHASE38_BUNDLE = "docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json"


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


def run_phase40_family_spec_bindings(
    settings: Any,
    *,
    universe_name: str,
    state_change_scores_limit: int = 50_000,
    lag_calendar_days: int = 7,
    baseline_run_id: str = "",
    alternate_run_id: str = "",
    research_data_dir: str = "data/research_engine",
    governance_registry_path: str = "data/research_engine/governance_join_policy_registry_v1.json",
    phase38_bundle_ref: str = DEFAULT_PHASE38_BUNDLE,
    bundle_out_ref: str = "docs/operator_closeout/phase40_family_spec_bindings_bundle.json",
    explanation_out: str = "docs/operator_closeout/phase40_explanation_surface_v3.md",
    gate_history_filename: str = "promotion_gate_history_v1.json",
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    pit = run_phase40_pit_families(
        client,
        universe_name=universe_name,
        state_change_scores_limit=state_change_scores_limit,
        lag_calendar_days=lag_calendar_days,
        baseline_run_id=baseline_run_id.strip() or None,
        alternate_run_id=alternate_run_id.strip() or None,
        governance_registry_path=governance_registry_path,
    )

    rdir = Path(research_data_dir)
    ensure_research_data_dir(rdir)
    hypotheses = _load_hypotheses(rdir)
    if not hypotheses:
        return {
            "ok": False,
            "phase": "phase40_family_spec_bindings",
            "error": "hypotheses_v1.json missing or empty",
            "pit_execution": pit,
        }

    if not pit.get("ok"):
        return {
            "ok": False,
            "phase": "phase40_family_spec_bindings",
            "pit_execution": pit,
            "error": pit.get("error"),
        }

    evidence_ref = bundle_out_ref.strip() or "docs/operator_closeout/phase40_family_spec_bindings_bundle.json"
    apply_phase40_hypothesis_lifecycle(
        hypotheses,
        families_executed=list(pit.get("families_executed") or []),
        evidence_ref=evidence_ref,
    )

    adv_path = rdir / "adversarial_reviews_v1.json"
    adv_raw = _load_json(adv_path)
    adv_list = adv_raw if isinstance(adv_raw, list) else []
    new_rev = family_execution_reviews(families_executed=list(pit.get("families_executed") or []))
    adv_merged = merge_family_adversarial(adv_list, new_rev)

    prior_gate_path = rdir / "promotion_gate_v1.json"
    prior_gate = _load_json(prior_gate_path)
    if not isinstance(prior_gate, dict):
        prior_gate = {}

    new_gate = build_promotion_gate_phase40(
        prior_gate=prior_gate,
        pit_result=pit,
        hypotheses=hypotheses,
        adversarial_reviews=adv_merged,
    )

    hist_path = str((rdir / gate_history_filename).resolve())
    append_gate_history_phase40(hist_path, prior_record=prior_gate, new_record=new_gate)

    write_json(rdir / "hypotheses_v1.json", hypotheses)
    write_json(adv_path, adv_merged)
    write_json(prior_gate_path, new_gate)

    p41 = recommend_phase41_after_phase40(bundle={})
    manifest = build_phase40_contract_manifest(phase38_bundle_ref=phase38_bundle_ref)

    life_after = {str(h.get("hypothesis_id") or ""): str(h.get("status") or "") for h in hypotheses}
    by_family: dict[str, int] = {}
    for r in adv_merged:
        if not r.get(BATCH_TAG):
            continue
        fid = str(r.get("phase40_family_id") or "unknown")
        by_family[fid] = by_family.get(fid, 0) + 1

    core: dict[str, Any] = {
        "ok": True,
        "phase": "phase40_family_spec_bindings",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "universe_name": universe_name,
        "phase38_bundle_ref": phase38_bundle_ref,
        "pit_execution": pit,
        "pit_contract_manifest": manifest,
        "implemented_family_spec_count": pit.get("implemented_family_spec_count"),
        "families_executed_count": pit.get("families_executed_count"),
        "family_level_summary": [
            {
                "family_id": f.get("family_id"),
                "hypothesis_id": f.get("hypothesis_id"),
                "spec_keys": f.get("spec_keys_executed"),
                "leakage_passed": (f.get("leakage_audit") or {}).get("passed"),
                "joined_any_row": f.get("joined_any_row"),
                "summary_counts_by_spec": f.get("summary_counts_by_spec"),
            }
            for f in (pit.get("families_executed") or [])
        ],
        "leakage_audit_by_family": {
            str(f.get("family_id") or ""): (f.get("leakage_audit") or {}).get("passed")
            for f in (pit.get("families_executed") or [])
        },
        "lifecycle_after": life_after,
        "lifecycle_status_distribution": dict(Counter(life_after.values())),
        "adversarial_reviews_after_count": len(adv_merged),
        "adversarial_review_count_by_family_tag": by_family,
        "promotion_gate_phase40": new_gate,
        "phase41": p41,
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
    core["explanation_v3"] = {"format": "markdown", "path": str(expl_path.resolve())}
    expl_path.write_text(render_phase40_explanation_v3_md(bundle=core), encoding="utf-8")
    return core
