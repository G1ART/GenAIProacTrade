"""Record Phase 41 substrate evidence on hypotheses (append-only; status unchanged if already supported)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def apply_phase41_substrate_evidence(
    hypotheses: list[dict[str, Any]],
    *,
    pit_result: dict[str, Any],
    evidence_ref: str,
) -> dict[str, Any]:
    """
    Attach falsifier substrate summaries to filing + sector hypotheses without forcing
    redundant lifecycle status churn when already conditionally_supported.
    """
    filing_summary = (pit_result.get("filing_substrate") or {}).get("summary") or {}
    sector_summary = (pit_result.get("sector_substrate") or {}).get("summary") or {}
    families = pit_result.get("families_executed") or []
    leak_by_fid = {
        str(f.get("family_id") or ""): bool((f.get("leakage_audit") or {}).get("passed"))
        for f in families
    }

    event = {
        "phase": "phase41",
        "evidence_ref": evidence_ref,
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "filing_substrate_summary": filing_summary,
        "sector_substrate_summary": sector_summary,
        "leakage_passed_signal_filing_boundary": leak_by_fid.get("signal_filing_boundary_v1"),
        "leakage_passed_issuer_sector": leak_by_fid.get("issuer_sector_reporting_cadence_v1"),
    }

    targets = (
        ("hyp_signal_availability_filing_boundary_v1", "signal_filing_boundary_v1"),
        ("hyp_issuer_sector_reporting_cadence_v1", "issuer_sector_reporting_cadence_v1"),
    )
    out = {"attached": []}
    for hid, fid in targets:
        hyp = next((h for h in hypotheses if str(h.get("hypothesis_id") or "") == hid), None)
        if not hyp:
            continue
        log = hyp.get("substrate_audit_log")
        if not isinstance(log, list):
            log = []
            hyp["substrate_audit_log"] = log
        row = dict(event)
        row["family_id"] = fid
        row["falsifier_label_filing"] = _filing_label(filing_summary)
        row["falsifier_label_sector"] = _sector_label(sector_summary)
        log.append(row)
        out["attached"].append(hid)

    return out


def _filing_label(summary: dict[str, Any]) -> str:
    n = int(summary.get("row_count") or 0)
    proxy = int(summary.get("rows_with_explicit_signal_proxy") or 0)
    if n <= 0:
        return "unknown"
    if proxy == 0:
        return "genuinely_more_falsifiable_filing_ts"
    if proxy >= n:
        return "proxy_limited_filing_ts"
    return "partially_proxy_limited_filing_ts"


def _sector_label(summary: dict[str, Any]) -> str:
    by_c = summary.get("by_classification") or {}
    n = int(summary.get("row_count") or 0)
    miss = int(by_c.get("sector_metadata_missing") or 0)
    if n <= 0:
        return "unknown"
    if miss == 0:
        return "sector_aware_replay_enabled"
    if miss >= n:
        return "proxy_limited_sector_metadata"
    return "partially_sector_metadata"
