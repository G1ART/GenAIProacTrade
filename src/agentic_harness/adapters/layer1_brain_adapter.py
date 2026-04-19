"""Layer 1 Brain-bundle stale-asset provider (production wiring, read-only).

Combines two read-only sources to synthesise a ``StaleAssetProvider``:

1. **Universe** - the sorted unique ``asset_id`` set observed in the active
   Brain bundle (``data/mvp/metis_brain_bundle_v0.json`` or whichever path
   the ``METIS_BRAIN_BUNDLE`` env override points to).  This is the same
   universe Today surfaces via the registry, so Layer 1 is *consuming*
   Brain state rather than bypassing it (Spec §3.3).
2. **Last fetched time** - ``max(fetched_at)`` per symbol from
   ``public.raw_transcript_payloads_fmp`` (primary) with a fallback to
   ``public.transcript_ingest_runs`` rows whose ``detail_json->>symbol``
   matches and whose ``status='success'``.

**Invariants**:

- No mutation of Brain bundle, registry, or any source table.
- No live FMP fetch - that is gated behind a separate follow-up patch
  (the worker continues to use ``_fallback_transcript_fetcher`` unless
  operators explicitly override it).
- Env overrides (``METIS_HARNESS_L1_FRESHNESS_HOURS`` /
  ``METIS_HARNESS_L1_UNIVERSE_SOURCE``) are honoured at factory time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Optional

from agentic_harness.agents.layer1_ingest import StaleAssetProvider
from agentic_harness.store.protocol import HarnessStoreProtocol


DEFAULT_FRESHNESS_HOURS = 90 * 24  # 2160 - quarterly transcript cadence.
DEFAULT_UNIVERSE_SOURCE = "brain_bundle"
_ALLOWED_UNIVERSE_SOURCES = {"brain_bundle"}


# ---------------------------------------------------------------------------
# Brain bundle universe
# ---------------------------------------------------------------------------


def _brain_bundle_path() -> Path:
    """Resolve the active Brain bundle JSON path, honouring the same env
    override (``METIS_BRAIN_BUNDLE``) used by ``metis_brain.bundle``."""

    override = (os.environ.get("METIS_BRAIN_BUNDLE") or "").strip()
    if override:
        return Path(override)
    # ``src/agentic_harness/adapters/layer1_brain_adapter.py`` - repo root
    # is three parents up from ``adapters``.
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "data" / "mvp" / "metis_brain_bundle_v0.json"


def _universe_from_brain_bundle(path: Optional[Path] = None) -> list[str]:
    """Return the sorted unique ``asset_id`` list from the Brain bundle's
    ``spectrum_rows_by_horizon``.

    Missing / malformed bundle is treated as an empty universe rather than
    a crash: that keeps the harness tick safe even when Brain is being
    rebuilt mid-deploy.
    """

    p = path or _brain_bundle_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    buckets = raw.get("spectrum_rows_by_horizon")
    if not isinstance(buckets, dict):
        return []
    seen: set[str] = set()
    for rows in buckets.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            aid = str(row.get("asset_id") or "").strip().upper()
            if aid:
                seen.add(aid)
    return sorted(seen)


# ---------------------------------------------------------------------------
# Last-fetched lookup (Supabase, read-only)
# ---------------------------------------------------------------------------


ClientFactory = Callable[[], Any]
"""Zero-arg factory returning a Supabase Client, so tests inject a stub."""


def _query_last_fetched_raw(
    client: Any, symbols: list[str]
) -> dict[str, str]:
    """Primary path: ``raw_transcript_payloads_fmp`` grouped by symbol.

    We ask for all rows for the requested symbols ordered by ``fetched_at``
    desc, then keep the first occurrence per symbol.  Batched to stay under
    PostgREST query-string limits - 100 symbols per page.
    """

    out: dict[str, str] = {}
    if not symbols:
        return out
    CHUNK = 100
    for i in range(0, len(symbols), CHUNK):
        chunk = symbols[i : i + CHUNK]
        try:
            r = (
                client.table("raw_transcript_payloads_fmp")
                .select("symbol,fetched_at")
                .in_("symbol", chunk)
                .order("fetched_at", desc=True)
                .execute()
            )
        except Exception:
            continue
        for row in getattr(r, "data", None) or []:
            sym = str(row.get("symbol") or "").upper().strip()
            ts = str(row.get("fetched_at") or "").strip()
            if sym and ts and sym not in out:
                out[sym] = ts
    return out


def _query_last_fetched_runs(
    client: Any, symbols: list[str], already: dict[str, str]
) -> dict[str, str]:
    """Fallback path: ``transcript_ingest_runs`` where ``status='success'``
    and ``detail_json->>symbol = <s>``.  We only query symbols that the
    primary lookup didn't already cover.
    """

    missing = [s for s in symbols if s not in already]
    if not missing:
        return already
    out = dict(already)
    for sym in missing:
        try:
            r = (
                client.table("transcript_ingest_runs")
                .select("created_at,detail_json,status")
                .eq("status", "success")
                .filter("detail_json->>symbol", "eq", sym)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception:
            continue
        rows = getattr(r, "data", None) or []
        if rows:
            ts = str((rows[0] or {}).get("created_at") or "").strip()
            if ts:
                out[sym] = ts
    return out


def _last_fetched_map(client: Any, symbols: list[str]) -> dict[str, str]:
    """Public helper kept visible for tests; production code calls the
    factory below."""

    primary = _query_last_fetched_raw(client, symbols)
    return _query_last_fetched_runs(client, symbols, primary)


# ---------------------------------------------------------------------------
# StaleAssetProvider factory
# ---------------------------------------------------------------------------


def _resolve_freshness_hours(explicit: Optional[int]) -> int:
    if explicit is not None:
        return max(1, int(explicit))
    raw = os.getenv("METIS_HARNESS_L1_FRESHNESS_HOURS", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return DEFAULT_FRESHNESS_HOURS


def _resolve_universe_source(explicit: Optional[str]) -> str:
    src = (explicit or os.getenv("METIS_HARNESS_L1_UNIVERSE_SOURCE") or DEFAULT_UNIVERSE_SOURCE).strip()
    if src not in _ALLOWED_UNIVERSE_SOURCES:
        raise ValueError(
            f"unsupported METIS_HARNESS_L1_UNIVERSE_SOURCE={src!r}; "
            f"supported: {sorted(_ALLOWED_UNIVERSE_SOURCES)}"
        )
    return src


def build_stale_asset_provider(
    *,
    freshness_hours: Optional[int] = None,
    universe_source: Optional[str] = None,
    client_factory: ClientFactory,
    universe_loader: Optional[Callable[[], list[str]]] = None,
    last_fetched_loader: Optional[Callable[[Any, list[str]], dict[str, str]]] = None,
) -> StaleAssetProvider:
    """Return a ``StaleAssetProvider`` ready to plug into Layer 1.

    Parameters let tests substitute loaders without monkeypatching modules.
    """

    fh = _resolve_freshness_hours(freshness_hours)
    src = _resolve_universe_source(universe_source)
    uni_fn = universe_loader or _universe_from_brain_bundle
    fetched_fn = last_fetched_loader or _last_fetched_map

    def _provider(
        store: HarnessStoreProtocol, now_iso: str
    ) -> list[dict[str, Any]]:
        # store is unused in read-only adapter path - Layer 1 writes via
        # ingest_coordinator_agent after source_scout_agent filters.
        del store, now_iso

        if src != "brain_bundle":  # pragma: no cover - guarded above
            return []
        symbols = uni_fn()
        if not symbols:
            return []
        client = client_factory()
        last_map = fetched_fn(client, symbols)
        out: list[dict[str, Any]] = []
        for s in symbols:
            out.append(
                {
                    "asset_id": s,
                    "last_fetched_at_utc": str(last_map.get(s) or ""),
                    "expected_freshness_hours": fh,
                    "provenance_refs": [
                        f"brain_bundle://{src}",
                        "supabase://raw_transcript_payloads_fmp",
                    ],
                    "source_family": "earnings_transcript",
                }
            )
        return out

    return _provider
