"""Single-vendor (FMP) transcript binding + probe status classification."""

from __future__ import annotations

from typing import Any, Optional

from config import Settings

from sources.fmp_transcript_client import fetch_earning_call_transcript

# Probe / path lifecycle (truthful; no fake success).
NOT_CONFIGURED = "not_configured"
CONFIGURED_BUT_UNVERIFIED = "configured_but_unverified"
PARTIAL = "partial"
AVAILABLE = "available"
FAILED_RIGHTS_OR_AUTH = "failed_rights_or_auth"
FAILED_NETWORK = "failed_network"

DEFAULT_PROBE_SYMBOL = "AAPL"
DEFAULT_PROBE_YEAR = 2020
DEFAULT_PROBE_QUARTER = 3


def effective_transcripts_provider(settings: Settings) -> str:
    p = (settings.transcripts_provider or "fmp").strip().lower()
    return p if p else "fmp"


def fmp_api_key_present(settings: Settings) -> bool:
    return bool(settings.fmp_api_key and str(settings.fmp_api_key).strip())


def run_fmp_probe(
    settings: Settings,
    *,
    symbol: str = DEFAULT_PROBE_SYMBOL,
    year: int = DEFAULT_PROBE_YEAR,
    quarter: int = DEFAULT_PROBE_QUARTER,
) -> dict[str, Any]:
    """
    One HTTP round-trip to FMP earning_call_transcript.
    Does not persist transcript rows (use ingest CLI for that).
    """
    if effective_transcripts_provider(settings) != "fmp":
        return {
            "probe_status": NOT_CONFIGURED,
            "detail": "only_fmp_supported_in_phase11",
            "provider": "fmp",
        }
    if not fmp_api_key_present(settings):
        return {
            "probe_status": NOT_CONFIGURED,
            "detail": "FMP_API_KEY_missing",
            "provider": "fmp",
        }
    key = str(settings.fmp_api_key).strip()
    try:
        status, payload = fetch_earning_call_transcript(
            key, symbol=symbol, year=year, quarter=quarter
        )
    except RuntimeError as e:
        return {
            "probe_status": FAILED_NETWORK,
            "http_status": None,
            "detail": str(e),
            "provider": "fmp",
        }
    ps = classify_fmp_http_response(status, payload)
    return {
        "probe_status": ps,
        "http_status": status,
        "provider": "fmp",
        "symbol": symbol.upper(),
        "year": year,
        "quarter": quarter,
        "payload_shape": type(payload).__name__,
        "list_len": len(payload) if isinstance(payload, list) else None,
    }


def classify_fmp_http_response(http_status: int, payload: Any) -> str:
    if http_status in (401, 403):
        return FAILED_RIGHTS_OR_AUTH
    if http_status == 402:
        return FAILED_RIGHTS_OR_AUTH
    if http_status == 404:
        return PARTIAL
    if http_status != 200:
        return FAILED_RIGHTS_OR_AUTH
    if isinstance(payload, dict) and (
        payload.get("Error Message") or payload.get("error")
    ):
        return FAILED_RIGHTS_OR_AUTH
    if isinstance(payload, list):
        if len(payload) == 0:
            return PARTIAL
        has_text = any(
            isinstance(x, dict) and str(x.get("content") or "").strip()
            for x in payload
        )
        return AVAILABLE if has_text else PARTIAL
    return CONFIGURED_BUT_UNVERIFIED


def overlay_availability_after_probe(probe_status: str) -> Optional[str]:
    """
    DB source_overlay_availability.availability.
    None = leave previous value (e.g. transient network failure).
    """
    if probe_status == AVAILABLE:
        return "available"
    if probe_status == PARTIAL:
        return "partial"
    if probe_status in (NOT_CONFIGURED, FAILED_RIGHTS_OR_AUTH, CONFIGURED_BUT_UNVERIFIED):
        return "not_available_yet"
    if probe_status == FAILED_NETWORK:
        return None
    return "not_available_yet"


def overlay_availability_after_ingest(*, normalization_status: str, has_transcript_text: bool) -> str:
    """After a successful HTTP ingest + normalize attempt."""
    if normalization_status == "ok" and has_transcript_text:
        return "available"
    return "partial"
