"""AGH v1 Patch 5 — production-capable ``governance_scan`` spec provider.

Wraps a real Supabase client (``db.client.get_supabase_client``) into the
``GovernanceScanSpecProvider`` surface declared by
``agentic_harness.agents.layer4_promotion_evaluator_v1``. The provider walks
recent ``factor_validation_runs`` (``status='completed'``) and maps each one
to zero or more evaluator specs by joining:

    1. ``factor_validation_runs`` + ``factor_validation_summaries`` for the
       newest completed run per ``(universe_name, horizon_type)`` within a
       dedupe window.
    2. The live brain bundle's ``registry_entries[*]`` whose ``universe`` +
       ``horizon`` match the validation run's ``universe_name`` +
       ``map_validation_horizon_to_bundle_horizon(horizon_type)``.
    3. Each registry entry's optional ``research_factor_bindings_v1`` list
       (``[{factor_name, return_basis}, ...]``), which is the ONLY place
       where a ``factor_name`` / ``return_basis`` pair is linked to a
       registry entry. Unbound registry entries are honest-skipped (no
       spec emitted).

Idempotency: before appending a spec, the provider consults the harness
packet store for a pre-existing ``ValidationPromotionEvaluationV1`` whose
``(registry_entry_id, horizon, derived_artifact_id, validation_run_id)``
tuple already matches. If found, the spec is dropped so a second
``governance_scan`` tick on the same evidence does not produce duplicate
proposals.

Non-goals:

* The provider NEVER mutates the registry itself. It only emits
  ``list[spec]`` that the evaluator consumes read-only.
* No live ``factor_validation`` pipeline is triggered from the provider.
  The presence of a ``completed`` run is the only trigger.
* No free-form inference of factor → registry binding. Registry entries
  without ``research_factor_bindings_v1`` are dropped with an explicit
  skip reason.

Env-gated install site: ``src/main.py`` ``perform_tick`` bootstrap.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Optional

from agentic_harness.agents.layer4_promotion_evaluator_v1 import (
    GovernanceScanSpecProvider,
    derive_artifact_id,
)
from agentic_harness.store.protocol import HarnessStoreProtocol
from metis_brain.artifact_from_validation_v1 import (
    map_validation_horizon_to_bundle_horizon,
)
from metis_brain.bundle_promotion_merge_v0 import load_bundle_json


log = logging.getLogger(__name__)


DEFAULT_DEDUPE_WINDOW_DAYS = 14
DEFAULT_RUN_FETCH_LIMIT = 50


def _emit_perf_log(*, fn: str, ms: float, extra: dict[str, Any] | None = None) -> None:
    """AGH v1 Patch 7 C2d — single-line structured perf log to stderr.

    No new dependencies: vanilla ``json.dumps`` to ``sys.stderr``. The
    scheduler tick / Today spectrum builder / governance dedupe use the
    same ``kind:"metis_perf"`` envelope so a future analyzer can grep
    stderr without parsing rich log frames. Failures are swallowed to
    keep perf instrumentation strictly side-channel.
    """
    try:
        rec = {
            "kind": "metis_perf",
            "fn": fn,
            "ms": round(float(ms), 3),
        }
        if extra:
            rec.update(extra)
        sys.stderr.write(json.dumps(rec, sort_keys=True) + "\n")
    except Exception:  # pragma: no cover - defensive
        pass


def _parse_iso(s: str) -> Optional[datetime]:
    s = str(s or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def list_recent_completed_validation_runs(
    client: Any,
    *,
    since_iso: str,
    limit: int = DEFAULT_RUN_FETCH_LIMIT,
) -> list[dict[str, Any]]:
    """Fetch ``factor_validation_runs`` with ``status='completed'`` and
    ``completed_at >= since_iso``, newest-first.

    For each run, expand one or more summaries (``factor_validation_summaries``
    rows keyed by ``run_id``) so the caller can see every ``factor_name`` +
    ``return_basis`` combo the run produced. Returns a flat list of dicts
    with the shape::

        {
            "run_id": str,
            "universe_name": str,
            "horizon_type": str,
            "completed_at": str,
            "factor_name": str,
            "return_basis": str,
        }

    Empty list on any failure (logged + swallowed) so an occasional
    transient fetch error never stalls the cadence.
    """

    try:
        r = (
            client.table("factor_validation_runs")
            .select("id,universe_name,horizon_type,completed_at,status")
            .eq("status", "completed")
            .gte("completed_at", since_iso)
            .order("completed_at", desc=True)
            .limit(int(limit))
            .execute()
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("governance_scan provider: fetch_runs failed: %s", exc)
        return []

    runs = list(getattr(r, "data", None) or [])
    if not runs:
        return []

    run_ids = [str(row.get("id") or "") for row in runs if row.get("id")]
    if not run_ids:
        return []

    try:
        s = (
            client.table("factor_validation_summaries")
            .select("run_id,factor_name,return_basis")
            .in_("run_id", run_ids)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("governance_scan provider: fetch_summaries failed: %s", exc)
        return []

    summaries = list(getattr(s, "data", None) or [])
    by_run: dict[str, list[dict[str, Any]]] = {}
    for row in summaries:
        rid = str(row.get("run_id") or "")
        if not rid:
            continue
        by_run.setdefault(rid, []).append(
            {
                "factor_name": str(row.get("factor_name") or ""),
                "return_basis": str(row.get("return_basis") or ""),
            }
        )

    out: list[dict[str, Any]] = []
    for run in runs:
        rid = str(run.get("id") or "")
        pairs = by_run.get(rid) or []
        if not pairs:
            continue
        seen: set[tuple[str, str]] = set()
        for pair in pairs:
            factor = pair["factor_name"].strip()
            basis = pair["return_basis"].strip() or "raw"
            if not factor:
                continue
            key = (factor, basis)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "run_id": rid,
                    "universe_name": str(run.get("universe_name") or "").strip(),
                    "horizon_type": str(run.get("horizon_type") or "").strip(),
                    "completed_at": str(run.get("completed_at") or ""),
                    "factor_name": factor,
                    "return_basis": basis,
                }
            )
    return out


def match_runs_to_registry_entries(
    runs: list[dict[str, Any]],
    bundle_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    """Join the flat ``runs`` list to the bundle's ``registry_entries``.

    Emits one spec per (run, registry_entry, binding) triple where:

    * ``run.universe_name == entry.universe``
    * ``map_validation_horizon_to_bundle_horizon(run.horizon_type) == entry.horizon``
    * ``entry.research_factor_bindings_v1`` contains a
      ``{factor_name, return_basis}`` matching the run.

    Registry entries that carry no ``research_factor_bindings_v1`` are
    honest-skipped. The emitted spec shape matches what
    ``evaluate_registry_entries`` expects, with an extra ``_evidence``
    block so downstream code (and tests) can trace the run origin.
    """

    entries = list(bundle_dict.get("registry_entries") or [])
    if not entries or not runs:
        return []

    specs: list[dict[str, Any]] = []
    for run in runs:
        universe = str(run.get("universe_name") or "").strip()
        htype = str(run.get("horizon_type") or "").strip()
        if not universe or not htype:
            continue
        try:
            bundle_horizon = map_validation_horizon_to_bundle_horizon(htype)
        except ValueError:
            continue
        factor = str(run.get("factor_name") or "").strip()
        basis = str(run.get("return_basis") or "").strip() or "raw"
        run_id = str(run.get("run_id") or "").strip()
        completed_at = str(run.get("completed_at") or "")
        if not factor or not run_id:
            continue

        for ent in entries:
            if not isinstance(ent, dict):
                continue
            if str(ent.get("universe") or "").strip() != universe:
                continue
            if str(ent.get("horizon") or "").strip() != bundle_horizon:
                continue
            bindings = list(ent.get("research_factor_bindings_v1") or [])
            if not bindings:
                continue
            match = None
            for b in bindings:
                if not isinstance(b, dict):
                    continue
                if (
                    str(b.get("factor_name") or "").strip() == factor
                    and (str(b.get("return_basis") or "").strip() or "raw") == basis
                ):
                    match = b
                    break
            if match is None:
                continue
            specs.append(
                {
                    "registry_entry_id": str(ent.get("registry_entry_id") or ""),
                    "horizon": bundle_horizon,
                    "factor_name": factor,
                    "universe_name": universe,
                    "horizon_type": htype,
                    "return_basis": basis,
                    "_evidence": {
                        "validation_run_id": run_id,
                        "completed_at": completed_at,
                    },
                }
            )
    return specs


def _existing_evaluation_matches(
    store: HarnessStoreProtocol,
    *,
    registry_entry_id: str,
    horizon: str,
    derived_artifact_id: str,
    validation_run_id: str,
    limit: int = 200,
) -> bool:
    """Legacy per-spec lookup kept for backward compatibility.

    AGH v1 Patch 7 switches ``deduplicate_specs`` to a single hoisted
    ``list_packets`` call to avoid an N+1 query pattern (see
    ``docs/plan/METIS_Scale_Readiness_Note_Patch7_v1.md`` Finding 2).
    This helper is no longer on the dedupe hot path, but we keep it so
    external callers (and isolated unit tests) can still ask "does this
    evaluation already exist?" without rebuilding the index.
    """
    try:
        rows = store.list_packets(
            packet_type="ValidationPromotionEvaluationV1", limit=limit
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("governance_scan provider: list_packets failed: %s", exc)
        return False
    for r in rows or []:
        payload = r.get("payload") or {}
        if (
            str(payload.get("registry_entry_id") or "") == registry_entry_id
            and str(payload.get("horizon") or "") == horizon
            and str(payload.get("derived_artifact_id") or "") == derived_artifact_id
            and str(payload.get("validation_run_id") or "") == validation_run_id
        ):
            return True
    return False


def _build_existing_evaluation_index(
    store: HarnessStoreProtocol,
    *,
    limit: int,
) -> set[tuple[str, str, str, str]]:
    """Load ``ValidationPromotionEvaluationV1`` packets once and return a
    hash index keyed by the 4-tuple that dedupe decisions care about.

    AGH v1 Patch 7 Scope C2a: see
    ``docs/plan/METIS_Scale_Readiness_Note_Patch7_v1.md`` Finding 2.
    """
    try:
        rows = store.list_packets(
            packet_type="ValidationPromotionEvaluationV1", limit=limit
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("governance_scan provider: list_packets failed: %s", exc)
        return set()
    index: set[tuple[str, str, str, str]] = set()
    for r in rows or []:
        payload = r.get("payload") or {}
        index.add(
            (
                str(payload.get("registry_entry_id") or ""),
                str(payload.get("horizon") or ""),
                str(payload.get("derived_artifact_id") or ""),
                str(payload.get("validation_run_id") or ""),
            )
        )
    return index


def deduplicate_specs(
    store: HarnessStoreProtocol,
    specs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop specs that already have a matching
    ``ValidationPromotionEvaluationV1`` packet in the store.

    Uses the same deterministic ``derive_artifact_id`` policy as the
    evaluator so "same evidence -> same artifact id" holds across ticks.

    AGH v1 Patch 7 C2a: the existing evaluation lookup is hoisted out of
    the per-spec loop — one ``list_packets`` call, O(1) membership
    check against an in-memory set — so a governance_scan tick costs a
    constant number of store reads regardless of how many specs the
    validation runner produced. Semantics are unchanged (same 4-tuple
    equality as the legacy ``_existing_evaluation_matches`` helper).
    """

    if not specs:
        return []
    t0 = perf_counter()
    existing = _build_existing_evaluation_index(
        store, limit=max(200, 2 * len(specs))
    )
    out: list[dict[str, Any]] = []
    dropped = 0
    for spec in specs:
        ev = spec.get("_evidence") or {}
        validation_run_id = str(ev.get("validation_run_id") or "").strip()
        if not validation_run_id:
            out.append(spec)
            continue
        try:
            derived = derive_artifact_id(
                factor_name=str(spec["factor_name"]),
                universe_name=str(spec["universe_name"]),
                horizon_type=str(spec["horizon_type"]),
                return_basis=str(spec["return_basis"]),
                validation_run_id=validation_run_id,
            )
        except ValueError:
            continue
        key = (
            str(spec["registry_entry_id"]),
            str(spec["horizon"]),
            derived,
            validation_run_id,
        )
        if key in existing:
            dropped += 1
            continue
        out.append(spec)
    _emit_perf_log(
        fn="governance_scan_provider_v1.deduplicate_specs",
        ms=(perf_counter() - t0) * 1000.0,
        extra={
            "specs_in": len(specs),
            "specs_out": len(out),
            "dropped": dropped,
            "existing_index_size": len(existing),
        },
    )
    return out


