"""Phase 39 orchestrator — hypotheses, lifecycle, adversarial, gate, contract, explanation."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase37.hypothesis_registry import HypothesisStatus, seed_hypothesis_join_key_mismatch_pit
from phase37.persistence import ensure_research_data_dir, write_json
from phase39.adversarial_batch import merge_adversarial_reviews
from phase39.explanation_v2 import render_phase39_explanation_v2_md
from phase39.hypothesis_seeds import all_phase39_hypothesis_seeds
from phase39.lifecycle import apply_lifecycle_transition, normalize_hypothesis_lifecycle_fields
from phase39.phase40_recommend import recommend_phase40_after_phase39
from phase39.pit_family_contract import build_pit_runner_family_contract
from phase39.promotion_gate_phase39 import append_gate_history, build_promotion_gate_phase39

PRIMARY_HID = "hyp_pit_join_key_mismatch_as_of_boundary_v1"
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
    if not isinstance(data, list) or not data:
        return [seed_hypothesis_join_key_mismatch_pit().to_json_dict()]
    return [normalize_hypothesis_lifecycle_fields(dict(h)) for h in data if isinstance(h, dict)]


def _merge_hypothesis_seeds(existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(h.get("hypothesis_id") or ""): h for h in existing}
    for seed in all_phase39_hypothesis_seeds():
        hid = str(seed.get("hypothesis_id") or "")
        if hid not in by_id:
            by_id[hid] = dict(seed)
    return list(by_id.values())


def _apply_primary_lifecycle(hypotheses: list[dict[str, Any]], *, evidence_ref: str) -> None:
    for h in hypotheses:
        if str(h.get("hypothesis_id") or "") != PRIMARY_HID:
            continue
        if str(h.get("status") or "") == HypothesisStatus.UNDER_TEST.value:
            apply_lifecycle_transition(
                h,
                to_status=HypothesisStatus.CHALLENGED.value,
                reason=(
                    "Phase 39: Phase 38 PIT kept join_key_mismatch for 8 rows under baseline, alternate, lag; "
                    "leakage passed; single-family thesis insufficient alone."
                ),
                evidence_ref=evidence_ref,
            )
        break


def _fixture_still_mismatch_all_specs(pit: dict[str, Any]) -> bool:
    rows = pit.get("row_results") or []
    if not rows:
        return False
    for r in rows:
        for col in ("baseline", "alternate_prior_run", "lag_signal_bound"):
            cell = r.get(col) or {}
            oc = str(cell.get("outcome_category") or "")
            if oc == "alternate_spec_not_executed":
                continue
            if oc != "still_join_key_mismatch":
                return False
    return True


def run_phase39_hypothesis_family_expansion(
    *,
    phase38_bundle_in: str = DEFAULT_PHASE38_BUNDLE,
    research_data_dir: str = "data/research_engine",
    explanation_out: str = "docs/operator_closeout/phase39_explanation_surface_v2.md",
    gate_history_filename: str = "promotion_gate_history_v1.json",
) -> dict[str, Any]:
    bpath = Path(phase38_bundle_in)
    p38 = _load_json(bpath) or {}
    pit = p38.get("pit_execution") or {}
    pit_ok = bool(p38.get("ok")) and bool(pit.get("ok", True))
    leak_passed = bool((pit.get("leakage_audit") or {}).get("passed"))
    adv_from_bundle = p38.get("adversarial_review_updated") or {}
    primary_adv_status = str(adv_from_bundle.get("phase38_resolution_status") or "")

    rdir = Path(research_data_dir)
    ensure_research_data_dir(rdir)

    hypotheses = _merge_hypothesis_seeds(_load_hypotheses(rdir))
    # Prefer repo-relative ref in lifecycle audit (avoid absolute paths in JSON)
    evidence_ref = phase38_bundle_in.strip() or str(bpath)
    _apply_primary_lifecycle(hypotheses, evidence_ref=evidence_ref)

    adv_path = rdir / "adversarial_reviews_v1.json"
    adv_raw = _load_json(adv_path)
    adv_list = adv_raw if isinstance(adv_raw, list) else []
    lineage_id = str(
        adv_from_bundle.get("review_id")
        or next(
            (str(a.get("review_id")) for a in adv_list if str(a.get("reviewer_stance")) == "data_lineage_auditor"),
            "",
        )
    )
    adv_merged = merge_adversarial_reviews(adv_list, lineage_auditor_review_id=lineage_id)

    prior_gate_path = rdir / "promotion_gate_v1.json"
    prior_raw = _load_json(prior_gate_path)
    prior_gate = prior_raw if isinstance(prior_raw, dict) else {}

    new_gate = build_promotion_gate_phase39(
        prior_gate=prior_gate,
        hypotheses=hypotheses,
        adversarial_reviews=adv_merged,
        pit_leakage_passed=leak_passed,
        primary_adversarial_status=primary_adv_status,
    )

    hist_path = str((rdir / gate_history_filename).resolve())
    append_gate_history(hist_path, prior_record=prior_gate, new_record=new_gate)

    write_json(rdir / "hypotheses_v1.json", hypotheses)
    write_json(adv_path, adv_merged)
    write_json(prior_gate_path, new_gate)

    contract = build_pit_runner_family_contract(phase38_bundle_path=phase38_bundle_in)
    p40 = recommend_phase40_after_phase39(bundle={})

    p38_summary = {
        "pit_ok": pit_ok,
        "leakage_passed": leak_passed,
        "experiment_id": pit.get("experiment_id"),
        "phase38_resolution_status": primary_adv_status,
        "fixture_still_mismatch_all_specs": _fixture_still_mismatch_all_specs(pit),
    }

    core_bundle: dict[str, Any] = {
        "ok": True,
        "phase": "phase39_hypothesis_family_expansion",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase38_bundle_ref": phase38_bundle_in,
        "phase38_evidence_summary": p38_summary,
        "hypotheses_after": hypotheses,
        "hypothesis_family_count": len(hypotheses),
        "lifecycle_status_distribution": dict(Counter(str(h.get("status") or "") for h in hypotheses)),
        "adversarial_reviews_after": adv_merged,
        "adversarial_review_count_by_stance": dict(
            Counter(str(r.get("reviewer_stance") or "") for r in adv_merged)
        ),
        "pit_runner_family_contract": contract,
        "promotion_gate_phase39": new_gate,
        "promotion_gate_primary_block_category": new_gate.get("primary_block_category"),
        "promotion_gate_distribution": {str(new_gate.get("primary_block_category") or ""): 1},
        "phase40": p40,
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
    core_bundle["explanation_v2"] = {
        "format": "markdown",
        "path": str(expl_path.resolve()),
    }
    expl_path.write_text(render_phase39_explanation_v2_md(bundle=core_bundle), encoding="utf-8")
    return core_bundle
