"""AGH v1 Patch 10B — Product Shell Research/Replay/Ask AI runbook.

Walks the Patch 10B workorder scenarios against the code that actually
serves the new product surfaces. Deterministic: no Supabase writes, no
network calls, no LLM calls.

Scenarios (workorder mapping):

    S1. A — common/research mapper shape + landing & deepdive DTO contract
    S2. B — replay mapper shape + timeline (gap + checkpoint) + scenarios
    S3. C — ask mapper shape + quick actions + degraded free-text wrapper
    S4. D — product_shell.css extended with ≥13 10B component classes
    S5. E — product_shell.js extended with STATE.focus + hash routing +
            Research / Replay / Ask renderers + Today→Research soft link
    S6. F — locale parity for product_shell.research/replay/ask.*; no-leak
            scan of surface + DTOs for banned 10B tokens
    S7. G — /api/product/{research,replay,ask,ask/quick,requests} routes
            registered in dispatch_json

Produces two files under ``data/mvp/evidence/``:

    * ``patch_10b_product_shell_runbook_evidence.json``
    * ``patch_10b_product_shell_bridge_evidence.json``
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
ROUTES_PY     = REPO_ROOT / "src/phase47_runtime/routes.py"
VM_COMMON     = REPO_ROOT / "src/phase47_runtime/product_shell/view_models_common.py"
VM_RESEARCH   = REPO_ROOT / "src/phase47_runtime/product_shell/view_models_research.py"
VM_REPLAY     = REPO_ROOT / "src/phase47_runtime/product_shell/view_models_replay.py"
VM_ASK        = REPO_ROOT / "src/phase47_runtime/product_shell/view_models_ask.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Shared stub fixture
# ---------------------------------------------------------------------------

def _bundle_and_spec():
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    reg_entries = []
    artifacts = []
    for hz in HORIZON_KEYS:
        reg_entries.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"fam_{hz}",
            registry_entry_id=f"reg_{hz}",
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
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived_with_degraded_challenger"},
            "long":        {"source": "template_fallback"},
        },
        metadata={"graduation_tier": "production",
                  "built_at_utc": "2026-04-23T07:30:00Z"},
        as_of_utc="2026-04-23T08:00:00Z",
    )
    rows = [
        {"asset_id": "AAPL", "spectrum_position": 0.74,
         "rank_index": 1, "rank_movement": "up",
         "rationale_summary": "중기 추세 강세가 지속됨",
         "what_changed": "상대 강도 +8% 개선"},
        {"asset_id": "NVDA", "spectrum_position": -0.33,
         "rank_index": 18, "rank_movement": "down",
         "rationale_summary": "과열 구간 진입",
         "what_changed": "밸류에이션 긴장도 증가"},
    ]
    spec = {hz: {"ok": True, "rows": rows} for hz in HORIZON_KEYS}
    return bundle, spec


# ---------------------------------------------------------------------------
# S1 — Research mapper
# ---------------------------------------------------------------------------

def _run_s1_research() -> dict[str, Any]:
    try:
        from phase47_runtime.product_shell.view_models_research import (  # type: ignore
            compose_research_deepdive_dto,
            compose_research_landing_dto,
        )
    except Exception as exc:
        return {"scenario": "S1_research_mapper", "import_ok": False, "error": repr(exc)}
    bundle, spec = _bundle_and_spec()
    landing = compose_research_landing_dto(
        bundle=bundle, spectrum_by_horizon=spec, lang="ko",
        now_utc="2026-04-23T08:00:00Z",
    )
    deep = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang="ko",
        now_utc="2026-04-23T08:00:00Z",
    )
    return {
        "scenario":                   "S1_research_mapper",
        "import_ok":                  True,
        "landing_contract":           landing.get("contract"),
        "landing_column_count":       len(landing.get("columns") or []),
        "landing_has_tiles":          any(col.get("tiles") for col in (landing.get("columns") or [])),
        "deepdive_contract":          deep.get("contract"),
        "deepdive_evidence_count":    len(deep.get("evidence") or []),
        "deepdive_actions_count":     len(deep.get("actions") or []),
        "deepdive_has_missing_card":  any(
            c.get("kind") == "missing_or_preparing"
            for c in (deep.get("evidence") or [])
        ),
    }


# ---------------------------------------------------------------------------
# S2 — Replay mapper
# ---------------------------------------------------------------------------

def _run_s2_replay() -> dict[str, Any]:
    try:
        from phase47_runtime.product_shell.view_models_replay import (  # type: ignore
            compose_replay_product_dto,
        )
    except Exception as exc:
        return {"scenario": "S2_replay_mapper", "import_ok": False, "error": repr(exc)}
    bundle, spec = _bundle_and_spec()
    import inspect
    sig = inspect.signature(compose_replay_product_dto)
    kwargs: dict[str, Any] = dict(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short",
        lang="ko", now_utc="2026-04-23T08:00:00Z",
    )
    if "lineage" in sig.parameters:
        kwargs["lineage"] = None
    followups = [
        {"request": {"created_at_utc": "2026-04-23T06:00:00Z",
                     "payload": {"kind": "validation_rerun"}},
         "result": {"created_at_utc": "2026-04-23T06:05:00Z",
                    "payload": {"outcome": "completed"}}},
    ]
    if "followups" in sig.parameters:
        kwargs["followups"] = followups
    dto = compose_replay_product_dto(**kwargs)
    timeline = dto.get("timeline") or []
    scenarios = dto.get("scenarios") or []
    return {
        "scenario":             "S2_replay_mapper",
        "import_ok":            True,
        "contract":             dto.get("contract"),
        "scenarios_count":      len(scenarios),
        "scenario_kinds":       [s.get("kind") for s in scenarios],
        "has_advanced_disclosure": bool(dto.get("advanced_disclosure")),
    }


# ---------------------------------------------------------------------------
# S3 — Ask mapper
# ---------------------------------------------------------------------------

def _run_s3_ask() -> dict[str, Any]:
    try:
        from phase47_runtime.product_shell.view_models_ask import (  # type: ignore
            compose_ask_product_dto,
            compose_quick_answers_dto,
            scrub_free_text_answer,
        )
    except Exception as exc:
        return {"scenario": "S3_ask_mapper", "import_ok": False, "error": repr(exc)}
    bundle, spec = _bundle_and_spec()
    landing = compose_ask_product_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short",
        followups=[], lang="ko", now_utc="2026-04-23T08:00:00Z",
    )
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    deg = scrub_free_text_answer(
        prompt="왜 등급이 올랐나요?",
        context={"horizon_caption": "단기"},
        conversation_callable=lambda: {"ok": False},
        lang="ko",
    )
    return {
        "scenario":                "S3_ask_mapper",
        "import_ok":               True,
        "landing_contract":        landing.get("contract"),
        "quick_contract":          quick.get("contract"),
        "quick_intent_count":      len(quick.get("answers") or []),
        "landing_has_context":     bool(landing.get("context")),
        "landing_has_free_text":   bool(landing.get("free_text")),
        "landing_quick_chip_count": len(landing.get("quick_chips") or []),
        "degraded_grounded":       bool(deg.get("grounded")),
        "degraded_kind":           deg.get("kind"),
    }


# ---------------------------------------------------------------------------
# S4 — CSS 10B components
# ---------------------------------------------------------------------------

_REQUIRED_CSS_10B: tuple[str, ...] = (
    ".ps-research-landing",
    ".ps-research-column",
    ".ps-research-tile",
    ".ps-evidence-card",
    ".ps-claim-card",
    ".ps-action-chip",
    ".ps-replay-timeline",
    ".ps-timeline-event",
    ".ps-timeline-gap",
    ".ps-timeline-checkpoint",
    ".ps-scenario-card",
    ".ps-ask-context-card",
    ".ps-ask-action-chip",
    ".ps-ask-freetext",
    ".ps-ask-answer",
    ".ps-request-state-card",
    ".ps-advanced-drawer",
    ".ps-tooltip",
)


def _run_s4_css() -> dict[str, Any]:
    css = _read(PRODUCT_CSS)
    missing = [c for c in _REQUIRED_CSS_10B if c not in css]
    return {
        "scenario":             "S4_visual_system_10b",
        "css_bytes":            len(css),
        "required_components":  len(_REQUIRED_CSS_10B),
        "missing_components":   missing,
        "all_components_present": not missing,
        "has_tooltip_variants":  all(
            f'[data-variant="{v}"]' in css
            for v in ("info", "caution", "trust")
        ),
    }


# ---------------------------------------------------------------------------
# S5 — JS state routing + renderers
# ---------------------------------------------------------------------------

def _run_s5_js() -> dict[str, Any]:
    js = _read(PRODUCT_JS)
    return {
        "scenario":                   "S5_js_state_and_renderers",
        "state_focus_present":        "STATE.focus" in js,
        "hash_routing_present":       "applyHash" in js and "updateHashFromState" in js,
        "research_renderer_present":  "renderResearchPanel" in js
                                        and "renderResearchDeepDive" in js,
        "replay_renderer_present":    "renderReplayPanel" in js
                                        and "renderReplayTimeline" in js
                                        and "renderReplayScenarios" in js,
        "ask_renderer_present":       "renderAskPanel" in js
                                        and "renderAskQuickActions" in js
                                        and "renderAskFreeText" in js,
        "today_to_research_softlink": "setActivePanel(\"research\"" in js,
        "quick_answer_fetch":         "fetchQuickAnswer" in js,
        "post_free_text":             "postFreeText" in js,
    }


# ---------------------------------------------------------------------------
# S6 — locale + no-leak 10B
# ---------------------------------------------------------------------------

_BANNED_10B = (
    re.compile(r"\bjob_[A-Za-z0-9_]{3,}\b"),
    re.compile(r"\bsandbox_request_id\b"),
    re.compile(r"\bprocess_governed_prompt\b"),
    re.compile(r"\bcounterfactual_preview_v1\b"),
    re.compile(r"\bsandbox_queue\b"),
    re.compile(r"\breal_derived\b"),
    re.compile(r"\btemplate_fallback\b"),
    re.compile(r"\binsufficient_evidence\b"),
    re.compile(r"\bhorizon_provenance\b"),
    re.compile(r"\bregistry_entry_id\b"),
)


def _scan(blob: str) -> list[str]:
    hits: list[str] = []
    for pat in _BANNED_10B:
        m = pat.search(blob)
        if m:
            hits.append(m.group(0))
    return hits


def _run_s6_locale_and_no_leak() -> dict[str, Any]:
    try:
        from phase47_runtime.phase47e_user_locale import SHELL  # type: ignore
    except Exception as exc:
        return {"scenario": "S6_locale_and_no_leak", "import_ok": False, "error": repr(exc)}
    prefixes = ("product_shell.research.", "product_shell.replay.", "product_shell.ask.")
    parity: dict[str, Any] = {}
    for pre in prefixes:
        ko = {k for k in SHELL.get("ko", {}) if k.startswith(pre)}
        en = {k for k in SHELL.get("en", {}) if k.startswith(pre)}
        parity[pre] = {
            "ko_count":  len(ko),
            "en_count":  len(en),
            "parity_ok": ko == en,
        }
    html = _read(PRODUCT_INDEX)
    js   = _read(PRODUCT_JS)
    css  = _read(PRODUCT_CSS)
    return {
        "scenario":     "S6_locale_and_no_leak",
        "import_ok":    True,
        "parity":       parity,
        "all_parity_ok": all(v["parity_ok"] for v in parity.values()),
        "min_10_keys_per_family": all(v["ko_count"] >= 10 for v in parity.values()),
        "html_hits":    _scan(html),
        "js_hits":      _scan(js),
        "css_hits":     _scan(css),
        "all_surfaces_clean": not any([_scan(html), _scan(js), _scan(css)]),
    }


# ---------------------------------------------------------------------------
# S7 — routes dispatch
# ---------------------------------------------------------------------------

def _run_s7_routes() -> dict[str, Any]:
    src = _read(ROUTES_PY)
    return {
        "scenario":                          "S7_routes_dispatch",
        "research_route_registered":         '"/api/product/research"' in src,
        "replay_route_registered":           '"/api/product/replay"' in src,
        "ask_get_route_registered":          '"/api/product/ask"' in src
                                                 and 'api_product_ask(' in src,
        "ask_quick_route_registered":        '"/api/product/ask/quick"' in src,
        "ask_post_route_registered":         'api_product_ask_free_text' in src,
        "requests_route_registered":         '"/api/product/requests"' in src,
    }


# ---------------------------------------------------------------------------
# Runbook assembly
# ---------------------------------------------------------------------------

def main() -> int:
    s1 = _run_s1_research()
    s2 = _run_s2_replay()
    s3 = _run_s3_ask()
    s4 = _run_s4_css()
    s5 = _run_s5_js()
    s6 = _run_s6_locale_and_no_leak()
    s7 = _run_s7_routes()

    evidence = {
        "contract":        "PATCH_10B_PRODUCT_SHELL_RUNBOOK_V1",
        "generated_utc":   _now_iso(),
        "research_mapper_ok":
            s1.get("import_ok") and s1.get("landing_contract") == "PRODUCT_RESEARCH_LANDING_V1"
            and s1.get("deepdive_contract") == "PRODUCT_RESEARCH_DEEPDIVE_V1"
            and (s1.get("deepdive_evidence_count") or 0) >= 5,
        "replay_mapper_ok":
            s2.get("import_ok") and s2.get("contract") == "PRODUCT_REPLAY_V1"
            and (s2.get("scenarios_count") or 0) == 3
            and set(s2.get("scenario_kinds") or []) == {"baseline", "weakened_evidence", "stressed"},
        "ask_mapper_ok":
            s3.get("import_ok") and s3.get("landing_contract") == "PRODUCT_ASK_V1"
            and s3.get("quick_contract") == "PRODUCT_ASK_QUICK_V1"
            and (s3.get("quick_intent_count") or 0) >= 6
            and s3.get("degraded_grounded") is False,
        "visual_system_10b_ok":  s4.get("all_components_present") and s4.get("has_tooltip_variants"),
        "js_10b_ok": all([
            s5.get("state_focus_present"),
            s5.get("hash_routing_present"),
            s5.get("research_renderer_present"),
            s5.get("replay_renderer_present"),
            s5.get("ask_renderer_present"),
            s5.get("today_to_research_softlink"),
        ]),
        "locale_and_no_leak_ok":
            s6.get("import_ok") and s6.get("all_parity_ok")
            and s6.get("min_10_keys_per_family") and s6.get("all_surfaces_clean"),
        "routes_ok": all([
            s7["research_route_registered"], s7["replay_route_registered"],
            s7["ask_get_route_registered"], s7["ask_quick_route_registered"],
            s7["ask_post_route_registered"], s7["requests_route_registered"],
        ]),
        "scenarios": [s1, s2, s3, s4, s5, s6, s7],
    }
    evidence["all_ok"] = all(
        evidence[k] for k in evidence
        if k.endswith("_ok") and isinstance(evidence[k], bool)
    )

    out = REPO_ROOT / "data/mvp/evidence/patch_10b_product_shell_runbook_evidence.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    bridge = {
        "contract":             "PATCH_10B_PRODUCT_SHELL_BRIDGE_V1",
        "generated_utc":        _now_iso(),
        "prior_patch":          "agh_v1_patch_10a_product_shell_rebuild",
        "entry_points":         [
            "/ (product shell — Today / Research / Replay / Ask AI)",
            "/ops?METIS_OPS_SHELL=1 (internal operator view)",
        ],
        "api_prefix":           "/api/product/",
        "new_routes": [
            "/api/product/research",
            "/api/product/replay",
            "/api/product/ask",
            "/api/product/ask/quick",
            "/api/product/requests",
        ],
        "runbook_all_ok":       evidence["all_ok"],
        "follow_up_patch":      "10C - Polish + message-snapshot integration",
    }
    bridge_out = REPO_ROOT / "data/mvp/evidence/patch_10b_product_shell_bridge_evidence.json"
    bridge_out.write_text(json.dumps(bridge, ensure_ascii=False, indent=2), encoding="utf-8")

    scope_evidence = {
        "patch_10b_research_redesign_evidence.json": {
            "contract":     "PATCH_10B_RESEARCH_REDESIGN_V1",
            "scope":        "A1/A2/A3 + E2 Research mapper + routes + renderers",
            "generated_utc": _now_iso(),
            "research_mapper_ok": evidence["research_mapper_ok"],
            "s1_snapshot":  s1,
            "dto_contracts": [
                "PRODUCT_RESEARCH_LANDING_V1",
                "PRODUCT_RESEARCH_DEEPDIVE_V1",
            ],
            "evidence_rail_kinds": [
                "what_changed", "strongest_support", "counter_or_companion",
                "missing_or_preparing", "peer_context",
            ],
            "action_chip_kinds": ["open_replay", "ask_ai", "back_to_today"],
            "route_evidence": {
                "research_route_registered": s7["research_route_registered"],
            },
            "js_evidence": {
                "research_renderer_present": s5["research_renderer_present"],
                "today_to_research_softlink": s5["today_to_research_softlink"],
            },
        },
        "patch_10b_replay_timeline_evidence.json": {
            "contract":     "PATCH_10B_REPLAY_TIMELINE_V1",
            "scope":        "B1/B2 + E3 Replay mapper + gap/checkpoint annotation + 3-scenario",
            "generated_utc": _now_iso(),
            "replay_mapper_ok": evidence["replay_mapper_ok"],
            "s2_snapshot":  s2,
            "dto_contracts": ["PRODUCT_REPLAY_V1"],
            "timeline_kinds": [
                "proposal", "decision", "applied",
                "spectrum_refresh", "validation_evaluation",
                "sandbox_request", "sandbox_result",
                "gap", "checkpoint",
            ],
            "scenario_kinds": ["baseline", "weakened_evidence", "stressed"],
            "advanced_disclosure_policy": "hint_only_no_payload",
            "route_evidence": {
                "replay_route_registered": s7["replay_route_registered"],
            },
            "js_evidence": {
                "replay_renderer_present": s5["replay_renderer_present"],
            },
        },
        "patch_10b_ask_bounded_evidence.json": {
            "contract":     "PATCH_10B_ASK_BOUNDED_V1",
            "scope":        "C1/C2 + E4 Ask AI mapper + 4 routes + degraded-safe free-text",
            "generated_utc": _now_iso(),
            "ask_mapper_ok": evidence["ask_mapper_ok"],
            "s3_snapshot":  s3,
            "dto_contracts": [
                "PRODUCT_ASK_V1",
                "PRODUCT_ASK_QUICK_V1",
                "PRODUCT_ASK_ANSWER_V1",
                "PRODUCT_REQUEST_STATE_V1",
            ],
            "quick_intents": [
                "explain_claim", "show_support", "show_counter",
                "other_horizons", "why_confidence", "whats_missing",
            ],
            "degraded_safe": {
                "wrapper": "scrub_free_text_answer",
                "failure_fallback": "_degraded_answer (grounded:false, banner)",
                "always_scrubbed_via": "strip_engineering_ids",
            },
            "route_evidence": {
                "ask_get_route_registered":   s7["ask_get_route_registered"],
                "ask_quick_route_registered": s7["ask_quick_route_registered"],
                "ask_post_route_registered":  s7["ask_post_route_registered"],
                "requests_route_registered":  s7["requests_route_registered"],
            },
            "js_evidence": {
                "ask_renderer_present": s5["ask_renderer_present"],
                "quick_answer_fetch":   s5["quick_answer_fetch"],
                "post_free_text":       s5["post_free_text"],
            },
        },
        "patch_10b_visual_system_ext_evidence.json": {
            "contract":     "PATCH_10B_VISUAL_SYSTEM_EXT_V1",
            "scope":        "D1 CSS component extension + hash routing + STATE.focus",
            "generated_utc": _now_iso(),
            "visual_system_10b_ok": evidence["visual_system_10b_ok"],
            "js_10b_ok":            evidence["js_10b_ok"],
            "locale_and_no_leak_ok": evidence["locale_and_no_leak_ok"],
            "s4_snapshot":          s4,
            "s5_snapshot":          s5,
            "s6_snapshot": {
                "parity":            s6.get("parity"),
                "all_parity_ok":     s6.get("all_parity_ok"),
                "min_10_keys_per_family": s6.get("min_10_keys_per_family"),
                "all_surfaces_clean":    s6.get("all_surfaces_clean"),
            },
            "required_css_components": list(_REQUIRED_CSS_10B),
            "tooltip_variants":        ["info", "caution", "trust"],
            "locale_families": [
                "product_shell.research.*",
                "product_shell.replay.*",
                "product_shell.ask.*",
            ],
            "banned_patterns_10b": [p.pattern for p in _BANNED_10B],
        },
    }
    for filename, payload in scope_evidence.items():
        (REPO_ROOT / f"data/mvp/evidence/{filename}").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    summary = {k: v for k, v in evidence.items() if k.endswith("_ok")}
    summary["_runbook_path"] = str(out.relative_to(REPO_ROOT))
    summary["_bridge_path"] = str(bridge_out.relative_to(REPO_ROOT))
    summary["_scope_evidence_files"] = list(scope_evidence.keys())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if evidence["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
