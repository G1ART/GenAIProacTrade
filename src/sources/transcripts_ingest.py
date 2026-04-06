"""FMP transcript PoC: fetch → raw → normalize → overlay/registry updates (single vendor)."""

from __future__ import annotations

from typing import Any, Optional

from config import Settings
from db import records as dbrec
from sources.fmp_transcript_client import fetch_earning_call_transcript
from sources.transcripts_normalizer import (
    SOURCE_REGISTRY_ID,
    normalize_fmp_earning_call_payload,
)
from sources import transcripts_provider_binding as bind

OVERLAY_KEY = "earnings_call_transcripts"


def _raw_json_blob(payload: Any) -> Any:
    if isinstance(payload, (dict, list)):
        return payload
    return {"_non_object_payload": str(payload)[:8000]}


def _apply_fmp_registry_after_probe(client: Any, probe_status: str) -> None:
    """active only on verified partial/available probe; else inactive (no stale active)."""
    if probe_status in (bind.AVAILABLE, bind.PARTIAL):
        dbrec.patch_data_source_registry_activation(
            client, source_id=SOURCE_REGISTRY_ID, activation_status="active"
        )
    else:
        dbrec.patch_data_source_registry_activation(
            client, source_id=SOURCE_REGISTRY_ID, activation_status="inactive"
        )


def _apply_fmp_registry_after_ingest_overlay(client: Any, avail_db: str) -> None:
    if avail_db in ("available", "partial"):
        dbrec.patch_data_source_registry_activation(
            client, source_id=SOURCE_REGISTRY_ID, activation_status="active"
        )
    else:
        dbrec.patch_data_source_registry_activation(
            client, source_id=SOURCE_REGISTRY_ID, activation_status="inactive"
        )


def run_fmp_probe_and_update_overlay(
    client: Any,
    settings: Settings,
    *,
    operational_run_id: Optional[str] = None,
) -> dict[str, Any]:
    pr = bind.run_fmp_probe(settings)
    avail = bind.overlay_availability_after_probe(pr["probe_status"])
    patch: dict[str, Any] = {
        "phase11_fmp_probe": pr,
        "phase11_probe_operational_run_id": operational_run_id,
    }
    dbrec.merge_update_source_overlay_availability(
        client,
        overlay_key=OVERLAY_KEY,
        availability=avail,
        metadata_patch=patch,
    )
    dbrec.insert_source_overlay_run_row(
        client,
        run_type="transcript_fmp_probe_v1",
        payload_json={"probe": pr, "operational_run_id": operational_run_id},
    )
    _apply_fmp_registry_after_probe(client, str(pr.get("probe_status") or ""))
    return pr


