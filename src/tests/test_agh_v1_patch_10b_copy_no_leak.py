"""Patch 10B — Copy & engineering-ID no-leak scanner (Research/Replay/Ask).

Scope (Product Shell Rebuild v1 Patch 10B workorder):

1. The customer-facing Product Shell artifacts (``static/index.html``,
   ``static/product_shell.js``, ``static/product_shell.css``) must stay
   clean of engineering identifiers, raw provenance enums, *and* the
   new 10B-specific internal tokens (``job_``, ``sandbox_request_id``,
   ``process_governed_prompt``, ``counterfactual_preview_v1``,
   ``sandbox_queue``).
2. The Research / Replay / Ask product DTOs served at
   ``/api/product/{research,replay,ask,ask/quick,requests}`` must
   never leak those tokens either.
3. ``product_shell.research.*`` / ``product_shell.replay.*`` /
   ``product_shell.ask.*`` locale keys must have 1:1 KO↔EN parity.

The internal Ops Cockpit (``static/ops.html`` / ``static/ops.js``) is
deliberately excluded — it is the operator surface and retains
full-fidelity IDs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase47_runtime.phase47e_user_locale import SHELL  # type: ignore
from phase47_runtime.product_shell.view_models_ask import (  # type: ignore
    compose_ask_product_dto,
    compose_quick_answers_dto,
    compose_request_state_dto,
    scrub_free_text_answer,
)
from phase47_runtime.product_shell.view_models_common import (  # type: ignore
    HORIZON_KEYS,
)
from phase47_runtime.product_shell.view_models_replay import (  # type: ignore
    compose_replay_product_dto,
)
from phase47_runtime.product_shell.view_models_research import (  # type: ignore
    compose_research_deepdive_dto,
    compose_research_landing_dto,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATIC = _REPO_ROOT / "src" / "phase47_runtime" / "static"

# Artifact paths scoped to the customer surface ONLY.
_PRODUCT_ARTIFACTS: tuple[Path, ...] = (
    _STATIC / "index.html",
    _STATIC / "product_shell.js",
    _STATIC / "product_shell.css",
)

# Banned patterns extended for 10B. We keep the 10A set and add new 10B
# tokens for the internal sandbox / governance-lineage machinery.
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
    # 10B-specific internal tokens.
    "internal_token_job_id":          re.compile(r"\bjob_[A-Za-z0-9_]{3,}\b"),
    "internal_token_sandbox_rid":     re.compile(r"\bsandbox_request_id\b"),
    "internal_token_governed_prompt": re.compile(r"\bprocess_governed_prompt\b"),
    "internal_token_cf_preview":      re.compile(r"\bcounterfactual_preview_v1\b"),
    "internal_token_sandbox_queue":   re.compile(r"\bsandbox_queue\b"),
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


# ---------------------------------------------------------------------------
# 1. Customer surface files — no banned tokens (including 10B additions).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("artifact_path", _PRODUCT_ARTIFACTS, ids=lambda p: p.name)
@pytest.mark.parametrize("pat_name", sorted(_BANNED_PATTERNS.keys()))
def test_product_surface_file_is_clean_10b(artifact_path: Path, pat_name: str):
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
# 2. Research / Replay / Ask DTOs — no banned tokens.
# ---------------------------------------------------------------------------


def _mixed_bundle():
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
                  "built_at_utc": "2026-04-23T07:30:00Z"},
        as_of_utc="2026-04-23T08:00:00Z",
    )


def _mixed_spectrum():
    return {
        hz: {"ok": True, "rows": [
            {"asset_id": "AAPL", "spectrum_position": 0.6,
             "rank_index": 1, "rank_movement": "up",
             "rationale_summary": "단기 모멘텀 우세",
             "what_changed": "지난 주 대비 상승"},
            {"asset_id": "NVDA", "spectrum_position": -0.3,
             "rank_index": 2, "rank_movement": "down",
             "rationale_summary": "단기 조정",
             "what_changed": "지난 주 대비 하락"},
        ]}
        for hz in HORIZON_KEYS
    }


def _sandbox_followups_sample():
    return [
        {
            "request": {
                "created_at_utc": "2026-04-23T07:00:00Z",
                "payload": {"kind": "validation_rerun"},
            },
            "result": {
                "created_at_utc": "2026-04-23T07:05:00Z",
                "payload": {"outcome": "completed"},
            },
        },
        {
            "request": {
                "created_at_utc": "2026-04-23T07:15:00Z",
                "payload": {"kind": "validation_rerun"},
            },
            "result": None,
        },
    ]


def _all_dtos_blob(lang: str) -> str:
    bundle = _mixed_bundle()
    spec = _mixed_spectrum()
    now = "2026-04-23T08:00:00Z"
    landing = compose_research_landing_dto(
        bundle=bundle, spectrum_by_horizon=spec, lang=lang, now_utc=now,
    )
    deepdive = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang, now_utc=now,
    )
    replay_dto = compose_replay_product_dto(
        bundle=bundle,
        spectrum_by_horizon=spec,
        asset_id="AAPL",
        horizon_key="short",
        lineage=None,
        lang=lang,
        now_utc=now,
    ) if _compose_replay_signature_supports_lineage() else _call_replay_dto(
        bundle=bundle, spec=spec, lang=lang, now=now,
    )
    ask_dto = compose_ask_product_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short",
        followups=_sandbox_followups_sample(), lang=lang, now_utc=now,
    )
    quick_dto = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=spec,
        asset_id="AAPL", horizon_key="short", lang=lang,
    )
    req_dto = compose_request_state_dto(_sandbox_followups_sample(), lang=lang)
    # Degraded free-text answer path.
    ft = scrub_free_text_answer(
        prompt="왜 등급이 올랐나요?",
        context={"horizon_caption": "단기"},
        conversation_callable=lambda: {"ok": False},
        lang=lang,
    )
    return json.dumps(
        {
            "landing": landing,
            "deepdive": deepdive,
            "replay": replay_dto,
            "ask": ask_dto,
            "quick": quick_dto,
            "requests": req_dto,
            "freetext_degraded": ft,
        },
        ensure_ascii=False,
    )


def _compose_replay_signature_supports_lineage() -> bool:
    import inspect
    sig = inspect.signature(compose_replay_product_dto)
    return "lineage" in sig.parameters


def _call_replay_dto(*, bundle, spec, lang: str, now: str):
    kwargs = dict(
        bundle=bundle,
        spectrum_by_horizon=spec,
        asset_id="AAPL",
        horizon_key="short",
        lang=lang,
        now_utc=now,
    )
    import inspect
    sig = inspect.signature(compose_replay_product_dto)
    if "lineage" in sig.parameters:
        kwargs["lineage"] = None
    if "followups" in sig.parameters:
        kwargs["followups"] = _sandbox_followups_sample()
    return compose_replay_product_dto(**kwargs)


@pytest.mark.parametrize("lang", ["ko", "en"])
@pytest.mark.parametrize("pat_name", sorted(_BANNED_PATTERNS.keys()))
def test_all_product_dtos_are_clean_10b(lang: str, pat_name: str):
    blob = _all_dtos_blob(lang)
    pat = _BANNED_PATTERNS[pat_name]
    m = pat.search(blob)
    assert m is None, (
        f"DTO blob (lang={lang}) leaked banned pattern {pat_name!r}: {m.group()!r}"
    )


def test_contract_markers_present():
    blob = _all_dtos_blob("ko")
    for marker in (
        "PRODUCT_RESEARCH_LANDING_V1",
        "PRODUCT_RESEARCH_DEEPDIVE_V1",
        "PRODUCT_REPLAY_V1",
        "PRODUCT_ASK_V1",
        "PRODUCT_ASK_QUICK_V1",
        "PRODUCT_REQUEST_STATE_V1",
    ):
        assert marker in blob, f"missing contract marker: {marker}"


# ---------------------------------------------------------------------------
# 3. product_shell.research / replay / ask locale parity.
# ---------------------------------------------------------------------------


_FAMILY_PREFIXES_10B: tuple[str, ...] = (
    "product_shell.research.",
    "product_shell.replay.",
    "product_shell.ask.",
)


def _keys_for_prefix(lg: str, pre: str) -> set[str]:
    return {k for k in SHELL[lg] if k.startswith(pre)}


@pytest.mark.parametrize("prefix", _FAMILY_PREFIXES_10B)
def test_locale_10b_family_parity_ko_vs_en(prefix: str):
    ko = _keys_for_prefix("ko", prefix)
    en = _keys_for_prefix("en", prefix)
    assert ko == en, (
        f"{prefix} KO/EN parity broken. "
        f"only_ko={sorted(ko - en)}, only_en={sorted(en - ko)}"
    )


@pytest.mark.parametrize("prefix", _FAMILY_PREFIXES_10B)
def test_locale_10b_family_minimum_coverage(prefix: str):
    ko = _keys_for_prefix("ko", prefix)
    assert len(ko) >= 10, (
        f"expected >=10 keys under {prefix}, got {len(ko)}: {sorted(ko)}"
    )


def test_locale_10b_values_are_non_empty():
    for lg in ("ko", "en"):
        for pre in _FAMILY_PREFIXES_10B:
            for k in _keys_for_prefix(lg, pre):
                v = SHELL[lg][k]
                assert isinstance(v, str) and v.strip(), (
                    f"empty/non-string locale value: lang={lg} key={k!r}"
                )
