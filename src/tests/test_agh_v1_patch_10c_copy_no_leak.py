"""Patch 10C — Copy & engineering-ID no-leak scanner (coherence closure).

This file inherits the 10A/10B guarantees and additionally verifies that
the new 10C coherence/focus/trust/out-of-scope additions do NOT smuggle
internal tokens onto the customer surface.

Scope specific to 10C:

1. Every 10C DTO surface (``shared_focus``, ``coherence_signature``,
   ``evidence_lineage_summary``, ``shared_wording``) round-trips through
   :func:`strip_engineering_ids` without leaking banned patterns.
2. The 12-hex ``coherence_signature.fingerprint`` and the
   ``COHERENCE_V1`` contract version are preserved verbatim — we never
   want the scrubber to eat the very fingerprint we rely on for
   cross-surface verification.
3. New locale families — ``product_shell.continuity.*``,
   ``product_shell.trust.*``, ``product_shell.ask.out_of_scope.*`` —
   have strict KO/EN parity and every value is a non-empty string.
4. Free-text out-of-scope and post-LLM hallucination guardrails do not
   re-emit the flagged input into the DTO (no echo of advice prompts /
   foreign tickers).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase47_runtime.phase47e_user_locale import SHELL
from phase47_runtime.product_shell.view_models import compose_today_product_dto
from phase47_runtime.product_shell.view_models_ask import (
    compose_ask_product_dto,
    compose_quick_answers_dto,
    scrub_free_text_answer,
    _focus_context_card,
)
from phase47_runtime.product_shell.view_models_common import (
    HORIZON_KEYS,
    SHARED_WORDING,
    SHARED_WORDING_KINDS,
    build_shared_focus_block,
    compute_coherence_signature,
    strip_engineering_ids,
)
from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto
from phase47_runtime.product_shell.view_models_research import (
    compose_research_deepdive_dto,
    compose_research_landing_dto,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATIC = _REPO_ROOT / "src" / "phase47_runtime" / "static"
_PRODUCT_ARTIFACTS: tuple[Path, ...] = (
    _STATIC / "index.html",
    _STATIC / "product_shell.js",
    _STATIC / "product_shell.css",
)


# Reuse 10B banned patterns and add 10C-specific tokens that must stay
# internal (e.g. the low-level ``_quantize_position`` helper should
# never appear on the customer surface, nor should raw method handles
# like ``build_shared_focus_block`` references).
_BANNED_PATTERNS: dict[str, re.Pattern[str]] = {
    "artifact_id_literal":            re.compile(r"\bart_[A-Za-z0-9_]{3,}\b"),
    "registry_slug_literal":          re.compile(r"\breg_[A-Za-z0-9_]{3,}\b"),
    "factor_slug_literal":            re.compile(r"\bfactor_[A-Za-z0-9_]{3,}\b"),
    "packet_id_literal":              re.compile(r"\bpkt_[A-Za-z0-9_]{3,}\b"),
    "demo_pit_pointer":               re.compile(r"\bpit:demo:"),
    "raw_provenance_real":            re.compile(r"\breal_derived\b"),
    "raw_provenance_insufficient":    re.compile(r"\binsufficient_evidence\b"),
    "raw_provenance_template":        re.compile(r"\btemplate_fallback\b"),
    "raw_provenance_horizon_key":     re.compile(r"\bhorizon_provenance\b"),
    "internal_token_replay_lineage":  re.compile(r"\breplay_lineage_pointer\b"),
    "internal_token_registry_entry":  re.compile(r"\bregistry_entry_id\b"),
    "internal_token_artifact_id_key": re.compile(r"\bartifact_id\b"),
    "internal_token_proposal_pkt":    re.compile(r"\bproposal_packet_id\b"),
    "internal_token_job_id":          re.compile(r"\bjob_[A-Za-z0-9_]{3,}\b"),
    "internal_token_sandbox_rid":     re.compile(r"\bsandbox_request_id\b"),
    "internal_token_governed_prompt": re.compile(r"\bprocess_governed_prompt\b"),
    "internal_token_cf_preview":      re.compile(r"\bcounterfactual_preview_v1\b"),
    "internal_token_sandbox_queue":   re.compile(r"\bsandbox_queue\b"),
    # Patch 10C additions — internal scoring helpers / raw hook names
    # that should never appear in the customer-visible bytes.
    "internal_token_quantize":        re.compile(r"\b_quantize_position\b"),
    "internal_token_short_hash":      re.compile(r"\b_short_hash\b"),
    "internal_token_scan_hallu":      re.compile(r"\bscan_response_for_hallucinations\b"),
    "internal_token_classify_scope":  re.compile(r"\bclassify_question_scope\b"),
    "buy_sell_imperative_ko_buy":     re.compile(r"(?<![가-힣])매수하세요"),
    "buy_sell_imperative_ko_sell":    re.compile(r"(?<![가-힣])매도하세요"),
    "buy_sell_imperative_en_buy":     re.compile(r"\b(?:Buy|BUY) now\b"),
    "buy_sell_imperative_en_sell":    re.compile(r"\b(?:Sell|SELL) now\b"),
}

_ALLOWED_SUBSTRINGS: tuple[str, ...] = (
    "/api/product/today",
    "/api/product/research",
    "/api/product/replay",
    "/api/product/ask",
    "/api/product/ask/quick",
    "/api/product/requests",
    "product_shell.css",
    "product_shell.js",
    "ps-",
    "--ps-",
    "__PS__",
)


def _scrub_allowed(text: str) -> str:
    out = text
    for s in _ALLOWED_SUBSTRINGS:
        out = out.replace(s, "")
    return out


NOW = "2026-04-23T09:00:00Z"


def _bundle():
    reg_entries = []
    artifacts = []
    for hz in HORIZON_KEYS:
        reg_entries.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"art_xyz_{hz}",
            registry_entry_id=f"reg_xyz_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
        artifacts.append(SimpleNamespace(
            artifact_id=f"art_xyz_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
    return SimpleNamespace(
        artifacts=artifacts,
        registry_entries=reg_entries,
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived_with_degraded_challenger"},
            "medium_long": {"source": "template_fallback"},
            "long":        {"source": "insufficient_evidence"},
        },
        metadata={"graduation_tier": "production",
                  "built_at_utc": NOW},
        as_of_utc=NOW,
    )


def _spectrum():
    return {
        hz: {"ok": True, "rows": [
            {"asset_id": "AAPL", "spectrum_position": 0.55,
             "rank_index": 1, "rank_movement": "up",
             "rationale_summary": "단기 모멘텀 우세",
             "what_changed": "지난 주 대비 상승"},
        ]} for hz in HORIZON_KEYS
    }


def _all_dtos_blob(lang: str) -> str:
    bundle, spec = _bundle(), _spectrum()
    today = compose_today_product_dto(
        bundle=bundle, spectrum_by_horizon=spec, lang=lang, now_utc=NOW,
    )
    landing = compose_research_landing_dto(
        bundle=bundle, spectrum_by_horizon=spec, lang=lang, now_utc=NOW,
    )
    deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=NOW,
    )
    replay = compose_replay_product_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        lineage=None, asset_id="AAPL", horizon_key="short",
        lang=lang, now_utc=NOW,
    )
    ask = compose_ask_product_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short",
        followups=None, lang=lang, now_utc=NOW,
    )
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang,
    )
    ctx = _focus_context_card(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang,
    )
    oos = scrub_free_text_answer(
        prompt="AAPL 지금 매수 추천해 주세요." if lang == "ko" else "Should I buy AAPL now?",
        context=ctx,
        conversation_callable=lambda: {"ok": True, "body": "unreachable"},
        lang=lang,
    )
    return json.dumps(
        {
            "today": today,
            "landing": landing,
            "deepdive": deepdive,
            "replay": replay,
            "ask": ask,
            "quick": quick,
            "out_of_scope": oos,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# 1. Customer surface files — no banned tokens (including 10C additions).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("artifact_path", _PRODUCT_ARTIFACTS, ids=lambda p: p.name)
@pytest.mark.parametrize("pat_name", sorted(_BANNED_PATTERNS.keys()))
def test_product_surface_file_is_clean_10c(artifact_path: Path, pat_name: str):
    assert artifact_path.is_file(), f"missing product-surface artifact: {artifact_path}"
    text = artifact_path.read_text(encoding="utf-8")
    scrubbed = _scrub_allowed(text)
    pat = _BANNED_PATTERNS[pat_name]
    m = pat.search(scrubbed)
    assert m is None, (
        f"{artifact_path.name} leaked banned pattern {pat_name!r} at "
        f"{m.start()}…{m.end()}: {m.group()!r}"
    )


# ---------------------------------------------------------------------------
# 2. 10C DTO blob — no banned tokens.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["ko", "en"])
@pytest.mark.parametrize("pat_name", sorted(_BANNED_PATTERNS.keys()))
def test_all_product_dtos_are_clean_10c(lang: str, pat_name: str):
    blob = _all_dtos_blob(lang)
    pat = _BANNED_PATTERNS[pat_name]
    m = pat.search(blob)
    assert m is None, (
        f"DTO blob (lang={lang}) leaked banned pattern {pat_name!r}: {m.group()!r}"
    )


def test_coherence_signature_and_shared_focus_are_preserved():
    """The scrubber must never eat the very fields that prove coherence.

    If the scrubber incorrectly redacts ``COHERENCE_V1`` or the
    fingerprint, cross-surface coherence verification would silently
    break. This test pins both.
    """
    block = build_shared_focus_block(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    after = strip_engineering_ids(block)
    assert after["coherence_signature"]["contract_version"] == "COHERENCE_V1"
    fp_before = block["coherence_signature"]["fingerprint"]
    fp_after = after["coherence_signature"]["fingerprint"]
    assert fp_before == fp_after, (
        f"fingerprint was mutated by strip_engineering_ids: {fp_before!r} vs {fp_after!r}"
    )
    # Fingerprints are exactly 12 lowercase hex chars.
    assert re.fullmatch(r"[0-9a-f]{12}", fp_before) is not None


def test_out_of_scope_response_does_not_echo_flagged_prompt():
    """The pre-LLM guard must not echo the user's advice-prompt body
    into the DTO. Otherwise we'd be letting prompt-injection content
    through the scrubber's outer ring."""
    ctx = _focus_context_card(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    def _llm():
        raise AssertionError("LLM must not be called for out-of-scope")
    prompt = "AAPL 지금 매수하세요 가격 목표 200달러"
    a = scrub_free_text_answer(
        prompt=prompt, context=ctx, conversation_callable=_llm, lang="ko",
    )
    blob = json.dumps(a, ensure_ascii=False)
    assert "매수하세요" not in blob
    assert "200달러" not in blob
    assert "가격 목표" not in blob


# ---------------------------------------------------------------------------
# 3. 10C locale parity (continuity / trust / ask.out_of_scope).
# ---------------------------------------------------------------------------


_FAMILY_PREFIXES_10C: tuple[str, ...] = (
    "product_shell.continuity.",
    "product_shell.trust.",
    "product_shell.ask.out_of_scope.",
)


def _keys_for_prefix(lg: str, pre: str) -> set[str]:
    return {k for k in SHELL[lg] if k.startswith(pre)}


@pytest.mark.parametrize("prefix", _FAMILY_PREFIXES_10C)
def test_locale_10c_family_parity_ko_vs_en(prefix: str):
    ko = _keys_for_prefix("ko", prefix)
    en = _keys_for_prefix("en", prefix)
    assert ko == en, (
        f"{prefix} KO/EN parity broken. "
        f"only_ko={sorted(ko - en)}, only_en={sorted(en - ko)}"
    )


@pytest.mark.parametrize("prefix", _FAMILY_PREFIXES_10C)
def test_locale_10c_family_minimum_coverage(prefix: str):
    ko = _keys_for_prefix("ko", prefix)
    # continuity >= 8, trust >= 5, out_of_scope >= 3.
    expected = {
        "product_shell.continuity.":       8,
        "product_shell.trust.":             5,
        "product_shell.ask.out_of_scope.":  3,
    }[prefix]
    assert len(ko) >= expected, (
        f"expected >={expected} keys under {prefix}, got {len(ko)}: {sorted(ko)}"
    )


def test_locale_10c_values_are_non_empty():
    for lg in ("ko", "en"):
        for pre in _FAMILY_PREFIXES_10C:
            for k in _keys_for_prefix(lg, pre):
                v = SHELL[lg][k]
                assert isinstance(v, str) and v.strip(), (
                    f"empty/non-string locale value: lang={lg} key={k!r}"
                )


# ---------------------------------------------------------------------------
# 4. SHARED_WORDING dictionary is total and flushable through scrubber.
# ---------------------------------------------------------------------------


def test_shared_wording_is_scrubber_safe():
    clean = strip_engineering_ids(SHARED_WORDING)
    for kind in SHARED_WORDING_KINDS:
        for lang in ("ko", "en"):
            body_before = SHARED_WORDING[lang][kind]["body"]
            body_after = clean[lang][kind]["body"]
            assert body_before == body_after, (
                f"scrubber altered SHARED_WORDING[{lang}][{kind}].body"
            )


def test_contract_markers_10c_present():
    blob = _all_dtos_blob("ko")
    for marker in (
        "PRODUCT_TODAY_V1",
        "PRODUCT_RESEARCH_LANDING_V1",
        "PRODUCT_RESEARCH_DEEPDIVE_V1",
        "PRODUCT_REPLAY_V1",
        "PRODUCT_ASK_V1",
        "PRODUCT_ASK_QUICK_V1",
        "COHERENCE_V1",
    ):
        assert marker in blob, f"missing contract marker: {marker}"
