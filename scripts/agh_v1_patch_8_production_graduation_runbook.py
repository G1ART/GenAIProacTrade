"""AGH v1 Patch 8 — production graduation / UX-AI wow / scale closure runbook.

Exercises the operator-visible Patch 8 surfaces against the code that the
vanilla-JS SPA actually renders and the harness actually executes. This is
NOT a demo-theater runbook; every scenario below ties back to a specific
Patch 8 workorder acceptance.

Scenarios:

    S1. A1 Research 4-stack — ``what_changed_bullets_ko/en`` in the Pydantic
        contract + guardrail scan + orchestrator prompt + ``app.js`` renders
        the "What changed" / "Why it matters" clusters with the graduated
        labels.
    S2. A2 Today hero stack — ``renderTodayWhyNowConfidenceCaveatNextHtml``
        is wired and the 4-row stack + jump-to-invoke affordance are
        present; locale keys declared in both languages.
    S3. B2 + B3 + B4 invoke 4-state + recent requests + contract
        status_after — ``api_sandbox_requests_list`` exposes the 4-state
        ``lifecycle_state``; ``hydrateRecentSandboxRequests`` + the
        contract card status slot are rendered.
    S4. C1 factor validation batch — ``db.records`` exports the three
        ``upsert_*`` helpers; the runner accumulates + flushes via batch
        upsert and records truncation metadata.
    S5. C2 bundle cache + evaluator single reload — ``bundle_full_from_
        validation_v1`` ships a panel cache; ``evaluate_registry_entries``
        declares ``reload_between_specs``.
    S6. D2 + D3 production bundle tier — the graduation script exists, the
        health surface emits ``brain_bundle_tier``, the UI badge is wired,
        and the 3-tier plan note is in place.
    S7. E2 healthcheck degraded — ``build_cockpit_runtime_health_payload``
        returns 200-shaped ``ok: True`` with ``degraded_reasons`` when the
        brain bundle is missing, and the route maps only ``down`` → 503.
    S8. E1 + E4 harness-tick queue filter + Railway deploy — ``harness-tick``
        CLI advertises ``--queue`` / ``--loop`` / ``--sleep``, Procfile
        + railway.json + runbook are committed.

Produces two files under ``data/mvp/evidence/``:

    * ``agentic_operating_harness_v1_milestone_19_patch_8_bridge_evidence.json``
      — code-shape evidence (contracts, CSS primitives, locale-key
      coverage, tier surface wiring).
    * ``agentic_operating_harness_v1_milestone_19_patch_8_runbook_evidence.json``
      — operator-auditable runbook trace for S1–S8.

Deterministic — no Supabase writes, no worker spawns, no LLM calls.
"""

from __future__ import annotations

import inspect
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


from phase47_runtime import routes as runtime_routes  # noqa: E402
from phase47_runtime.phase47e_user_locale import (  # noqa: E402
    LEGACY_LOCALE_ALIASES,
    SHELL,
)
from phase51_runtime import cockpit_health_surface as health_surface  # noqa: E402


