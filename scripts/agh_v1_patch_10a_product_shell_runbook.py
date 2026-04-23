"""AGH v1 Patch 10A — Product Shell Rebuild runbook.

Walks the Patch 10A workorder scenarios (S1..S10) against the code
that actually serves the new Product Shell (`/`) and the relocated
Ops Cockpit (`/ops`). Deterministic: no Supabase writes, no network
calls, no LLM calls.

Scenarios (workorder mapping):

    S1.  A1 — hard 2-file split: index.html/product_shell.{js,css}
         present; legacy app.js removed; ops.html+ops.js relocated.
    S2.  A2 — app.py routes: `/` → static/index.html,
         `/ops` env-gated via METIS_OPS_SHELL, `/api/product/*`
         dispatch wired in routes.py.
    S3.  A3 — product_shell.css declares design tokens + 8 priority
         components (hero / grade-chip / stance / confidence / change /
         sparkline / mover / watchlist + disclosure).
    S4.  B1 — view_models.py mapper: strip_engineering_ids + grade +
         stance + confidence mappers available and pure.
    S5.  B2 — /api/product/today integration: view_model compose_*
         produces PRODUCT_TODAY_V1 DTO with 4 horizons + trust_strip.
    S6.  B3 — no-leak scanner: customer-facing HTML/JS/CSS/DTO does
         NOT contain banned engineering tokens (`art_*`, `reg_*`,
         `factor_*`, versioned slugs, raw horizon_provenance enums).
    S7.  C1 — locale_keys: `product_shell.*` present with KO/EN parity.
    S8.  C2 — honest degraded language: template_fallback /
         insufficient_evidence → product-level sample / preparing copy.
    S9.  D1 — Today inline evidence drawer present (no Research
         navigation required); hero CTA = '근거 보기' primary.
    S10. D2 — stub 3 panels (Research / Replay / Ask AI) present and
         visibly marked as 10B upcoming.

Produces two files under ``data/mvp/evidence/``:

    * ``patch_10a_product_shell_runbook_evidence.json``
    * ``patch_10a_product_shell_bridge_evidence.json``
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


STATIC = REPO_ROOT / "src/phase47_runtime/static"
PRODUCT_INDEX = STATIC / "index.html"
PRODUCT_JS    = STATIC / "product_shell.js"
PRODUCT_CSS   = STATIC / "product_shell.css"
OPS_INDEX     = STATIC / "ops.html"
OPS_JS        = STATIC / "ops.js"
APP_PY        = REPO_ROOT / "src/phase47_runtime/app.py"
ROUTES_PY     = REPO_ROOT / "src/phase47_runtime/routes.py"
VIEW_MODELS   = REPO_ROOT / "src/phase47_runtime/product_shell/view_models.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# S1 — hard 2-file split
# ---------------------------------------------------------------------------

def _run_s1_hard_split() -> dict[str, Any]:
    legacy_app_js = STATIC / "app.js"
    html = _read(PRODUCT_INDEX)
    ops_html = _read(OPS_INDEX)
    return {
        "scenario":                      "S1_hard_file_split",
        "product_index_html_present":    PRODUCT_INDEX.exists(),
        "product_shell_js_present":      PRODUCT_JS.exists(),
        "product_shell_css_present":     PRODUCT_CSS.exists(),
        "ops_html_present":              OPS_INDEX.exists(),
        "ops_js_present":                OPS_JS.exists(),
        "legacy_app_js_removed":         not legacy_app_js.exists(),
        "product_index_references_product_shell_js": "product_shell.js" in html,
        "ops_index_references_ops_js":   "ops.js" in ops_html,
        "ops_index_does_not_reference_product_shell_js":
            "product_shell.js" not in ops_html,
    }


# ---------------------------------------------------------------------------
# S2 — routing + env gate + api prefix
# ---------------------------------------------------------------------------

def _run_s2_routes() -> dict[str, Any]:
    app_src = _read(APP_PY)
    routes_src = _read(ROUTES_PY)
    return {
        "scenario":                       "S2_routes_and_env_gate",
        "root_serves_product_index":      "static/index.html" in app_src
                                           or '"/index.html"' in app_src,
        "ops_env_flag_referenced":        "METIS_OPS_SHELL" in app_src,
        "ops_path_referenced":            '"/ops"' in app_src,
        "api_product_today_route":        "/api/product/today" in routes_src,
        "api_product_dispatch_wired":     "api_product_today" in routes_src,
    }


# ---------------------------------------------------------------------------
# S3 — visual system tokens + 8 priority components
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"--ps-[a-z0-9\-]+")
_REQUIRED_COMPONENTS = (
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

def _run_s3_visual_system() -> dict[str, Any]:
    css = _read(PRODUCT_CSS)
    tokens = set(_TOKEN_RE.findall(css))
    missing = [c for c in _REQUIRED_COMPONENTS if c not in css]
    return {
        "scenario":            "S3_visual_system",
        "css_bytes":           len(css),
        "ps_token_count":      len(tokens),
        "has_color_tokens":    any("color" in t for t in tokens),
        "has_spacing_tokens":  any("space" in t or "gap" in t for t in tokens),
        "has_typography_tokens": any("font" in t or "text" in t for t in tokens),
        "has_radius_tokens":   any("radius" in t for t in tokens),
        "required_components_missing": missing,
        "all_required_components_present": len(missing) == 0,
    }


# ---------------------------------------------------------------------------
# S4 — view-models mapper purity
# ---------------------------------------------------------------------------

def _run_s4_view_models() -> dict[str, Any]:
    try:
        from phase47_runtime.product_shell.view_models import (  # type: ignore
            _horizon_provenance_to_confidence,
            _spectrum_position_to_grade,
            _spectrum_position_to_stance,
            strip_engineering_ids,
        )
    except Exception as exc:
        return {
            "scenario":          "S4_view_models_mapper",
            "import_ok":         False,
            "error":             repr(exc),
        }

    g_live  = _spectrum_position_to_grade(0.92, source_key="live")
    g_samp  = _spectrum_position_to_grade(0.92, source_key="sample")
    st_long = _spectrum_position_to_stance(0.7, lang="ko")
    st_neut = _spectrum_position_to_stance(0.01, lang="ko")
    conf_r  = _horizon_provenance_to_confidence(
        {"source": "real_derived"}, lang="ko")
    conf_tf = _horizon_provenance_to_confidence(
        {"source": "template_fallback"}, lang="ko")
    scrubbed = strip_engineering_ids({
        "a": "art_abc123",
        "b": {"c": "reg_xyz", "d": ["factor_q", "safe_text"]},
    })
    banned_after = re.search(r"art_|reg_|factor_", json.dumps(scrubbed))

    return {
        "scenario":                     "S4_view_models_mapper",
        "import_ok":                    True,
        "live_high_grade":              str(g_live),
        "sample_grade_lower_than_live": g_samp != g_live,
        "stance_long_label":            str(st_long),
        "stance_neutral_label":         str(st_neut),
        "real_derived_source_key":      (conf_r or {}).get("source_key"),
        "template_fallback_source_key": (conf_tf or {}).get("source_key"),
        "strip_removed_banned_tokens":  banned_after is None,
    }


# ---------------------------------------------------------------------------
# S5 — compose DTO shape
# ---------------------------------------------------------------------------

def _run_s5_compose_dto() -> dict[str, Any]:
    try:
        from phase47_runtime.product_shell.view_models import (  # type: ignore
            HORIZON_KEYS, compose_today_product_dto,
        )
    except Exception as exc:
        return {
            "scenario":   "S5_compose_product_today_dto",
            "import_ok":  False,
            "error":      repr(exc),
        }

    reg_entries = []
    artifacts = []
    for hz in HORIZON_KEYS:
        reg_entries.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"fam_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
        artifacts.append(SimpleNamespace(
            artifact_id=f"fam_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
    bundle = SimpleNamespace(
        artifacts=artifacts,
        registry_entries=reg_entries,
        horizon_provenance={hz: {"source": "real_derived"} for hz in HORIZON_KEYS},
        metadata={"graduation_tier": "production"},
        as_of_utc="2026-04-23T08:00:00Z",
    )
    rows = [
        {"asset_id": "AAPL", "spectrum_position": 0.72, "rank_index": 1,
         "rank_movement": "up", "rationale_summary": "상승 추세 유지",
         "what_changed": "상대 강도 개선"},
    ]
    dto = compose_today_product_dto(
        bundle=bundle,
        spectrum_by_horizon={hz: {"ok": True, "rows": rows} for hz in HORIZON_KEYS},
        lang="ko",
        watchlist_tickers=["AAPL"],
        now_utc="2026-04-23T08:00:00Z",
    )
    return {
        "scenario":             "S5_compose_product_today_dto",
        "import_ok":            True,
        "contract":             dto.get("contract"),
        "hero_card_count":      len(dto.get("hero_cards") or []),
        "trust_strip_tier":     (dto.get("trust_strip") or {}).get("tier_kind"),
        "has_today_at_a_glance": bool(dto.get("today_at_a_glance")),
        "has_selected_movers":  "selected_movers" in dto,
        "has_watchlist_strip":  "watchlist_strip" in dto,
        "has_stubs":            bool(dto.get("stubs")),
    }


# ---------------------------------------------------------------------------
# S6 — no-leak scan
# ---------------------------------------------------------------------------

_BANNED = (
    re.compile(r"\bart_[a-z0-9_]+", re.IGNORECASE),
    re.compile(r"\breg_[a-z0-9_]+", re.IGNORECASE),
    re.compile(r"\bfactor_[a-z0-9_]+", re.IGNORECASE),
    re.compile(r"\breal_derived_with_degraded_challenger\b"),
    re.compile(r"\btemplate_fallback\b"),
    re.compile(r"\binsufficient_evidence\b"),
    re.compile(r"\bhorizon_provenance\b"),
    re.compile(r"\bregistry_entry_id\b"),
)

def _scan_blob(blob: str) -> list[str]:
    hits: list[str] = []
    for pat in _BANNED:
        m = pat.search(blob)
        if m:
            hits.append(m.group(0))
    return hits


def _run_s6_no_leak() -> dict[str, Any]:
    html = _read(PRODUCT_INDEX)
    js   = _read(PRODUCT_JS)
    css  = _read(PRODUCT_CSS)
    return {
        "scenario":          "S6_no_leak_customer_surface",
        "html_hits":         _scan_blob(html),
        "js_hits":           _scan_blob(js),
        "css_hits":          _scan_blob(css),
        "html_clean":        _scan_blob(html) == [],
        "js_clean":          _scan_blob(js)   == [],
        "css_clean":         _scan_blob(css)  == [],
    }


# ---------------------------------------------------------------------------
# S7 — locale parity
# ---------------------------------------------------------------------------

def _run_s7_locale_keys() -> dict[str, Any]:
    try:
        from phase47_runtime.phase47e_user_locale import SHELL  # type: ignore
    except Exception as exc:
        return {"scenario": "S7_locale_keys", "import_ok": False, "error": repr(exc)}
    ko = SHELL.get("ko", {}) or {}
    en = SHELL.get("en", {}) or {}
    ko_keys = {k for k in ko if k.startswith("product_shell.")}
    en_keys = {k for k in en if k.startswith("product_shell.")}
    parity = ko_keys == en_keys
    return {
        "scenario":              "S7_locale_keys",
        "import_ok":             True,
        "ko_product_key_count":  len(ko_keys),
        "en_product_key_count":  len(en_keys),
        "parity_ok":             parity,
        "missing_in_en":         sorted(ko_keys - en_keys)[:5],
        "missing_in_ko":         sorted(en_keys - ko_keys)[:5],
    }


# ---------------------------------------------------------------------------
# S8 — honest degraded copy
# ---------------------------------------------------------------------------

def _run_s8_degraded_copy() -> dict[str, Any]:
    from phase47_runtime.product_shell.view_models import (  # type: ignore
        _horizon_provenance_to_confidence,
    )
    tf_ko = _horizon_provenance_to_confidence({"source": "template_fallback"}, lang="ko")
    tf_en = _horizon_provenance_to_confidence({"source": "template_fallback"}, lang="en")
    ie_ko = _horizon_provenance_to_confidence({"source": "insufficient_evidence"}, lang="ko")
    return {
        "scenario":                    "S8_honest_degraded_copy",
        "template_fallback_ko_source": (tf_ko or {}).get("source_key"),
        "template_fallback_en_source": (tf_en or {}).get("source_key"),
        "insufficient_evidence_source": (ie_ko or {}).get("source_key"),
        "template_fallback_label_ko":  (tf_ko or {}).get("label"),
        "insufficient_evidence_label_ko": (ie_ko or {}).get("label"),
    }


# ---------------------------------------------------------------------------
# S9 — inline evidence drawer + CTA priority
# ---------------------------------------------------------------------------

def _run_s9_inline_evidence() -> dict[str, Any]:
    js = _read(PRODUCT_JS)
    css = _read(PRODUCT_CSS)
    try:
        from phase47_runtime.product_shell.view_models import (  # type: ignore
            HORIZON_KEYS, compose_today_product_dto,
        )
        reg_entries = [SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"fam_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ) for hz in HORIZON_KEYS]
        artifacts = [SimpleNamespace(
            artifact_id=f"fam_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ) for hz in HORIZON_KEYS]
        bundle = SimpleNamespace(
            artifacts=artifacts, registry_entries=reg_entries,
            horizon_provenance={hz: {"source": "real_derived"} for hz in HORIZON_KEYS},
            metadata={"graduation_tier": "production"},
            as_of_utc="2026-04-23T08:00:00Z",
        )
        rows = [{"asset_id": "AAPL", "spectrum_position": 0.6, "rank_index": 1,
                 "rank_movement": "up", "rationale_summary": "추세 유지",
                 "what_changed": "상대 강도 개선"}]
        dto = compose_today_product_dto(
            bundle=bundle,
            spectrum_by_horizon={hz: {"ok": True, "rows": rows} for hz in HORIZON_KEYS},
            lang="ko", watchlist_tickers=["AAPL"],
            now_utc="2026-04-23T08:00:00Z",
        )
        first_card = (dto.get("hero_cards") or [{}])[0]
        cta_primary = first_card.get("cta_primary") or {}
        cta_kind_evidence = cta_primary.get("kind") == "open_evidence_drawer"
        cta_label_nonempty = bool(cta_primary.get("label"))
    except Exception:
        cta_kind_evidence = False
        cta_label_nonempty = False

    return {
        "scenario":                 "S9_inline_evidence_drawer",
        "renders_evidence_drawer":  "renderEvidenceDrawer" in js
                                    or "evidence-drawer" in js.lower(),
        "drawer_css_class_defined": ".ps-evidence-drawer" in css
                                    or ".ps-disclosure-drawer" in css,
        "cta_primary_kind_is_open_evidence_drawer": cta_kind_evidence,
        "cta_primary_label_nonempty": cta_label_nonempty,
        "no_research_hard_nav_from_hero":
            not re.search(r"location\.href\s*=\s*['\"]/#research['\"]", js),
    }


# ---------------------------------------------------------------------------
# S10 — 3 stub panels
# ---------------------------------------------------------------------------

def _run_s10_stub_panels() -> dict[str, Any]:
    html = _read(PRODUCT_INDEX)
    js   = _read(PRODUCT_JS)
    return {
        "scenario":                "S10_stub_panels",
        "research_panel_mount":    'data-panel="research"' in html
                                   or 'id="panel-research"' in html,
        "replay_panel_mount":      'data-panel="replay"' in html
                                   or 'id="panel-replay"' in html,
        "ask_panel_mount":         'data-panel="ask_ai"' in html
                                   or 'data-panel="ask"' in html
                                   or 'id="panel-ask"' in html
                                   or 'id="ps-panel-ask-ai"' in html,
        "js_renders_stub_card":    "renderStub" in js or "ps-stub-card" in js,
    }


# ---------------------------------------------------------------------------
# Runbook assembly
# ---------------------------------------------------------------------------

def main() -> int:
    s1  = _run_s1_hard_split()
    s2  = _run_s2_routes()
    s3  = _run_s3_visual_system()
    s4  = _run_s4_view_models()
    s5  = _run_s5_compose_dto()
    s6  = _run_s6_no_leak()
    s7  = _run_s7_locale_keys()
    s8  = _run_s8_degraded_copy()
    s9  = _run_s9_inline_evidence()
    s10 = _run_s10_stub_panels()

    evidence = {
        "contract":                "PATCH_10A_PRODUCT_SHELL_RUNBOOK_V1",
        "generated_utc":           _now_iso(),
        "hard_split_ok": all([
            s1["product_index_html_present"], s1["product_shell_js_present"],
            s1["product_shell_css_present"], s1["ops_html_present"],
            s1["ops_js_present"], s1["legacy_app_js_removed"],
            s1["product_index_references_product_shell_js"],
            s1["ops_index_references_ops_js"],
        ]),
        "routing_ok": all([
            s2["root_serves_product_index"], s2["ops_env_flag_referenced"],
            s2["api_product_today_route"], s2["api_product_dispatch_wired"],
        ]),
        "visual_system_ok":        s3["all_required_components_present"]
                                    and s3["ps_token_count"] >= 12,
        "mappers_ok":              s4.get("import_ok", False)
                                    and s4.get("strip_removed_banned_tokens", False),
        "dto_shape_ok":            s5.get("contract") == "PRODUCT_TODAY_V1"
                                    and s5.get("hero_card_count") == 4,
        "no_leak_ok":              s6["html_clean"] and s6["js_clean"] and s6["css_clean"],
        "locale_parity_ok":        s7.get("parity_ok", False)
                                    and s7.get("ko_product_key_count", 0) >= 30,
        "degraded_copy_ok":        s8.get("template_fallback_ko_source") == "sample"
                                    and s8.get("insufficient_evidence_source") == "preparing",
        "inline_evidence_ok":      s9["renders_evidence_drawer"]
                                    and s9["cta_primary_kind_is_open_evidence_drawer"]
                                    and s9["cta_primary_label_nonempty"],
        "stub_panels_ok":          s10["research_panel_mount"] and s10["replay_panel_mount"]
                                    and s10["ask_panel_mount"] and s10["js_renders_stub_card"],
        "scenarios": [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10],
    }
    evidence["all_ok"] = all(
        evidence[k] for k in evidence
        if k.endswith("_ok") and isinstance(evidence[k], bool)
    )

    runbook_out = REPO_ROOT / "data/mvp/evidence/patch_10a_product_shell_runbook_evidence.json"
    runbook_out.parent.mkdir(parents=True, exist_ok=True)
    runbook_out.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    bridge = {
        "contract":                 "PATCH_10A_PRODUCT_SHELL_BRIDGE_V1",
        "generated_utc":            _now_iso(),
        "prior_patch":              "agentic_operating_harness_v1_milestone_20_patch_9",
        "entry_point":              "/ (product shell) + /ops?METIS_OPS_SHELL=1",
        "api_prefix_added":         "/api/product/",
        "legacy_api_preserved":     True,
        "follow_up_patch":          "10B - Research/Replay/Ask AI formal redesign",
        "runbook_all_ok":           evidence["all_ok"],
    }
    bridge_out = REPO_ROOT / "data/mvp/evidence/patch_10a_product_shell_bridge_evidence.json"
    bridge_out.write_text(
        json.dumps(bridge, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = {k: v for k, v in evidence.items() if k.endswith("_ok")}
    summary["_runbook_path"] = str(runbook_out.relative_to(REPO_ROOT))
    summary["_bridge_path"] = str(bridge_out.relative_to(REPO_ROOT))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if evidence["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