def run_fmp_sample_ingest(
    client: Any,
    settings: Settings,
    *,
    symbol: str,
    year: int,
    quarter: int,
    operational_run_id: Optional[str] = None,
) -> dict[str, Any]:
    if bind.effective_transcripts_provider(settings) != "fmp":
        raise RuntimeError("phase11_supports_fmp_only")
    if not bind.fmp_api_key_present(settings):
        raise RuntimeError("FMP_API_KEY_not_configured")

    sym = symbol.upper().strip()
    key = str(settings.fmp_api_key).strip()
    fiscal_period = f"{year}-Q{quarter}"

    try:
        http_status, payload = fetch_earning_call_transcript(
            key, symbol=sym, year=year, quarter=quarter
        )
    except RuntimeError as e:
        ingest_run_id = dbrec.insert_transcript_ingest_run(
            client,
            provider_code="fmp",
            operation="ingest_sample",
            status="failed",
            probe_status=bind.FAILED_NETWORK,
            detail_json={
                "symbol": sym,
                "year": year,
                "quarter": quarter,
                "error": str(e),
                "operational_run_id": operational_run_id,
            },
        )
        patch = {
            "phase11_last_ingest_error": str(e)[:2000],
            "transcript_ingest_run_id": ingest_run_id,
            "phase11_ingest_operational_run_id": operational_run_id,
        }
        dbrec.merge_update_source_overlay_availability(
            client,
            overlay_key=OVERLAY_KEY,
            availability=None,
            metadata_patch=patch,
        )
        dbrec.insert_source_overlay_run_row(
            client,
            run_type="transcript_fmp_ingest_sample_v1",
            payload_json={
                "ingest_run_id": ingest_run_id,
                "error": str(e),
                "operational_run_id": operational_run_id,
            },
        )
        _apply_fmp_registry_after_ingest_overlay(client, "not_available_yet")
        raise

    classify = bind.classify_fmp_http_response(http_status, payload)

    ingest_run_id = dbrec.insert_transcript_ingest_run(
        client,
        provider_code="fmp",
        operation="ingest_sample",
        status="completed",
        probe_status=classify,
        detail_json={
            "symbol": sym,
            "year": year,
            "quarter": quarter,
            "http_status": http_status,
            "operational_run_id": operational_run_id,
        },
    )

    dbrec.archive_raw_transcript_payload_fmp_before_upsert(
        client,
        symbol=sym,
        fiscal_year=year,
        fiscal_quarter=quarter,
        ingest_run_id=ingest_run_id,
    )

    raw_id = dbrec.upsert_raw_transcript_payload_fmp(
        client,
        symbol=sym,
        fiscal_year=year,
        fiscal_quarter=quarter,
        http_status=http_status,
        raw_response_json=_raw_json_blob(payload),
        ingest_run_id=ingest_run_id,
    )

    issuer_id = dbrec.fetch_issuer_id_for_ticker(client, ticker=sym)
    prior = dbrec.fetch_normalized_transcript_by_period(
        client,
        provider_name="financial_modeling_prep",
        ticker=sym,
        fiscal_period=fiscal_period,
    )
    pid = str(prior["id"]) if prior and prior.get("id") else None
    prev_rev = str(prior["revision_id"]) if prior and prior.get("revision_id") else None

    norm_row = normalize_fmp_earning_call_payload(
        ticker=sym,
        fiscal_year=year,
        fiscal_quarter=quarter,
        http_status=http_status,
        payload=payload,
        raw_payload_fmp_id=raw_id,
        issuer_id=issuer_id,
        ingest_run_id=ingest_run_id,
        prior_normalized_id=pid,
        prior_revision_id=prev_rev,
    )

    norm_id: Optional[str] = None
    if norm_row:
        norm_id = dbrec.upsert_normalized_transcript(client, norm_row)

    nstatus = (norm_row or {}).get("normalization_status") or "none"
    has_text = bool(norm_row and str(norm_row.get("transcript_text") or "").strip())

    if classify == bind.FAILED_RIGHTS_OR_AUTH:
        avail_db = "not_available_yet"
    elif classify in (bind.FAILED_NETWORK, bind.NOT_CONFIGURED):
        avail_db = "not_available_yet"
    else:
        avail_db = bind.overlay_availability_after_ingest(
            normalization_status=str(nstatus),
            has_transcript_text=has_text,
        )

    patch: dict[str, Any] = {
        "phase11_last_ingest": {
            "symbol": sym,
            "fiscal_year": year,
            "fiscal_quarter": quarter,
            "http_status": http_status,
            "classify": classify,
            "normalization_status": nstatus,
            "normalized_transcript_id": norm_id,
            "transcript_ingest_run_id": ingest_run_id,
        },
        "phase11_ingest_operational_run_id": operational_run_id,
    }
    dbrec.merge_update_source_overlay_availability(
        client,
        overlay_key=OVERLAY_KEY,
        availability=avail_db,
        metadata_patch=patch,
    )
    dbrec.insert_source_overlay_run_row(
        client,
        run_type="transcript_fmp_ingest_sample_v1",
        payload_json={
            "ingest_run_id": ingest_run_id,
            "normalized_transcript_id": norm_id,
            "availability": avail_db,
            "operational_run_id": operational_run_id,
        },
    )
    _apply_fmp_registry_after_ingest_overlay(client, avail_db)

    return {
        "symbol": sym,
        "year": year,
        "quarter": quarter,
        "http_status": http_status,
        "classify": classify,
        "transcript_ingest_run_id": ingest_run_id,
        "raw_payload_fmp_id": raw_id,
        "normalized_transcript_id": norm_id,
        "normalization_status": nstatus,
        "overlay_availability": avail_db,
    }


def report_transcripts_overlay_status(client: Any) -> dict[str, Any]:
    row = dbrec.fetch_source_overlay_availability_by_key(
        client, overlay_key=OVERLAY_KEY
    )
    if not row:
        return {"overlay_key": OVERLAY_KEY, "error": "row_not_found"}
    return {
        "overlay_key": OVERLAY_KEY,
        "availability": row.get("availability"),
        "linked_source_id": row.get("linked_source_id"),
        "last_checked_at": row.get("last_checked_at"),
        "metadata_json": row.get("metadata_json") or {},
    }
