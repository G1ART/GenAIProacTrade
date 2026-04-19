"""High-level entrypoints for CLI integration.

The CLI (`harness-tick`, `harness-status`, `harness-ask`) calls into this
module rather than reaching into the scheduler / store / agent layers
directly. It is the single place where the agent topology is wired up.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from agentic_harness.scheduler.tick import (
    LayerCadenceSpec,
    QueueSpec,
    run_one_tick,
)
from agentic_harness.store import FixtureHarnessStore, HarnessStoreProtocol


# Module-level singleton fixture store, for `--use-fixture` mode, so repeated
# CLI invocations within one process share state.
_FIXTURE_STORE: Optional[FixtureHarnessStore] = None

_LAYER1_PRODUCTION_BOOTSTRAPPED = False


def _get_fixture_store() -> FixtureHarnessStore:
    global _FIXTURE_STORE
    if _FIXTURE_STORE is None:
        _FIXTURE_STORE = FixtureHarnessStore()
    return _FIXTURE_STORE


def build_store(*, use_fixture: bool = False) -> HarnessStoreProtocol:
    """Return a store respecting the ``use_fixture`` flag.

    Fixture store is default-safe: it never touches the network. The
    Supabase-backed store requires SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY.
    """

    if use_fixture:
        return _get_fixture_store()
    from config import load_settings
    from db.client import get_supabase_client
    from agentic_harness.store.supabase_store import SupabaseHarnessStore

    settings = load_settings()
    client = get_supabase_client(settings)
    return SupabaseHarnessStore(client)


def build_layer_cadences() -> list[LayerCadenceSpec]:
    """Wire up layer propose_fns. Empty until agents are registered below."""

    specs: list[LayerCadenceSpec] = []
    try:
        from agentic_harness.agents.layer1_ingest import propose_layer1_cadence

        specs.append(
            LayerCadenceSpec(
                cadence_key="layer1.transcript_ingest",
                propose_fn=propose_layer1_cadence,
            )
        )
    except ImportError:
        pass
    try:
        from agentic_harness.agents.layer2_library import propose_layer2_cadence

        specs.append(
            LayerCadenceSpec(
                cadence_key="layer2.coverage_triage",
                propose_fn=propose_layer2_cadence,
            )
        )
    except ImportError:
        pass
    try:
        from agentic_harness.agents.layer3_research import propose_layer3_cadence

        specs.append(
            LayerCadenceSpec(
                cadence_key="layer3.challenger_cycle",
                propose_fn=propose_layer3_cadence,
            )
        )
    except ImportError:
        pass
    try:
        from agentic_harness.agents.layer4_governance import propose_layer4_cadence

        specs.append(
            LayerCadenceSpec(
                cadence_key="layer4.registry_proposal",
                propose_fn=propose_layer4_cadence,
            )
        )
    except ImportError:
        pass
    return specs


def build_queue_specs() -> list[QueueSpec]:
    """Wire up queue workers. Empty until layer workers are registered."""

    specs: list[QueueSpec] = []
    try:
        from agentic_harness.agents.layer1_ingest import ingest_queue_worker

        specs.append(QueueSpec(queue_class="ingest_queue", worker_fn=ingest_queue_worker))
    except ImportError:
        pass
    try:
        from agentic_harness.agents.layer2_library import quality_queue_worker

        specs.append(QueueSpec(queue_class="quality_queue", worker_fn=quality_queue_worker))
    except ImportError:
        pass
    try:
        from agentic_harness.agents.layer3_research import research_queue_worker

        specs.append(QueueSpec(queue_class="research_queue", worker_fn=research_queue_worker))
    except ImportError:
        pass
    try:
        from agentic_harness.agents.layer4_governance import governance_queue_worker

        specs.append(
            QueueSpec(queue_class="governance_queue", worker_fn=governance_queue_worker)
        )
    except ImportError:
        pass
    return specs


def _maybe_bootstrap_layer1_production(
    store: HarnessStoreProtocol, *, use_fixture: bool
) -> None:
    """Env-gated hook: wire Layer 1's StaleAssetProvider to the real Brain
    bundle + transcript ingest history.

    Activation:

    * Requires ``METIS_HARNESS_L1_WIRE_PRODUCTION`` in {``1``, ``true``, ``yes``}.
    * Skipped for fixture stores so pytest / ``--use-fixture`` smoke runs
      stay hermetic.
    * Idempotent: runs at most once per process.

    The worker-side ``set_transcript_fetcher`` is **intentionally not** wired
    here.  Live FMP fetch is deferred to a follow-up patch; the current
    fallback ``transcript_fetcher_not_configured`` path means queued alerts
    simply fail-to-DLQ, which is the desired "propose but don't pull" state.
    """

    global _LAYER1_PRODUCTION_BOOTSTRAPPED
    if _LAYER1_PRODUCTION_BOOTSTRAPPED:
        return
    flag = (os.getenv("METIS_HARNESS_L1_WIRE_PRODUCTION") or "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        return
    if use_fixture:
        return
    try:
        from agentic_harness.adapters.layer1_brain_adapter import (
            build_stale_asset_provider,
        )
        from agentic_harness.agents.layer1_ingest import set_stale_asset_provider
        from config import load_settings
        from db.client import get_supabase_client
    except ImportError:
        return

    settings = load_settings()

    def _client_factory() -> Any:
        return get_supabase_client(settings)

    provider = build_stale_asset_provider(client_factory=_client_factory)
    set_stale_asset_provider(provider)
    _LAYER1_PRODUCTION_BOOTSTRAPPED = True


def perform_tick(
    *,
    use_fixture: bool = False,
    max_jobs: int = 5,
    dry_run: bool = False,
    store: Optional[HarnessStoreProtocol] = None,
) -> dict[str, Any]:
    s = store if store is not None else build_store(use_fixture=use_fixture)
    _maybe_bootstrap_layer1_production(s, use_fixture=use_fixture)
    return run_one_tick(
        store=s,
        layer_cadences=build_layer_cadences(),
        queue_specs=build_queue_specs(),
        max_jobs_per_queue=max_jobs,
        dry_run=dry_run,
    )


def build_status_snapshot(
    *,
    use_fixture: bool = False,
    store: Optional[HarnessStoreProtocol] = None,
    lang: str = "ko",
) -> dict[str, Any]:
    s = store if store is not None else build_store(use_fixture=use_fixture)
    queue = s.queue_depth()
    counts = s.count_packets_by_layer()
    last_tick = s.last_tick_of_kind("harness_tick")
    return {
        "contract": "METIS_AGENTIC_HARNESS_STATUS_V1",
        "lang": lang,
        "queue_depth": queue,
        "packet_counts_by_layer": counts,
        "last_harness_tick_at_utc": (last_tick or {}).get("tick_at_utc"),
        "last_harness_tick_summary": (last_tick or {}).get("summary"),
    }


def perform_ask(
    *,
    asset_id: str,
    question: str,
    lang: str = "ko",
    provider_name: Optional[str] = None,
    use_fixture: bool = False,
    store: Optional[HarnessStoreProtocol] = None,
) -> dict[str, Any]:
    try:
        from agentic_harness.agents.layer5_orchestrator import run_layer5_ask
    except ImportError as e:
        raise RuntimeError(
            "Layer 5 orchestrator not available; harness-ask is unsupported "
            "until agentic_harness.agents.layer5_orchestrator is installed."
        ) from e
    s = store if store is not None else build_store(use_fixture=use_fixture)
    return run_layer5_ask(
        store=s,
        asset_id=asset_id,
        question=question,
        lang=lang,
        provider_name=provider_name,
    )
