"""Bounded SEC sample ingest per unique cohort CIK (reuse `run_sample_ingest`)."""

from __future__ import annotations

from typing import Any

from phase30.filing_index_gaps import _resolve_ticker_for_filing_ingest
from research_validation.metrics import norm_cik
from sec.ingest_company_sample import run_sample_ingest

from phase43.target_types import CohortTargetRow


def run_bounded_filing_backfill_for_cohort(
    settings: Any,
    client: Any,
    targets: list[CohortTargetRow],
    *,
    max_cik_repairs: int = 8,
) -> dict[str, Any]:
    """
    One `run_sample_ingest` per distinct CIK (order = first appearance), capped.
    ADSK vs others: each CIK is attempted independently; outcomes recorded per attempt.
    """
    attempts: list[dict[str, Any]] = []
    seen_cik: set[str] = set()
    for t in targets:
        cik = norm_cik(t.get("cik"))
        if not cik or cik in seen_cik:
            continue
        seen_cik.add(cik)
        if len(attempts) >= max_cik_repairs:
            attempts.append(
                {
                    "cik": cik,
                    "symbol": t.get("symbol"),
                    "status": "skipped",
                    "reason": "max_cik_repairs_reached",
                }
            )
            continue
        sym = str(t.get("symbol") or "")
        ticker, br = _resolve_ticker_for_filing_ingest(client, symbol=sym, cik=cik)
        if br:
            attempts.append(
                {
                    "cik": cik,
                    "symbol": sym,
                    "status": "blocked",
                    "reason": br,
                }
            )
            continue
        assert ticker is not None
        try:
            out = run_sample_ingest(ticker, settings, client=client)
            attempts.append(
                {
                    "cik": cik,
                    "symbol": sym,
                    "ticker": ticker,
                    "status": "attempted",
                    "ingest_summary": out,
                }
            )
        except Exception as ex:  # noqa: BLE001
            attempts.append(
                {
                    "cik": cik,
                    "symbol": sym,
                    "ticker": ticker,
                    "status": "failed",
                    "error": str(ex),
                }
            )
    return {
        "repair": "bounded_run_sample_ingest_per_cik",
        "max_cik_repairs": max_cik_repairs,
        "unique_ciks_touched": len(seen_cik),
        "attempts": attempts,
    }
