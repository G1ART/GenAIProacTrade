"""Compute cohort integrity for a named ticker set (e.g. backfill_200) across
the factor-validation data path.

Stages reported, in processing order, for one
``(universe, factor_name, horizon_type, return_basis)`` slice:

1. ``issuer_master`` — symbols that resolve to a CIK via ``issuer_master``.
2. ``issuer_quarter_factor_panels`` — CIKs with a non-null ``factor_value`` for
   ``factor_name`` in the latest panels for their accessions.
3. ``factor_market_validation_panels`` — CIKs present in the forward-returns
   validation panels for ``universe``.
4. ``factor_validation_summaries`` — ``sample_count`` / ``valid_factor_count``
   from the latest completed ``factor_validation_runs`` row for the slice.

The resulting report highlights missing symbols per stage, the pass ratio of
stage-3 CIKs relative to the cohort size, and a single ``pass`` boolean that
the CLI uses as its exit code signal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

# Re-use the same primitives the validation pipeline uses so the cohort report
# reflects the same path the bundle builder consumes.
from db.records import (
    fetch_cik_map_for_tickers,
    fetch_factor_market_validation_panels_for_symbols,
    fetch_issuer_quarter_factor_panels_for_accessions,
    fetch_latest_factor_validation_summaries,
    issuer_quarter_factor_panel_join_key,
    normalize_sec_cik,
)


def _cohort_symbols_from_file(path: Path) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        tickers: list[str] = [str(t).upper().strip() for t in raw if t]
    elif isinstance(raw, dict):
        bucket = raw.get("tickers") or raw.get("symbols") or raw.get("selected_symbols")
        if not isinstance(bucket, list):
            raise ValueError(
                "cohort file must contain a top-level list under 'tickers', "
                "'symbols', or 'selected_symbols'"
            )
        tickers = [str(t).upper().strip() for t in bucket if t]
    else:
        raise ValueError("cohort file root must be list or object")
    out: list[str] = []
    seen: set[str] = set()
    for t in tickers:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _deduped(seq: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def compute_cohort_integrity_report(
    client: Any,
    *,
    cohort_symbols: list[str],
    universe: str,
    factor_name: str,
    horizon_type: str,
    return_basis: str = "raw",
    min_pass_ratio: float = 0.9,
    panel_limit: int = 8000,
    show_missing_limit: int = 30,
) -> dict[str, Any]:
    cohort = _deduped(str(s).upper().strip() for s in cohort_symbols)
    n = len(cohort)

    # Stage 1 — symbol → CIK via issuer_master
    cik_map = fetch_cik_map_for_tickers(client, cohort)
    resolved_symbols = sorted([s for s, c in cik_map.items() if c])
    resolved_ciks = _deduped(
        [normalize_sec_cik(cik_map[s]) for s in resolved_symbols if cik_map.get(s)]
    )
    missing_in_issuer_master = sorted(set(cohort) - set(resolved_symbols))

    # Stage 3 — factor_market_validation_panels for the whole universe; used
    # as the upstream accession/symbol join source.
    vpanels = fetch_factor_market_validation_panels_for_symbols(
        client, symbols=resolved_symbols, limit=panel_limit
    )
    vpanel_ciks = _deduped(
        [normalize_sec_cik(str(p.get("cik") or "")) for p in vpanels if p.get("cik")]
    )
    accessions = sorted({str(p.get("accession_no")) for p in vpanels if p.get("accession_no")})

    # Stage 2 — issuer_quarter_factor_panels for those accessions with factor_value
    fp_map = fetch_issuer_quarter_factor_panels_for_accessions(
        client, accession_nos=accessions, limit_per_batch=panel_limit
    )
    factor_ciks: list[str] = []
    seen_f: set[str] = set()
    for vp in vpanels:
        key = issuer_quarter_factor_panel_join_key(
            vp.get("cik"),
            vp.get("accession_no"),
            vp.get("factor_version"),
            default_factor_version="v1",
        )
        fp = fp_map.get(key)
        if not fp:
            continue
        if fp.get(factor_name) is None:
            continue
        ck = normalize_sec_cik(str(vp.get("cik") or ""))
        if ck and ck not in seen_f:
            seen_f.add(ck)
            factor_ciks.append(ck)

    # Stage 4 — summary run
    run_id, summary_rows = fetch_latest_factor_validation_summaries(
        client,
        factor_name=factor_name,
        universe_name=universe,
        horizon_type=horizon_type,
    )
    summary = None
    if summary_rows:
        summary = next(
            (r for r in summary_rows if str(r.get("return_basis")) == return_basis), None
        )

    # Derive missing breakdowns
    resolved_cik_set = set(resolved_ciks)
    missing_factor_ciks = sorted(resolved_cik_set - set(factor_ciks))
    missing_vpanel_ciks = sorted(resolved_cik_set - set(vpanel_ciks))

    # Map missing CIKs back to cohort symbols for human-readable output.
    cik_to_symbols: dict[str, list[str]] = {}
    for sym, c in cik_map.items():
        if not c:
            continue
        k = normalize_sec_cik(c)
        cik_to_symbols.setdefault(k, []).append(sym)

    def _syms(ciks: list[str]) -> list[str]:
        out: list[str] = []
        for c in ciks:
            out.extend(cik_to_symbols.get(c) or [])
        return sorted(set(out))

    missing_factor_symbols = _syms(missing_factor_ciks)
    missing_vpanel_symbols = _syms(missing_vpanel_ciks)

    pass_ratio = float(len(vpanel_ciks)) / float(n) if n else 0.0
    pass_ok = bool(n) and pass_ratio >= float(min_pass_ratio)

    report: dict[str, Any] = {
        "ok": True,
        "contract": "METIS_COHORT_INTEGRITY_REPORT_V1",
        "cohort_size": n,
        "universe": universe,
        "factor_name": factor_name,
        "horizon_type": horizon_type,
        "return_basis": return_basis,
        "min_pass_ratio": float(min_pass_ratio),
        "stages": {
            "issuer_master": {
                "resolved_symbol_count": len(resolved_symbols),
                "resolved_cik_count": len(resolved_ciks),
                "missing_symbol_count": len(missing_in_issuer_master),
                "missing_symbols_sample": missing_in_issuer_master[:show_missing_limit],
            },
            "factor_market_validation_panels": {
                "cik_count": len(vpanel_ciks),
                "missing_cik_count": len(missing_vpanel_ciks),
                "missing_symbols_sample": missing_vpanel_symbols[:show_missing_limit],
                "accession_count": len(accessions),
            },
            "issuer_quarter_factor_panels": {
                "cik_with_factor_value_count": len(factor_ciks),
                "missing_cik_count": len(missing_factor_ciks),
                "missing_symbols_sample": missing_factor_symbols[:show_missing_limit],
            },
            "factor_validation_summaries": {
                "run_id": run_id or "",
                "sample_count": int(summary.get("sample_count") or 0) if summary else 0,
                "valid_factor_count": int(summary.get("valid_factor_count") or 0) if summary else 0,
                "return_basis": return_basis,
            },
        },
        "headline": {
            "pass": pass_ok,
            "pass_ratio": round(pass_ratio, 4),
            "pass_numerator_vpanel_ciks": len(vpanel_ciks),
            "pass_denominator_cohort_size": n,
            "gate": (
                "vpanel_ciks / cohort_size >= min_pass_ratio"
            ),
        },
    }
    return report
