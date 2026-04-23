"""AGH v1 Patch 6 — UI renderer surface assertions (B1/B3/C1/C2).

Pytest cannot execute the vanilla-JS SPA renderer, but we can still
lock in the structural contract that the renderer must exist and wire
into the product surface:

  * B1: the 4-block Today layout helpers are present
    (``renderTodaySummaryRailHtml`` / ``renderTodayPrimaryPanelHtml`` /
    ``renderTodayDecisionStackHtml`` / ``renderTodayEvidenceStripHtml``).
  * B1: ``renderTodayObjectDetailHtml`` composes the 4 blocks in order.
  * B2: ``renderResearchStructuredSection`` reads ``research_structured_v1``
    and emits the 5-section structure.
  * B3: ``hydrateReplayGovernanceLineageCompact`` hits
    ``/api/replay/governance-lineage`` and renders step indicators.
  * C1: ``renderReplayTimelinePlotSvg`` exists and emits an inline
    ``<svg class="tsr-timeline-plot">``.
  * C2: ``tsrInstallTooltip`` installs ``window.tooltipAt`` /
    ``window.tooltipHide``.
  * ``styles.css`` block (embedded in index.html) declares the ``tsr-*``
    primitives used by all renderers + honors reduced motion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_JS = REPO_ROOT / "src" / "phase47_runtime" / "static" / "ops.js"
INDEX_HTML = REPO_ROOT / "src" / "phase47_runtime" / "static" / "ops.html"


@pytest.fixture(scope="module")
def app_js_src() -> str:
    return APP_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def index_html_src() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# B1 — Today 4-block renderer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fn_name",
    [
        "renderTodaySummaryRailHtml",
        "renderTodayPrimaryPanelHtml",
        "renderTodayDecisionStackHtml",
        "renderTodayEvidenceStripHtml",
        "renderTodayObjectDetailHtml",
    ],
)
def test_today_4block_helpers_present(app_js_src: str, fn_name: str) -> None:
    assert f"function {fn_name}(" in app_js_src, (
        f"B1: {fn_name} missing from app.js"
    )


def test_today_object_detail_composes_4_blocks_in_order(app_js_src: str) -> None:
    idx = app_js_src.find("function renderTodayObjectDetailHtml(")
    assert idx > 0
    body = app_js_src[idx : idx + 4000]
    order = [
        "renderTodaySummaryRailHtml",
        "renderTodayPrimaryPanelHtml",
        "renderTodayDecisionStackHtml",
        "renderTodayEvidenceStripHtml",
    ]
    positions = [body.find(tok) for tok in order]
    assert all(p > 0 for p in positions), positions
    assert positions == sorted(positions), (
        f"B1 block order broken: {list(zip(order, positions))}"
    )


# ---------------------------------------------------------------------------
# B2 — Research 5-section renderer
# ---------------------------------------------------------------------------


def test_research_structured_section_reads_payload(app_js_src: str) -> None:
    assert "function renderResearchStructuredSection(" in app_js_src
    assert "research_structured_v1" in app_js_src
    for sec in (
        "current_read",
        "why_plausible",
        "unproven",
        "watch",
        "bounded_next",
    ):
        assert f'data-tsr-sec="{sec}"' in app_js_src, f"B2 missing section {sec}"


def test_research_locale_coverage_badge_present(app_js_src: str) -> None:
    assert "tsr-research-coverage" in app_js_src
    for cov in ("dual", "ko_only", "en_only", "degraded"):
        assert cov in app_js_src


# ---------------------------------------------------------------------------
# B3 — Replay governance lineage compact
# ---------------------------------------------------------------------------


def test_replay_governance_lineage_hydrator_uses_api(app_js_src: str) -> None:
    assert "function hydrateReplayGovernanceLineageCompact(" in app_js_src
    assert "/api/replay/governance-lineage" in app_js_src
    assert "tsr-step-indicator" in app_js_src


# ---------------------------------------------------------------------------
# C1 — Replay timeline SVG plot
# ---------------------------------------------------------------------------


def test_replay_timeline_plot_emits_inline_svg(app_js_src: str) -> None:
    assert "function renderReplayTimelinePlotSvg(" in app_js_src
    assert '<svg class="tsr-timeline-plot"' in app_js_src
    assert "plot-govern-apply" in app_js_src
    assert "plot-sandbox-tick" in app_js_src


# ---------------------------------------------------------------------------
# C2 — Tooltip primitive
# ---------------------------------------------------------------------------


def test_tooltip_primitive_installs_globals(app_js_src: str) -> None:
    assert "function tsrInstallTooltip(" in app_js_src or "tsrInstallTooltip" in app_js_src
    assert "window.tooltipAt" in app_js_src
    assert "window.tooltipHide" in app_js_src
    assert "data-tsr-tt-label" in app_js_src


# ---------------------------------------------------------------------------
# E2 — UI enqueue + copy CLI click handlers
# ---------------------------------------------------------------------------


def test_ui_enqueue_and_copy_cli_wire_to_endpoint(app_js_src: str) -> None:
    assert "data-tsr-copy-cli" in app_js_src
    assert "data-tsr-enqueue-sandbox" in app_js_src
    assert "/api/sandbox/enqueue" in app_js_src


# ---------------------------------------------------------------------------
# B4 — progressive disclosure CSS + reduced motion + premium empty state
# ---------------------------------------------------------------------------


def test_index_html_has_tsr_primitives_and_reduced_motion(index_html_src: str) -> None:
    # TSR CSS primitives live in the embedded style block of index.html.
    for cls in (
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
    ):
        assert cls in index_html_src, f"missing CSS primitive {cls}"
    assert "prefers-reduced-motion" in index_html_src, (
        "B4: must honor prefers-reduced-motion"
    )
