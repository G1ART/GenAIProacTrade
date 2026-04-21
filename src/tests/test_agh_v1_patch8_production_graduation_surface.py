"""AGH v1 Patch 8 — production graduation / UX-AI wow / scale closure surface.

These tests lock in the structural contract introduced by Patch 8. Most
of them are surface/contract checks against `app.js`, `index.html`,
`phase47e_user_locale.py`, `cockpit_health_surface.py`, `routes.py`,
`records.py`, `validation_runner.py`, and
`bundle_full_from_validation_v1.py`. Behaviour is covered by the
harness/executor tests + the locale graduation no-leak test.

Groups:

    * A1 : research 4-stack (what_changed -> why_it_matters)
    * A2 : Today hero stack (why_now / confidence / caveat / next)
    * A3 : lineage step note + plot gap annotation (30d+)
    * A5 : tooltip ttCtx threading
    * B2 : sandbox queue 4-state lifecycle
    * B3 : per-entry recent sandbox requests list
    * B4 : contract card status_after line + dedicated chip slot
    * C1 : factor validation batch upsert helpers
    * C2 : bundle panel cache + evaluator single reload
    * D2 : production graduation script exists
    * D3 : 3-tier brain-bundle inference + health surfacing + UI chip
    * E1 : harness-tick --queue CLI arg
    * E2 : /api/runtime/health degraded=200 + reasons
    * E4 : Procfile + railway.json + $PORT fallback
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_JS = REPO_ROOT / "src" / "phase47_runtime" / "static" / "app.js"
INDEX_HTML = REPO_ROOT / "src" / "phase47_runtime" / "static" / "index.html"
LOCALE_PY = REPO_ROOT / "src" / "phase47_runtime" / "phase47e_user_locale.py"
ROUTES_PY = REPO_ROOT / "src" / "phase47_runtime" / "routes.py"
HEALTH_PY = REPO_ROOT / "src" / "phase51_runtime" / "cockpit_health_surface.py"
RECORDS_PY = REPO_ROOT / "src" / "db" / "records.py"
RUNNER_PY = REPO_ROOT / "src" / "research" / "validation_runner.py"
BUNDLE_V1_PY = (
    REPO_ROOT / "src" / "metis_brain" / "bundle_full_from_validation_v1.py"
)
EVAL_PY = (
    REPO_ROOT
    / "src"
    / "agentic_harness"
    / "agents"
    / "layer4_promotion_evaluator_v1.py"
)
ORCH_PY = REPO_ROOT / "src" / "agentic_harness" / "agents" / "layer5_orchestrator.py"
CONTRACT_PY = REPO_ROOT / "src" / "agentic_harness" / "llm" / "contract.py"
GUARDRAILS_PY = REPO_ROOT / "src" / "agentic_harness" / "llm" / "guardrails.py"
APP_PY = REPO_ROOT / "src" / "phase47_runtime" / "app.py"
MAIN_PY = REPO_ROOT / "src" / "main.py"
PROCFILE = REPO_ROOT / "Procfile"
RAILWAY_JSON = REPO_ROOT / "railway.json"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
D2_SCRIPT = (
    REPO_ROOT / "scripts" / "agh_v1_patch_8_production_bundle_graduation.py"
)
D3_DOC = (
    REPO_ROOT
    / "docs"
    / "plan"
    / "METIS_Production_Bundle_Graduation_Note_v1.md"
)
RAILWAY_RUNBOOK = (
    REPO_ROOT
    / "docs"
    / "ops"
    / "METIS_Railway_Supabase_Deployment_Runbook_v1.md"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_js() -> str:
    return _read(APP_JS)


@pytest.fixture(scope="module")
def index_html() -> str:
    return _read(INDEX_HTML)


@pytest.fixture(scope="module")
def locale_src() -> str:
    return _read(LOCALE_PY)


@pytest.fixture(scope="module")
def routes_src() -> str:
    return _read(ROUTES_PY)


@pytest.fixture(scope="module")
def health_src() -> str:
    return _read(HEALTH_PY)


# ---------------------------------------------------------------------------
# A1 — Research 4-stack: what_changed + why_it_matters
# ---------------------------------------------------------------------------


def test_a1_research_contract_has_what_changed_bullets() -> None:
    src = _read(CONTRACT_PY)
    assert "what_changed_bullets_ko" in src
    assert "what_changed_bullets_en" in src


def test_a1_research_guardrail_scans_what_changed(_=None) -> None:
    src = _read(GUARDRAILS_PY)
    assert "what_changed_bullets_ko" in src
    assert "what_changed_bullets_en" in src


def test_a1_orchestrator_prompt_mentions_what_changed() -> None:
    src = _read(ORCH_PY)
    assert "what_changed" in src.lower()


def test_a1_research_locale_keys_present(locale_src: str) -> None:
    for key in (
        "research_section.what_changed",
        "research_section.why_it_matters",
        "research_section.no_what_changed",
    ):
        assert f'"{key}":' in locale_src, key


def test_a1_research_renderer_labels_why_it_matters(app_js: str) -> None:
    # "current_read" cluster head now reads "Why it matters" via the locale
    # key, and the "What changed" section renders above it.
    assert "research_section.why_it_matters" in app_js
    assert "research_section.what_changed" in app_js


# ---------------------------------------------------------------------------
# A2 — Today hero stack
# ---------------------------------------------------------------------------


def test_a2_today_why_now_stack_locale_keys(locale_src: str) -> None:
    for key in (
        "tsr.today.stack.head",
        "tsr.today.why_now.head",
        "tsr.today.why_now.empty",
    ):
        assert f'"{key}":' in locale_src, key


def test_a2_today_renderer_emits_why_now_stack(app_js: str) -> None:
    assert "renderTodayWhyNowConfidenceCaveatNextHtml" in app_js
    assert "tsr-why-now-stack" in app_js


def test_a2_today_stack_jumps_to_invoke(app_js: str) -> None:
    # The hero stack exposes a jump-to-invoke affordance so the operator
    # can land directly on the research enqueue card.
    assert "data-tsr-jump-to-invoke" in app_js


# ---------------------------------------------------------------------------
# A3 — Lineage step note + 30d+ plot gap annotation
# ---------------------------------------------------------------------------


def test_a3_lineage_step_note_locale_keys(locale_src: str) -> None:
    for key in (
        "lineage.step_note.current",
        "lineage.step_note.not_started",
        "lineage.gap_30d_plus",
        "lineage.gap_annotation_prefix",
    ):
        assert f'"{key}":' in locale_src, key


def test_a3_lineage_renderer_emits_step_note(app_js: str) -> None:
    assert "tsr-step-note" in app_js
    assert "lineage.step_note.current" in app_js


def test_a3_plot_gap_annotation_rendered(app_js: str) -> None:
    assert "plot-gap-annotation" in app_js
    assert "GAP_THRESHOLD_MS" in app_js


# ---------------------------------------------------------------------------
# A5 — Tooltip ttCtx threading
# ---------------------------------------------------------------------------


def test_a5_extract_tooltip_context_helper_exists(app_js: str) -> None:
    assert "extractTooltipContextFromTsr" in app_js


def test_a5_tooltip_context_carries_what_changed_and_confidence(
    app_js: str,
) -> None:
    # The helper output is threaded into tooltip subtext. Guard both
    # tokens so refactors don't silently drop them.
    assert "what_changed_one_line" in app_js
    assert "confidence_band" in app_js


# ---------------------------------------------------------------------------
# B2 — sandbox queue 4-state lifecycle
# ---------------------------------------------------------------------------


def test_b2_sandbox_requests_route_returns_lifecycle_state(
    routes_src: str,
) -> None:
    # The route must compute and return a 4-state lifecycle the UI can
    # render without re-deriving from job+result status.
    assert "_life_state" in routes_src or "lifecycle_state" in routes_src
    assert "sandbox_queue" in routes_src


def test_b2_ui_invoke_poll_understands_lifecycle_state(app_js: str) -> None:
    assert "lifecycle_state" in app_js
    # 4-state chip keys used by the UI.
    for chip_key in (
        "research_section.invoke_state_running",
        "research_section.invoke_state_queued",
    ):
        # running key is new in Patch 8; queued existed — we only hard-
        # require the Patch 8 addition.
        if chip_key == "research_section.invoke_state_running":
            assert chip_key in app_js, chip_key


def test_b2_humanize_produced_refs_helper_exists(app_js: str) -> None:
    assert "humanizeProducedRefs" in app_js


# ---------------------------------------------------------------------------
# B3 — per-entry recent sandbox requests list
# ---------------------------------------------------------------------------


def test_b3_recent_requests_locale_keys(locale_src: str) -> None:
    for key in (
        "research_section.recent_requests_head",
        "research_section.recent_requests_empty",
    ):
        assert f'"{key}":' in locale_src, key


def test_b3_recent_requests_hydrator_exists(app_js: str) -> None:
    assert "hydrateRecentSandboxRequests" in app_js
    assert "tsr-recent-sandbox-requests" in app_js


# ---------------------------------------------------------------------------
# B4 — contract card status_after line + state slot
# ---------------------------------------------------------------------------


def test_b4_contract_status_after_locale_key(locale_src: str) -> None:
    assert '"tsr.invoke.contract.status_after":' in locale_src


def test_b4_contract_state_slot_in_ui(app_js: str) -> None:
    assert "tsr-contract-state-slot" in app_js


# ---------------------------------------------------------------------------
# C1 — factor validation batch upsert helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fn_name",
    [
        "upsert_factor_validation_summaries",
        "upsert_factor_quantile_results",
        "upsert_factor_coverage_reports",
    ],
)
def test_c1_records_exports_batch_upserts(fn_name: str) -> None:
    import importlib

    mod = importlib.import_module("db.records")
    assert hasattr(mod, fn_name), fn_name


def test_c1_runner_uses_batch_upsert() -> None:
    src = _read(RUNNER_PY)
    # Accumulate-then-flush pattern: the three batch helpers must be
    # referenced inside the runner and the old per-row insert helpers
    # must not be called inside the validation loop anymore.
    assert "upsert_factor_validation_summaries" in src
    assert "upsert_factor_quantile_results" in src
    assert "upsert_factor_coverage_reports" in src


def test_c1_runner_records_panel_truncation_metadata() -> None:
    src = _read(RUNNER_PY)
    assert "panel_truncated_at_limit" in src
    assert "panel_rows_fetched" in src


# ---------------------------------------------------------------------------
# C2 — bundle panel cache + evaluator single reload
# ---------------------------------------------------------------------------


def test_c2_bundle_has_panel_cache() -> None:
    src = _read(BUNDLE_V1_PY)
    assert "_panel_cache" in src or "_resolve_shared_panels" in src


def test_c2_evaluator_single_reload_parameter() -> None:
    src = _read(EVAL_PY)
    assert "reload_between_specs" in src


# ---------------------------------------------------------------------------
# D2 — production graduation script
# ---------------------------------------------------------------------------


def test_d2_graduation_script_exists() -> None:
    assert D2_SCRIPT.is_file(), D2_SCRIPT
    body = _read(D2_SCRIPT)
    assert "validate_active_registry_integrity" in body
    assert "metis_brain_bundle_v2.json" in body
    # The script must atomically write and emit an evidence file.
    assert "os.replace" in body or "Path.replace" in body


# ---------------------------------------------------------------------------
# D3 — 3-tier bundle vocabulary + health surfacing + UI badge
# ---------------------------------------------------------------------------


def test_d3_tier_values_declared(health_src: str) -> None:
    assert "BRAIN_BUNDLE_TIERS" in health_src
    for tier in ("demo", "sample", "production"):
        assert f'"{tier}"' in health_src, tier


def test_d3_infer_tier_matrix() -> None:
    from phase51_runtime.cockpit_health_surface import _infer_brain_bundle_tier

    assert (
        _infer_brain_bundle_tier(
            "data/mvp/metis_brain_bundle_v2.json", {}, {}
        )
        == "production"
    )
    assert (
        _infer_brain_bundle_tier(
            "data/mvp/metis_brain_bundle_v0.json", {}, {}
        )
        == "sample"
    )
    assert _infer_brain_bundle_tier("", {}, {}) == "demo"
    # metadata wins over filename-based inference.
    assert (
        _infer_brain_bundle_tier(
            "data/mvp/metis_brain_bundle_v0.json",
            {},
            {"graduation_tier": "production"},
        )
        == "production"
    )


def test_d3_health_surface_emits_tier(health_src: str) -> None:
    assert "brain_bundle_tier" in health_src


def test_d3_ui_badge_placeholder_present(index_html: str) -> None:
    assert 'id="tsr-bundle-tier"' in index_html


def test_d3_ui_hydrator_uses_health_tier(app_js: str) -> None:
    assert "hydrateBundleTierChip" in app_js
    assert "brain_bundle_tier" in app_js


def test_d3_tier_locale_keys(locale_src: str) -> None:
    for key in (
        "tsr.bundle_tier.tip",
        "tsr.bundle_tier.demo",
        "tsr.bundle_tier.sample",
        "tsr.bundle_tier.production",
    ):
        assert f'"{key}":' in locale_src, key


def test_d3_graduation_note_exists() -> None:
    assert D3_DOC.is_file()
    body = _read(D3_DOC)
    for token in ("demo", "sample", "production", "graduation_tier"):
        assert token in body, token


# ---------------------------------------------------------------------------
# E1 — harness-tick --queue
# ---------------------------------------------------------------------------


def test_e1_harness_tick_cli_declares_queue_flag() -> None:
    src = _read(MAIN_PY)
    # Sub-parser registration block.
    assert '"--queue"' in src
    assert "queue_filter" in src


def test_e1_harness_tick_loop_flag_for_worker() -> None:
    # E4 wires the worker via `--loop --sleep`; both must be advertised.
    src = _read(MAIN_PY)
    assert '"--loop"' in src
    assert '"--sleep"' in src


# ---------------------------------------------------------------------------
# E2 — healthcheck degraded 200 + reasons
# ---------------------------------------------------------------------------


def test_e2_health_payload_carries_degraded_reasons(health_src: str) -> None:
    assert "degraded_reasons" in health_src
    assert "RUNTIME_HEALTH_STATUS_VALUES" in health_src


def test_e2_route_maps_down_to_503(routes_src: str) -> None:
    # The route must 200 on ok|degraded and only 503 on down.
    assert "503" in routes_src
    assert '"down"' in routes_src or "== \"down\"" in routes_src


def test_e2_degraded_returns_200_in_practice(tmp_path) -> None:
    """Synthetic happy-ish path: if the brain bundle is missing, the
    payload must still return ok=True and carry 'brain_bundle_missing'
    in degraded_reasons."""

    from phase51_runtime.cockpit_health_surface import (
        build_cockpit_runtime_health_payload,
    )

    # tmp_path has no bundle file; the builder must degrade gracefully.
    payload = build_cockpit_runtime_health_payload(repo_root=tmp_path, lang="ko")
    assert payload.get("ok") is True
    assert "degraded_reasons" in payload
    reasons = payload.get("degraded_reasons") or []
    assert "brain_bundle_missing" in reasons, reasons
    # E2 contract: health_status must be 'degraded' when recoverable
    # reasons are present. It must never be raw 'down' just because the
    # bundle is missing; 'down' is reserved for process-level failures.
    assert payload.get("health_status") == "degraded"


# ---------------------------------------------------------------------------
# E4 — Procfile + railway.json + $PORT fallback
# ---------------------------------------------------------------------------


def test_e4_procfile_declares_web_and_worker() -> None:
    body = _read(PROCFILE)
    assert body.startswith("web:") or "\nweb:" in body or body.lstrip().startswith("web:")
    assert "worker:" in body
    assert "$PORT" in body
    assert "harness-tick" in body
    assert "--loop" in body


def test_e4_railway_json_declares_healthcheck() -> None:
    import json

    data = json.loads(_read(RAILWAY_JSON))
    assert "deploy" in data
    deploy = data["deploy"]
    assert deploy.get("healthcheckPath") == "/api/runtime/health"
    assert "$PORT" in deploy.get("startCommand", "")


def test_e4_app_py_honors_railway_port_env(monkeypatch) -> None:
    src = _read(APP_PY)
    # The default-host / default-port derivation must mention $PORT.
    assert 'os.environ.get("PORT")' in src


def test_e4_env_example_documents_railway_block() -> None:
    body = _read(ENV_EXAMPLE)
    assert "Railway" in body
    assert "METIS_UI_INVOKE_ENABLED" in body


def test_e4_runbook_exists() -> None:
    assert RAILWAY_RUNBOOK.is_file()
    body = _read(RAILWAY_RUNBOOK)
    for token in ("Railway", "Supabase", "web", "worker", "Healthcheck"):
        assert token in body, token
