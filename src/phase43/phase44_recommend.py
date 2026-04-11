"""Phase 44 recommendation after bounded backfill + retest."""

from __future__ import annotations

from typing import Any


def recommend_phase44_after_phase43(
    *,
    before_after_row_audit: list[dict[str, Any]],
    scorecard_before: dict[str, Any],
    scorecard_after: dict[str, Any],
    gate_before: dict[str, Any],
    gate_after: dict[str, Any],
) -> dict[str, Any]:
    filing_improved = any(
        str(r.get("filing_blocker_before") or "") != str(r.get("filing_blocker_after") or "")
        for r in before_after_row_audit
    )
    sector_improved = any(
        str(r.get("sector_blocker_before") or "") != str(r.get("sector_blocker_after") or "")
        for r in before_after_row_audit
    )
    fb = scorecard_before.get("filing_blocker_distribution") or {}
    fa = scorecard_after.get("filing_blocker_distribution") or {}
    sb = scorecard_before.get("sector_blocker_distribution") or {}
    sa = scorecard_after.get("sector_blocker_distribution") or {}

    exact_up = int(fa.get("exact_public_ts_available", 0)) > int(fb.get("exact_public_ts_available", 0))
    sec_ok_up = int(sa.get("sector_available", 0)) > int(sb.get("sector_available", 0))
    gate_changed = (gate_before.get("primary_block_category") != gate_after.get("primary_block_category")) or (
        gate_before.get("gate_status") != gate_after.get("gate_status")
    )

    material = (
        filing_improved
        or sector_improved
        or exact_up
        or sec_ok_up
        or fb != fa
        or sb != sa
        or gate_changed
    )

    if material:
        return {
            "phase44_recommendation": "continue_bounded_falsifier_retest_or_narrow_claims_v1",
            "rationale": (
                "Bounded backfill or retest changed at least one row-level blocker, scorecard bucket, or gate "
                "field. Next: optional second bounded pass, or narrow claims if proxy limits persist."
            ),
        }
    return {
        "phase44_recommendation": "narrow_claims_or_accept_proxy_limits_no_broad_substrate_v1",
        "rationale": (
            "After bounded cohort-only filing ingest and metadata hydration, blockers and scorecard were "
            "unchanged at the recorded grain. Do not reopen broad public-core substrate; narrow claims or "
            "document acceptance of falsifier limits for this cohort."
        ),
    }
