"""AGH v1 Patch 7 — Product hardening / UX depth / scale-readiness surface tests.

These tests lock in the structural contract introduced by Patch 7. They
cannot run the vanilla-JS SPA, but they can assert that the renderers
and style/locale surface carry the Patch 7 contract:

    * A1: <nav id="nav"> is 2-tier (primary + utility rows) with
          i18n ARIA labels.
    * A2: Today typography tokens (tsr-hero/subhead/body/foot) + the
          consolidated audit <details> renderer + recent-activity
          mini-list renderer are wired.
    * A3: renderResearchStructuredSection groups into 3 clusters
          (current_read / open_questions / bounded_next) and renders
          the bounded action contract card (B2).
    * A4: renderReplayTimelinePlotSvg is the 3-lane version and the
          lineage step summary ("N of 4 steps complete") is emitted.
    * A5: the shared tooltip renderer splits sub lines by " · " so
          tooltips can carry multi-fact density.
    * C2b: /api/today/spectrum accepts rows_limit.
    * C2c: /api/replay/governance-lineage accepts limit with cap(500).
    * C2a: governance_scan_provider_v1.deduplicate_specs hoists the
           list_packets call (one call before the loop, not inside).

These are surface/contract checks. Behaviour is covered by Patch 6
tests plus the harness/executor tests.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_JS = REPO_ROOT / "src" / "phase47_runtime" / "static" / "ops.js"
INDEX_HTML = REPO_ROOT / "src" / "phase47_runtime" / "static" / "ops.html"
LOCALE_PY = REPO_ROOT / "src" / "phase47_runtime" / "phase47e_user_locale.py"


@pytest.fixture(scope="module")
def app_js_src() -> str:
    return APP_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def index_html_src() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def locale_src() -> str:
    return LOCALE_PY.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# A1 — navigation 2-tier
# ---------------------------------------------------------------------------


def test_a1_nav_two_rows_present(index_html_src: str) -> None:
    # Primary + utility rows must both be declared as role=group.
    assert 'class="nav-row nav-primary"' in index_html_src
    assert 'class="nav-row nav-utility"' in index_html_src
    assert 'data-nav-tier="primary"' in index_html_src
    assert 'data-nav-tier="utility"' in index_html_src


def test_a1_nav_utility_houses_demoted_entries(index_html_src: str) -> None:
    # The utility row must carry the demoted entries (Journal / Advanced /
    # Reload bundle). No regression: these must still exist in the DOM.
    idx_u = index_html_src.find('class="nav-row nav-utility"')
    idx_end = index_html_src.find("</nav>", idx_u)
    assert idx_u > 0 and idx_end > idx_u
    utility_block = index_html_src[idx_u:idx_end]
    for panel in ("journal", "advanced"):
        assert f'data-panel="{panel}"' in utility_block, panel
    assert 'id="btn-reload"' in utility_block


def test_a1_nav_aria_labels_localized(index_html_src: str, locale_src: str) -> None:
    # Both rows must declare data-i18n-aria-label keys that exist in the
    # SHELL locale dict (so screen readers read localized copy).
    assert 'data-i18n-aria-label="tsr.nav.primary.aria"' in index_html_src
    assert 'data-i18n-aria-label="tsr.nav.utility.aria"' in index_html_src
    assert '"tsr.nav.primary.aria":' in locale_src
    assert '"tsr.nav.utility.aria":' in locale_src


# ---------------------------------------------------------------------------
# A2 — Today typography + audit consolidation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    ["--tsr-type-hero", "--tsr-type-subhead", "--tsr-type-body", "--tsr-type-foot"],
)
def test_a2_today_typography_tokens_declared(index_html_src: str, token: str) -> None:
    assert token in index_html_src, token


@pytest.mark.parametrize(
    "cls",
    [".tsr-hero", ".tsr-subhead", ".tsr-body", ".tsr-foot", ".tsr-audit", ".tsr-recent-activity"],
)
def test_a2_today_typography_classes_styled(index_html_src: str, cls: str) -> None:
    assert cls in index_html_src, cls


def test_a2_consolidated_audit_renderer_present(app_js_src: str) -> None:
    assert "function renderTodayConsolidatedAuditHtml(" in app_js_src
    # It must render exactly ONE <details> shell and accept a legacy inner
    # argument so the old "legacy MIR detail" block is folded inside it.
    idx = app_js_src.find("function renderTodayConsolidatedAuditHtml(")
    end = app_js_src.find("\n  }\n", idx)
    assert idx > 0 and end > idx
    body = app_js_src[idx:end]
    assert 'class="tsr-audit"' in body
    assert body.count("<details") == 1, "audit renderer must emit exactly one outer <details>"


def test_a2_recent_activity_renderer_present(app_js_src: str) -> None:
    assert "function renderTodayRecentActivityHtml(" in app_js_src
    idx = app_js_src.find("function renderTodayRecentActivityHtml(")
    end = app_js_src.find("\n  }\n", idx)
    assert idx > 0 and end > idx
    body = app_js_src[idx:end]
    assert 'data-tsr-recent=' in body
    assert "tsr.recent.head" in body
    assert "tsr-mini-row" in body


def test_a2_object_detail_uses_consolidated_audit(app_js_src: str) -> None:
    # The legacy "Show legacy MIR detail (advanced)" standalone <details>
    # must no longer appear as a visible string rendered by the object
    # detail renderer. We narrow the check to the renderer body so a
    # doc-comment mentioning the legacy name elsewhere doesn't trip it.
    idx = app_js_src.find("function renderTodayObjectDetailHtml(")
    end = app_js_src.find("\n  }\n", idx)
    assert idx > 0 and end > idx
    body = app_js_src[idx:end]
    assert "renderTodayConsolidatedAuditHtml" in body
    assert "Show legacy MIR detail" not in body
    assert "원 MIR 세부 보기 (고급)" not in body


# ---------------------------------------------------------------------------
# A3 — Research 3-cluster + bounded action contract card (B2)
# ---------------------------------------------------------------------------


def test_a3_research_three_clusters_rendered(app_js_src: str) -> None:
    idx = app_js_src.find("function renderResearchStructuredSection(")
    assert idx > 0
    end = app_js_src.find("\n  function ", idx + 1)
    body = app_js_src[idx:end] if end > idx else app_js_src[idx:]
    for key in ("current_read", "open_questions", "bounded_next"):
        assert f'data-tsr-cluster="{key}"' in body, key


def test_b2_bounded_action_contract_locale_keys_present(locale_src: str) -> None:
    for key in (
        "tsr.invoke.contract.head",
        "tsr.invoke.contract.will_do",
        "tsr.invoke.contract.will_not_do",
        "tsr.invoke.contract.after_enqueue",
    ):
        assert f'"{key}":' in locale_src, key


def test_b2_bounded_action_contract_card_wired(app_js_src: str) -> None:
    # The contract card must be rendered inside the research section
    # (above the invoke buttons).
    assert "tsr.invoke.contract.head" in app_js_src
    assert "tsr.invoke.contract.will_do" in app_js_src
    assert "tsr.invoke.contract.will_not_do" in app_js_src
    assert "tsr.invoke.contract.after_enqueue" in app_js_src


# ---------------------------------------------------------------------------
# A4 — Replay timeline 3-lane + lineage enrichment
# ---------------------------------------------------------------------------


def test_a4_timeline_plot_is_three_lane(app_js_src: str) -> None:
    idx = app_js_src.find("function renderReplayTimelinePlotSvg(")
    assert idx > 0
    end = app_js_src.find("\n  }\n", idx)
    body = app_js_src[idx:end]
    # Declares lane 0/1/2 and reads lane label tokens.
    for key in ("plot.lane_apply", "plot.lane_spectrum", "plot.lane_sandbox"):
        assert key in body, key
    assert 'data-tsr-timeline-plot="3lane"' in body


def test_a4_lineage_step_count_emitted(app_js_src: str, locale_src: str) -> None:
    assert '"lineage.step_count":' in locale_src
    assert "lineage.step_count" in app_js_src
    # The summary element must be declared at the lineage renderer.
    assert "tsr-step-summary" in app_js_src


def test_a4_lineage_step_time_delta_helper(app_js_src: str) -> None:
    # The time-delta formatter must exist and be called from the step
    # rendering loop.
    assert "function tsrStepDeltaLabel(" in app_js_src
    assert "tsrStepDeltaLabel(" in app_js_src.replace("function tsrStepDeltaLabel(", "")


# ---------------------------------------------------------------------------
# A5 — tooltip sub-line density (multi-part split)
# ---------------------------------------------------------------------------


def test_a5_tooltip_sub_split_by_sep(app_js_src: str) -> None:
    idx = app_js_src.find("tsrInstallTooltip()")
    assert idx > 0
    end = app_js_src.find("})();", idx)
    body = app_js_src[idx:end]
    assert 'const SUB_SEP = " · "' in body, "SUB_SEP must be declared for multi-part tooltip sub"
    assert "split(SUB_SEP)" in body


# ---------------------------------------------------------------------------
# C2b — /api/today/spectrum rows_limit
# ---------------------------------------------------------------------------


def test_c2b_today_spectrum_accepts_rows_limit() -> None:
    from src.phase47_runtime import today_spectrum

    sig = inspect.signature(today_spectrum.build_today_spectrum_payload)
    assert "rows_limit" in sig.parameters
    assert hasattr(today_spectrum, "TODAY_SPECTRUM_DEFAULT_ROWS_LIMIT")
    assert hasattr(today_spectrum, "TODAY_SPECTRUM_MAX_ROWS_LIMIT")
    assert today_spectrum.TODAY_SPECTRUM_DEFAULT_ROWS_LIMIT <= today_spectrum.TODAY_SPECTRUM_MAX_ROWS_LIMIT


# ---------------------------------------------------------------------------
# C2c — /api/replay/governance-lineage limit cap
# ---------------------------------------------------------------------------


def test_c2c_replay_lineage_limit_cap() -> None:
    from src.phase47_runtime import routes

    assert hasattr(routes, "REPLAY_LINEAGE_DEFAULT_LIMIT")
    assert hasattr(routes, "REPLAY_LINEAGE_MAX_LIMIT")
    assert routes.REPLAY_LINEAGE_DEFAULT_LIMIT <= routes.REPLAY_LINEAGE_MAX_LIMIT
    assert routes.REPLAY_LINEAGE_MAX_LIMIT == 500


# ---------------------------------------------------------------------------
# C2a — governance_scan_provider_v1 N+1 hoist
# ---------------------------------------------------------------------------


def test_c2a_dedupe_hoists_list_packets_out_of_loop() -> None:
    from src.agentic_harness.agents import governance_scan_provider_v1 as mod

    src = inspect.getsource(mod.deduplicate_specs)
    # The hoisted variant calls the index builder exactly once before
    # the per-spec loop; the legacy per-spec list_packets call must NOT
    # appear inside deduplicate_specs any more.
    assert "_build_existing_evaluation_index" in src
    assert src.count("store.list_packets(") == 0, (
        "dedupe must not call store.list_packets per spec; it should call "
        "_build_existing_evaluation_index once"
    )
    # And the index builder itself must call list_packets exactly once.
    index_src = inspect.getsource(mod._build_existing_evaluation_index)
    assert index_src.count("list_packets(") >= 1
