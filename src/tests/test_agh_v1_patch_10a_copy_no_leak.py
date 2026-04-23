"""Patch 10A — Copy & engineering-ID no-leak scanner.

Scope (Product Shell Rebuild v1 workorder §4.3, §4.4):

1. The customer-facing Product Shell artifacts (``static/index.html``,
   ``static/product_shell.js``, ``static/product_shell.css``) may not
   contain engineering identifiers or raw provenance enums.
2. The Product Today DTO served at ``/api/product/today`` with stub
   inputs may not leak those tokens either.
3. The ``product_shell.*`` locale keys must have 1:1 KO↔EN parity.

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
from phase47_runtime.product_shell.view_models import (  # type: ignore
    compose_today_product_dto,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATIC = _REPO_ROOT / "src" / "phase47_runtime" / "static"

# Artifact paths scoped to the customer surface ONLY.
_PRODUCT_ARTIFACTS: tuple[Path, ...] = (
    _STATIC / "index.html",
    _STATIC / "product_shell.js",
    _STATIC / "product_shell.css",
)

# Engineering tokens / provenance enums that must never appear in any
# value served to customers.
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
    "buy_sell_imperative_ko_buy":     re.compile(r"(?<![가-힣])매수하세요"),
    "buy_sell_imperative_ko_sell":    re.compile(r"(?<![가-힣])매도하세요"),
    "buy_sell_imperative_en_buy":     re.compile(r"\b(?:Buy|BUY) now\b"),
    "buy_sell_imperative_en_sell":    re.compile(r"\b(?:Sell|SELL) now\b"),
}

# Allow-list: API path / CSS variable patterns that legitimately contain
# "product_shell" or similar. Anything listed here is a literal SUBSTRING
# permitted even inside the surface artifacts.
_ALLOWED_SUBSTRINGS: tuple[str, ...] = (
    "/api/product/today",
    "product_shell.css",
    "product_shell.js",
    "ps-",          # CSS utility prefix
    "--ps-",        # CSS variable prefix
    "__PS__",       # JS debug hook
)


def _scrub_allowed(text: str) -> str:
    """Remove allow-listed substrings before regex scanning, so e.g. a
    `data-source="live"` doesn't produce false positives against an
    accidentally over-broad allowlist."""
    out = text
    for s in _ALLOWED_SUBSTRINGS:
        out = out.replace(s, "")
    return out


# ---------------------------------------------------------------------------
# 1. Customer surface files — no banned tokens.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("artifact_path", _PRODUCT_ARTIFACTS, ids=lambda p: p.name)
@pytest.mark.parametrize("pat_name", sorted(_BANNED_PATTERNS.keys()))
def test_product_surface_file_is_clean(artifact_path: Path, pat_name: str):
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
# 2. Product Today DTO — no banned tokens surface through composition.
# ---------------------------------------------------------------------------


def _dto_with_mixed_provenance(lang: str) -> dict:
    from phase47_runtime.product_shell.view_models import HORIZON_KEYS
    reg_entries = []
    artifacts = []
    for hz in HORIZON_KEYS:
        reg_entries.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"art_xyz_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
        artifacts.append(SimpleNamespace(
            artifact_id=f"art_xyz_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
    bundle = SimpleNamespace(
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
    spectrum_by_hz = {
        hz: {"ok": True, "rows": [
            {"asset_id": "AAPL", "spectrum_position": 0.6,
             "rank_index": 1, "rank_movement": "up",
             "rationale_summary": "단기 모멘텀 우세",
             "what_changed": "지난 주 대비 상승"},
        ]}
        for hz in HORIZON_KEYS
    }
    return compose_today_product_dto(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_hz,
        lang=lang,
        watchlist_tickers=["AAPL", "NVDA"],
        now_utc="2026-04-23T08:00:00Z",
    )


@pytest.mark.parametrize("lang", ["ko", "en"])
@pytest.mark.parametrize("pat_name", sorted(_BANNED_PATTERNS.keys()))
def test_product_today_dto_is_clean(lang: str, pat_name: str):
    dto = _dto_with_mixed_provenance(lang)
    blob = json.dumps(dto, ensure_ascii=False)
    # DTO is a composed packet — allow-list scrubbing is not applied here
    # because every string in the packet is user-facing.
    pat = _BANNED_PATTERNS[pat_name]
    m = pat.search(blob)
    assert m is None, (
        f"DTO (lang={lang}) leaked banned pattern {pat_name!r}: {m.group()!r}"
    )


def test_dto_contract_marker_present():
    dto = _dto_with_mixed_provenance("ko")
    assert dto.get("contract") == "PRODUCT_TODAY_V1"


# ---------------------------------------------------------------------------
# 3. product_shell.* locale parity.
# ---------------------------------------------------------------------------


def _product_shell_keys(lg: str) -> set[str]:
    return {k for k in SHELL[lg] if k.startswith("product_shell.")}


def test_locale_product_shell_parity_ko_vs_en():
    ko = _product_shell_keys("ko")
    en = _product_shell_keys("en")
    assert ko == en, (
        f"product_shell.* KO/EN parity broken. "
        f"only_ko={sorted(ko - en)}, only_en={sorted(en - ko)}"
    )


def test_locale_product_shell_has_minimum_key_count():
    ko = _product_shell_keys("ko")
    assert len(ko) >= 40, f"expected >=40 product_shell.* keys, got {len(ko)}"


def test_locale_product_shell_values_are_non_empty():
    for lg in ("ko", "en"):
        for k in _product_shell_keys(lg):
            v = SHELL[lg][k]
            assert isinstance(v, str) and v.strip(), (
                f"empty/non-string locale value: lang={lg} key={k!r}"
            )


def test_locale_product_shell_covers_required_families():
    """Every broad family referenced by the shell JS must exist."""
    required_prefixes = (
        "product_shell.nav.",
        "product_shell.trust_strip.",
        "product_shell.glance.",
        "product_shell.hero.",
        "product_shell.stance.",
        "product_shell.confidence.",
        "product_shell.evidence.",
        "product_shell.movers.",
        "product_shell.watchlist.",
        "product_shell.advanced.",
        "product_shell.stubs.",
        "product_shell.error.",
    )
    for lg in ("ko", "en"):
        ks = _product_shell_keys(lg)
        for pre in required_prefixes:
            assert any(k.startswith(pre) for k in ks), (
                f"locale {lg} missing any key for family {pre!r}"
            )
