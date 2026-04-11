"""Per-row before/after audit rows for Phase 43 bundle + MD."""

from __future__ import annotations

from typing import Any

from phase43.target_types import CohortTargetRow


def build_before_after_row_audit(
    targets: list[CohortTargetRow],
    *,
    filing_before: list[dict[str, Any]],
    filing_after: list[dict[str, Any]],
    sector_before: list[dict[str, Any]],
    sector_after: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not (
        len(targets)
        == len(filing_before)
        == len(filing_after)
        == len(sector_before)
        == len(sector_after)
    ):
        raise ValueError("before/after snapshot lists must align with targets")
    out: list[dict[str, Any]] = []
    for i, t in enumerate(targets):
        fb, fa = filing_before[i], filing_after[i]
        sb, sa = sector_before[i], sector_after[i]
        out.append(
            {
                "symbol": t.get("symbol"),
                "cik": t.get("cik"),
                "signal_available_date": t.get("signal_available_date"),
                "filing_blocker_before": t.get("filing_blocker_cause_before"),
                "filing_blocker_after": fa.get("filing_blocker_cause"),
                "sector_blocker_before": t.get("sector_blocker_cause_before"),
                "sector_blocker_after": sa.get("sector_blocker_cause"),
                "filing_index_row_count_before": fb.get("filing_index_row_count"),
                "filing_index_row_count_after": fa.get("filing_index_row_count"),
                "n_10k_10q_before": fb.get("n_10k_10q"),
                "n_10k_10q_after": fa.get("n_10k_10q"),
                "any_pre_signal_candidate_before": fb.get("any_pre_signal_10kq_candidate"),
                "any_pre_signal_candidate_after": fa.get("any_pre_signal_10kq_candidate"),
                "raw_row_count_before": sb.get("raw_row_count"),
                "raw_row_count_after": sa.get("raw_row_count"),
                "sector_present_before": sb.get("sector_present"),
                "sector_present_after": sa.get("sector_present"),
                "industry_present_before": sb.get("industry_present"),
                "industry_present_after": sa.get("industry_present"),
            }
        )
    return out


def render_before_after_audit_md(*, rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 43 — Before/after blocker audit (8-row cohort)",
        "",
        "_Deterministic per-row evidence for filing_index + market_metadata_latest._",
        "",
    ]
    for r in rows:
        lines.extend(
            [
                f"## {r.get('symbol')} (CIK `{r.get('cik')}`, signal `{r.get('signal_available_date')}`)",
                "",
                "| Field | Before | After |",
                "| --- | --- | --- |",
                f"| filing_blocker | `{r.get('filing_blocker_before')}` | `{r.get('filing_blocker_after')}` |",
                f"| sector_blocker | `{r.get('sector_blocker_before')}` | `{r.get('sector_blocker_after')}` |",
                f"| filing_index_row_count | {r.get('filing_index_row_count_before')} | {r.get('filing_index_row_count_after')} |",
                f"| n_10k_10q | {r.get('n_10k_10q_before')} | {r.get('n_10k_10q_after')} |",
                f"| any_pre_signal_10kq | {r.get('any_pre_signal_candidate_before')} | {r.get('any_pre_signal_candidate_after')} |",
                f"| metadata raw_row_count | {r.get('raw_row_count_before')} | {r.get('raw_row_count_after')} |",
                f"| sector_present | {r.get('sector_present_before')} | {r.get('sector_present_after')} |",
                f"| industry_present | {r.get('industry_present_before')} | {r.get('industry_present_after')} |",
                "",
            ]
        )
    return "\n".join(lines)