def build_supabase_governance_scan_provider(
    *,
    client_factory: Callable[[], Any],
    bundle_path_factory: Callable[[], Path],
    dedupe_window_days: int = DEFAULT_DEDUPE_WINDOW_DAYS,
    run_fetch_limit: int = DEFAULT_RUN_FETCH_LIMIT,
) -> GovernanceScanSpecProvider:
    """Return a ``GovernanceScanSpecProvider`` callable suitable for
    ``set_governance_scan_spec_provider``.

    The provider is a pure-function wrapper: every call rebuilds the
    Supabase client (via ``client_factory``) and re-reads the brain bundle
    (via ``bundle_path_factory``) so cadence ticks always see the latest
    state. Failures are logged and swallowed as empty spec lists.
    """

    def _provider(
        store: HarnessStoreProtocol, now_iso: str
    ) -> list[dict[str, Any]]:
        now = _parse_iso(now_iso) or datetime.now(timezone.utc)
        since = (now - timedelta(days=max(1, int(dedupe_window_days)))).isoformat()
        try:
            client = client_factory()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("governance_scan provider: client_factory failed: %s", exc)
            return []
        runs = list_recent_completed_validation_runs(
            client, since_iso=since, limit=run_fetch_limit
        )
        if not runs:
            return []
        try:
            bundle_path = bundle_path_factory()
            bundle_dict = load_bundle_json(bundle_path)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("governance_scan provider: bundle load failed: %s", exc)
            return []
        specs = match_runs_to_registry_entries(runs, bundle_dict)
        return deduplicate_specs(store, specs)

    return _provider


def scan_and_build_specs(
    store: HarnessStoreProtocol,
    *,
    client: Any,
    bundle_dict: dict[str, Any],
    now_iso: str,
    dedupe_window_days: int = DEFAULT_DEDUPE_WINDOW_DAYS,
    run_fetch_limit: int = DEFAULT_RUN_FETCH_LIMIT,
) -> list[dict[str, Any]]:
    """Synchronous helper used by tests / runbooks when the caller already
    has a ready client + bundle dict (no factories needed).
    """

    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    since = (now - timedelta(days=max(1, int(dedupe_window_days)))).isoformat()
    runs = list_recent_completed_validation_runs(
        client, since_iso=since, limit=run_fetch_limit
    )
    if not runs:
        return []
    specs = match_runs_to_registry_entries(runs, bundle_dict)
    return deduplicate_specs(store, specs)
