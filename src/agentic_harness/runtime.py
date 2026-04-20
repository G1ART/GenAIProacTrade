"""High-level entrypoints for CLI integration.

The CLI (`harness-tick`, `harness-status`, `harness-ask`) calls into this
module rather than reaching into the scheduler / store / agent layers
directly. It is the single place where the agent topology is wired up.
"""

from __future__ import annotations

import json
import logging
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
_LAYER1_LIVE_FETCH_BOOTSTRAPPED = False
_GOVERNANCE_SCAN_BOOTSTRAPPED = False
_SANDBOX_CLIENT_FACTORY_BOOTSTRAPPED = False

log = logging.getLogger(__name__)


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
    try:
        from agentic_harness.agents.layer4_promotion_evaluator_v1 import (
            propose_governance_scan_cadence,
        )

        specs.append(
            LayerCadenceSpec(
                cadence_key="layer4.governance_scan",
                propose_fn=propose_governance_scan_cadence,
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
    try:
        from agentic_harness.agents.layer4_registry_patch_executor import (
            registry_patch_executor,
        )

        specs.append(
            QueueSpec(
                queue_class="registry_apply_queue",
                worker_fn=registry_patch_executor,
            )
        )
    except ImportError:
        pass
    try:
        from agentic_harness.agents.layer3_sandbox_executor_v1 import (
            sandbox_queue_worker,
        )

        specs.append(
            QueueSpec(
                queue_class="sandbox_queue",
                worker_fn=sandbox_queue_worker,
            )
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


def _maybe_bootstrap_layer1_live_fetch(
    store: HarnessStoreProtocol, *, use_fixture: bool
) -> None:
    """Env-gated hook: wire Layer 1's transcript fetcher to the real FMP
    ingest pipeline (``run_fmp_sample_ingest``).

    Activation requires **both**:

    * ``METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH`` in {``1``, ``true``, ``yes``}
    * ``FMP_API_KEY`` configured (via env / ``.env``)

    If the flag is on but the key is missing, we log a warning and leave
    the fallback fetcher in place so queued jobs surface the config
    problem honestly rather than pretending to fetch.  The hook is
    skipped for fixture stores so pytest / ``--use-fixture`` smoke runs
    remain hermetic.  Idempotent across process lifetime.
    """

    global _LAYER1_LIVE_FETCH_BOOTSTRAPPED
    if _LAYER1_LIVE_FETCH_BOOTSTRAPPED:
        return
    flag = (os.getenv("METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH") or "").strip().lower()
    if flag not in {"1", "true", "yes"}:
        return
    if use_fixture:
        return
    try:
        from agentic_harness.adapters.layer1_transcript_fetcher import (
            build_transcript_fetcher,
        )
        from agentic_harness.agents.layer1_ingest import set_transcript_fetcher
        from config import load_settings
        from db.client import get_supabase_client
    except ImportError:
        return

    settings = load_settings()
    if not (getattr(settings, "fmp_api_key", "") or "").strip():
        log.warning(
            "METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH=1 but FMP_API_KEY missing; "
            "leaving Layer 1 on fallback transcript fetcher"
        )
        return

    def _client_factory() -> Any:
        return get_supabase_client(settings)

    set_transcript_fetcher(
        build_transcript_fetcher(
            client_factory=_client_factory,
            settings=settings,
        )
    )
    _LAYER1_LIVE_FETCH_BOOTSTRAPPED = True


def _maybe_bootstrap_governance_scan_provider(
    store: HarnessStoreProtocol, *, use_fixture: bool
) -> None:
    """AGH v1 Patch 5 — env-gated install of the production
    ``governance_scan`` spec provider.

    Activation requires BOTH ``SUPABASE_URL`` and
    ``SUPABASE_SERVICE_ROLE_KEY`` (via ``config.load_settings``). Without
    them we leave the provider slot empty so the cadence emits an honest
    ``no_governance_scan_spec_provider`` skip instead of inventing specs.

    * Fixture stores are skipped — tests install the provider directly.
    * Idempotent across process lifetime.
    """

    global _GOVERNANCE_SCAN_BOOTSTRAPPED
    if _GOVERNANCE_SCAN_BOOTSTRAPPED:
        return
    if use_fixture:
        return
    try:
        from agentic_harness.agents.governance_scan_provider_v1 import (
            build_supabase_governance_scan_provider,
        )
        from agentic_harness.agents.layer4_promotion_evaluator_v1 import (
            _repo_root_from_env,
            set_governance_scan_client_factory,
            set_governance_scan_spec_provider,
        )
        from config import load_settings
        from db.client import get_supabase_client
        from metis_brain.bundle import brain_bundle_path
    except ImportError:
        return
    try:
        settings = load_settings()
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("governance_scan bootstrap: load_settings failed: %s", exc)
        return
    url = str(getattr(settings, "supabase_url", "") or "").strip()
    key = str(getattr(settings, "supabase_service_role_key", "") or "").strip()
    if not url or not key:
        log.warning(
            "governance_scan bootstrap skipped: SUPABASE_URL / "
            "SUPABASE_SERVICE_ROLE_KEY missing (honest no-provider)"
        )
        return

    def _client_factory() -> Any:
        return get_supabase_client(settings)

    def _bundle_path_factory() -> Any:
        return brain_bundle_path(_repo_root_from_env())

    provider = build_supabase_governance_scan_provider(
        client_factory=_client_factory,
        bundle_path_factory=_bundle_path_factory,
    )
    set_governance_scan_spec_provider(provider)
    set_governance_scan_client_factory(_client_factory)
    _GOVERNANCE_SCAN_BOOTSTRAPPED = True


def _maybe_bootstrap_sandbox_client_factory(
    store: HarnessStoreProtocol, *, use_fixture: bool
) -> None:
    """AGH v1 Patch 5 — env-gated install of the production Supabase client
    factory used by the sandbox ``validation_rerun`` runner.

    Activation requires BOTH ``SUPABASE_URL`` and
    ``SUPABASE_SERVICE_ROLE_KEY`` (via ``config.load_settings``). Without
    them, the sandbox executor leaves the client factory unset and queued
    requests land as ``blocked_insufficient_inputs`` (honest no-client)
    instead of pretending to rerun.

    * Fixture stores are skipped — tests install a deterministic runner
      stub directly via ``set_sandbox_validation_rerun_runner``.
    * Idempotent across process lifetime.
    """

    global _SANDBOX_CLIENT_FACTORY_BOOTSTRAPPED
    if _SANDBOX_CLIENT_FACTORY_BOOTSTRAPPED:
        return
    if use_fixture:
        return
    try:
        from agentic_harness.agents.layer3_sandbox_executor_v1 import (
            set_sandbox_client_factory,
        )
        from config import load_settings
        from db.client import get_supabase_client
    except ImportError:
        return
    try:
        settings = load_settings()
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("sandbox client factory bootstrap: load_settings failed: %s", exc)
        return
    url = str(getattr(settings, "supabase_url", "") or "").strip()
    key = str(getattr(settings, "supabase_service_role_key", "") or "").strip()
    if not url or not key:
        log.warning(
            "sandbox client factory bootstrap skipped: SUPABASE_URL / "
            "SUPABASE_SERVICE_ROLE_KEY missing (honest no-client)"
        )
        return

    def _client_factory() -> Any:
        return get_supabase_client(settings)

    set_sandbox_client_factory(_client_factory)
    _SANDBOX_CLIENT_FACTORY_BOOTSTRAPPED = True


def perform_tick(
    *,
    use_fixture: bool = False,
    max_jobs: int = 5,
    dry_run: bool = False,
    store: Optional[HarnessStoreProtocol] = None,
) -> dict[str, Any]:
    s = store if store is not None else build_store(use_fixture=use_fixture)
    _maybe_bootstrap_layer1_production(s, use_fixture=use_fixture)
    _maybe_bootstrap_layer1_live_fetch(s, use_fixture=use_fixture)
    _maybe_bootstrap_governance_scan_provider(s, use_fixture=use_fixture)
    _maybe_bootstrap_sandbox_client_factory(s, use_fixture=use_fixture)
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


def perform_decision(
    *,
    proposal_id: str,
    action: str,
    actor: str,
    reason: str,
    next_revisit_hint_utc: Optional[str] = None,
    use_fixture: bool = False,
    store: Optional[HarnessStoreProtocol] = None,
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """AGH v1 Patch 2 - operator-gated promotion-bridge decision entrypoint.

    Records a ``RegistryDecisionPacketV1`` for the given
    ``RegistryUpdateProposalV1`` and, on ``approve``, enqueues a job on
    ``registry_apply_queue`` so the next ``harness-tick`` runs the
    ``registry_patch_executor`` worker.  This entrypoint never writes to
    the brain bundle itself; that stays in the queue worker so the apply
    step is deterministic, retryable, and audit-logged.
    """

    from agentic_harness.agents.layer4_governance import (
        DecisionError,
        record_registry_decision,
    )
    from agentic_harness.store.protocol import now_utc_iso

    s = store if store is not None else build_store(use_fixture=use_fixture)
    now_iso = str(now_utc or now_utc_iso())
    try:
        result = record_registry_decision(
            s,
            proposal_id=proposal_id,
            action=action,
            actor=actor,
            reason=reason,
            now_iso=now_iso,
            next_revisit_hint_utc=next_revisit_hint_utc,
        )
    except DecisionError as exc:
        return {
            "ok": False,
            "error": f"decision_error:{exc}",
            "proposal_id": proposal_id,
            "action": action,
        }
    return result


def perform_sandbox_request(
    *,
    request_id: str,
    sandbox_kind: str,
    registry_entry_id: str,
    horizon: str,
    target_spec: dict[str, Any],
    requested_by: str,
    cited_evidence_packet_ids: list[str],
    cited_ask_packet_id: Optional[str] = None,
    use_fixture: bool = False,
    store: Optional[HarnessStoreProtocol] = None,
) -> dict[str, Any]:
    """AGH v1 Patch 5 - operator/research-ask-gated sandbox request entry.

    Creates a ``SandboxRequestPacketV1`` and enqueues a ``sandbox_queue``
    job pointing at it. The next ``harness-tick`` runs
    ``layer3_sandbox_executor_v1.sandbox_queue_worker`` which records the
    corresponding ``SandboxResultPacketV1``.

    This path NEVER mutates the brain bundle or the active registry;
    operator-gated promotion continues to ride the Patch 2/3/4 rails.
    """

    from agentic_harness.agents.layer3_sandbox_executor_v1 import (
        enqueue_sandbox_request,
    )

    s = store if store is not None else build_store(use_fixture=use_fixture)
    return enqueue_sandbox_request(
        s,
        request_id=request_id,
        sandbox_kind=sandbox_kind,
        registry_entry_id=registry_entry_id,
        horizon=horizon,
        target_spec=target_spec,
        requested_by=requested_by,
        cited_evidence_packet_ids=cited_evidence_packet_ids,
        cited_ask_packet_id=cited_ask_packet_id,
    )


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
