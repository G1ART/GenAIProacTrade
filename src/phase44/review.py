"""Phase 44 review MD, bundle JSON, explanation v7."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase44.audit_render import render_phase44_provenance_audit_md


def write_phase44_claim_narrowing_truthfulness_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def write_phase44_provenance_audit_md(path: str, *, rows: list[dict[str, Any]]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_phase44_provenance_audit_md(rows=rows), encoding="utf-8")
    return str(p.resolve())


def write_phase44_claim_narrowing_truthfulness_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    truth = bundle.get("phase44_truthfulness_assessment") or {}
    retry = bundle.get("retry_eligibility") or {}
    cn = bundle.get("claim_narrowing") or {}
    p45 = bundle.get("phase45") or {}
    lines = [
        "# Phase 44 — Claim narrowing & audit truthfulness",
        "",
        f"- Bundle phase: `{bundle.get('phase')}`",
        f"- Generated: `{bundle.get('generated_utc')}`",
        f"- Phase 43 input: `{bundle.get('input_phase43_bundle_path')}`",
        f"- Phase 42 Supabase input: `{bundle.get('input_phase42_supabase_bundle_path')}`",
        "",
        "## Truthfulness assessment",
        "",
        f"- **material_falsifier_improvement**: `{truth.get('material_falsifier_improvement')}`",
        f"- **optimistic_sector_relabel_only**: `{truth.get('optimistic_sector_relabel_only')}`",
        f"- **falsifier_usability_improved**: `{truth.get('falsifier_usability_improved')}`",
        f"- **gate_materially_improved**: `{truth.get('gate_materially_improved')}`",
        f"- **discrimination_rollups_improved**: `{truth.get('discrimination_rollups_improved')}`",
        "",
        "### Notes",
        "",
    ]
    for n in truth.get("notes") or []:
        lines.append(f"- {n}")
    if not (truth.get("notes") or []):
        lines.append("- _(none)_")
    lines.extend(
        [
        "",
        "## Retry eligibility",
        "",
        f"- **filing_retry_eligible**: `{retry.get('filing_retry_eligible')}`",
        f"- **sector_retry_eligible**: `{retry.get('sector_retry_eligible')}`",
        f"- **reason**: {retry.get('eligibility_reason')}",
        "",
        "## Claim narrowing (cohort)",
        "",
        f"- **claim_status**: `{cn.get('cohort_claim_limits', {}).get('claim_status')}`",
        f"- **bounded_retry_eligibility**: `{cn.get('bounded_retry_eligibility')}`",
        "",
        "## Phase 45",
        "",
        f"- **recommendation**: `{p45.get('phase45_recommendation')}`",
        f"- **rationale**: {p45.get('rationale')}",
        "",
        "## Provenance audit",
        "",
        "See `phase44_provenance_audit.md` (input bundle vs runtime snapshots, separated).",
        "",
        ]
    )
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())


def render_phase44_explanation_surface_v7_md(*, bundle: dict[str, Any]) -> str:
    truth = bundle.get("phase44_truthfulness_assessment") or {}
    cn = bundle.get("claim_narrowing") or {}
    retry = bundle.get("retry_eligibility") or {}
    p45 = bundle.get("phase45") or {}
    sc_b = bundle.get("scorecard_phase42_supabase_before") or {}
    sc_a = bundle.get("scorecard_phase43_after") or {}

    return "\n".join(
        [
            "# Explanation surface v7 — Phase 44 (truthfulness after Phase 43)",
            "",
            "## What Phase 43 improved",
            "",
            "- **Sector taxonomy precision**: scorecard bucket moved from "
            "`no_market_metadata_row_for_symbol` to `sector_field_blank_on_metadata_row` for the 8-row cohort, "
            "matching runtime rows where metadata exists but `sector` is empty.",
            "- **Stable digest** changed between Phase 42 runs bracketing Phase 43 (see Phase 43 bundle); "
            "this records execution drift, not by itself a falsifier upgrade.",
            "",
            "## What Phase 43 did not improve",
            "",
            "- **Filing falsifier strength** (aggregate): `exact_public_ts_available` and related usability "
            "counts did not increase; filing blocker distribution is unchanged at the scorecard level.",
            "- **Sector usability**: `sector_available` did not increase; sector-informed falsification "
            "remains unavailable.",
            "- **Gate**: `gate_status` and `primary_block_category` unchanged (still proxy-limited substrate).",
            "- **Discrimination rollups**: family outcome signatures unchanged for this cohort.",
            "",
            "## Is another bounded retry justified?",
            "",
            f"- Phase 44 material improvement flag: **{truth.get('material_falsifier_improvement')}**.",
            f"- Filing retry eligible: **{retry.get('filing_retry_eligible')}**; "
            f"sector retry eligible: **{retry.get('sector_retry_eligible')}**.",
            "- Without a **newly named** source/path, generic “run another bounded pass” is **not** authorized.",
            "",
            "## Narrowed claims (machine-readable summary)",
            "",
            f"- Cohort status: `{cn.get('cohort_claim_limits', {}).get('claim_status')}`",
            f"- Bounded retry registry: `{cn.get('bounded_retry_eligibility')}`",
            "",
            "### Scorecard anchors",
            "",
            f"- Phase 42 Supabase (before Phase 43): `{sc_b.get('sector_blocker_distribution')!r}` / "
            f"`{sc_b.get('filing_blocker_distribution')!r}`",
            f"- After Phase 43 Phase 42 rerun: `{sc_a.get('sector_blocker_distribution')!r}` / "
            f"`{sc_a.get('filing_blocker_distribution')!r}`",
            "",
            "## Broad substrate reopening",
            "",
            "Broad public-core filing_index or metadata campaigns remain **out of scope**; "
            "Phase 44 is a governance and interpretation patch, not a substrate expansion.",
            "",
            "## Phase 45 recommendation",
            "",
            f"- **`{p45.get('phase45_recommendation')}`** — {p45.get('rationale')}",
            "",
        ]
    )
