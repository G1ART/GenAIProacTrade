"""Phase 38 orchestrator — DB PIT + gate + casebook + explanation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.client import get_supabase_client

from phase37.adversarial_review import seed_adversarial_review_for_pit_hypothesis
from phase37.casebook import seed_casebook_entries
from phase37.persistence import ensure_research_data_dir, write_json
from phase38.adversarial_update import build_updated_adversarial_review
from phase38.explanation_phase38 import render_phase38_explanation_md
from phase38.phase39_recommend import recommend_phase39_after_phase38
from phase38.pit_runner import run_db_bound_pit_for_join_mismatch_fixture
from phase38.promotion_gate_v1 import build_promotion_gate_v1

HYPOTHESIS_ID = "hyp_pit_join_key_mismatch_as_of_boundary_v1"

_STANDARD = (
    "still_join_key_mismatch",
    "reclassified_to_joined",
    "reclassified_to_other_exclusion",
    "invalid_due_to_leakage_or_non_pit",
)


def _rollup_standard(row_results: list[dict[str, Any]], col_name: str) -> dict[str, int]:
    c = {k: 0 for k in _STANDARD}
    for r in row_results:
        oc = str((r.get(col_name) or {}).get("outcome_category") or "")
        if oc == "alternate_spec_not_executed":
            continue
        if oc in c:
            c[oc] += 1
    return c


def _load_json_list(path: Path) -> list[Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else None
    except (OSError, json.JSONDecodeError):
        return None


def run_phase38_db_bound_pit_runner(
    settings: Any,
    *,
    universe_name: str,
    state_change_scores_limit: int = 50_000,
    lag_calendar_days: int = 7,
    baseline_run_id: str = "",
    alternate_run_id: str = "",
    research_data_dir: str = "data/research_engine",
    explanation_out: str = "docs/operator_closeout/phase38_explanation_surface.md",
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    pit = run_db_bound_pit_for_join_mismatch_fixture(
        client,
        universe_name=universe_name,
        state_change_scores_limit=state_change_scores_limit,
        lag_calendar_days=lag_calendar_days,
        baseline_run_id=baseline_run_id.strip() or None,
        alternate_run_id=alternate_run_id.strip() or None,
    )

    rdir = Path(research_data_dir)
    adv_path = rdir / "adversarial_reviews_v1.json"
    cb_path = rdir / "casebook_v1.json"

    adv_list = _load_json_list(adv_path)
    if not adv_list:
        adv_list = [seed_adversarial_review_for_pit_hypothesis().to_json_dict()]
    orig = next(
        (a for a in adv_list if str(a.get("hypothesis_id") or "") == HYPOTHESIS_ID),
        adv_list[0],
    )

    if not pit.get("ok"):
        return {
            "ok": False,
            "phase": "phase38_db_bound_pit_runner",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "pit_execution": pit,
            "error": pit.get("error"),
        }

    row_results = list(pit.get("row_results") or [])
    summary_std = {
        "baseline": _rollup_standard(row_results, "baseline"),
        "lag_signal_bound": _rollup_standard(row_results, "lag_signal_bound"),
        "alternate_prior_run": _rollup_standard(row_results, "alternate_prior_run"),
    }

    adv_up = build_updated_adversarial_review(original=orig, pit_result=pit)
    gate = build_promotion_gate_v1(
        hypothesis_id=HYPOTHESIS_ID,
        pit_result=pit,
        adversarial_updated=adv_up,
    )
    p39 = recommend_phase39_after_phase38(pit_result=pit)

    casebook = _load_json_list(cb_path)
    if not casebook:
        casebook = seed_casebook_entries()
    cb_summary: dict[str, Any] = {
        "case_id_updated": "case_pit_no_sc_join_key_mismatch_8",
        "fields_added": [],
    }
    for c in casebook:
        if str(c.get("case_id") or "") != "case_pit_no_sc_join_key_mismatch_8":
            continue
        md = dict(c.get("metadata") or {})
        md["phase38_pit_experiment_id"] = pit.get("experiment_id")
        md["phase38_baseline_summary"] = pit.get("summary_counts", {}).get("baseline")
        md["phase38_lag_summary"] = pit.get("summary_counts", {}).get("lag_signal_bound")
        md["phase38_alternate_summary"] = pit.get("summary_counts", {}).get(
            "alternate_prior_run"
        )
        md["phase38_leakage_audit_passed"] = (pit.get("leakage_audit") or {}).get("passed")
        md["better_understood"] = True
        md["phase38_narrative"] = (
            "Residual 8 rows replayed against live issuer_state_change_scores; "
            "see phase38 bundle row_results and summary_counts."
        )
        c["metadata"] = md
        cb_summary["fields_added"] = list(md.keys())
        break

    ensure_research_data_dir(rdir)
    new_adv = []
    replaced = False
    for a in adv_list:
        if str(a.get("hypothesis_id") or "") == HYPOTHESIS_ID:
            new_adv.append(adv_up)
            replaced = True
        else:
            new_adv.append(a)
    if not replaced:
        new_adv.append(adv_up)
    write_json(adv_path, new_adv)
    write_json(cb_path, casebook)
    gate_path = rdir / "promotion_gate_v1.json"
    write_json(gate_path, gate)

    bundle_core = {
        "ok": True,
        "phase": "phase38_db_bound_pit_runner",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "universe_name": universe_name,
        "hypothesis_id": HYPOTHESIS_ID,
        "pit_execution": pit,
        "summary_counts_standard": summary_std,
        "adversarial_review_updated": adv_up,
        "promotion_gate_v1": gate,
        "casebook_update_summary": cb_summary,
        "phase39": p39,
        "persistent_writes": {
            "adversarial_reviews_v1": str(adv_path.resolve()),
            "casebook_v1": str(cb_path.resolve()),
            "promotion_gate_v1": str(gate_path.resolve()),
        },
    }

    expl_p = Path(explanation_out)
    expl_p.parent.mkdir(parents=True, exist_ok=True)
    expl_p.write_text(
        render_phase38_explanation_md(bundle=bundle_core),
        encoding="utf-8",
    )
    bundle_core["explanation_surface"] = {
        "format": "markdown",
        "path": str(expl_p.resolve()),
    }
    return bundle_core
