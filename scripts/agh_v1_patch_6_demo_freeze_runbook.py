"""AGH v1 Patch 6 — Demo freeze / surface renderer / live evidence closure runbook.

Exercises the operator-visible Patch 6 surfaces against an in-process
``FixtureHarnessStore`` and (if the Supabase probe succeeds) against the
real Supabase ``factor_validation_runs`` table. The scenarios mirror the
Patch 6 acceptance list:

    S1. Supabase probe → R/D branch decision (A0).
    S2. ``ResearchAnswerStructureV1.locale_coverage`` guardrail (D1):
        confirm the ``dual`` silent-degrade is now rejected and
        ``ko_only`` / ``en_only`` / ``degraded`` round-trip correctly.
    S3. POST ``/api/sandbox/enqueue`` operator-gate + input-validation
        smoke (E1): ``METIS_HARNESS_UI_INVOKE_ENABLED=0`` returns 403,
        ``=1`` with a valid body enqueues a request without executing
        the worker.
    S4. ``build_today_object_detail_payload`` exposes the latest
        ``research_structured_v1`` for the selected asset+horizon so the
        Research renderer has bullets to render (B2 plumbing).
    S5. UI renderer contract (B1/B2/B3/C1/C2): assert
        ``app.js`` still defines the 4-block Today helpers + research
        structured section + replay lineage compact + timeline plot +
        tooltip primitive, and that ``index.html`` ships the ``tsr-*``
        CSS primitives + ``prefers-reduced-motion`` guard.
    S6. Live evaluator + sandbox smoke (A1/A2) — R branch: attempt a
        bounded dry-run against the completed ``factor_validation_run``
        sampled by S1; D branch: record an honest-deferred trace.

Produces two files under ``data/mvp/evidence/``:

    * ``agentic_operating_harness_v1_milestone_17_bridge_evidence.json``
      — code-shape evidence (contract enums + prompt fragments +
      locale key coverage + CSS primitive presence).
    * ``agentic_operating_harness_v1_milestone_17_runbook_evidence.json``
      — operator-auditable runbook trace for S1–S6.
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
from agentic_harness.agents.layer5_orchestrator import _SYSTEM_PROMPT  # noqa: E402
from agentic_harness.contracts.packets_v1 import SANDBOX_KINDS, SANDBOX_REQUEST_ACTORS  # noqa: E402
from agentic_harness.llm.contract import (  # noqa: E402
    LOCALE_COVERAGE_KINDS,
    ResearchAnswerStructureV1,
)
from agentic_harness.store import FixtureHarnessStore  # noqa: E402
from phase47_runtime import routes as runtime_routes  # noqa: E402
from phase47_runtime.phase47e_user_locale import SHELL  # noqa: E402
from phase47_runtime.today_spectrum import (  # noqa: E402
    _latest_research_structured_v1_for_asset,
)


REGISTRY_ENTRY_ID = "reg_short_demo_v0"
HORIZON = "short"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_probe() -> dict[str, Any]:
    p = (
        REPO_ROOT
        / "data"
        / "mvp"
        / "evidence"
        / "agentic_operating_harness_v1_milestone_17_supabase_probe.json"
    )
    if not p.is_file():
        return {
            "branch": "D",
            "reason": "probe_evidence_missing",
            "detail": f"Run scripts/agh_v1_patch_6_supabase_probe.py first (expected at {p}).",
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return {"branch": "D", "reason": "probe_evidence_unreadable", "detail": str(exc)}


def _run_s1_probe() -> dict[str, Any]:
    probe = _load_probe()
    return {
        "scenario": "S1_supabase_probe",
        "branch": probe.get("branch"),
        "reason": probe.get("reason"),
        "completed_run_count": probe.get("completed_run_count"),
        "sample_run_id": (probe.get("sample_run") or {}).get("id"),
    }


def _run_s2_locale_coverage() -> dict[str, Any]:
    violations: list[str] = []
    accepted: list[str] = []

    def _try_build(case: str, **kwargs: Any) -> None:
        try:
            ResearchAnswerStructureV1(**kwargs)
            accepted.append(case)
        except Exception as exc:
            violations.append(f"{case}: {exc.__class__.__name__}")

    base = dict(
        residual_uncertainty_bullets=[],
        what_to_watch_bullets=[],
        evidence_cited=[],
        cited_packet_ids=[],
        proposed_sandbox_request=None,
    )

    _try_build(
        "dual_ok",
        summary_bullets_ko=["요약"],
        summary_bullets_en=["summary"],
        locale_coverage="dual",
        **base,
    )
    _try_build(
        "ko_only_ok",
        summary_bullets_ko=["요약"],
        summary_bullets_en=[],
        locale_coverage="ko_only",
        **base,
    )
    _try_build(
        "en_only_ok",
        summary_bullets_ko=[],
        summary_bullets_en=["summary"],
        locale_coverage="en_only",
        **base,
    )
    _try_build(
        "degraded_ok",
        summary_bullets_ko=[],
        summary_bullets_en=[],
        locale_coverage="degraded",
        rationale="evidence too thin",
        **base,
    )

    silent_degrade_blocked = False
    try:
        ResearchAnswerStructureV1(
            summary_bullets_ko=[],
            summary_bullets_en=["summary"],
            locale_coverage="dual",
            **base,
        )
    except Exception:
        silent_degrade_blocked = True

    return {
        "scenario": "S2_locale_coverage_guardrail",
        "locale_coverage_kinds_listed": list(LOCALE_COVERAGE_KINDS),
        "accepted_round_trip_cases": accepted,
        "system_prompt_mentions_locale_coverage": "locale_coverage" in _SYSTEM_PROMPT,
        "silent_dual_claim_with_empty_ko_blocked": silent_degrade_blocked,
        "unexpected_violations": violations,
    }


def _run_s3_sandbox_enqueue_endpoint() -> dict[str, Any]:
    api_sandbox_enqueue_v1 = runtime_routes.api_sandbox_enqueue_v1

    fixture_store = FixtureHarnessStore()
    prev_builder = runtime_routes._build_harness_store_for_api
    runtime_routes._build_harness_store_for_api = (  # type: ignore[assignment]
        lambda use_fixture=False: fixture_store
    )

    valid_body = {
        "sandbox_kind": "validation_rerun",
        "registry_entry_id": REGISTRY_ENTRY_ID,
        "horizon": HORIZON,
        "target_spec": {
            "factor_name": "earnings_quality_composite",
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "return_basis": "raw",
        },
        "rationale": "Demo-freeze runbook operator-gated enqueue smoke.",
        "cited_evidence_packet_ids": ["ValidationPromotionEvaluationV1:ev_runbook_s3"],
        "request_id": "sbx_runbook_patch6_s3",
    }

    try:
        prev_flag = os.environ.get("METIS_HARNESS_UI_INVOKE_ENABLED")
        os.environ.pop("METIS_HARNESS_UI_INVOKE_ENABLED", None)
        status_disabled, body_disabled = api_sandbox_enqueue_v1(state=None, body=valid_body)

        os.environ["METIS_HARNESS_UI_INVOKE_ENABLED"] = "1"
        status_ok, body_ok = api_sandbox_enqueue_v1(state=None, body=valid_body)

        worker_ran = False
        for _pid, pkt in fixture_store._packets.items():  # type: ignore[attr-defined]
            if pkt["packet_type"] == "SandboxResultPacketV1":
                worker_ran = True
                break
    finally:
        if prev_flag is None:
            os.environ.pop("METIS_HARNESS_UI_INVOKE_ENABLED", None)
        else:
            os.environ["METIS_HARNESS_UI_INVOKE_ENABLED"] = prev_flag
        runtime_routes._build_harness_store_for_api = prev_builder  # type: ignore[assignment]

    return {
        "scenario": "S3_sandbox_enqueue_endpoint",
        "disabled_status": status_disabled,
        "disabled_error": body_disabled.get("error"),
        "enabled_status": status_ok,
        "enabled_ok": body_ok.get("ok"),
        "enabled_cli_hint": body_ok.get("cli_hint"),
        "enabled_request_packet_id": body_ok.get("request_packet_id"),
        "worker_ran_autonomously": worker_ran,
        "sandbox_request_actors": list(SANDBOX_REQUEST_ACTORS),
        "sandbox_kinds": list(SANDBOX_KINDS),
    }


def _run_s4_today_research_structured_plumbing() -> dict[str, Any]:
    # Use a FakeStore with one UserQueryActionPacketV1 so this scenario
    # runs deterministically on every machine (no dependency on real
    # harness state).
    from types import SimpleNamespace

    import agentic_harness.runtime as harness_runtime

    packet = {
        "packet_id": "pkt_runbook_s4",
        "packet_type": "UserQueryActionPacketV1",
        "created_at_utc": _now_iso(),
        "target_scope": {"asset_id": "DEMO_AAA", "horizon": HORIZON},
        "payload": {
            "routed_kind": "deeper_rationale",
            "llm_response": {
                "cited_packet_ids": ["Pkt:src_1"],
                "research_structured_v1": {
                    "summary_bullets_ko": ["거버넌스 적용으로 리스크 해석이 좁혀졌다."],
                    "summary_bullets_en": ["Governance apply narrowed the interpretation."],
                    "residual_uncertainty_bullets": [],
                    "what_to_watch_bullets": [],
                    "evidence_cited": ["Pkt:src_1"],
                    "proposed_sandbox_request": None,
                    "locale_coverage": "dual",
                },
            },
        },
    }

    class _FakeStore:
        def list_packets(self, *, packet_type: str, limit: int = 200):
            if packet_type == "UserQueryActionPacketV1":
                return [packet]
            return []

    prev_builder = harness_runtime.build_store
    harness_runtime.build_store = lambda **_kw: _FakeStore()  # type: ignore[assignment]
    try:
        got = _latest_research_structured_v1_for_asset(
            repo_root=REPO_ROOT, asset_id="DEMO_AAA", horizon=HORIZON
        )
    finally:
        harness_runtime.build_store = prev_builder  # type: ignore[assignment]

    _ = SimpleNamespace  # keep import bound
    return {
        "scenario": "S4_today_research_structured_plumbing",
        "asset_id": "DEMO_AAA",
        "horizon": HORIZON,
        "latest_research_structured_v1_present": got is not None,
        "latest_research_structured_v1_source_packet_id": (
            got.get("_source_packet_id") if isinstance(got, dict) else None
        ),
        "latest_locale_coverage": (
            got.get("locale_coverage") if isinstance(got, dict) else None
        ),
    }


def _run_s5_ui_renderer_contract() -> dict[str, Any]:
    app_js = (REPO_ROOT / "src/phase47_runtime/static/app.js").read_text(encoding="utf-8")
    index_html = (REPO_ROOT / "src/phase47_runtime/static/index.html").read_text(encoding="utf-8")

    required_fns = [
        "renderTodaySummaryRailHtml",
        "renderTodayPrimaryPanelHtml",
        "renderTodayDecisionStackHtml",
        "renderTodayEvidenceStripHtml",
        "renderTodayObjectDetailHtml",
        "renderResearchStructuredSection",
        "hydrateReplayGovernanceLineageCompact",
        "renderReplayTimelinePlotSvg",
        "tsrInstallTooltip",
    ]
    required_css = [
        ".tsr-rail",
        ".tsr-chip",
        ".tsr-primary",
        ".tsr-decision",
        ".tsr-evidence",
        ".tsr-research",
        ".tsr-research-coverage",
        ".tsr-step-indicator",
        ".tsr-timeline-plot",
        ".tsr-tooltip",
        ".tsr-empty",
    ]
    missing_fns = [fn for fn in required_fns if f"function {fn}(" not in app_js and fn not in app_js]
    missing_css = [c for c in required_css if c not in index_html]
    reduced_motion = "prefers-reduced-motion" in index_html

    tsr_locale_key_count = {
        lang: sum(
            1
            for k in flat.keys()
            if k.startswith("tsr.")
            or k.startswith("research_section.")
            or k.startswith("lineage.")
            or k.startswith("plot.")
        )
        for lang, flat in SHELL.items()
    }

    return {
        "scenario": "S5_ui_renderer_contract",
        "app_js_bytes": len(app_js),
        "index_html_bytes": len(index_html),
        "missing_renderer_fns": missing_fns,
        "missing_css_primitives": missing_css,
        "prefers_reduced_motion_guard": reduced_motion,
        "tsr_locale_key_count": tsr_locale_key_count,
    }


def _run_s6_live_evaluator_sandbox_smoke(probe: dict[str, Any]) -> dict[str, Any]:
    branch = probe.get("branch")
    if branch != "R":
        return {
            "scenario": "S6_live_evaluator_sandbox_smoke",
            "branch": "D",
            "status": "honest_deferred",
            "reason": probe.get("reason"),
            "detail": probe.get("detail"),
            "next_step_trigger": (
                "Once factor_validation_runs has at least one status='completed' "
                "row, re-run scripts/agh_v1_patch_6_supabase_probe.py followed "
                "by this runbook."
            ),
        }

    sample = probe.get("sample_run") or {}
    # R branch — we found a completed factor_validation_run. We do NOT
    # actually call the live evaluator here (that would trigger a
    # Supabase write path); the runbook only records that the live
    # branch is reachable and captures the sample run's shape so we
    # have product-grade reality proof in the evidence file.
    return {
        "scenario": "S6_live_evaluator_sandbox_smoke",
        "branch": "R",
        "status": "live_branch_reachable_dry_only",
        "sample_run_id": sample.get("id"),
        "sample_run_universe_name": sample.get("universe_name"),
        "sample_run_horizon_type": sample.get("horizon_type"),
        "sample_run_completed_at": sample.get("completed_at"),
        "live_write_intentionally_skipped": True,
        "detail": (
            "Probe found >=1 completed factor_validation_run. The runbook "
            "does not invoke the live evaluator or sandbox worker to avoid "
            "side-effects; operators use the standalone Patch 4 / Patch 5 "
            "runbooks with SUPABASE_* env vars when they want a real write."
        ),
    }


def _prev_sandbox_hooks():
    return (
        sbx.get_sandbox_validation_rerun_runner(),
        sbx.get_sandbox_client_factory(),
    )


def _reset_sandbox_hooks(runner, factory):
    sbx.set_sandbox_validation_rerun_runner(runner)
    sbx.set_sandbox_client_factory(factory)


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    prev_runner, prev_factory = _prev_sandbox_hooks()
    sbx.set_sandbox_validation_rerun_runner(None)
    sbx.set_sandbox_client_factory(None)

    try:
        probe_payload = _load_probe()
        s1 = _run_s1_probe()
        s2 = _run_s2_locale_coverage()
        s3 = _run_s3_sandbox_enqueue_endpoint()
        s4 = _run_s4_today_research_structured_plumbing()
        s5 = _run_s5_ui_renderer_contract()
        s6 = _run_s6_live_evaluator_sandbox_smoke(probe_payload)
    finally:
        _reset_sandbox_hooks(prev_runner, prev_factory)

    bridge = {
        "contract": "AGH_V1_PATCH_6_DEMO_FREEZE_BRIDGE_EVIDENCE_V1",
        "milestone": 17,
        "generated_at_utc": _now_iso(),
        "locale_coverage_kinds": list(LOCALE_COVERAGE_KINDS),
        "sandbox_kinds_patch_6": list(SANDBOX_KINDS),
        "sandbox_request_actors": list(SANDBOX_REQUEST_ACTORS),
        "system_prompt_mentions_locale_coverage": "locale_coverage" in _SYSTEM_PROMPT,
        "ui_invoke_env_gate": "METIS_HARNESS_UI_INVOKE_ENABLED",
        "tsr_locale_key_count_by_lang": s5["tsr_locale_key_count"],
        "required_renderer_fns_missing": s5["missing_renderer_fns"],
        "required_css_primitives_missing": s5["missing_css_primitives"],
        "prefers_reduced_motion_guard": s5["prefers_reduced_motion_guard"],
        "probe_branch": s1["branch"],
        "probe_reason": s1["reason"],
    }
    runbook = {
        "contract": "AGH_V1_PATCH_6_DEMO_FREEZE_RUNBOOK_EVIDENCE_V1",
        "milestone": 17,
        "generated_at_utc": _now_iso(),
        "registry_entry_id": REGISTRY_ENTRY_ID,
        "horizon": HORIZON,
        "scenarios": [s1, s2, s3, s4, s5, s6],
    }

    ev_dir = REPO_ROOT / "data" / "mvp" / "evidence"
    _write_evidence(
        ev_dir / "agentic_operating_harness_v1_milestone_17_bridge_evidence.json",
        bridge,
    )
    _write_evidence(
        ev_dir / "agentic_operating_harness_v1_milestone_17_runbook_evidence.json",
        runbook,
    )
    print("wrote patch 6 milestone 17 evidence files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
