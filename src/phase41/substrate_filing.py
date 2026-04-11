"""Filing / public-availability substrate classification for Phase 41 (deterministic, labeled)."""

from __future__ import annotations

from typing import Any

_FORMS = frozenset({"10-K", "10-Q"})


def classify_filing_substrate_row(
    *,
    signal_available_date: str,
    filing_index_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Per fixture row: choose latest 10-K/10-Q with filed_at <= signal (calendar YYYY-MM-DD).
    - If `accepted_at` present (ISO, >=10 chars): exact_filing_public_ts_available (date prefix).
    - Elif `filed_at` present: exact_filing_filed_date_available (SEC filing date only).
    - Else: filing_public_ts_unavailable → documented signal proxy (explicit).
    """
    sig = (signal_available_date or "")[:10]
    if len(sig) < 10:
        sig = "9999-12-31"

    candidates: list[dict[str, Any]] = []
    for r in filing_index_rows or []:
        form = str(r.get("form") or "").strip()
        if form not in _FORMS:
            continue
        filed = str(r.get("filed_at") or "").strip()
        filed_ymd = filed[:10] if len(filed) >= 10 else ""
        if len(filed_ymd) < 10:
            continue
        if filed_ymd <= sig:
            candidates.append(r)

    if not candidates:
        return {
            "classification": "filing_public_ts_unavailable",
            "effective_pick_bound_ymd": sig,
            "filing_bound_source": "signal_available_date_proxy",
            "explicit_proxy": True,
            "accession_no": None,
            "form": None,
            "filed_at_ymd": None,
            "acceptance_date_prefix": None,
        }

    best = max(candidates, key=lambda x: str(x.get("filed_at") or ""))
    filed_raw = str(best.get("filed_at") or "").strip()
    filed_ymd = filed_raw[:10] if len(filed_raw) >= 10 else ""
    acc_raw = str(best.get("accepted_at") or "").strip()
    acc_ymd = acc_raw[:10] if len(acc_raw) >= 10 else ""

    if len(acc_ymd) >= 10:
        effective = min(sig, acc_ymd)
        return {
            "classification": "exact_filing_public_ts_available",
            "effective_pick_bound_ymd": effective,
            "filing_bound_source": "filing_index.accepted_at_date_prefix",
            "explicit_proxy": False,
            "accession_no": best.get("accession_no"),
            "form": best.get("form"),
            "filed_at_ymd": filed_ymd or None,
            "acceptance_date_prefix": acc_ymd,
        }

    effective = min(sig, filed_ymd) if len(filed_ymd) >= 10 else sig
    return {
        "classification": "exact_filing_filed_date_available",
        "effective_pick_bound_ymd": effective,
        "filing_bound_source": "filing_index.filed_at_date_only",
        "explicit_proxy": False,
        "accession_no": best.get("accession_no"),
        "form": best.get("form"),
        "filed_at_ymd": filed_ymd or None,
        "acceptance_date_prefix": None,
    }


def summarize_filing_substrate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate counts by classification string."""
    from collections import Counter

    c = Counter(str(r.get("classification") or "") for r in rows)
    n_proxy = sum(1 for r in rows if r.get("explicit_proxy") is True)
    return {
        "row_count": len(rows),
        "by_classification": dict(c),
        "rows_with_explicit_signal_proxy": n_proxy,
    }
