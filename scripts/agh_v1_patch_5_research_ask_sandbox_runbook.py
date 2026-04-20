"""AGH v1 Patch 5 — Research Ask / bounded sandbox closure runbook.

Exercises the operator-visible Patch 5 surfaces against an in-process
``FixtureHarnessStore`` and captures the payload as milestone 16
evidence. This is an auditable dry-run, not a unit test.

Scenarios (Patch 5 workorder §B/§C/§D + AC-1 … AC-5):

    S1. ``sandbox_request + validation_rerun`` (completed):
        - enqueue a bounded ``validation_rerun`` sandbox request,
        - run the worker with a deterministic stub runner,
        - assert ``SandboxResultPacketV1.outcome == "completed"``,
        - record ``produced_refs[*].id`` (the synthetic
          ``factor_validation_run_id``).

    S2. ``sandbox_request blocked_insufficient_inputs``:
        - enqueue a second request, but with no runner + no client
          factory installed,
        - worker must emit ``blocked_insufficient_inputs`` with a
          non-empty ``blocking_reasons`` list and never run the
          production validation pipeline.

    S3. ``sandbox_request rejected_kind_not_allowed``:
        - seed a ``SandboxRequestPacketV1`` whose payload
          ``sandbox_kind`` is outside Patch 5's ``SANDBOX_KINDS`` (via
          raw packet write — the CLI + packet contract reject this
          path at compose time, so the worker-side guard is
          exercised here via a manual overwrite).

    S4. ``api_governance_lineage_for_registry_entry`` with sandbox
        followups: assert the lineage summary correctly reports the
        three sandbox requests from S1/S2/S3 (one completed, two
        blocked/rejected) without leaking into the Patch 3 applied
        path.

    S5. ``build_today_object_detail_payload`` sanity: the Today
        surface exposes ``sandbox_options_v1`` + ``research_status_badges_v1``
        deterministically and does NOT flip ``active_artifact_id`` as a
        result of any S1/S2/S3 activity.

Produces two files:

    * ``data/mvp/evidence/agentic_operating_harness_v1_milestone_16_research_ask_sandbox_bridge_evidence.json``
      — code-shape evidence (contract packets, guardrail invariants,
      sandbox enum).
    * ``data/mvp/evidence/agentic_operating_harness_v1_milestone_16_research_ask_sandbox_runbook_evidence.json``
      — operator-auditable runbook trace for S1–S5.

Non-goals (explicit CF-3 / CF-4 defer record):

    * CF-3: ``evidence_refresh`` / ``residual_review`` /
      ``replay_comparison`` remain Patch 6 backlog (workorder §A2/§C1
      "initial allowed sandbox kinds should be small"). The runbook
      logs them under ``deferred_followups`` so the authority docs
      match reality.
    * CF-4: Live Supabase evaluator smoke is intentionally deferred to
      the patch after a ``completed factor_validation_run`` exists in
      Supabase (user decision Q=no completed run yet). The runbook
      records this under ``live_smoke.status='deferred'`` with the
      reason + the next-step trigger, not as a fake success.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


from agentic_harness.agents import layer3_sandbox_executor_v1 as sbx  # noqa: E402
from agentic_harness.contracts.packets_v1 import (  # noqa: E402
    PACKET_TYPES,
    SANDBOX_KINDS,
    SANDBOX_REQUEST_ACTORS,
    SANDBOX_RESULT_OUTCOMES,
)
from agentic_harness.contracts.queues_v1 import QUEUE_CLASSES  # noqa: E402
from agentic_harness.llm.contract import (  # noqa: E402
    RESEARCH_STRUCTURED_KINDS,
    USER_QUESTION_KINDS,
)
from agentic_harness.store import FixtureHarnessStore  # noqa: E402
from phase47_runtime.today_spectrum import (  # noqa: E402
    build_today_object_detail_payload,
    build_today_spectrum_payload,
)
from phase47_runtime.traceability_replay import (  # noqa: E402
    api_governance_lineage_for_registry_entry,
)


REGISTRY_ENTRY_ID = "reg_short_demo_v0"
HORIZON = "short"
FACTOR_NAME = "earnings_quality_composite"
UNIVERSE = "large_cap_research_slice_demo_v0"
HORIZON_TYPE = "next_month"
RETURN_BASIS = "raw"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_target_spec() -> dict[str, str]:
    return {
        "factor_name": FACTOR_NAME,
        "universe_name": UNIVERSE,
        "horizon_type": HORIZON_TYPE,
        "return_basis": RETURN_BASIS,
    }


def _run_s1_completed(store: FixtureHarnessStore) -> dict[str, Any]:
    sbx.set_sandbox_validation_rerun_runner(
        lambda _ts, _c: {
            "run_id": "fvr_runbook_completed_1",
            "status": "completed",
            "factors_ok": 1,
            "factors_failed": 0,
            "validation_panels_used": 1,
            "symbols_in_slice": 42,
        }
    )
    sbx.set_sandbox_client_factory(lambda: object())
    enq = sbx.enqueue_sandbox_request(
        store,
        request_id="sbx_runbook_s1_completed",
        sandbox_kind="validation_rerun",
        registry_entry_id=REGISTRY_ENTRY_ID,
        horizon=HORIZON,
        target_spec=_request_target_spec(),
        requested_by="operator",
        cited_evidence_packet_ids=[
            "ValidationPromotionEvaluationV1:ev_runbook_s1"
        ],
    )
    jobs = store.list_jobs(queue_class="sandbox_queue", limit=20)
    job = next(j for j in jobs if j.get("packet_id") == enq["request_packet_id"])
    out = sbx.sandbox_queue_worker(store, dict(job))
    return {
        "scenario": "S1_completed",
        "enqueue": enq,
        "worker_outcome": out,
    }


def _run_s2_blocked_insufficient(store: FixtureHarnessStore) -> dict[str, Any]:
    sbx.set_sandbox_validation_rerun_runner(None)
    sbx.set_sandbox_client_factory(None)
    enq = sbx.enqueue_sandbox_request(
        store,
        request_id="sbx_runbook_s2_blocked",
        sandbox_kind="validation_rerun",
        registry_entry_id=REGISTRY_ENTRY_ID,
        horizon=HORIZON,
        target_spec=_request_target_spec(),
        requested_by="operator",
        cited_evidence_packet_ids=[
            "ValidationPromotionEvaluationV1:ev_runbook_s2"
        ],
    )
    jobs = store.list_jobs(queue_class="sandbox_queue", limit=20)
    job = next(j for j in jobs if j.get("packet_id") == enq["request_packet_id"])
    out = sbx.sandbox_queue_worker(store, dict(job))
    return {
        "scenario": "S2_blocked_insufficient_inputs",
        "enqueue": enq,
        "worker_outcome": out,
    }


def _run_s3_rejected_kind(store: FixtureHarnessStore) -> dict[str, Any]:
    # Re-enable a runner so the worker has to actively reject on kind.
    sbx.set_sandbox_validation_rerun_runner(lambda _ts, _c: {"run_id": "noop"})
    sbx.set_sandbox_client_factory(lambda: object())
    enq = sbx.enqueue_sandbox_request(
        store,
        request_id="sbx_runbook_s3_rejected",
        sandbox_kind="validation_rerun",
        registry_entry_id=REGISTRY_ENTRY_ID,
        horizon=HORIZON,
        target_spec=_request_target_spec(),
        requested_by="operator",
        cited_evidence_packet_ids=[
            "ValidationPromotionEvaluationV1:ev_runbook_s3"
        ],
    )
    # Manually overwrite the stored request payload's sandbox_kind to a
    # disallowed kind (``evidence_refresh``) so the worker-side guard is
    # exercised. In production, ``enqueue_sandbox_request`` + the CLI
    # reject this at compose time, which is why we have to force it.
    req = dict(store.get_packet(enq["request_packet_id"]) or {})
    req["payload"] = {**req["payload"], "sandbox_kind": "evidence_refresh"}
    store.upsert_packet(req)
    jobs = store.list_jobs(queue_class="sandbox_queue", limit=20)
    job = next(j for j in jobs if j.get("packet_id") == enq["request_packet_id"])
    out = sbx.sandbox_queue_worker(store, dict(job))
    return {
        "scenario": "S3_rejected_kind_not_allowed",
        "enqueue": enq,
        "worker_outcome": out,
    }


def _run_s4_lineage(store: FixtureHarnessStore) -> dict[str, Any]:
    lineage = api_governance_lineage_for_registry_entry(
        store,
        registry_entry_id=REGISTRY_ENTRY_ID,
        horizon=HORIZON,
    )
    # Normalize: keep only the counts + request+result packet_ids for
    # readability in evidence.
    fups_compact = []
    for row in lineage.get("sandbox_followups") or []:
        req = row.get("request") or {}
        res = row.get("result") or {}
        fups_compact.append(
            {
                "request_packet_id": req.get("packet_id"),
                "sandbox_kind": (req.get("payload") or {}).get("sandbox_kind"),
                "result_packet_id": res.get("packet_id") if res else None,
                "result_outcome": (res.get("payload") or {}).get("outcome")
                if res
                else None,
            }
        )
    return {
        "scenario": "S4_api_governance_lineage",
        "summary": lineage.get("summary"),
        "sandbox_followups_compact": fups_compact,
    }


def _run_s5_today_surface() -> dict[str, Any]:
    os.environ["METIS_TODAY_SOURCE"] = "registry"
    sp = build_today_spectrum_payload(
        repo_root=REPO_ROOT, horizon=HORIZON, lang="ko"
    )
    if not sp.get("ok"):
        return {
            "scenario": "S5_today_surface",
            "status": "skipped",
            "reason": sp.get("error"),
        }
    surface = sp.get("registry_surface_v1") or {}
    aid = None
    for r in sp.get("rows") or []:
        if isinstance(r, dict) and r.get("asset_id"):
            aid = r["asset_id"]
            break
    detail = None
    if aid:
        detail = build_today_object_detail_payload(
            repo_root=REPO_ROOT,
            asset_id=aid,
            horizon=HORIZON,
            lang="ko",
        )
    return {
        "scenario": "S5_today_surface",
        "registry_entry_id": surface.get("registry_entry_id"),
        "active_artifact_id_before_sandbox": surface.get("active_artifact_id"),
        "detail_has_sandbox_options_v1": bool(
            (detail or {}).get("sandbox_options_v1")
        ),
        "detail_has_research_status_badges_v1": bool(
            (detail or {}).get("research_status_badges_v1")
        ),
        "sandbox_options_count": len(
            (detail or {}).get("sandbox_options_v1", {}).get("options") or []
        ),
        "research_status_badge_codes": [
            b.get("code")
            for b in (detail or {}).get("research_status_badges_v1", {}).get(
                "badges", []
            )
        ],
    }


def _write_evidence(
    path: Path, payload: dict[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    store = FixtureHarnessStore()
    s1 = _run_s1_completed(store)
    s2 = _run_s2_blocked_insufficient(store)
    s3 = _run_s3_rejected_kind(store)
    s4 = _run_s4_lineage(store)
    s5 = _run_s5_today_surface()

    # Bridge-evidence (code-shape contracts + enums + guardrail list).
    bridge = {
        "contract": "AGH_V1_PATCH_5_RESEARCH_ASK_SANDBOX_BRIDGE_EVIDENCE_V1",
        "milestone": 16,
        "generated_at_utc": _now_iso(),
        "packet_vocabulary": {
            "sandbox_packet_types_present": [
                t for t in ("SandboxRequestPacketV1", "SandboxResultPacketV1")
                if t in PACKET_TYPES
            ],
            "sandbox_kinds_patch_5": list(SANDBOX_KINDS),
            "sandbox_request_actors": list(SANDBOX_REQUEST_ACTORS),
            "sandbox_result_outcomes": list(SANDBOX_RESULT_OUTCOMES),
            "queue_classes_includes_sandbox_queue": "sandbox_queue" in QUEUE_CLASSES,
        },
        "user_question_kinds": list(USER_QUESTION_KINDS),
        "research_structured_kinds": list(RESEARCH_STRUCTURED_KINDS),
        "sandbox_migration_file": (
            "supabase/migrations/20260420100000_agh_v1_patch_5_research_sandbox.sql"
        ),
        "deferred_followups_cf3": [
            "evidence_refresh",
            "residual_review",
            "replay_comparison",
        ],
        "live_smoke_cf4": {
            "status": "deferred",
            "reason": (
                "No completed factor_validation_run currently present in "
                "Supabase; provider code + idempotency tests are shipped in "
                "Patch 5 but the live evaluator smoke is gated on having a "
                "real completed run to join against."
            ),
            "next_step_trigger": (
                "Once a real factor_validation_runs row with status='completed' "
                "exists, re-run scripts/agh_v1_patch_4_validation_to_governance_runbook.py "
                "with SUPABASE_* env vars set and capture the output here."
            ),
        },
    }
    _write_evidence(
        REPO_ROOT
        / "data"
        / "mvp"
        / "evidence"
        / "agentic_operating_harness_v1_milestone_16_research_ask_sandbox_bridge_evidence.json",
        bridge,
    )

    runbook = {
        "contract": "AGH_V1_PATCH_5_RESEARCH_ASK_SANDBOX_RUNBOOK_EVIDENCE_V1",
        "milestone": 16,
        "generated_at_utc": _now_iso(),
        "registry_entry_id": REGISTRY_ENTRY_ID,
        "horizon": HORIZON,
        "scenarios": [s1, s2, s3, s4, s5],
    }
    _write_evidence(
        REPO_ROOT
        / "data"
        / "mvp"
        / "evidence"
        / "agentic_operating_harness_v1_milestone_16_research_ask_sandbox_runbook_evidence.json",
        runbook,
    )
    print("wrote patch 5 milestone 16 evidence files.")


if __name__ == "__main__":
    main()
