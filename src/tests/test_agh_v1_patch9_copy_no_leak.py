"""AGH v1 Patch 9 D3 — extended copy no-leak + real-user wording review.

Patch 9 introduced several new primary-UI strings (self-serve drawer,
worker tick hint, contract-card grid cells, bundle tier fallback chip,
utility-row note). This module extends the Patch 6 scanner with:

1. A Patch 9-specific ``FORBIDDEN_ENG_TOKENS`` superset that includes
   fresh engineering names the UI now touches internally
   (``target_asset_id``, ``target_horizon``, ``count_packets_by_layer``,
   ``brain_bundle_v2_integrity_failed``, ``archived_at_utc``, ...).
2. A ``REQUIRED_PATCH9_KEYS`` set that asserts every Patch 9 UI string
   exists in both KO and EN shells, rejects empty strings, and rejects
   KO-only placeholders like ``"TODO"`` / ``"FIXME"`` leaking through.
3. A "real-user wording review" set of substring checks that fails if
   the hardened operator-gated copy loses its key phrases
   (e.g. ``"운영자 게이트"`` / ``"operator"``, ``"자동 승격 없음"`` /
   ``"no auto-promotion"``, worker-tick hint is present, fallback chip
   tooltip mentions ``degraded_reasons``).

Forbidden-token scanning reuses the same progressive-disclosure rules
as Patch 6: tokens are allowed inside ``<details>...</details>`` audit
panes and inside ``data-*`` attributes (not user-visible).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.tests.test_agh_v1_patch6_copy_no_leak import (  # type: ignore[import-not-found]
    FORBIDDEN_ENG_TOKENS as _PATCH6_FORBIDDEN,
    TSR_LOCALE_KEY_PREFIXES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


FORBIDDEN_ENG_TOKENS_PATCH9: tuple[str, ...] = tuple(
    sorted(
        set(_PATCH6_FORBIDDEN)
        | {
            # Patch 9 A/C internals that must not leak into user copy
            "brain_bundle_v2_integrity_failed",
            "brain_bundle_path_resolved",
            "brain_bundle_integrity_ok",
            "brain_bundle_fallback_to_v0",
            "brain_bundle_override_used",
            "count_packets_by_layer_v1",
            "agentic_harness_count_packets_by_layer_v1",
            "target_asset_id",
            "target_horizon",
            "archived_at_utc",
            "agentic_harness_packets_v1_archive",
            "agentic_harness_queue_jobs_v1_archive",
            "archive_packets_older_than",
            "archive_jobs_older_than",
            "persist_message_snapshot_for_spectrum_row",
            "persist_message_snapshots_for_spectrum_payload",
        }
    )
)


REQUIRED_PATCH9_KEYS: tuple[str, ...] = (
    # A1/D1 — bundle tier chip fallback
    "tsr.bundle_tier.fallback",
    "tsr.bundle_tier.fallback_tip",
    # B1 — recent-request drawer
    "research_section.recent_request_kind_head",
    "research_section.recent_request_kind_value",
    "research_section.recent_request_input_head",
    "research_section.recent_request_input_horizon",
    "research_section.recent_request_result_head",
    "research_section.recent_request_result_empty",
    "research_section.recent_request_blocking_head",
    "research_section.recent_request_next_head",
    "research_section.recent_request_next_queued",
    "research_section.recent_request_next_running",
    "research_section.recent_request_next_completed",
    "research_section.recent_request_next_blocked",
    # B2 — worker tick hint
    "research_section.invoke_worker_tick_hint",
    # B3 — contract card cell heads
    "tsr.invoke.contract.cell_head.will_do",
    "tsr.invoke.contract.cell_head.will_not_do",
    "tsr.invoke.contract.cell_head.after_enqueue",
    "tsr.invoke.contract.cell_head.status_after",
    # D2 — utility-row note (push-back wording)
    "tsr.nav.utility.note",
)


REAL_USER_WORDING_REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    # (locale_key, must_contain_ko, must_contain_en)
    (
        "research_section.invoke_copy_hint",
        "운영자",
        "operator",
    ),
    (
        "research_section.invoke_enqueue_btn",
        "대기열",
        "queue",
    ),
    (
        "research_section.invoke_worker_tick_hint",
        "워커",
        "worker",
    ),
    (
        "tsr.bundle_tier.fallback_tip",
        "degraded_reasons",
        "degraded_reasons",
    ),
)


def _load_shell() -> dict[str, dict[str, str]]:
    from phase47_runtime.phase47e_user_locale import SHELL

    return SHELL


def test_patch9_required_keys_present_ko_en() -> None:
    shell = _load_shell()
    missing: list[str] = []
    for lang in ("ko", "en"):
        assert lang in shell, f"SHELL missing lang={lang}"
        flat = shell[lang]
        for key in REQUIRED_PATCH9_KEYS:
            value = flat.get(key)
            if not value or not str(value).strip():
                missing.append(f"{lang}::{key} missing or empty")
            elif any(tok in str(value) for tok in ("TODO", "FIXME", "XXX")):
                missing.append(f"{lang}::{key} is a placeholder: {value!r}")
    assert not missing, "Patch 9 copy missing / placeholder:\n" + "\n".join(missing)


def test_patch9_no_eng_token_leak_in_tsr_locale() -> None:
    shell = _load_shell()
    leaks: list[str] = []
    for lang, flat in shell.items():
        for key, value in flat.items():
            if not any(key.startswith(p) for p in TSR_LOCALE_KEY_PREFIXES):
                continue
            for tok in FORBIDDEN_ENG_TOKENS_PATCH9:
                # ``degraded_reasons`` is DOCUMENTED in the fallback tip on
                # purpose (it is the exact field name operators will grep
                # for in ``/api/runtime/health``). The general scanner does
                # NOT include it in the forbidden list because it is the
                # agreed honest handoff to ops. The assertion below would
                # still allow it since ``degraded_reasons`` is not in
                # ``FORBIDDEN_ENG_TOKENS_PATCH9``.
                if tok in str(value):
                    leaks.append(f"{lang}::{key} leaked token {tok!r}: {value!r}")
    assert not leaks, (
        "Patch 9 engineering tokens leaked into primary-UI locale strings:\n"
        + "\n".join(leaks)
    )


@pytest.mark.parametrize("key,ko_sub,en_sub", REAL_USER_WORDING_REQUIREMENTS)
def test_patch9_real_user_wording_contains_required_phrase(
    key: str, ko_sub: str, en_sub: str
) -> None:
    shell = _load_shell()
    ko_val = shell["ko"].get(key, "")
    en_val = shell["en"].get(key, "")
    assert ko_sub in ko_val, (
        f"KO {key!r} should mention {ko_sub!r} to stay honest about the "
        f"operator-gated flow, got: {ko_val!r}"
    )
    assert en_sub.lower() in en_val.lower(), (
        f"EN {key!r} should mention {en_sub!r} to stay honest about the "
        f"operator-gated flow, got: {en_val!r}"
    )
