"""Live FMP transcript fetcher adapter for Agentic Operating Harness v1 Layer 1.

This is the production worker-side counterpart to
``layer1_brain_adapter.py``.  It plugs into
``agentic_harness.agents.layer1_ingest.set_transcript_fetcher(...)`` and
closes the Layer 1 loop:

    stale asset (scout) -> IngestAlertPacketV1 (coordinator) ->
    ingest_queue_worker -> **this fetcher** -> real FMP call ->
    ``raw_transcript_payloads_fmp`` + ``transcript_ingest_runs`` rows ->
    SourceArtifactPacketV1 (ok | empty) OR retryable / fail-fast failure.

The adapter is a thin wrapper around the existing
``sources.transcripts_ingest.run_fmp_sample_ingest`` pipeline so we reuse
the same DB audit trail (history table, normalized transcripts, overlay
availability row).  The fetcher itself does no direct registry / Brain
bundle mutation - ``run_fmp_sample_ingest`` already stays within source /
overlay tables, not the active Today registry.

**Retry policy (matches scheduler wiring):**

* Retryable (``retryable=True``): HTTP 429, HTTP 5xx, network / DNS
  failures.  Scheduler will backoff and try again up to ``max_attempts``.
* Fail-fast (``retryable=False``): HTTP 401 / 402 / 403, missing
  ``FMP_API_KEY``, misconfiguration.  Scheduler sends the job straight to
  DLQ so operators surface the config/auth problem immediately.

**Outcome semantics:**

* ``fetch_outcome='ok'`` - HTTP 200 + transcript content.
* ``fetch_outcome='empty'`` - HTTP 200 empty list, 404, HTTP 200 parse
  error, or HTTP 200 with error-message body.  The fetcher still returns
  ``ok=True`` so the worker persists a SourceArtifactPacketV1 that
  **honestly records** the absence (with ``blocking_reasons``) rather than
  pretending we fetched text.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Tuple

from agentic_harness.agents.layer1_ingest import TranscriptFetcher
from sources import transcripts_provider_binding as bind


log = logging.getLogger(__name__)


ClientFactory = Callable[[], Any]


# ---------------------------------------------------------------------------
# Fiscal target heuristic
# ---------------------------------------------------------------------------


def _infer_target_fiscal_quarter(now_utc: datetime) -> Tuple[int, int]:
    """Return the most recent fiscal quarter whose earnings call transcript
    is plausibly already published as of ``now_utc``.

    Earnings calls for quarter *N* are typically released 3-8 weeks after
    the quarter ends, so the "latest completed + released" quarter is the
    one that ended in the previous calendar quarter.

        * Jan-Mar -> prev year Q4
        * Apr-Jun -> cur year Q1
        * Jul-Sep -> cur year Q2
        * Oct-Dec -> cur year Q3

    This is a pragmatic default; individual issuers may be early/late, in
    which case the fetch returns a ``PARTIAL`` classification (404) and
    the adapter surfaces ``fetch_outcome='empty'``.
    """

    m = now_utc.month
    if m <= 3:
        return now_utc.year - 1, 4
    if m <= 6:
        return now_utc.year, 1
    if m <= 9:
        return now_utc.year, 2
    return now_utc.year, 3


def _parse_fiscal_target_override(raw: str) -> Optional[Tuple[int, int]]:
    """Parse ``METIS_HARNESS_L1_FISCAL_TARGET`` of the form ``YYYY-Q<n>``.

    Returns ``None`` if the value is empty or malformed so callers fall
    back to the inferred default.
    """

    s = (raw or "").strip().upper()
    if not s:
        return None
    try:
        year_s, q_s = s.split("-Q", 1)
        y = int(year_s)
        q = int(q_s)
    except (ValueError, AttributeError):
        return None
    if q not in (1, 2, 3, 4) or y < 1900 or y > 2999:
        return None
    return y, q


# ---------------------------------------------------------------------------
# FMP result classification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FetchClassification:
    """Classifier output for one FMP call.

    Attributes:
      ok: Whether the scheduler should treat this as success (worker emits
        a SourceArtifactPacketV1).  Both ``fetch_outcome='ok'`` and
        ``'empty'`` map to ``ok=True`` - the packet records the truth.
      fetch_outcome: One of ``'ok' | 'empty'`` when ``ok=True``; unused
        when ``ok=False``.
      retryable: When ``ok=False``, tells the scheduler whether to retry
        with backoff (``True``) or send to DLQ immediately (``False``).
      error: Short stable error key, e.g. ``'fmp_auth_failed:401'``.
      blocking_reasons: Reasons attached to the emitted SourceArtifact
        packet when the outcome is non-ok (e.g. ``'transcript_not_available'``).
    """

    ok: bool
    fetch_outcome: str
    retryable: bool
    error: str = ""
    blocking_reasons: Tuple[str, ...] = ()


def classify_fmp_result(
    http_status: int, probe_status: str, payload: Any
) -> FetchClassification:
    """Map (``http_status``, FMP-binding classify label, raw ``payload``)
    onto the fetcher contract.

    We look at ``http_status`` directly for auth/rate/server signals
    because the existing ``classify_fmp_http_response`` lumps 401/429/5xx
    into the same ``FAILED_RIGHTS_OR_AUTH`` label (which is fine for
    source-overlay truthfulness but not granular enough for retry
    decisions).
    """

    if http_status in (401, 402, 403):
        return FetchClassification(
            ok=False,
            fetch_outcome="",
            retryable=False,
            error=f"fmp_auth_failed:{http_status}",
        )

    if http_status == 429:
        return FetchClassification(
            ok=False,
            fetch_outcome="",
            retryable=True,
            error="fmp_rate_limited:429",
        )

    if 500 <= http_status <= 599:
        return FetchClassification(
            ok=False,
            fetch_outcome="",
            retryable=True,
            error=f"fmp_server_error:{http_status}",
        )

    if http_status == 404:
        return FetchClassification(
            ok=True,
            fetch_outcome="empty",
            retryable=False,
            blocking_reasons=("transcript_not_available_for_quarter",),
        )

    if http_status == 200:
        if probe_status == bind.AVAILABLE:
            return FetchClassification(ok=True, fetch_outcome="ok", retryable=False)
        if probe_status == bind.PARTIAL:
            return FetchClassification(
                ok=True,
                fetch_outcome="empty",
                retryable=False,
                blocking_reasons=("transcript_payload_empty_list",),
            )
        if probe_status == bind.FAILED_RIGHTS_OR_AUTH:
            # 200 but body carries an error message field.  FMP serves
            # these for quota / entitlement violations - treat as auth.
            return FetchClassification(
                ok=False,
                fetch_outcome="",
                retryable=False,
                error="fmp_auth_failed:error_body",
            )
        # CONFIGURED_BUT_UNVERIFIED = unexpected shape but HTTP ok.
        return FetchClassification(
            ok=True,
            fetch_outcome="empty",
            retryable=False,
            blocking_reasons=("transcript_payload_unexpected_shape",),
        )

    # Any other HTTP status: be defensive and retry.
    return FetchClassification(
        ok=False,
        fetch_outcome="",
        retryable=True,
        error=f"fmp_unexpected_http:{http_status}",
    )


# ---------------------------------------------------------------------------
# Fetcher factory
# ---------------------------------------------------------------------------


def build_transcript_fetcher(
    *,
    client_factory: ClientFactory,
    settings: Any,
    now_fn: Optional[Callable[[], datetime]] = None,
    asset_to_symbol: Callable[[str], str] = lambda a: a,
    run_fmp_sample_ingest_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> TranscriptFetcher:
    """Return a ``TranscriptFetcher`` closure suitable for
    ``set_transcript_fetcher(...)``.

    Parameters:
      client_factory: Zero-arg callable returning a Supabase client.
        Called once per job so the client respects any per-request state
        (service role key, etc.).
      settings: Parsed application settings (needs ``fmp_api_key``).  A
        missing key short-circuits to ``retryable=False`` so the
        scheduler surfaces the config error instead of burning retries.
      now_fn / asset_to_symbol / run_fmp_sample_ingest_fn: Test seams.
        ``run_fmp_sample_ingest_fn`` defaults to the real
        ``sources.transcripts_ingest.run_fmp_sample_ingest``.
    """

    # Lazy-import so unit tests can mock the module before the factory is
    # called, without importing the heavy source path at harness startup.
    if run_fmp_sample_ingest_fn is None:
        from sources.transcripts_ingest import run_fmp_sample_ingest as _default

        run_fmp_sample_ingest_fn = _default

    _now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def _fetcher(job_meta: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(job_meta.get("asset_id") or "").strip().upper()
        alert_packet_id = str(job_meta.get("alert_packet_id") or "").strip()
        if not asset_id:
            return {
                "ok": False,
                "error": "fetcher_missing_asset_id",
                "retryable": False,
            }

        # Preflight: if the key is missing, bail with a fail-fast error.
        # This is also gated at bootstrap but we keep a defense-in-depth
        # check here so direct callers (tests, scripts) see the same
        # behaviour as the wired-up path.
        if not bind.fmp_api_key_present(settings):
            return {
                "ok": False,
                "error": "fmp_api_key_missing",
                "retryable": False,
            }

        symbol = str(asset_to_symbol(asset_id)).upper().strip() or asset_id

        override = _parse_fiscal_target_override(
            os.getenv("METIS_HARNESS_L1_FISCAL_TARGET", "")
        )
        job_override = job_meta.get("_force_target") or {}
        if isinstance(job_override, dict) and job_override.get("year"):
            try:
                year = int(job_override.get("year"))
                quarter = int(job_override.get("quarter"))
                if quarter not in (1, 2, 3, 4):
                    raise ValueError("bad_quarter")
            except (TypeError, ValueError):
                year, quarter = _infer_target_fiscal_quarter(_now_fn())
        elif override is not None:
            year, quarter = override
        else:
            year, quarter = _infer_target_fiscal_quarter(_now_fn())

        client = client_factory()

        fmp_uri = f"fmp://earning_call_transcript/{symbol}/{year}/Q{quarter}"

        try:
            result = run_fmp_sample_ingest_fn(
                client,
                settings,
                symbol=symbol,
                year=year,
                quarter=quarter,
                operational_run_id=alert_packet_id or None,
            )
        except RuntimeError as e:
            msg = str(e)
            if msg.startswith("fmp_network_error"):
                return {
                    "ok": False,
                    "error": "fmp_network_error",
                    "retryable": True,
                    "provenance_refs": [fmp_uri],
                }
            if msg == "FMP_API_KEY_not_configured":
                return {
                    "ok": False,
                    "error": "fmp_api_key_missing",
                    "retryable": False,
                }
            if msg == "phase11_supports_fmp_only":
                return {
                    "ok": False,
                    "error": "transcripts_provider_not_fmp",
                    "retryable": False,
                }
            # Unknown RuntimeError from the pipeline - treat as retryable
            # (the pipeline may have recorded a transcript_ingest_runs row
            # already; scheduler will retry or DLQ based on attempts).
            return {
                "ok": False,
                "error": f"fmp_pipeline_error:{msg[:160]}",
                "retryable": True,
                "provenance_refs": [fmp_uri],
            }
        except Exception as e:  # pragma: no cover - defensive
            return {
                "ok": False,
                "error": f"fmp_unexpected_exception:{type(e).__name__}",
                "retryable": True,
                "provenance_refs": [fmp_uri],
            }

        http_status = int(result.get("http_status") or 0)
        probe_status = str(result.get("classify") or "")
        ingest_run_id = str(result.get("transcript_ingest_run_id") or "")
        raw_payload_id = str(result.get("raw_payload_fmp_id") or "")

        cls = classify_fmp_result(http_status, probe_status, payload=None)

        # Provenance in priority order: specific rows, then the API URI,
        # then the triggering alert packet.  Strings only - downstream
        # consumers may embed in Markdown so commas in URIs are safer.
        provenance_refs: list[str] = []
        if ingest_run_id:
            provenance_refs.append(
                f"supabase://transcript_ingest_runs/{ingest_run_id}"
            )
        if raw_payload_id:
            provenance_refs.append(
                f"supabase://raw_transcript_payloads_fmp/{raw_payload_id}"
            )
        provenance_refs.append(fmp_uri)
        if alert_packet_id:
            provenance_refs.append(f"packet:{alert_packet_id}")

        fetched_at_utc = _now_fn().isoformat()

        if not cls.ok:
            return {
                "ok": False,
                "error": cls.error or f"fmp_non_ok:{http_status}",
                "retryable": cls.retryable,
                "provenance_refs": provenance_refs,
                "http_status": http_status,
                "probe_status": probe_status,
            }

        artifact_ref = raw_payload_id or f"{symbol}:{year}-Q{quarter}"
        confidence = 0.9 if cls.fetch_outcome == "ok" else 0.5

        return {
            "ok": True,
            "fetch_outcome": cls.fetch_outcome,
            "artifact_kind": "transcript_text",
            "artifact_ref": artifact_ref,
            "fetched_at_utc": fetched_at_utc,
            "provenance_refs": provenance_refs,
            "confidence": confidence,
            "blocking_reasons": list(cls.blocking_reasons),
            "http_status": http_status,
            "probe_status": probe_status,
        }

    return _fetcher
