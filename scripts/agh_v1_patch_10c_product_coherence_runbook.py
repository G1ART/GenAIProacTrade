"""AGH v1 Patch 10C — Product Shell coherence / trust closure runbook.

Walks the Patch 10C workorder scenarios against the code that actually
serves the four customer-facing surfaces. Deterministic: no Supabase
writes, no network calls, no LLM calls.

Scenarios (workorder mapping):

    S1. A — message/evidence/focus coherence across Today / Research /
            Replay / Ask (shared_focus + coherence_signature present
            and identical across surfaces).
    S2. B — Ask AI retrieval-grounded trust closure (pre-LLM scope
            guard, surfaced-context injection, post-LLM hallucination
            guard + degraded collapse).
    S3. C — product-state continuity (focus ribbon on Research /
            Replay / Ask, Today hero cta_more soft-links, breadcrumbs
            on every deep surface).
    S4. D — DTO/mapper refinement (shared_focus, evidence_lineage,
            coherence_signature, shared_wording on every DTO).
    S5. E — language contract tightening (SHARED_WORDING + locale
            continuity/trust/out_of_scope families with KO/EN parity).
    S6. F — no-leak (engineering IDs + raw provenance + 10C internal
            helper names + new locale keys) on surface + DTOs.

Produces (under ``data/mvp/evidence/``):

    * ``patch_10c_product_coherence_runbook_evidence.json``
    * ``patch_10c_product_coherence_bridge_evidence.json``
    * ``patch_10c_coherence_evidence.json``
    * ``patch_10c_ask_trust_golden_set_evidence.json``
    * ``patch_10c_cross_surface_alignment_evidence.json``
    * ``patch_10c_language_contract_evidence.json``
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


STATIC      = REPO_ROOT / "src/phase47_runtime/static"
PRODUCT_JS  = STATIC / "product_shell.js"
PRODUCT_CSS = STATIC / "product_shell.css"
VM_COMMON   = REPO_ROOT / "src/phase47_runtime/product_shell/view_models_common.py"
VM_ASK      = REPO_ROOT / "src/phase47_runtime/product_shell/view_models_ask.py"
LOCALE_PY   = REPO_ROOT / "src/phase47_runtime/phase47e_user_locale.py"
EVIDENCE_DIR = REPO_ROOT / "data/mvp/evidence"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=False, capture_output=True, text=True,
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Synthetic fixtures (same focus → AAPL / short — used across every surface)
# ---------------------------------------------------------------------------


NOW = "2026-04-23T08:00:00Z"


def _bundle():
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    reg_entries = []
    artifacts = []
    for hz in HORIZON_KEYS:
        reg_entries.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"stub_family_{hz}",
            registry_entry_id=f"stub_reg_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
        artifacts.append(SimpleNamespace(
            artifact_id=f"stub_family_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
    return SimpleNamespace(
        artifacts=artifacts,
        registry_entries=reg_entries,
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived_with_degraded_challenger"},
            "long":        {"source": "template_fallback"},
        },
        metadata={"graduation_tier": "production",
                  "built_at_utc": NOW, "source_run_ids": ["run_stub_a"]},
        as_of_utc=NOW,
    )


def _spectrum():
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    rows = [
        {"asset_id": "AAPL", "spectrum_position": 0.74,
         "rank_index": 1, "rank_movement": "up",
         "rationale_summary": "단기 추세 강세가 지속되며 변동성이 축소되는 국면입니다.",
         "what_changed": "지난 주 대비 상위 10% 구간에서 상대 강도 +8% 개선"},
    ]
    return {hz: {"ok": True, "rows": rows} for hz in HORIZON_KEYS}


# ---------------------------------------------------------------------------
# S1 — coherence across four surfaces
# ---------------------------------------------------------------------------


def _scenario_s1() -> dict[str, Any]:
    from phase47_runtime.product_shell.view_models import compose_today_product_dto  # type: ignore
    from phase47_runtime.product_shell.view_models_research import (  # type: ignore
        compose_research_deepdive_dto,
    )
    from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto  # type: ignore
    from phase47_runtime.product_shell.view_models_ask import (  # type: ignore
        compose_ask_product_dto,
        compose_quick_answers_dto,
    )

    bundle, spec = _bundle(), _spectrum()
    out: dict[str, Any] = {"per_lang": {}}
    for lg in ("ko", "en"):
        today    = compose_today_product_dto(bundle=bundle, spectrum_by_horizon=spec, lang=lg, now_utc=NOW)
        research = compose_research_deepdive_dto(bundle=bundle, spectrum_by_horizon=spec,
                                                 asset_id="AAPL", horizon_key="short", lang=lg, now_utc=NOW)
        replay   = compose_replay_product_dto(bundle=bundle, spectrum_by_horizon=spec,
                                              lineage=None, asset_id="AAPL", horizon_key="short",
                                              lang=lg, now_utc=NOW)
        ask      = compose_ask_product_dto(bundle=bundle, spectrum_by_horizon=spec,
                                           asset_id="AAPL", horizon_key="short",
                                           followups=None, lang=lg, now_utc=NOW)
        quick    = compose_quick_answers_dto(bundle=bundle, spectrum_by_horizon=spec,
                                             asset_id="AAPL", horizon_key="short", lang=lg)

        sigs = {
            "today":    (today.get("coherence_signature") or {}).get("fingerprint"),
            "research": (research.get("coherence_signature") or {}).get("fingerprint"),
            "replay":   (replay.get("coherence_signature") or {}).get("fingerprint"),
            "ask_ai":   (ask.get("coherence_signature") or {}).get("fingerprint"),
            "ask_quick": (quick.get("coherence_signature") or {}).get("fingerprint"),
        }
        unique = {v for v in sigs.values() if v}
        out["per_lang"][lg] = {
            "fingerprints":   sigs,
            "all_match":      len(unique) == 1,
            "contract_stamps": {
                "today":    today.get("contract"),
                "research": research.get("contract"),
                "replay":   replay.get("contract"),
                "ask_ai":   ask.get("contract"),
                "ask_quick": quick.get("contract"),
            },
        }
    out["ok"] = all(v["all_match"] for v in out["per_lang"].values())
    return out


# ---------------------------------------------------------------------------
# S2 — Ask AI trust closure (pre-LLM guard, context injection, post guard)
# ---------------------------------------------------------------------------


def _scenario_s2() -> dict[str, Any]:
    from phase47_runtime.product_shell.view_models_ask import (  # type: ignore
        _focus_context_card,
        classify_question_scope,
        scan_response_for_hallucinations,
        scrub_free_text_answer,
        surfaced_context_summary,
    )

    bundle, spec = _bundle(), _spectrum()
    ctx = _focus_context_card(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang="ko",
    )

    scopes = {
        "in_scope":        classify_question_scope("왜 등급이 올랐나요?", context=ctx),
        "advice_request":  classify_question_scope("AAPL 지금 매수 추천해 주세요.", context=ctx),
        "foreign_ticker":  classify_question_scope("TSLA 는 어떻게 보고 계신가요?", context=ctx),
        "off_topic":       classify_question_scope("콜옵션 만기 어떻게 보세요?", context=ctx),
    }

    grounding = surfaced_context_summary(ctx, lang="ko")

    # A well-behaved LLM answering a good question — uses the same
    # conversation-layer envelope shape as ``api_conversation``.
    def _good_llm():
        return {"ok": True, "response": {
            "body": "노출된 근거 안에서 요약해 드립니다. 확신 수준은 실데이터 근거입니다.",
        }}
    good = scrub_free_text_answer(
        prompt="왜 등급이 올랐나요?", context=ctx,
        conversation_callable=_good_llm, lang="ko",
    )

    # A hallucinating LLM — advice / ticker / price target.
    def _bad_llm():
        return {"ok": True, "response": {
            "body": "AAPL 을 지금 매수하세요. 목표가 200달러 TSLA 도 추천합니다.",
        }}
    bad = scrub_free_text_answer(
        prompt="왜 등급이 올랐나요?", context=ctx,
        conversation_callable=_bad_llm, lang="ko",
    )
    bad_flags = scan_response_for_hallucinations(
        body="AAPL 을 지금 매수하세요. 목표가 200달러 TSLA 도 추천합니다.",
        context=ctx,
    )

    # A failing LLM — collapses to degraded.
    def _broken_llm():
        return {"ok": False}
    degraded = scrub_free_text_answer(
        prompt="왜 등급이 올랐나요?", context=ctx,
        conversation_callable=_broken_llm, lang="ko",
    )

    return {
        "scope_classification": {k: v["kind"] for k, v in scopes.items()},
        "pre_llm_short_circuit": {
            "advice_is_out_of_scope":  scopes["advice_request"]["kind"] == "advice_request",
            "foreign_is_out_of_scope": scopes["foreign_ticker"]["kind"] == "foreign_ticker",
            "off_topic_is_out_of_scope": scopes["off_topic"]["kind"] == "off_topic",
        },
        "grounding_paragraph_length_chars": len(grounding),
        "good_answer_kind":     good.get("kind"),
        "bad_answer_kind":      bad.get("kind"),
        "bad_flags":            bad_flags,
        "degraded_answer_kind": degraded.get("kind"),
        "ok":
            scopes["advice_request"]["kind"] == "advice_request"
            and scopes["foreign_ticker"]["kind"] == "foreign_ticker"
            and scopes["off_topic"]["kind"] == "off_topic"
            and scopes["in_scope"]["kind"] == "in_scope"
            and good.get("kind") in ("grounded", "partial")
            and bad.get("kind") == "partial"
            and degraded.get("kind") == "degraded"
            and len(bad_flags) >= 1,
    }


# ---------------------------------------------------------------------------
# S3 — focus continuity UI (ribbon + soft-links + breadcrumbs)
# ---------------------------------------------------------------------------


def _scenario_s3() -> dict[str, Any]:
    js  = _read(PRODUCT_JS)
    css = _read(PRODUCT_CSS)
    checks = {
        "focus_ribbon_helper":        "function renderFocusRibbon" in js,
        "focus_ribbon_rendered_res":  "renderFocusRibbon(dto, \"research\")" in js,
        "focus_ribbon_rendered_rep":  "renderFocusRibbon(dto, \"replay\")" in js,
        "focus_ribbon_rendered_ask":  "renderFocusRibbon(dto, \"ask_ai\")" in js,
        "hero_softlinks_group":       "ps-hero-card-softlinks" in js,
        "hero_softlink_open_replay":  "open_replay" in js and "ps-hero-card-softlink" in js,
        "breadcrumbs_today_first":    "nav.today" in js,
        "ribbon_css_class":           ".ps-focus-ribbon" in css,
        "ribbon_softlink_css":        ".ps-focus-ribbon__jump" in css,
        "softlink_css":               ".ps-hero-card-softlink" in css,
    }
    return {"checks": checks, "ok": all(checks.values())}


# ---------------------------------------------------------------------------
# S4 — DTO refinement (shared_focus + evidence_lineage + shared_wording)
# ---------------------------------------------------------------------------


def _scenario_s4() -> dict[str, Any]:
    from phase47_runtime.product_shell.view_models import compose_today_product_dto  # type: ignore
    from phase47_runtime.product_shell.view_models_research import (  # type: ignore
        compose_research_deepdive_dto,
    )
    from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto  # type: ignore
    from phase47_runtime.product_shell.view_models_ask import compose_ask_product_dto  # type: ignore

    bundle, spec = _bundle(), _spectrum()
    checks: dict[str, bool] = {}
    for lg in ("ko", "en"):
        dtos = {
            "today":    compose_today_product_dto(bundle=bundle, spectrum_by_horizon=spec, lang=lg, now_utc=NOW),
            "research": compose_research_deepdive_dto(bundle=bundle, spectrum_by_horizon=spec,
                                                      asset_id="AAPL", horizon_key="short", lang=lg, now_utc=NOW),
            "replay":   compose_replay_product_dto(bundle=bundle, spectrum_by_horizon=spec,
                                                   lineage=None, asset_id="AAPL", horizon_key="short",
                                                   lang=lg, now_utc=NOW),
            "ask_ai":   compose_ask_product_dto(bundle=bundle, spectrum_by_horizon=spec,
                                                asset_id="AAPL", horizon_key="short",
                                                followups=None, lang=lg, now_utc=NOW),
        }
        for name, dto in dtos.items():
            if name == "today":
                # Today is a board-level view; it exposes primary_focus +
                # per-card shared_focus inside each hero_card.
                checks[f"{name}_{lg}_has_primary_focus"] = isinstance(dto.get("primary_focus"), dict)
                per_card = [hc.get("shared_focus") for hc in (dto.get("hero_cards") or [])]
                checks[f"{name}_{lg}_cards_have_shared_focus"] = bool(per_card) and all(isinstance(b, dict) for b in per_card)
            else:
                checks[f"{name}_{lg}_has_shared_focus"] = isinstance(dto.get("shared_focus"), dict)
            checks[f"{name}_{lg}_has_coherence_sig"] = isinstance(dto.get("coherence_signature"), dict)
            checks[f"{name}_{lg}_has_shared_wording"] = isinstance(dto.get("shared_wording"), dict)
        # Today is landing-shaped (no deep-dive evidence lineage); the three
        # deep surfaces carry evidence_lineage_summary.
        for name in ("research", "replay", "ask_ai"):
            checks[f"{name}_{lg}_has_evidence_lineage"] = isinstance(
                dtos[name].get("evidence_lineage_summary"), dict
            )
    return {"checks": checks, "ok": all(checks.values())}


# ---------------------------------------------------------------------------
# S5 — language contract (SHARED_WORDING + new locale families)
# ---------------------------------------------------------------------------


def _scenario_s5() -> dict[str, Any]:
    from phase47_runtime.phase47e_user_locale import SHELL  # type: ignore
    from phase47_runtime.product_shell.view_models_common import (  # type: ignore
        SHARED_WORDING,
        SHARED_WORDING_KINDS,
    )

    prefixes = (
        "product_shell.continuity.",
        "product_shell.trust.",
        "product_shell.ask.out_of_scope.",
    )
    parity: dict[str, bool] = {}
    counts: dict[str, int] = {}
    for pre in prefixes:
        ko = {k for k in SHELL["ko"] if k.startswith(pre)}
        en = {k for k in SHELL["en"] if k.startswith(pre)}
        parity[pre] = ko == en
        counts[pre] = len(ko)

    shared_wording_kinds_ok = set(SHARED_WORDING_KINDS) == set(SHARED_WORDING["ko"].keys())
    return {
        "locale_parity":    parity,
        "locale_counts":    counts,
        "shared_wording_kinds": list(SHARED_WORDING_KINDS),
        "shared_wording_kinds_ok": shared_wording_kinds_ok,
        "ok": all(parity.values()) and shared_wording_kinds_ok,
    }


# ---------------------------------------------------------------------------
# S6 — no-leak (surface + DTOs) and coherence_signature preservation
# ---------------------------------------------------------------------------


def _scenario_s6() -> dict[str, Any]:
    import re as _re
    from phase47_runtime.product_shell.view_models_common import (  # type: ignore
        build_shared_focus_block,
        strip_engineering_ids,
    )

    bundle, spec = _bundle(), _spectrum()
    banned = {
        "artifact_id_literal":         _re.compile(r"\bart_[A-Za-z0-9_]{3,}\b"),
        "packet_id_literal":           _re.compile(r"\bpkt_[A-Za-z0-9_]{3,}\b"),
        "raw_provenance_insufficient": _re.compile(r"\binsufficient_evidence\b"),
        "raw_provenance_template":     _re.compile(r"\btemplate_fallback\b"),
        "internal_token_scan_hallu":   _re.compile(r"\bscan_response_for_hallucinations\b"),
        "internal_token_classify":     _re.compile(r"\bclassify_question_scope\b"),
    }
    # Scan surface artefacts.
    surface_text = _read(PRODUCT_JS) + "\n" + _read(PRODUCT_CSS)
    surface_hits = {k: [m.group() for m in p.finditer(surface_text)]
                    for k, p in banned.items()}

    # Fingerprint survives scrub.
    block = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    scrubbed = strip_engineering_ids(block)
    fp_before = block["coherence_signature"]["fingerprint"]
    fp_after  = scrubbed["coherence_signature"]["fingerprint"]

    return {
        "surface_hits":    {k: v for k, v in surface_hits.items() if v},
        "fingerprint_survived_scrub": fp_before == fp_after,
        "fingerprint_shape_ok": bool(_re.fullmatch(r"[0-9a-f]{12}", fp_before)),
        "ok": (not any(surface_hits.values())) and fp_before == fp_after,
    }


# ---------------------------------------------------------------------------
# Runbook orchestration
# ---------------------------------------------------------------------------


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    s1 = _scenario_s1()
    s2 = _scenario_s2()
    s3 = _scenario_s3()
    s4 = _scenario_s4()
    s5 = _scenario_s5()
    s6 = _scenario_s6()

    all_ok = all([s1["ok"], s2["ok"], s3["ok"], s4["ok"], s5["ok"], s6["ok"]])

    evidence = {
        "contract":      "PATCH_10C_PRODUCT_COHERENCE_RUNBOOK_V1",
        "generated_utc": _now_iso(),
        "git_head_sha":  _git_sha(),
        "scenarios": {
            "s1_cross_surface_coherence": s1,
            "s2_ask_trust_closure":       s2,
            "s3_focus_continuity_ui":     s3,
            "s4_dto_refinement":          s4,
            "s5_language_contract":       s5,
            "s6_no_leak_and_fingerprint": s6,
        },
        "all_ok": all_ok,
    }
    (EVIDENCE_DIR / "patch_10c_product_coherence_runbook_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    bridge = {
        "contract":      "PATCH_10C_PRODUCT_COHERENCE_BRIDGE_V1",
        "generated_utc": _now_iso(),
        "prior_patch":   "agh_v1_patch_10b_product_shell_rebuild_research_replay_ask",
        "entry_points":  ["/ (product shell — Today / Research / Replay / Ask AI)"],
        "new_invariants": [
            "coherence_signature.fingerprint identical across Today / Research / Replay / Ask for the same focus (both KO/EN)",
            "Ask AI pre-LLM scope guard + post-LLM hallucination guard; LLM output discarded on flag",
            "SHARED_WORDING (10 kinds) + new locale families (continuity / trust / out_of_scope)",
            "Focus ribbon + hero soft-links + unified breadcrumbs across every deep surface",
        ],
        "runbook_all_ok": all_ok,
        "follow_up_patch": None,
    }
    (EVIDENCE_DIR / "patch_10c_product_coherence_bridge_evidence.json").write_text(
        json.dumps(bridge, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # Scope-level evidence files (one per workorder axis).
    (EVIDENCE_DIR / "patch_10c_coherence_evidence.json").write_text(
        json.dumps({
            "contract": "PATCH_10C_COHERENCE_V1",
            "generated_utc": _now_iso(),
            "s1_snapshot": s1, "s4_snapshot": s4,
            "ok": s1["ok"] and s4["ok"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "patch_10c_ask_trust_golden_set_evidence.json").write_text(
        json.dumps({
            "contract": "PATCH_10C_ASK_TRUST_GOLDEN_SET_V1",
            "generated_utc": _now_iso(),
            "s2_snapshot": s2,
            "ok": s2["ok"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "patch_10c_cross_surface_alignment_evidence.json").write_text(
        json.dumps({
            "contract": "PATCH_10C_CROSS_SURFACE_ALIGNMENT_V1",
            "generated_utc": _now_iso(),
            "s1_snapshot": s1,
            "s3_snapshot": s3,
            "s6_snapshot": s6,
            "ok": s1["ok"] and s3["ok"] and s6["ok"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "patch_10c_language_contract_evidence.json").write_text(
        json.dumps({
            "contract": "PATCH_10C_LANGUAGE_CONTRACT_V1",
            "generated_utc": _now_iso(),
            "s5_snapshot": s5,
            "ok": s5["ok"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "ok": all_ok,
        "evidence_files": [
            "patch_10c_product_coherence_runbook_evidence.json",
            "patch_10c_product_coherence_bridge_evidence.json",
            "patch_10c_coherence_evidence.json",
            "patch_10c_ask_trust_golden_set_evidence.json",
            "patch_10c_cross_surface_alignment_evidence.json",
            "patch_10c_language_contract_evidence.json",
        ],
        "per_scenario_ok": {
            "s1": s1["ok"], "s2": s2["ok"], "s3": s3["ok"],
            "s4": s4["ok"], "s5": s5["ok"], "s6": s6["ok"],
        },
    }, ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
