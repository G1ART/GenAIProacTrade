"""Stricter material-improvement rules (Phase 44); blank-field relabel alone is insufficient."""

from __future__ import annotations

from typing import Any


def is_only_sector_no_row_to_blank_relabel(
    *,
    sector_dist_before: dict[str, Any],
    sector_dist_after: dict[str, Any],
) -> bool:
    """True when sector_available does not increase and counts move no_row → blank only."""
    sb = {str(k): int(v) for k, v in (sector_dist_before or {}).items()}
    sa = {str(k): int(v) for k, v in (sector_dist_after or {}).items()}
    if int(sa.get("sector_available", 0)) > int(sb.get("sector_available", 0)):
        return False
    if int(sa.get("sector_available", 0)) > 0 or int(sb.get("sector_available", 0)) > 0:
        return False
    b_no = int(sb.get("no_market_metadata_row_for_symbol", 0))
    a_no = int(sa.get("no_market_metadata_row_for_symbol", 0))
    b_blank = int(sb.get("sector_field_blank_on_metadata_row", 0))
    a_blank = int(sa.get("sector_field_blank_on_metadata_row", 0))
    if b_no <= 0:
        return False
    if a_no != 0:
        return False
    if a_blank < b_no + b_blank:
        return False
    return True


def falsifier_usability_improved(
    *,
    filing_before: dict[str, Any],
    filing_after: dict[str, Any],
    sector_before: dict[str, Any],
    sector_after: dict[str, Any],
) -> bool:
    fb, fa = filing_before or {}, filing_after or {}
    sb, sa = sector_before or {}, sector_after or {}
    if int(fa.get("exact_public_ts_available", 0)) > int(fb.get("exact_public_ts_available", 0)):
        return True
    if int(sa.get("sector_available", 0)) > int(sb.get("sector_available", 0)):
        return True
    if int(fa.get("accepted_at_missing_but_filed_date_only", 0)) > int(
        fb.get("accepted_at_missing_but_filed_date_only", 0)
    ):
        return True
    return False


def gate_materially_improved(*, gate_before: dict[str, Any], gate_after: dict[str, Any]) -> bool:
    if not gate_before or not gate_after:
        return False
    rank = {"blocked": 0, "deferred": 1, "conditionally_supported": 2, "promoted": 3}
    sb = rank.get(str(gate_before.get("gate_status") or ""), -1)
    sa = rank.get(str(gate_after.get("gate_status") or ""), -1)
    if sa > sb:
        return True
    cb = str(gate_before.get("primary_block_category") or "")
    ca = str(gate_after.get("primary_block_category") or "")
    if cb != ca and sa >= sb:
        return True
    return False


def discrimination_rollups_improved(
    *,
    disc_before: dict[str, Any] | None,
    disc_after: dict[str, Any] | None,
) -> bool:
    """If both present and outcome signatures differ meaningfully."""
    if not disc_before or not disc_after:
        return False
    sig_b = disc_before.get("outcome_rollup_signature_by_family") or {}
    sig_a = disc_after.get("outcome_rollup_signature_by_family") or {}
    return bool(sig_b != sig_a)


def assess_phase44_truthfulness(
    *,
    scorecard_before: dict[str, Any],
    scorecard_after: dict[str, Any],
    gate_before: dict[str, Any],
    gate_after: dict[str, Any],
    discrimination_before: dict[str, Any] | None = None,
    discrimination_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fb = scorecard_before.get("filing_blocker_distribution") or {}
    fa = scorecard_after.get("filing_blocker_distribution") or {}
    sb = scorecard_before.get("sector_blocker_distribution") or {}
    sa = scorecard_after.get("sector_blocker_distribution") or {}

    usability = falsifier_usability_improved(
        filing_before=fb, filing_after=fa, sector_before=sb, sector_after=sa
    )
    only_relabel = is_only_sector_no_row_to_blank_relabel(sector_dist_before=sb, sector_dist_after=sa)
    gate_imp = gate_materially_improved(gate_before=gate_before, gate_after=gate_after)
    disc_imp = discrimination_rollups_improved(
        disc_before=discrimination_before, disc_after=discrimination_after
    )

    filing_dist_changed = fb != fa
    sector_dist_changed = sb != sa
    digest_only_cosmetic = only_relabel and not usability and not filing_dist_changed

    material_falsifier_improvement = usability or gate_imp or disc_imp
    if only_relabel and not usability and not gate_imp and not disc_imp:
        material_falsifier_improvement = False

    notes: list[str] = []
    if only_relabel:
        notes.append(
            "Sector scorecard moved no_market_metadata_row_for_symbol → sector_field_blank_on_metadata_row "
            "without sector_available increase; treated as diagnostic relabel, not falsifier upgrade."
        )
    if not usability and not gate_imp:
        notes.append("No increase in exact_public_ts_available, sector_available, or filed-date-only path.")

    return {
        "material_falsifier_improvement": material_falsifier_improvement,
        "optimistic_sector_relabel_only": bool(only_relabel and not usability),
        "filing_distribution_changed": filing_dist_changed,
        "sector_distribution_changed": sector_dist_changed,
        "falsifier_usability_improved": usability,
        "gate_materially_improved": gate_imp,
        "discrimination_rollups_improved": disc_imp,
        "digest_only_cosmetic_sector_relabel": digest_only_cosmetic,
        "notes": notes,
    }
