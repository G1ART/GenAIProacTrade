"""Separate input-bundle blockers from runtime snapshots (Phase 43 mixed-provenance fix)."""

from __future__ import annotations

from typing import Any


def _infer_filing_blocker_from_metrics(
    *,
    filing_index_row_count: int,
    n_10k_10q: int,
    any_pre_signal_10kq: bool,
) -> str:
    """Filing taxonomy from aggregate metrics (bundle-safe; no full filing_index rows)."""
    if filing_index_row_count <= 0:
        return "no_filing_index_rows_for_cik"
    if n_10k_10q <= 0:
        return "no_10k_10q_rows_for_cik"
    if not any_pre_signal_10kq:
        return "only_post_signal_filings_available"
    return "pre_signal_10kq_requires_row_level_accepted_at_audit"


def _infer_sector_blocker_from_metrics(
    *,
    raw_row_count: int,
    sector_present: bool,
) -> str:
    if raw_row_count <= 0:
        return "no_market_metadata_row_for_symbol"
    if not sector_present:
        return "sector_field_blank_on_metadata_row"
    return "sector_available"


def _runtime_snapshot_from_audit_row(ba: dict[str, Any], *, when: str) -> dict[str, Any]:
    if when not in ("before", "after"):
        raise ValueError("when must be 'before' or 'after'")
    suf = "_before" if when == "before" else "_after"
    fic = int(ba.get(f"filing_index_row_count{suf}") or 0)
    n10 = int(ba.get(f"n_10k_10q{suf}") or 0)
    pre = bool(ba.get(f"any_pre_signal_candidate{suf}"))
    rrc = int(ba.get(f"raw_row_count{suf}") or 0)
    sp = bool(ba.get(f"sector_present{suf}"))
    ip = bool(ba.get(f"industry_present{suf}"))
    return {
        "filing_blocker": _infer_filing_blocker_from_metrics(
            filing_index_row_count=fic,
            n_10k_10q=n10,
            any_pre_signal_10kq=pre,
        ),
        "filing_index_row_count": fic,
        "n_10k_10q": n10,
        "any_pre_signal_candidate": pre,
        "sector_blocker": _infer_sector_blocker_from_metrics(raw_row_count=rrc, sector_present=sp),
        "raw_row_count": rrc,
        "sector_present": sp,
        "industry_present": ip,
    }


def build_provenance_audit_rows(
    *,
    phase43_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Align `target_cohort` with `before_after_row_audit` by symbol.
    input_bundle_before = Phase 42 cohort labels (no live DB conflation).
    runtime_* = metrics from Phase 43 audit row suffixes _before / _after only.
    """
    cohort = list(phase43_bundle.get("target_cohort") or [])
    audits = list(phase43_bundle.get("before_after_row_audit") or [])
    by_sym: dict[str, dict[str, Any]] = {str(r.get("symbol") or "").upper(): r for r in audits}
    out: list[dict[str, Any]] = []
    for t in cohort:
        sym = str(t.get("symbol") or "").upper()
        ba = by_sym.get(sym)
        if not ba:
            raise ValueError(f"provenance_audit: missing before_after_row_audit row for {sym}")
        in_f = str(t.get("filing_blocker_cause_before") or "")
        in_s = str(t.get("sector_blocker_cause_before") or "")
        out.append(
            {
                "symbol": sym,
                "cik": str(t.get("cik") or ""),
                "signal_available_date": str(t.get("signal_available_date") or "")[:10],
                "input_bundle_before": {
                    "filing_blocker": in_f,
                    "sector_blocker": in_s,
                },
                "runtime_snapshot_before_repair": _runtime_snapshot_from_audit_row(ba, when="before"),
                "runtime_snapshot_after_repair": _runtime_snapshot_from_audit_row(ba, when="after"),
            }
        )
    return out
