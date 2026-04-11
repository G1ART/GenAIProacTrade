"""Bounded evidence accumulation — scorecard, row blockers layout, discrimination, digests."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any


def extract_fixture_rows_from_phase41_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Cohort A: symbols/ciks/signals from Phase 41 filing-family row_results."""
    pit = bundle.get("pit_execution") or {}
    for f in pit.get("families_executed") or []:
        if str(f.get("family_id") or "") == "signal_filing_boundary_v1":
            out: list[dict[str, Any]] = []
            for row in f.get("row_results") or []:
                out.append(
                    {
                        "symbol": str(row.get("symbol") or ""),
                        "cik": str(row.get("cik") or ""),
                        "signal_available_date": str(row.get("signal_available_date") or ""),
                    }
                )
            return out
    return []


def _rollup_vector(family: dict[str, Any]) -> tuple[Any, ...]:
    sc = family.get("summary_counts_by_spec") or {}
    parts: list[tuple[str, tuple[tuple[str, int], ...]]] = []
    for spec_key in sorted(sc.keys()):
        bucket = sc[spec_key] or {}
        tup = tuple(sorted((str(k), int(bucket[k])) for k in sorted(bucket.keys())))
        parts.append((spec_key, tup))
    return tuple(parts)


def build_discrimination_summary(
    *,
    families_executed: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare outcome rollups across Phase 41 rerun families.
    With only two families, identical numeric rollups => neither discriminates on outcome counts alone.
    """
    vectors: dict[str, tuple[Any, ...]] = {}
    for f in families_executed:
        fid = str(f.get("family_id") or "")
        if fid:
            vectors[fid] = _rollup_vector(f)

    by_vec: dict[tuple[Any, ...], list[str]] = {}
    for fid, v in vectors.items():
        by_vec.setdefault(v, []).append(fid)

    identical_groups = [sorted(g) for g in by_vec.values() if len(g) > 1]
    discriminating = [fid for fid, v in vectors.items() if len(by_vec.get(v, [])) == 1]

    return {
        "n_families_compared": len(vectors),
        "outcome_rollup_signature_by_family": {k: repr(v) for k, v in vectors.items()},
        "families_with_identical_rollups_groups": identical_groups,
        "live_and_discriminating_family_ids": discriminating,
        "any_family_outcome_discriminating": len(discriminating) > 0,
    }


def build_evidence_density_by_family(
    *,
    families_executed: list[dict[str, Any]],
    row_level_blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Proxy vs stronger substrate counts, attributed to rerun families by id."""
    n = len(row_level_blockers)
    filing_exact = sum(
        1 for r in row_level_blockers if r.get("filing_blocker_cause") == "exact_public_ts_available"
    )
    filing_filed_only = sum(
        1
        for r in row_level_blockers
        if r.get("filing_blocker_cause") == "accepted_at_missing_but_filed_date_only"
    )
    sector_ok = sum(1 for r in row_level_blockers if r.get("sector_blocker_cause") == "sector_available")

    by_fid: dict[str, dict[str, Any]] = {}
    for f in families_executed:
        fid = str(f.get("family_id") or "")
        if not fid:
            continue
        if fid == "signal_filing_boundary_v1":
            by_fid[fid] = {
                "cohort_rows": n,
                "rows_with_exact_public_ts": filing_exact,
                "rows_with_filed_date_only": filing_filed_only,
                "rows_proxy_or_blocked": n - filing_exact - filing_filed_only,
            }
        elif fid == "issuer_sector_reporting_cadence_v1":
            by_fid[fid] = {
                "cohort_rows": n,
                "rows_with_sector_metadata": sector_ok,
                "rows_sector_blocked": n - sector_ok,
            }
        else:
            by_fid[fid] = {"note": "not_phase41_rerun_family"}

    return {"by_family": by_fid, "cohort_row_count": n}


def build_family_evidence_scorecard(
    *,
    phase41_pit: dict[str, Any],
    row_level_blockers: list[dict[str, Any]],
    discrimination_summary: dict[str, Any],
) -> dict[str, Any]:
    fc = Counter(str(r.get("filing_blocker_cause") or "") for r in row_level_blockers)
    sc = Counter(str(r.get("sector_blocker_cause") or "") for r in row_level_blockers)
    return {
        "cohort_label": "phase41_fixture_row_results",
        "cohort_row_count": len(row_level_blockers),
        "filing_blocker_distribution": dict(fc),
        "sector_blocker_distribution": dict(sc),
        "phase41_families": [
            str(f.get("family_id") or "") for f in (phase41_pit.get("families_executed") or [])
        ],
        "outcome_discriminating_family_count": len(
            discrimination_summary.get("live_and_discriminating_family_ids") or []
        ),
        "identical_rollup_groups": discrimination_summary.get("families_with_identical_rollups_groups"),
    }


def unchanged_vs_prior_run_digest(phase41_bundle: dict[str, Any]) -> dict[str, Any]:
    """Reuse Phase 41 bundle's embedded Phase 40 comparison."""
    raw = phase41_bundle.get("family_rerun_before_after")
    if not isinstance(raw, dict):
        return {"note": "no family_rerun_before_after in phase41 bundle"}
    out: dict[str, Any] = {}
    for fid, block in raw.items():
        if not isinstance(block, dict):
            continue
        out[str(fid)] = {
            "unchanged_rollups": block.get("unchanged_rollups"),
            "spec_keys_before": block.get("spec_keys_before"),
            "spec_keys_after": block.get("spec_keys_after"),
        }
    return out


def build_row_level_blockers_from_phase41_substrate(pit: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Replay Phase 42 blocker causes from a Phase 41 pit payload (no DB).
    Filing `filing_public_ts_unavailable` maps coarsely to `only_post_signal_filings_available`
    (Phase 41 does not preserve which sub-cause applied).
    """
    sig_by_key: dict[tuple[str, str], str] = {}
    for f in pit.get("families_executed") or []:
        if str(f.get("family_id") or "") != "signal_filing_boundary_v1":
            continue
        for row in f.get("row_results") or []:
            sym_u = str(row.get("symbol") or "").upper().strip()
            cik_s = str(row.get("cik") or "").strip()
            sig_by_key[(sym_u, cik_s)] = str(row.get("signal_available_date") or "")

    filing_rows = (pit.get("filing_substrate") or {}).get("per_row") or []
    sector_rows = (pit.get("sector_substrate") or {}).get("per_row") or []
    n = max(len(filing_rows), len(sector_rows))
    out: list[dict[str, Any]] = []
    for i in range(n):
        frow = filing_rows[i] if i < len(filing_rows) else {}
        srow = sector_rows[i] if i < len(sector_rows) else {}
        fc = str(frow.get("classification") or "")
        if fc == "exact_filing_public_ts_available":
            fbc = "exact_public_ts_available"
        elif fc == "exact_filing_filed_date_available":
            fbc = "accepted_at_missing_but_filed_date_only"
        else:
            fbc = "only_post_signal_filings_available"
        sc = str(srow.get("classification") or "")
        sbc = (
            "sector_available"
            if sc == "sector_metadata_available"
            else "no_market_metadata_row_for_symbol"
        )
        sym = str(frow.get("symbol") or srow.get("symbol") or "")
        cik = str(frow.get("cik") or srow.get("cik") or "")
        sig = sig_by_key.get((sym.upper().strip(), cik.strip()), "")
        out.append(
            {
                "symbol": sym,
                "cik": cik,
                "signal_available_date": sig,
                "filing_blocker_cause": fbc,
                "sector_blocker_cause": sbc,
                "blocker_replay_source": "phase41_bundle_substrate",
            }
        )
    return out


def stable_run_digest(*, bundle_core: dict[str, Any]) -> str:
    """Short hash for grouping semantically similar reruns (append-only friendly)."""
    payload = {
        "filing_dist": bundle_core.get("family_evidence_scorecard", {}).get("filing_blocker_distribution"),
        "sector_dist": bundle_core.get("family_evidence_scorecard", {}).get("sector_blocker_distribution"),
        "disc": bundle_core.get("discrimination_summary", {}).get(
            "families_with_identical_rollups_groups"
        ),
        "gate_cat": (bundle_core.get("promotion_gate_phase42") or {}).get("primary_block_category"),
    }
    s = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
