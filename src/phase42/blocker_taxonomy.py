"""Cause-coded falsifier blocker taxonomy (filing + sector). Row-level, no silent fallback."""

from __future__ import annotations

from typing import Any

_FORMS = frozenset({"10-K", "10-Q"})


def classify_filing_blocker_cause(
    *,
    signal_available_date: str,
    filing_index_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Deeper diagnostic than Phase 41 substrate classification alone.
    Returns `filing_blocker_cause` from the workorder taxonomy.
    """
    sig = (signal_available_date or "")[:10]
    if len(sig) < 10:
        sig = "9999-12-31"

    rows = list(filing_index_rows or [])
    if not rows:
        return {
            "filing_blocker_cause": "no_filing_index_rows_for_cik",
            "filing_index_row_count": 0,
            "phase41_equivalent": "filing_public_ts_unavailable",
        }

    forms_10 = [r for r in rows if str(r.get("form") or "").strip() in _FORMS]
    if not forms_10:
        return {
            "filing_blocker_cause": "no_10k_10q_rows_for_cik",
            "filing_index_row_count": len(rows),
            "n_10k_10q": 0,
            "phase41_equivalent": "filing_public_ts_unavailable",
        }

    pre_signal: list[dict[str, Any]] = []
    post_signal: list[dict[str, Any]] = []
    unusable_dates = 0

    for r in forms_10:
        filed = str(r.get("filed_at") or "").strip()
        fd = filed[:10] if len(filed) >= 10 else ""
        if len(fd) < 10:
            unusable_dates += 1
            continue
        if fd <= sig:
            pre_signal.append(r)
        else:
            post_signal.append(r)

    if pre_signal:
        best = max(pre_signal, key=lambda x: str(x.get("filed_at") or ""))
        acc = str(best.get("accepted_at") or "").strip()
        if len(acc) >= 10:
            return {
                "filing_blocker_cause": "exact_public_ts_available",
                "filing_index_row_count": len(rows),
                "n_10k_10q": len(forms_10),
                "chosen_accession": best.get("accession_no"),
                "phase41_equivalent": "exact_filing_public_ts_available",
            }
        return {
            "filing_blocker_cause": "accepted_at_missing_but_filed_date_only",
            "filing_index_row_count": len(rows),
            "n_10k_10q": len(forms_10),
            "chosen_accession": best.get("accession_no"),
            "phase41_equivalent": "exact_filing_filed_date_available",
        }

    if post_signal and unusable_dates < len(forms_10):
        return {
            "filing_blocker_cause": "only_post_signal_filings_available",
            "filing_index_row_count": len(rows),
            "n_10k_10q": len(forms_10),
            "n_post_signal_10kq": len(post_signal),
            "phase41_equivalent": "filing_public_ts_unavailable",
        }

    if unusable_dates == len(forms_10) and forms_10:
        return {
            "filing_blocker_cause": "filed_at_missing_or_unusable",
            "filing_index_row_count": len(rows),
            "n_10k_10q": len(forms_10),
            "phase41_equivalent": "filing_public_ts_unavailable",
        }

    return {
        "filing_blocker_cause": "only_post_signal_filings_available",
        "filing_index_row_count": len(rows),
        "n_10k_10q": len(forms_10),
        "phase41_equivalent": "filing_public_ts_unavailable",
    }


def classify_sector_blocker_cause(*, metadata_row: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata_row:
        return {
            "sector_blocker_cause": "no_market_metadata_row_for_symbol",
            "phase41_equivalent": "sector_metadata_missing",
        }
    sector = metadata_row.get("sector")
    sec_s = str(sector).strip() if sector is not None else ""
    if not sec_s:
        return {
            "sector_blocker_cause": "sector_field_blank_on_metadata_row",
            "phase41_equivalent": "sector_metadata_missing",
        }
    return {
        "sector_blocker_cause": "sector_available",
        "sector_label": sec_s,
        "phase41_equivalent": "sector_metadata_available",
    }
