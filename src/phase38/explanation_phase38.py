"""Post–Phase 38 explanation surface — reflects executed specs, not generic prototype."""

from __future__ import annotations

import json
from typing import Any


def render_phase38_explanation_md(*, bundle: dict[str, Any]) -> str:
    pit = bundle.get("pit_execution") or {}
    hyp = bundle.get("hypothesis_id") or "hyp_pit_join_key_mismatch_as_of_boundary_v1"
    exp = pit.get("experiment_id", "")
    specs = pit.get("executed_specs") or []
    leakage = pit.get("leakage_audit") or {}
    adv = bundle.get("adversarial_review_updated") or {}
    gate = bundle.get("promotion_gate_v1") or {}
    rows = pit.get("row_results") or []

    lines = [
        f"# Research explanation — after DB-bound PIT (`{hyp}`)",
        "",
        f"**Experiment id:** `{exp}`",
        "",
        "## What was actually tested",
        "",
        "- **Fixture:** 8 residual `state_change_built_but_join_key_mismatch` rows (Phase 37 fixture, loaded from persisted artifact / code).",
        "- **Database:** `issuer_state_change_scores` for resolved `state_change_runs.id` per spec.",
        "",
        "### Specs executed",
        "",
    ]
    for s in specs:
        sk = s.get("spec_key", "")
        lines.append(f"- **`{sk}`**: {s.get('description', '')}")
        if s.get("skipped_reason"):
            lines.append(f"  - *Note:* {s.get('skipped_reason')}")
    lines.extend(
        [
            "",
            "## Row-level outcomes (headline)",
            "",
            f"- **Baseline counts:** `{pit.get('summary_counts', {}).get('baseline')}`",
            f"- **Alternate prior run:** `{pit.get('summary_counts', {}).get('alternate_prior_run')}`",
            f"- **Lag signal bound:** `{pit.get('summary_counts', {}).get('lag_signal_bound')}`",
            "",
            "### Standard rollup (baseline / lag; excludes `alternate_spec_not_executed`)",
            "",
            f"- `{json.dumps(bundle.get('summary_counts_standard') or {}, ensure_ascii=False)}`",
            "",
            "## Leakage audit",
            "",
            f"- **Passed:** `{leakage.get('passed')}`",
            f"- **Violations:** {len(leakage.get('violations') or [])}",
            "- **Rule:** every picked row must satisfy `as_of_date <= signal_bound` for that spec.",
            "",
            "## Adversarial review (evidence-backed)",
            "",
            f"- **Status:** `{adv.get('phase38_resolution_status')}`",
            f"- **Leakage audit passed:** `{adv.get('phase38_leakage_audit_passed')}`",
            f"- **Summary:** {adv.get('phase38_evidence_summary', '')}",
            "",
            "## Promotion gate",
            "",
            f"- **Gate status:** `{gate.get('gate_status')}`",
            f"- **Blocking reasons:** {gate.get('blocking_reasons')}",
            "",
            "## What remains uncertain",
        ]
    )
    if any(
        str((r.get("baseline") or {}).get("outcome_category"))
        == "still_join_key_mismatch"
        for r in rows
    ):
        lines.append(
            "- Under baseline production-equivalent pick, **earliest score as_of remains after signal** "
            "for some rows — economic interpretation of the filing signal vs score grid lag is still an open research question."
        )
    lines.extend(
        [
            "",
            "## Why this is not a buy/sell recommendation",
            "",
            "- No return forecast, position sizing, or price target appears here.",
            "- **Promotion gate is blocked/deferred**; this document is audit and judgment support only.",
            "",
        ]
    )
    return "\n".join(lines)
