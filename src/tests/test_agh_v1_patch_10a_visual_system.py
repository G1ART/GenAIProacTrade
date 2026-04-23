"""Patch 10A — Product Shell visual system surface tests.

Light-weight, source-level assertions that the 8 priority components and
the design-token contract established in ``static/product_shell.css``
are present and reachable by the Product Shell JS renderer.

The scope is intentionally narrow — we do NOT assert rendered pixel
fidelity (that would require headless browser harness). We assert the
*surface contract* that a future visual regression harness or a hand-off
to a designer can rely on.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CSS = _REPO_ROOT / "src" / "phase47_runtime" / "static" / "product_shell.css"
_JS = _REPO_ROOT / "src" / "phase47_runtime" / "static" / "product_shell.js"
_HTML = _REPO_ROOT / "src" / "phase47_runtime" / "static" / "index.html"


def _css_text() -> str:
    assert _CSS.is_file(), "product_shell.css missing"
    return _CSS.read_text(encoding="utf-8")


def _js_text() -> str:
    assert _JS.is_file(), "product_shell.js missing"
    return _JS.read_text(encoding="utf-8")


def _html_text() -> str:
    assert _HTML.is_file(), "Product Shell index.html missing"
    return _HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------


def test_design_tokens_color_surfaces_declared():
    txt = _css_text()
    for tok in ("--ps-bg:", "--ps-surface-1:", "--ps-surface-2:", "--ps-surface-3:",
                "--ps-border-muted:", "--ps-border-strong:"):
        assert tok in txt, f"design token missing: {tok}"


def test_design_tokens_text_and_semantic_colors_declared():
    txt = _css_text()
    for tok in ("--ps-text-primary:", "--ps-text-secondary:", "--ps-text-tertiary:",
                "--ps-accent-up:", "--ps-accent-down:",
                "--ps-semantic-warn:", "--ps-semantic-sample:"):
        assert tok in txt, f"design token missing: {tok}"


def test_design_tokens_spacing_and_radius_scale():
    txt = _css_text()
    for tok in ("--ps-sp-2:", "--ps-sp-4:", "--ps-sp-6:", "--ps-sp-8:",
                "--ps-radius-sm:", "--ps-radius-md:", "--ps-radius-lg:"):
        assert tok in txt, f"scale token missing: {tok}"


def test_design_tokens_typography_scale():
    txt = _css_text()
    for tok in ("--ps-fs-caption:", "--ps-fs-small:", "--ps-fs-body:",
                "--ps-fs-h3:", "--ps-fs-h2:", "--ps-fs-h1:"):
        assert tok in txt, f"typography token missing: {tok}"


# ---------------------------------------------------------------------------
# 8 priority components
# ---------------------------------------------------------------------------


_PRIORITY_COMPONENTS: tuple[str, ...] = (
    ".ps-hero-card",
    ".ps-grade-chip",
    ".ps-stance-label",
    ".ps-confidence-badge",
    ".ps-change-bullet",
    ".ps-mini-sparkline",
    ".ps-mover-card",
    ".ps-watchlist-chip",
    ".ps-disclosure-drawer",
)


def test_priority_components_declared_in_css():
    txt = _css_text()
    for sel in _PRIORITY_COMPONENTS:
        assert sel in txt, f"priority component missing in css: {sel}"


def test_grade_chip_has_per_grade_variants():
    txt = _css_text()
    for grade in ("a_plus", "a", "b", "c", "d", "f"):
        assert f'.ps-grade-chip[data-grade="{grade}"]' in txt, (
            f"grade chip variant missing: {grade}"
        )


def test_stance_label_has_per_direction_variants():
    txt = _css_text()
    for stance in ("strong_long", "long", "neutral", "short", "strong_short"):
        assert f'.ps-stance-label[data-stance="{stance}"]' in txt, (
            f"stance label variant missing: {stance}"
        )


def test_confidence_badge_uses_product_taxonomy_not_raw_enums():
    txt = _css_text()
    # Must target product-level source keys.
    for src in ("live", "live_with_caveat", "sample", "preparing"):
        assert f'.ps-confidence-badge[data-source="{src}"]' in txt, (
            f"confidence badge variant missing: {src}"
        )
    # Must NOT use raw engineering enum values.
    for banned in ("real_derived", "template_fallback", "insufficient_evidence"):
        assert f'data-source="{banned}"' not in txt


def test_tier_chip_has_three_kinds():
    txt = _css_text()
    for tier in ("production", "sample", "degraded"):
        assert f'.ps-tier-chip[data-tier="{tier}"]' in txt, (
            f"trust strip tier chip variant missing: {tier}"
        )


# ---------------------------------------------------------------------------
# JS surface expectations
# ---------------------------------------------------------------------------


def test_js_exposes_renderAll_and_fetch_hooks():
    txt = _js_text()
    assert "window.__PS__" in txt, "regression hook missing"
    assert "renderAll" in txt
    assert "fetchTodayDto" in txt


def test_js_uses_product_today_endpoint_only():
    txt = _js_text()
    assert "/api/product/today" in txt
    # Must NOT call the legacy Ops endpoints from the Product Shell.
    for banned in ("/api/today/spectrum", "/api/overview", "/api/home/feed"):
        assert banned not in txt, f"Product Shell must not call ops endpoint {banned}"


def test_js_renders_hero_grade_chip_and_stance_label():
    txt = _js_text()
    # Stance + grade chips must both be emitted per hero card.
    assert "ps-grade-chip" in txt and "ps-stance-label" in txt
    assert "ps-confidence-badge" in txt


def test_js_renders_mini_sparkline_svg():
    txt = _js_text()
    assert "renderSparkline" in txt
    assert "ps-mini-sparkline" in txt
    assert "<svg" in txt and "viewBox" in txt


def test_html_shell_references_external_css_and_js():
    txt = _html_text()
    assert '/static/product_shell.css' in txt
    assert '/static/product_shell.js' in txt


def test_html_shell_has_four_panel_mount_points():
    txt = _html_text()
    for panel in ("ps-panel-today", "ps-panel-research", "ps-panel-replay", "ps-panel-ask-ai"):
        assert f'id="{panel}"' in txt, f"panel mount point missing: {panel}"


def test_html_shell_has_trust_strip_and_nav_mount():
    txt = _html_text()
    assert 'id="ps-trust-strip"' in txt
    assert 'id="ps-nav"' in txt
    assert 'id="ps-lang-toggle"' in txt
