"""Filing index evidence + Phase 42 taxonomy blocker for one CIK/signal."""

from __future__ import annotations

from typing import Any

from db import records as dbrec

from phase42.blocker_taxonomy import classify_filing_blocker_cause

_FORMS = frozenset({"10-K", "10-Q"})


def filing_evidence_snapshot(
    client: Any,
    *,
    cik: str,
    signal_available_date: str,
    filing_index_limit: int = 200,
) -> dict[str, Any]:
    rows = dbrec.fetch_filing_index_rows_for_cik(
        client, cik=cik, limit=filing_index_limit
    )
    forms_10 = [r for r in rows if str(r.get("form") or "").strip() in _FORMS]
    sig = (signal_available_date or "")[:10]
    if len(sig) < 10:
        sig = "9999-12-31"

    def _fd(r: dict[str, Any]) -> str:
        x = str(r.get("filed_at") or "").strip()
        return x[:10] if len(x) >= 10 else ""

    any_pre = False
    for r in forms_10:
        fd = _fd(r)
        if len(fd) >= 10 and fd <= sig:
            any_pre = True
            break

    cause = classify_filing_blocker_cause(
        signal_available_date=signal_available_date,
        filing_index_rows=rows,
    )["filing_blocker_cause"]

    return {
        "filing_blocker_cause": str(cause),
        "filing_index_row_count": len(rows),
        "n_10k_10q": len(forms_10),
        "any_pre_signal_10kq_candidate": any_pre,
    }