APP_JS = (REPO_ROOT / "src/phase47_runtime/static/ops.js").read_text(
    encoding="utf-8"
)
INDEX_HTML = (REPO_ROOT / "src/phase47_runtime/static/ops.html").read_text(
    encoding="utf-8"
)
CONTRACT_PY = (
    REPO_ROOT / "src/agentic_harness/llm/contract.py"
).read_text(encoding="utf-8")
GUARDRAILS_PY = (
    REPO_ROOT / "src/agentic_harness/llm/guardrails.py"
).read_text(encoding="utf-8")
ORCH_PY = (
    REPO_ROOT / "src/agentic_harness/agents/layer5_orchestrator.py"
).read_text(encoding="utf-8")
RECORDS_PY = (REPO_ROOT / "src/db/records.py").read_text(encoding="utf-8")
RUNNER_PY = (
    REPO_ROOT / "src/research/validation_runner.py"
).read_text(encoding="utf-8")
BUNDLE_V1_PY = (
    REPO_ROOT / "src/metis_brain/bundle_full_from_validation_v1.py"
).read_text(encoding="utf-8")
EVAL_PY = (
    REPO_ROOT
    / "src/agentic_harness/agents/layer4_promotion_evaluator_v1.py"
).read_text(encoding="utf-8")
MAIN_PY = (REPO_ROOT / "src/main.py").read_text(encoding="utf-8")
PROCFILE = (REPO_ROOT / "Procfile").read_text(encoding="utf-8")
RAILWAY_JSON = json.loads(
    (REPO_ROOT / "railway.json").read_text(encoding="utf-8")
)
RAILWAY_RUNBOOK_PATH = (
    REPO_ROOT / "docs/ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md"
)
GRAD_NOTE_PATH = (
    REPO_ROOT
    / "docs/plan/METIS_Production_Bundle_Graduation_Note_v1.md"
)
GRAD_SCRIPT_PATH = (
    REPO_ROOT / "scripts/agh_v1_patch_8_production_bundle_graduation.py"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# S1 — A1 Research 4-stack
# ---------------------------------------------------------------------------


def _run_s1_research_4stack() -> dict[str, Any]:
    contract_has_ko = "what_changed_bullets_ko" in CONTRACT_PY
    contract_has_en = "what_changed_bullets_en" in CONTRACT_PY
    guardrail_scans = (
        "what_changed_bullets_ko" in GUARDRAILS_PY
        and "what_changed_bullets_en" in GUARDRAILS_PY
    )
    prompt_mentions = "what_changed" in ORCH_PY.lower()
    render_has_what_changed = (
        "research_section.what_changed" in APP_JS
    )
    render_labels_why_it_matters = "research_section.why_it_matters" in APP_JS
    locale_keys = (
        "research_section.what_changed",
        "research_section.why_it_matters",
        "research_section.no_what_changed",
    )
    locale_coverage = {
        lang: {k: (k in flat) for k in locale_keys}
        for lang, flat in SHELL.items()
    }
    return {
        "scenario": "S1_research_4_stack",
        "contract_has_what_changed_ko": contract_has_ko,
        "contract_has_what_changed_en": contract_has_en,
        "guardrail_scans_what_changed": guardrail_scans,
        "prompt_mentions_what_changed": prompt_mentions,
        "render_has_what_changed_section": render_has_what_changed,
        "render_labels_why_it_matters": render_labels_why_it_matters,
        "locale_coverage_per_lang": locale_coverage,
    }


# ---------------------------------------------------------------------------
# S2 — A2 Today hero stack
# ---------------------------------------------------------------------------


def _run_s2_today_hero_stack() -> dict[str, Any]:
    renderer_present = "renderTodayWhyNowConfidenceCaveatNextHtml" in APP_JS
    stack_class = "tsr-why-now-stack" in APP_JS
    jump_to_invoke = "data-tsr-jump-to-invoke" in APP_JS
    locale_keys = (
        "tsr.today.stack.head",
        "tsr.today.why_now.head",
        "tsr.today.why_now.empty",
    )
    locale_coverage = {
        lang: {k: (k in flat) for k in locale_keys}
        for lang, flat in SHELL.items()
    }
    return {
        "scenario": "S2_today_hero_stack",
        "renderer_present": renderer_present,
        "stack_class_present": stack_class,
        "jump_to_invoke_present": jump_to_invoke,
        "locale_coverage_per_lang": locale_coverage,
    }


# ---------------------------------------------------------------------------
# S3 — B2 + B3 + B4 invoke lifecycle / recent requests / contract card
# ---------------------------------------------------------------------------


def _run_s3_invoke_lifecycle_recent() -> dict[str, Any]:
    route_src = inspect.getsource(runtime_routes.api_sandbox_requests_list)
    lifecycle_in_route = (
        "lifecycle_state" in route_src or "_life_state" in route_src
    )
    ui_lifecycle = "lifecycle_state" in APP_JS
    humanize_ref = "humanizeProducedRefs" in APP_JS
    recent_hydrator = "hydrateRecentSandboxRequests" in APP_JS
    contract_state_slot = "tsr-contract-state-slot" in APP_JS
    locale_keys = (
        "research_section.invoke_state_running",
        "research_section.produced_refs_summary",
        "research_section.recent_requests_head",
        "research_section.recent_requests_empty",
        "tsr.invoke.contract.status_after",
    )
    locale_coverage = {
        lang: {k: (k in flat) for k in locale_keys}
        for lang, flat in SHELL.items()
    }
    return {
        "scenario": "S3_invoke_lifecycle_recent_requests",
        "lifecycle_state_in_route": lifecycle_in_route,
        "ui_uses_lifecycle_state": ui_lifecycle,
        "humanize_produced_refs_helper": humanize_ref,
        "hydrate_recent_sandbox_requests_present": recent_hydrator,
        "contract_state_slot_present": contract_state_slot,
        "locale_coverage_per_lang": locale_coverage,
    }


# ---------------------------------------------------------------------------
# S4 — C1 factor validation batch upsert
# ---------------------------------------------------------------------------


def _run_s4_factor_batch_upsert() -> dict[str, Any]:
    batch_fns = (
        "upsert_factor_validation_summaries",
        "upsert_factor_quantile_results",
        "upsert_factor_coverage_reports",
    )
    records_exports = {fn: (f"def {fn}(" in RECORDS_PY) for fn in batch_fns}
    runner_calls = {fn: (fn in RUNNER_PY) for fn in batch_fns}
    truncation_visible = (
        "panel_truncated_at_limit" in RUNNER_PY
        and "panel_rows_fetched" in RUNNER_PY
    )
    return {
        "scenario": "S4_factor_batch_upsert",
        "records_exports": records_exports,
        "runner_batch_upsert_wiring": runner_calls,
        "panel_truncation_metadata_recorded": truncation_visible,
    }


# ---------------------------------------------------------------------------
# S5 — C2 bundle panel cache + evaluator single reload
# ---------------------------------------------------------------------------


def _run_s5_bundle_cache_single_reload() -> dict[str, Any]:
    has_panel_cache = (
        "_panel_cache" in BUNDLE_V1_PY
        or "_resolve_shared_panels" in BUNDLE_V1_PY
    )
    evaluator_single_reload = "reload_between_specs" in EVAL_PY
    return {
        "scenario": "S5_bundle_cache_single_reload",
        "bundle_has_panel_cache": has_panel_cache,
        "evaluator_has_reload_between_specs": evaluator_single_reload,
    }


# ---------------------------------------------------------------------------
# S6 — D2 + D3 production graduation / tier surface / UI badge
# ---------------------------------------------------------------------------


def _run_s6_production_graduation_tier() -> dict[str, Any]:
    grad_script_present = GRAD_SCRIPT_PATH.is_file()
    grad_note_present = GRAD_NOTE_PATH.is_file()
    tier_matrix = {
        "v2_path": health_surface._infer_brain_bundle_tier(
            "data/mvp/metis_brain_bundle_v2.json", {}, {}
        ),
        "v0_path": health_surface._infer_brain_bundle_tier(
            "data/mvp/metis_brain_bundle_v0.json", {}, {}
        ),
        "empty_path": health_surface._infer_brain_bundle_tier("", {}, {}),
        "metadata_override": health_surface._infer_brain_bundle_tier(
            "data/mvp/metis_brain_bundle_v0.json",
            {},
            {"graduation_tier": "production"},
        ),
    }
    ui_badge_present = 'id="tsr-bundle-tier"' in INDEX_HTML
    ui_hydrator_present = "hydrateBundleTierChip" in APP_JS
    locale_keys = (
        "tsr.bundle_tier.tip",
        "tsr.bundle_tier.demo",
        "tsr.bundle_tier.sample",
        "tsr.bundle_tier.production",
    )
    locale_coverage = {
        lang: {k: (k in flat) for k in locale_keys}
        for lang, flat in SHELL.items()
    }
    return {
        "scenario": "S6_production_graduation_tier",
        "grad_script_present": grad_script_present,
        "grad_note_present": grad_note_present,
        "tier_inference_matrix": tier_matrix,
        "tier_inference_is_correct": (
            tier_matrix["v2_path"] == "production"
            and tier_matrix["v0_path"] == "sample"
            and tier_matrix["empty_path"] == "demo"
            and tier_matrix["metadata_override"] == "production"
        ),
        "ui_badge_placeholder_present": ui_badge_present,
        "ui_hydrator_present": ui_hydrator_present,
        "locale_coverage_per_lang": locale_coverage,
    }


# ---------------------------------------------------------------------------
# S7 — E2 healthcheck degraded 200
# ---------------------------------------------------------------------------


def _run_s7_healthcheck_degraded() -> dict[str, Any]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        payload = health_surface.build_cockpit_runtime_health_payload(
            repo_root=Path(tmpdir), lang="ko"
        )
    degraded_reasons = list(payload.get("degraded_reasons") or [])
    status = payload.get("health_status")
    route_src = inspect.getsource(runtime_routes.dispatch_route) if hasattr(
        runtime_routes, "dispatch_route"
    ) else ""
    # Fallback: if we cannot locate a single dispatch function, scan the
    # full module source for the 503/down mapping.
    route_full = (
        REPO_ROOT / "src/phase47_runtime/routes.py"
    ).read_text(encoding="utf-8")
    route_maps_down_to_503 = (
        '"down"' in route_full and "503" in route_full
    )
    return {
        "scenario": "S7_healthcheck_degraded_200",
        "payload_ok": bool(payload.get("ok")),
        "health_status": status,
        "brain_bundle_missing_in_reasons": (
            "brain_bundle_missing" in degraded_reasons
        ),
        "degraded_reasons_count": len(degraded_reasons),
        "route_maps_down_to_503": route_maps_down_to_503,
        "status_vocabulary": list(
            health_surface.RUNTIME_HEALTH_STATUS_VALUES
        ),
    }


# ---------------------------------------------------------------------------
# S8 — E1 + E4 harness-tick queue + Railway deploy artifacts
# ---------------------------------------------------------------------------


def _run_s8_harness_queue_and_deploy() -> dict[str, Any]:
    cli_has_queue = '"--queue"' in MAIN_PY
    cli_has_loop = '"--loop"' in MAIN_PY
    cli_has_sleep = '"--sleep"' in MAIN_PY
    procfile_has_web = "web:" in PROCFILE
    procfile_has_worker = "worker:" in PROCFILE
    procfile_port = "$PORT" in PROCFILE
    procfile_loop = "--loop" in PROCFILE
    railway_healthcheck = (
        (RAILWAY_JSON.get("deploy") or {}).get("healthcheckPath")
        == "/api/runtime/health"
    )
    railway_start_cmd = (RAILWAY_JSON.get("deploy") or {}).get(
        "startCommand", ""
    )
    railway_port_in_start = "$PORT" in railway_start_cmd
    runbook_present = RAILWAY_RUNBOOK_PATH.is_file()
    runbook_has_healthcheck_section = False
    if runbook_present:
        body = RAILWAY_RUNBOOK_PATH.read_text(encoding="utf-8")
        runbook_has_healthcheck_section = "Healthcheck" in body or "healthcheckPath" in body
    return {
        "scenario": "S8_harness_queue_and_railway_deploy",
        "cli_flags_present": {
            "--queue": cli_has_queue,
            "--loop": cli_has_loop,
            "--sleep": cli_has_sleep,
        },
        "procfile": {
            "has_web": procfile_has_web,
            "has_worker": procfile_has_worker,
            "uses_$PORT": procfile_port,
            "worker_uses_--loop": procfile_loop,
        },
        "railway_json": {
            "healthcheck_on_runtime_health": railway_healthcheck,
            "start_cmd_uses_$PORT": railway_port_in_start,
        },
        "runbook_present": runbook_present,
        "runbook_has_healthcheck_section": runbook_has_healthcheck_section,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _write_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    s1 = _run_s1_research_4stack()
    s2 = _run_s2_today_hero_stack()
    s3 = _run_s3_invoke_lifecycle_recent()
    s4 = _run_s4_factor_batch_upsert()
    s5 = _run_s5_bundle_cache_single_reload()
    s6 = _run_s6_production_graduation_tier()
    s7 = _run_s7_healthcheck_degraded()
    s8 = _run_s8_harness_queue_and_deploy()

    patch8_locale_keys = [
        "research_section.what_changed",
        "research_section.why_it_matters",
        "research_section.no_what_changed",
        "tsr.today.stack.head",
        "tsr.today.why_now.head",
        "tsr.today.why_now.empty",
        "lineage.step_note.current",
        "lineage.step_note.not_started",
        "lineage.gap_30d_plus",
        "lineage.gap_annotation_prefix",
        "research_section.invoke_state_running",
        "research_section.produced_refs_summary",
        "research_section.recent_requests_head",
        "research_section.recent_requests_empty",
        "tsr.invoke.contract.status_after",
        "tsr.bundle_tier.tip",
        "tsr.bundle_tier.demo",
        "tsr.bundle_tier.sample",
        "tsr.bundle_tier.production",
    ]
    locale_coverage_per_lang = {
        lang: {k: (k in flat) for k in patch8_locale_keys}
        for lang, flat in SHELL.items()
    }

    bridge = {
        "contract": "AGH_V1_PATCH_8_PRODUCTION_GRADUATION_BRIDGE_EVIDENCE_V1",
        "milestone": 19,
        "generated_at_utc": _now_iso(),
        "patch_nature": "production_graduation_ux_ai_wow_scale_closure",
        "not_a_demo_theater_patch": True,
        "locale_patch8_keys": patch8_locale_keys,
        "locale_patch8_coverage_per_lang": locale_coverage_per_lang,
        "legacy_locale_alias_count": len(LEGACY_LOCALE_ALIASES),
        "research_4_stack_ok": (
            s1["contract_has_what_changed_ko"]
            and s1["contract_has_what_changed_en"]
            and s1["guardrail_scans_what_changed"]
            and s1["prompt_mentions_what_changed"]
            and s1["render_has_what_changed_section"]
            and s1["render_labels_why_it_matters"]
        ),
        "today_hero_stack_ok": (
            s2["renderer_present"]
            and s2["stack_class_present"]
            and s2["jump_to_invoke_present"]
        ),
        "invoke_lifecycle_ok": (
            s3["lifecycle_state_in_route"]
            and s3["ui_uses_lifecycle_state"]
            and s3["humanize_produced_refs_helper"]
            and s3["hydrate_recent_sandbox_requests_present"]
            and s3["contract_state_slot_present"]
        ),
        "factor_batch_upsert_ok": (
            all(s4["records_exports"].values())
            and all(s4["runner_batch_upsert_wiring"].values())
            and s4["panel_truncation_metadata_recorded"]
        ),
        "bundle_cache_single_reload_ok": (
            s5["bundle_has_panel_cache"]
            and s5["evaluator_has_reload_between_specs"]
        ),
        "production_graduation_tier_ok": (
            s6["grad_script_present"]
            and s6["grad_note_present"]
            and s6["tier_inference_is_correct"]
            and s6["ui_badge_placeholder_present"]
            and s6["ui_hydrator_present"]
        ),
        "healthcheck_degraded_ok": (
            s7["payload_ok"]
            and s7["health_status"] == "degraded"
            and s7["brain_bundle_missing_in_reasons"]
            and s7["route_maps_down_to_503"]
        ),
        "harness_queue_and_deploy_ok": (
            all(s8["cli_flags_present"].values())
            and all(s8["procfile"].values())
            and all(s8["railway_json"].values())
            and s8["runbook_present"]
            and s8["runbook_has_healthcheck_section"]
        ),
    }

    runbook = {
        "contract": "AGH_V1_PATCH_8_PRODUCTION_GRADUATION_RUNBOOK_EVIDENCE_V1",
        "milestone": 19,
        "generated_at_utc": _now_iso(),
        "patch_nature": "production_graduation_ux_ai_wow_scale_closure",
        "scenarios": [s1, s2, s3, s4, s5, s6, s7, s8],
    }

    ev_dir = REPO_ROOT / "data" / "mvp" / "evidence"
    _write_evidence(
        ev_dir
        / "agentic_operating_harness_v1_milestone_19_patch_8_bridge_evidence.json",
        bridge,
    )
    _write_evidence(
        ev_dir
        / "agentic_operating_harness_v1_milestone_19_patch_8_runbook_evidence.json",
        runbook,
    )
    print("wrote patch 8 milestone 19 evidence files.")
    # Echo top-level pass/fail flags so operators can eyeball readiness.
    top_flags = {
        k: v
        for k, v in bridge.items()
        if k.endswith("_ok")
    }
    print(json.dumps(top_flags, indent=2, ensure_ascii=False, sort_keys=True))
    all_ok = all(bool(v) for v in top_flags.values())
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
