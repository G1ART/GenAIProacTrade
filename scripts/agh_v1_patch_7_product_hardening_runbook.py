"""AGH v1 Patch 7 — Product hardening / UX depth / scale-readiness runbook.

Exercises the operator-visible Patch 7 surfaces against the code the
vanilla-JS SPA actually renders. This is NOT a demo-theater runbook;
every scenario must tie back to the Patch 7 workorder acceptance list:

    S1. A1 / IA simplification — assert the 2-tier ``<nav id="nav">``
        (primary + utility rows) is wired and the utility row carries
        the demoted entries (Journal / Advanced / Reload bundle).
    S2. A2 + A3 + A4 + A5 — Today typography / audit consolidation /
        Research 3-cluster grouping / Replay 3-lane timeline + lineage
        enrichment / shared-tooltip multi-part split all present in
        ``app.js`` and ``index.html``.
    S3. B1 + B2 — bounded invoke contract is visible at the action
        point: contract-card locale keys declared, ``app.js`` renders
        ``will_do`` / ``will_not_do`` / ``after_enqueue`` lines, and
        the server-enforced operator gate (``METIS_HARNESS_UI_INVOKE_ENABLED``)
        still disables unauthenticated enqueue.
    S4. C2b + C2c — response-size guardrails: ``/api/today/spectrum``
        exposes ``rows_limit`` and the payload declares ``total_rows``
        / ``truncated``; ``/api/replay/governance-lineage`` exposes a
        capped ``limit`` parameter.
    S5. C2a + C2d — governance_scan N+1 hoist: ``deduplicate_specs``
        does not call ``store.list_packets`` per spec; a single call
        to ``_build_existing_evaluation_index`` precedes the loop.
        Also assert perf-counter stderr log helpers exist where the
        workorder scope requires instrumentation.
    S6. C1 + C3 — Scale Readiness Note v1 is present and ends with an
        explicit S&P 500 verdict.

Produces two files under ``data/mvp/evidence/``:

    * ``agentic_operating_harness_v1_milestone_18_patch_7_bridge_evidence.json``
      — code-shape evidence (renderer contracts, CSS primitives,
      locale-key coverage, scale-readiness findings count).
    * ``agentic_operating_harness_v1_milestone_18_patch_7_runbook_evidence.json``
      — operator-auditable runbook trace for S1–S6.

This script is deterministic — no Supabase writes, no worker spawns.
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


from agentic_harness.agents import governance_scan_provider_v1 as gov_scan  # noqa: E402
from agentic_harness.contracts.packets_v1 import SANDBOX_KINDS  # noqa: E402
from agentic_harness.store import FixtureHarnessStore  # noqa: E402
from phase47_runtime import routes as runtime_routes  # noqa: E402
from phase47_runtime import today_spectrum as ts  # noqa: E402
from phase47_runtime.phase47e_user_locale import SHELL  # noqa: E402


APP_JS = (REPO_ROOT / "src/phase47_runtime/static/app.js").read_text(encoding="utf-8")
INDEX_HTML = (REPO_ROOT / "src/phase47_runtime/static/index.html").read_text(
    encoding="utf-8"
)
SCALE_NOTE = REPO_ROOT / "docs/plan/METIS_Scale_Readiness_Note_Patch7_v1.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# S1 — A1 2-tier nav
# ---------------------------------------------------------------------------


def _run_s1_nav_two_tier() -> dict[str, Any]:
    primary_block_open = INDEX_HTML.find('class="nav-row nav-primary"')
    utility_block_open = INDEX_HTML.find('class="nav-row nav-utility"')
    nav_close = INDEX_HTML.find("</nav>", max(primary_block_open, utility_block_open))
    utility_block = (
        INDEX_HTML[utility_block_open:nav_close]
        if utility_block_open > 0 and nav_close > utility_block_open
        else ""
    )

    demoted_entries = ["journal", "advanced"]
    demoted_present = {
        k: f'data-panel="{k}"' in utility_block for k in demoted_entries
    }
    reload_in_utility = 'id="btn-reload"' in utility_block

    aria_primary = 'data-i18n-aria-label="tsr.nav.primary.aria"' in INDEX_HTML
    aria_utility = 'data-i18n-aria-label="tsr.nav.utility.aria"' in INDEX_HTML
    aria_keys_declared = {
        lang: (
            "tsr.nav.primary.aria" in flat and "tsr.nav.utility.aria" in flat
        )
        for lang, flat in SHELL.items()
    }

    return {
        "scenario": "S1_information_architecture_two_tier_nav",
        "primary_row_present": primary_block_open > 0,
        "utility_row_present": utility_block_open > 0,
        "demoted_entries_in_utility": demoted_present,
        "reload_bundle_in_utility": reload_in_utility,
        "aria_primary_wired": aria_primary,
        "aria_utility_wired": aria_utility,
        "aria_keys_declared_per_lang": aria_keys_declared,
    }


# ---------------------------------------------------------------------------
# S2 — A2 / A3 / A4 / A5 surfaces
# ---------------------------------------------------------------------------


def _run_s2_ux_depth_surfaces() -> dict[str, Any]:
    typo_tokens = [
        "--tsr-type-hero",
        "--tsr-type-subhead",
        "--tsr-type-body",
        "--tsr-type-foot",
    ]
    typo_classes = [
        ".tsr-hero",
        ".tsr-subhead",
        ".tsr-body",
        ".tsr-foot",
        ".tsr-audit",
        ".tsr-recent-activity",
    ]
    a2_missing_tokens = [t for t in typo_tokens if t not in INDEX_HTML]
    a2_missing_classes = [c for c in typo_classes if c not in INDEX_HTML]
    a2_consolidated_audit = "function renderTodayConsolidatedAuditHtml(" in APP_JS
    a2_recent_activity = "function renderTodayRecentActivityHtml(" in APP_JS
    idx_od = APP_JS.find("function renderTodayObjectDetailHtml(")
    end_od = APP_JS.find("\n  }\n", idx_od) if idx_od > 0 else -1
    od_body = APP_JS[idx_od:end_od] if idx_od > 0 and end_od > idx_od else ""
    a2_legacy_copy_removed = (
        "Show legacy MIR detail" not in od_body
        and "원 MIR 세부 보기 (고급)" not in od_body
    )

    a3_clusters = [
        c
        for c in ("current_read", "open_questions", "bounded_next")
        if f'data-tsr-cluster="{c}"' in APP_JS
    ]

    a4_three_lane = 'data-tsr-timeline-plot="3lane"' in APP_JS
    a4_step_summary = "tsr-step-summary" in APP_JS and "lineage.step_count" in APP_JS
    a4_step_delta_helper = "function tsrStepDeltaLabel(" in APP_JS

    idx_tt = APP_JS.find("tsrInstallTooltip()")
    tt_body = APP_JS[idx_tt : idx_tt + 3000] if idx_tt > 0 else ""
    a5_multipart_split = 'const SUB_SEP = " · "' in tt_body and "split(SUB_SEP)" in tt_body

    return {
        "scenario": "S2_ux_depth_surfaces",
        "a2_typography_tokens_missing": a2_missing_tokens,
        "a2_typography_classes_missing": a2_missing_classes,
        "a2_consolidated_audit_renderer": a2_consolidated_audit,
        "a2_recent_activity_renderer": a2_recent_activity,
        "a2_legacy_mir_detail_copy_removed": a2_legacy_copy_removed,
        "a3_research_clusters_present": a3_clusters,
        "a4_timeline_three_lane": a4_three_lane,
        "a4_lineage_step_count_summary": a4_step_summary,
        "a4_lineage_step_delta_helper": a4_step_delta_helper,
        "a5_tooltip_multipart_split": a5_multipart_split,
    }


# ---------------------------------------------------------------------------
# S3 — B1 + B2 bounded invoke contract + operator gate
# ---------------------------------------------------------------------------


def _run_s3_bounded_invoke_contract() -> dict[str, Any]:
    contract_keys = [
        "tsr.invoke.contract.head",
        "tsr.invoke.contract.will_do",
        "tsr.invoke.contract.will_not_do",
        "tsr.invoke.contract.after_enqueue",
    ]
    contract_keys_declared = {
        lang: [k for k in contract_keys if k in flat] for lang, flat in SHELL.items()
    }
    contract_rendered = all(k in APP_JS for k in contract_keys)

    # Exercise the operator gate against a deterministic FixtureHarnessStore
    # so no real network is touched. This mirrors Patch 6's smoke but the
    # goal here is to prove Patch 7 did not accidentally regress the gate
    # while polishing the UI side.
    api_sandbox_enqueue_v1 = runtime_routes.api_sandbox_enqueue_v1
    fixture_store = FixtureHarnessStore()
    prev_builder = runtime_routes._build_harness_store_for_api
    runtime_routes._build_harness_store_for_api = (  # type: ignore[assignment]
        lambda use_fixture=False: fixture_store
    )

    valid_body = {
        "sandbox_kind": "validation_rerun",
        "registry_entry_id": "reg_patch7_demo_v0",
        "horizon": "short",
        "target_spec": {
            "factor_name": "earnings_quality_composite",
            "universe_name": "large_cap_research_slice_demo_v0",
            "horizon_type": "next_month",
            "return_basis": "raw",
        },
        "rationale": "Patch 7 runbook operator-gate regression smoke.",
        "cited_evidence_packet_ids": ["ValidationPromotionEvaluationV1:ev_runbook_s3_p7"],
        "request_id": "sbx_runbook_patch7_s3",
    }

    try:
        prev_flag = os.environ.get("METIS_HARNESS_UI_INVOKE_ENABLED")
        os.environ.pop("METIS_HARNESS_UI_INVOKE_ENABLED", None)
        status_disabled, body_disabled = api_sandbox_enqueue_v1(
            state=None, body=valid_body
        )
        os.environ["METIS_HARNESS_UI_INVOKE_ENABLED"] = "1"
        status_ok, body_ok = api_sandbox_enqueue_v1(state=None, body=valid_body)
    finally:
        if prev_flag is None:
            os.environ.pop("METIS_HARNESS_UI_INVOKE_ENABLED", None)
        else:
            os.environ["METIS_HARNESS_UI_INVOKE_ENABLED"] = prev_flag
        runtime_routes._build_harness_store_for_api = prev_builder  # type: ignore[assignment]

    return {
        "scenario": "S3_bounded_invoke_contract_and_gate",
        "contract_keys_declared_per_lang": contract_keys_declared,
        "contract_rendered_in_app_js": contract_rendered,
        "gate_disabled_status": status_disabled,
        "gate_disabled_error": body_disabled.get("error"),
        "gate_enabled_status": status_ok,
        "gate_enabled_cli_hint_present": bool(body_ok.get("cli_hint")),
        "gate_enabled_operator_note_present": bool(body_ok.get("operator_note")),
        "sandbox_kinds": list(SANDBOX_KINDS),
    }


# ---------------------------------------------------------------------------
# S4 — C2b + C2c response-size guardrails
# ---------------------------------------------------------------------------


def _run_s4_response_size_guardrails() -> dict[str, Any]:
    spectrum_sig = inspect.signature(ts.build_today_spectrum_payload)
    spectrum_has_rows_limit = "rows_limit" in spectrum_sig.parameters

    lineage_default = getattr(runtime_routes, "REPLAY_LINEAGE_DEFAULT_LIMIT", None)
    lineage_max = getattr(runtime_routes, "REPLAY_LINEAGE_MAX_LIMIT", None)
    lineage_sig = inspect.signature(runtime_routes.api_replay_governance_lineage)
    lineage_has_limit = "limit" in lineage_sig.parameters

    return {
        "scenario": "S4_response_size_guardrails",
        "spectrum_rows_limit_param_present": spectrum_has_rows_limit,
        "spectrum_default_rows_limit": ts.TODAY_SPECTRUM_DEFAULT_ROWS_LIMIT,
        "spectrum_max_rows_limit": ts.TODAY_SPECTRUM_MAX_ROWS_LIMIT,
        "lineage_limit_param_present": lineage_has_limit,
        "lineage_default_limit": lineage_default,
        "lineage_max_limit": lineage_max,
        "lineage_max_cap_500": lineage_max == 500,
    }


# ---------------------------------------------------------------------------
# S5 — C2a N+1 hoist + C2d perf instrumentation
# ---------------------------------------------------------------------------


def _run_s5_scale_safe_defaults() -> dict[str, Any]:
    dedupe_src = inspect.getsource(gov_scan.deduplicate_specs)
    hoist_builder_called = "_build_existing_evaluation_index" in dedupe_src
    per_spec_list_packets = dedupe_src.count("store.list_packets(")
    index_builder_src = inspect.getsource(gov_scan._build_existing_evaluation_index)
    index_builder_list_packets = index_builder_src.count("list_packets(")

    perf_sites = {
        "governance_scan_provider_v1.deduplicate_specs": "_emit_perf_log(" in dedupe_src,
        "today_spectrum.build_today_spectrum_payload": "_emit_perf_log("
        in inspect.getsource(ts.build_today_spectrum_payload),
        "today_spectrum.build_today_object_detail_payload": "_emit_perf_log("
        in inspect.getsource(ts.build_today_object_detail_payload),
    }
    try:
        from agentic_harness.scheduler import tick as tick_mod  # noqa: E402

        perf_sites["scheduler.tick.run_one_tick"] = "_emit_perf_log(" in inspect.getsource(
            tick_mod.run_one_tick
        )
    except Exception:  # pragma: no cover - defensive
        perf_sites["scheduler.tick.run_one_tick"] = False

    return {
        "scenario": "S5_scale_safe_defaults",
        "dedupe_hoists_index_builder": hoist_builder_called,
        "dedupe_per_spec_list_packets_calls": per_spec_list_packets,
        "index_builder_list_packets_calls": index_builder_list_packets,
        "perf_instrumentation_sites": perf_sites,
    }


# ---------------------------------------------------------------------------
# S6 — C1 + C3 Scale Readiness Note
# ---------------------------------------------------------------------------


def _run_s6_scale_readiness_note() -> dict[str, Any]:
    if not SCALE_NOTE.is_file():
        return {
            "scenario": "S6_scale_readiness_note",
            "present": False,
            "path": str(SCALE_NOTE.relative_to(REPO_ROOT)),
        }
    body = SCALE_NOTE.read_text(encoding="utf-8")
    findings = body.count("### Finding")
    has_verdict = "Verdict" in body or "verdict" in body
    has_sp500 = "S&P 500" in body or "S&P500" in body
    has_sufficient = "sufficient" in body
    has_blocks = "still blocks" in body.lower()
    has_next = "next concrete patch" in body.lower()
    return {
        "scenario": "S6_scale_readiness_note",
        "present": True,
        "path": str(SCALE_NOTE.relative_to(REPO_ROOT)),
        "finding_count": findings,
        "has_sp500_verdict_section": has_verdict and has_sp500,
        "mentions_what_is_sufficient": has_sufficient,
        "mentions_what_still_blocks": has_blocks,
        "mentions_next_concrete_patch": has_next,
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
    s1 = _run_s1_nav_two_tier()
    s2 = _run_s2_ux_depth_surfaces()
    s3 = _run_s3_bounded_invoke_contract()
    s4 = _run_s4_response_size_guardrails()
    s5 = _run_s5_scale_safe_defaults()
    s6 = _run_s6_scale_readiness_note()

    locale_patch7_keys = [
        "tsr.nav.primary.aria",
        "tsr.nav.utility.aria",
        "tsr.nav.utility.note",
        "tsr.invoke.contract.head",
        "tsr.invoke.contract.will_do",
        "tsr.invoke.contract.will_not_do",
        "tsr.invoke.contract.after_enqueue",
        "tsr.recent.head",
        "tsr.recent.empty",
        "tsr.audit.head",
        "plot.lane_apply",
        "plot.lane_spectrum",
        "plot.lane_sandbox",
        "plot.lane_legend_note",
        "lineage.step_count",
        "lineage.step_after",
        "lineage.step_pending",
    ]
    locale_coverage_per_lang = {
        lang: {k: (k in flat) for k in locale_patch7_keys}
        for lang, flat in SHELL.items()
    }

    bridge = {
        "contract": "AGH_V1_PATCH_7_PRODUCT_HARDENING_BRIDGE_EVIDENCE_V1",
        "milestone": 18,
        "generated_at_utc": _now_iso(),
        "patch_nature": "product_hardening_ux_depth_scale_readiness",
        "not_a_demo_theater_patch": True,
        "locale_patch7_keys": locale_patch7_keys,
        "locale_patch7_coverage_per_lang": locale_coverage_per_lang,
        "renderer_contracts_ok": {
            "two_tier_nav": s1["primary_row_present"] and s1["utility_row_present"],
            "today_typography": not s2["a2_typography_tokens_missing"]
            and not s2["a2_typography_classes_missing"],
            "audit_consolidated": s2["a2_consolidated_audit_renderer"]
            and s2["a2_legacy_mir_detail_copy_removed"],
            "research_three_clusters": len(s2["a3_research_clusters_present"]) == 3,
            "replay_three_lane": s2["a4_timeline_three_lane"]
            and s2["a4_lineage_step_count_summary"]
            and s2["a4_lineage_step_delta_helper"],
            "tooltip_multipart": s2["a5_tooltip_multipart_split"],
            "invoke_contract_card": s3["contract_rendered_in_app_js"],
        },
        "scale_guardrails_ok": {
            "spectrum_rows_limit": s4["spectrum_rows_limit_param_present"],
            "lineage_limit": s4["lineage_limit_param_present"],
            "lineage_max_cap_500": s4["lineage_max_cap_500"],
            "governance_dedupe_hoisted": s5["dedupe_hoists_index_builder"]
            and s5["dedupe_per_spec_list_packets_calls"] == 0,
            "perf_instrumentation_sites": s5["perf_instrumentation_sites"],
        },
        "scale_readiness_note_ok": s6["present"]
        and s6.get("finding_count", 0) >= 6
        and s6.get("has_sp500_verdict_section", False),
    }

    runbook = {
        "contract": "AGH_V1_PATCH_7_PRODUCT_HARDENING_RUNBOOK_EVIDENCE_V1",
        "milestone": 18,
        "generated_at_utc": _now_iso(),
        "patch_nature": "product_hardening_ux_depth_scale_readiness",
        "scenarios": [s1, s2, s3, s4, s5, s6],
    }

    ev_dir = REPO_ROOT / "data" / "mvp" / "evidence"
    _write_evidence(
        ev_dir / "agentic_operating_harness_v1_milestone_18_patch_7_bridge_evidence.json",
        bridge,
    )
    _write_evidence(
        ev_dir / "agentic_operating_harness_v1_milestone_18_patch_7_runbook_evidence.json",
        runbook,
    )
    print("wrote patch 7 milestone 18 evidence files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
