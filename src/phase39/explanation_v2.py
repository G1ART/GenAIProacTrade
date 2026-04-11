"""Explanation layer v2 — competing hypotheses, tested vs untested, no buy/sell."""

from __future__ import annotations

from typing import Any


def render_phase39_explanation_v2_md(*, bundle: dict[str, Any]) -> str:
    hyps = bundle.get("hypotheses_after") or []
    pit_contract = bundle.get("pit_runner_family_contract") or {}
    gate = bundle.get("promotion_gate_phase39") or {}
    p38 = bundle.get("phase38_evidence_summary") or {}
    p40 = bundle.get("phase40") or {}

    lines = [
        "# Research explanation (Phase 39 v2)",
        "",
        "_This document supports human judgment. It is **not** a buy, sell, or hold recommendation "
        "and does not constitute investment advice._",
        "",
        "## What Phase 38 showed (ground truth)",
        "",
        f"- PIT loop ok: `{p38.get('pit_ok')}`",
        f"- Leakage audit passed: `{p38.get('leakage_passed')}`",
        f"- Fixture rows: `{p38.get('fixture_still_mismatch_all_specs')}` still `join_key_mismatch` under "
        "baseline, alternate prior run, and lag signal bound.",
        f"- Adversarial (lineage): `{p38.get('phase38_resolution_status')}`",
        f"- Experiment id: `{p38.get('experiment_id')}`",
        "",
        "## Competing hypotheses (same 8-row fixture)",
        "",
    ]
    for h in hyps:
        hid = h.get("hypothesis_id")
        lines.append(f"### `{hid}`")
        lines.append(f"- **Status**: `{h.get('status')}`")
        lines.append(f"- **Thesis**: {h.get('economic_thesis', '')[:400]}")
        if (h.get("lifecycle_transitions") or [])[-1:]:
            last = (h.get("lifecycle_transitions") or [])[-1]
            lines.append(
                f"- **Latest transition**: {last.get('from_status')} → {last.get('to_status')} "
                f"({last.get('reason', '')[:120]})"
            )
        lines.append("")

    lines.extend(
        [
            "## Tested vs not tested",
            "",
            "| Hypothesis | Tested in Phase 38 PIT? | Notes |",
            "|------------|-------------------------|-------|",
            "| `hyp_pit_join_key_mismatch_as_of_boundary_v1` | Yes (baseline / alternate run / lag) | "
            "Outcome unchanged for all 8 rows. |",
            "| `hyp_score_publication_cadence_run_grid_lag_v1` | No | Planned specs in family contract only. |",
            "| `hyp_signal_availability_filing_boundary_v1` | No | Planned specs in family contract only. |",
            "| `hyp_issuer_sector_reporting_cadence_v1` | No | Planned stratified replay only. |",
            "| `hyp_governance_safe_alternate_join_policy_v1` | Partially (lag is governance-style bound) | "
            "Still mismatch; further governed policies not yet encoded. |",
            "",
            "## Unresolved",
            "",
            "- Why the eight rows remain `join_key_mismatch` under executed specs is **documented** but **not** "
            "economically resolved.",
            "- Multiple mechanisms (cadence, filing semantics, sector cadence, policy) remain **draft** families.",
            "- Multi-stance adversarial reviews are **deferred**; promotion remains gated.",
            "",
            "## PIT runner family contract (summary)",
            "",
            f"- Fixture class: `{pit_contract.get('fixture_class')}`",
            f"- Shared leakage rule reused: `{pit_contract.get('leakage_audit', {}).get('reused_across_families')}`",
            f"- Families defined: `{len(pit_contract.get('family_bindings') or [])}`",
            "",
            "## Promotion gate (lifecycle-aware)",
        ]
    )
    lines.append(f"- **Gate status**: `{gate.get('gate_status')}`")
    lines.append(f"- **Primary block category**: `{gate.get('primary_block_category')}`")
    lines.append(f"- **Lifecycle snapshot**: `{gate.get('lifecycle_snapshot')}`")
    lines.append("")
    lines.append("## Phase 40 (recommended next)")
    lines.append("")
    lines.append(f"- **`{p40.get('phase40_recommendation')}`**")
    lines.append(f"- {p40.get('rationale', '')}")
    lines.append("")
    return "\n".join(lines)
