"""Shared helpers for Product Shell view-model composers.

Patch 10A shipped a single ``view_models.py`` for the Today surface.
Patch 10B split that into one module per surface (Today / Research /
Replay / Ask AI) and lifted the cross-surface helpers into this module
so the invariants stay centralized:

- :func:`strip_engineering_ids` — last-line regex scrub; no DTO should
  ever leave the Product Shell surface without passing through this.
- :func:`spectrum_position_to_grade` / :func:`spectrum_position_to_stance` /
  :func:`horizon_provenance_to_confidence` — atomic mappers from internal
  numerics to product-facing labels.
- :func:`family_alias` — founder-facing family name lookup (never the
  raw engineering family slug).
- :func:`human_relative_time` — timestamp → "방금 갱신" / "3h ago".

Patch 10C (2026-04-23) — product coherence / trust closure. This
module now also holds the cross-surface coherence contract:

- :func:`build_shared_focus_block` — the **single source of truth** for
  ``(asset_id, horizon_key)`` presentation. Today / Research / Replay /
  Ask AI all embed the same block so their grade / stance / confidence /
  family-alias / evidence summary can never drift.
- :func:`compute_coherence_signature` — a deterministic, 12-hex
  fingerprint derived from the focus + evidence. Unit tests assert that
  the four surfaces emit the same signature for the same focus, and the
  Patch 10C runbook stamps it into the evidence JSONs.
- :data:`SHARED_WORDING` — the controlled vocabulary for the ten
  product-language buckets listed in Scope E of the 10C workorder
  (sample / preparing / limited_evidence / production / freshness /
  what_changed / knowable_then / bounded_ask / next_step / out_of_scope).
  Language-contract tests enforce that every surface draws from this
  dictionary rather than ad-hoc strings.

Patch 10A composers (``view_models.py``) re-export the older helpers
under their original underscored names for backwards compatibility;
tests continue to import them from
:mod:`phase47_runtime.product_shell.view_models`.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from metis_brain.bundle import BrainBundleV0


HORIZON_KEYS: tuple[str, ...] = ("short", "medium", "medium_long", "long")


HORIZON_DEFAULT_LABELS: dict[str, dict[str, str]] = {
    "ko": {
        "short":       "오늘~이번 주",
        "medium":      "이번 달",
        "medium_long": "한 분기",
        "long":        "반 년 이상",
    },
    "en": {
        "short":       "today / this week",
        "medium":      "this month",
        "medium_long": "this quarter",
        "long":        "half-year +",
    },
}


HORIZON_CAPTION: dict[str, dict[str, str]] = {
    "ko": {
        "short":       "단기",
        "medium":      "중기",
        "medium_long": "중장기",
        "long":        "장기",
    },
    "en": {
        "short":       "Short",
        "medium":      "Medium",
        "medium_long": "Medium-long",
        "long":        "Long",
    },
}


PROVENANCE_TO_SOURCE_KEY: dict[str, str] = {
    "real_derived":                          "live",
    "real_derived_with_degraded_challenger": "live_with_caveat",
    "template_fallback":                     "sample",
    "insufficient_evidence":                 "preparing",
}


# ---------------------------------------------------------------------------
# Engineering-ID scrubber (last-line defense)
# ---------------------------------------------------------------------------

ENG_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bart_[A-Za-z0-9_]+\b"),
    re.compile(r"\breg_[A-Za-z0-9_]+\b"),
    re.compile(r"\bfactor_[A-Za-z0-9_]+\b"),
    re.compile(r"\bpkt_[A-Za-z0-9_]+\b"),
    re.compile(r"\bjob_[A-Za-z0-9_]+\b"),
    # Patch 11 — overlay + persona-candidate engineering ids.
    re.compile(r"\bovr_[A-Za-z0-9_]+\b"),
    re.compile(r"\bpcp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bpersona_candidate_id\b"),
    re.compile(r"\bpit:demo:[A-Za-z0-9_:\-]+\b"),
    re.compile(
        r"\b(?:registry_entry_id|artifact_id|proposal_packet_id|"
        r"decision_packet_id|replay_lineage_pointer|sandbox_request_id|"
        r"sandbox_result_id|overlay_id|brain_overlay_ids)\b"
    ),
    re.compile(r"\bhorizon_provenance\b"),
    re.compile(
        r"\b(?:real_derived_with_degraded_challenger|real_derived|"
        r"insufficient_evidence|template_fallback)\b"
    ),
    re.compile(r"\bprocess_governed_prompt\b"),
    re.compile(r"\bcounterfactual_preview_v1\b"),
    re.compile(r"\bsandbox_queue\b"),
    re.compile(r"\b[a-zA-Z_]+_v\d+\b"),
)


def strip_engineering_ids(obj: Any) -> Any:
    """Recursively scrub engineering tokens from string *values* in ``obj``.

    Keys are preserved because DTO schemas use product-level names; only
    string values are rewritten. When a token matches, it is replaced
    with ``[redacted]``. On a clean DTO the replacement never fires — the
    scrubber is a last-line defense that CI regression tests also run
    against every freeze artifact.
    """
    if isinstance(obj, str):
        cleaned = obj
        for pat in ENG_ID_PATTERNS:
            cleaned = pat.sub("[redacted]", cleaned)
        return cleaned
    if isinstance(obj, dict):
        return {k: strip_engineering_ids(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_engineering_ids(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(strip_engineering_ids(v) for v in obj)
    return obj


# ---------------------------------------------------------------------------
# Atomic mappers: grade, stance, confidence
# ---------------------------------------------------------------------------


def spectrum_position_to_grade(
    position: float | None,
    *,
    source_key: str,
) -> dict[str, str]:
    """Map a representative ``spectrum_position`` into a grade chip.

    Grade encodes **how confidently the product is willing to speak**
    about this horizon — it combines signal magnitude with evidence
    quality. See ``view_models.py`` Patch 10A notes for the tier logic.
    """
    if source_key == "preparing":
        return {"key": "f", "label": "F"}
    if source_key == "sample":
        return {"key": "d", "label": "D"}
    if position is None:
        return {"key": "c", "label": "C"}
    mag = abs(float(position))
    if source_key == "live_with_caveat" and mag < 0.2:
        return {"key": "c", "label": "C"}
    if mag >= 0.8:
        return {"key": "a_plus", "label": "A+"}
    if mag >= 0.5:
        return {"key": "a", "label": "A"}
    if mag >= 0.2:
        return {"key": "b", "label": "B"}
    return {"key": "c", "label": "C"}


def spectrum_position_to_stance(
    position: float | None,
    *,
    lang: str,
) -> dict[str, str]:
    """Map a representative ``spectrum_position`` into a directional label.

    Stance is direction-only — never an imperative. Symmetric around
    zero and monotonic in position.
    """
    if position is None:
        key = "neutral"
    else:
        p = float(position)
        if p >= 0.5:
            key = "strong_long"
        elif p >= 0.2:
            key = "long"
        elif p > -0.2:
            key = "neutral"
        elif p > -0.5:
            key = "short"
        else:
            key = "strong_short"
    label_ko = {
        "strong_long":  "강한 매수 경향",
        "long":         "매수 경향",
        "neutral":      "중립",
        "short":        "매도 경향",
        "strong_short": "강한 매도 경향",
    }
    label_en = {
        "strong_long":  "Strong long bias",
        "long":         "Long bias",
        "neutral":      "Neutral",
        "short":        "Short bias",
        "strong_short": "Strong short bias",
    }
    label = label_ko.get(key, "") if lang == "ko" else label_en.get(key, "")
    return {"key": key, "label": label}


def horizon_provenance_to_confidence(
    provenance_entry: dict[str, Any] | None,
    *,
    lang: str,
) -> dict[str, str]:
    """Translate a ``horizon_provenance[hz]`` block into a confidence badge.

    The DTO surfaces ``source_key`` for CSS targeting and ``label`` /
    ``tooltip`` for user-visible text. The raw engineering enum
    (``real_derived`` and siblings) is deliberately dropped.
    """
    raw_src = ""
    if provenance_entry is not None and isinstance(provenance_entry, dict):
        raw_src = str(provenance_entry.get("source") or "").strip()
    source_key = PROVENANCE_TO_SOURCE_KEY.get(raw_src, "preparing")
    ko_labels = {
        "live":             ("실데이터 근거",
                             "실제 시장 데이터로 학습된 모델 출력입니다."),
        "live_with_caveat": ("실데이터 근거 (보조 지표 제한)",
                             "실데이터 근거이지만 보조 지표 일부가 기대치에 못 미칩니다."),
        "sample":           ("샘플 시나리오",
                             "실데이터가 아직 충분하지 않아 샘플 시나리오를 보여 드립니다."),
        "preparing":        ("실데이터 준비 중",
                             "이 구간의 실데이터 근거는 수집·학습 중입니다. 제품은 과장된 확신을 드리지 않습니다."),
    }
    en_labels = {
        "live":             ("Live-data evidence",
                             "Model output trained on real market data."),
        "live_with_caveat": ("Live with caveats",
                             "Real-data evidence, but companion signals are below threshold."),
        "sample":           ("Sample scenario",
                             "Live data is not yet sufficient; showing a labelled sample scenario."),
        "preparing":        ("Live data preparing",
                             "Evidence for this horizon is still being gathered. No overconfident claim is made."),
    }
    label_map = ko_labels if lang == "ko" else en_labels
    label, tooltip = label_map.get(source_key, label_map["preparing"])
    return {
        "source_key": source_key,
        "label": label,
        "tooltip": tooltip,
    }


# ---------------------------------------------------------------------------
# Spectrum-row helpers
# ---------------------------------------------------------------------------


def best_representative_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the row with the largest ``|spectrum_position|``."""
    best: dict[str, Any] | None = None
    best_mag: float = -1.0
    for r in rows or []:
        try:
            p = float(r.get("spectrum_position") or 0.0)
        except (TypeError, ValueError):
            continue
        mag = abs(p)
        if mag > best_mag:
            best_mag = mag
            best = r
    return best


def family_alias(
    bundle: BrainBundleV0 | None,
    horizon: str,
    *,
    lang: str,
) -> str:
    """Return a customer-facing family name for ``horizon``.

    Uses the founder-facing alias from the active registry entry /
    artifact (``display_family_name_ko`` / ``display_family_name_en``).
    Never returns the raw family slug.
    """
    if bundle is None:
        return ""
    by_art = {a.artifact_id: a for a in bundle.artifacts}
    for ent in bundle.registry_entries:
        if ent.status != "active" or ent.horizon != horizon:
            continue
        art = by_art.get(ent.active_artifact_id)
        if lang == "ko":
            return (
                (getattr(art, "display_family_name_ko", "") if art else "")
                or str(getattr(ent, "display_family_name_ko", "") or "")
                or ""
            )
        return (
            (getattr(art, "display_family_name_en", "") if art else "")
            or str(getattr(ent, "display_family_name_en", "") or "")
            or ""
        )
    return ""


def human_relative_time(utc_str: str, *, now_utc: str, lang: str) -> str:
    """Render a UTC timestamp as a ``X분 전 갱신`` / ``Xm ago`` string.

    Returns ``—`` for malformed or empty input.
    """
    if not utc_str:
        return "—"
    try:
        s = utc_str.replace("Z", "+00:00")
        then = datetime.fromisoformat(s)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        now_s = now_utc.replace("Z", "+00:00")
        now = datetime.fromisoformat(now_s)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return "—"
    delta_s = max(0, int((now - then).total_seconds()))
    mins = delta_s // 60
    hours = mins // 60
    days = hours // 24
    if lang == "ko":
        if days >= 1:
            return f"{days}일 전 갱신"
        if hours >= 1:
            return f"{hours}시간 전 갱신"
        if mins >= 1:
            return f"{mins}분 전 갱신"
        return "방금 갱신"
    if days >= 1:
        return f"{days}d ago"
    if hours >= 1:
        return f"{hours}h ago"
    if mins >= 1:
        return f"{mins}m ago"
    return "just now"


# ---------------------------------------------------------------------------
# Patch 10C — Cross-surface coherence contract
# ---------------------------------------------------------------------------
#
# All four customer surfaces (Today / Research / Replay / Ask AI) answer
# the same focus question — "what does the product think about
# (asset_id, horizon_key) right now?" — from slightly different angles.
# For the Product Shell to feel like *one* product instead of four
# connected pages, the surfaces must agree on:
#
#   - the stance label (direction),
#   - the grade chip (signal magnitude × evidence quality),
#   - the confidence badge (source_key + label + tooltip),
#   - the "what changed" and "strongest support" sentences,
#   - the degraded / sample / preparing wording.
#
# :func:`build_shared_focus_block` is the single helper that composes
# that presentation dictionary from the bundle + spectrum. Every view
# model embeds the result verbatim under ``shared_focus`` so the four
# surfaces cannot drift. The helper also stamps a deterministic
# :func:`compute_coherence_signature` fingerprint that tests use to
# verify the invariant.
#
# The signature is intentionally language-independent: KO and EN DTOs
# for the same focus MUST produce the same signature.


# Buckets 1–3 of Scope E: degraded-family wording. Every surface that
# needs to say "sample / preparing / limited evidence" pulls from here.
SHARED_WORDING: dict[str, dict[str, dict[str, str]]] = {
    "ko": {
        "sample": {
            "title": "샘플 시나리오",
            "body":  "실데이터가 아직 충분하지 않아 샘플 시나리오를 보여 드립니다.",
            "chip":  "샘플",
        },
        "preparing": {
            "title": "실데이터 준비 중",
            "body":  "이 구간의 실데이터 근거는 수집·학습 중입니다. 제품은 과장된 확신을 드리지 않습니다.",
            "chip":  "준비 중",
        },
        "limited_evidence": {
            "title": "근거가 제한적입니다",
            "body":  "이 구간을 지지하는 근거 문장이 아직 풍부하지 않습니다. 결론을 단정하지 않습니다.",
            "chip":  "근거 제한",
        },
        "production": {
            "title": "실데이터 파이프라인",
            "body":  "실제 시장 데이터로 학습된 모델 번들입니다.",
            "chip":  "실데이터",
        },
        "freshness_prefix": {
            "title": "마지막 갱신",
            "body":  "",  # filled by human_relative_time()
            "chip":  "갱신 시각",
        },
        "what_changed": {
            "title": "이번 갱신의 변화",
            "body":  "직전 갱신 대비 유의미한 변화가 기록되지 않았습니다.",
            "chip":  "변화",
        },
        "knowable_then": {
            "title": "그때 알 수 있었던 것",
            "body":  "이 시점의 제품은 아래 근거만 보고 있었습니다. 사후 지식으로 과거를 재해석하지 않습니다.",
            "chip":  "당시 지식",
        },
        "bounded_ask": {
            "title": "노출된 근거 안에서만 답합니다",
            "body":  "Ask AI 는 제품이 이미 보여 드린 근거 범위 안에서만 답변합니다.",
            "chip":  "범위 제한",
        },
        "next_step": {
            "title": "다음 단계",
            "body":  "다음으로 무엇을 열어 보실지 제안 드립니다. 제품은 매수·매도를 권유하지 않습니다.",
            "chip":  "다음 단계",
        },
        "out_of_scope": {
            "title": "노출된 근거 밖의 질문",
            "body":  "이 질문은 제품이 지금 보여 드린 근거 범위 밖에 있어 답변드리지 않습니다.",
            "chip":  "범위 밖",
        },
    },
    "en": {
        "sample": {
            "title": "Sample scenario",
            "body":  "Live data is not yet sufficient; showing a labelled sample scenario.",
            "chip":  "Sample",
        },
        "preparing": {
            "title": "Live data preparing",
            "body":  "Evidence for this horizon is still being gathered. No overconfident claim is made.",
            "chip":  "Preparing",
        },
        "limited_evidence": {
            "title": "Limited evidence",
            "body":  "Supporting evidence for this horizon is still thin — no firm conclusion is drawn.",
            "chip":  "Limited",
        },
        "production": {
            "title": "Live-data pipeline",
            "body":  "Model bundle trained on real market data.",
            "chip":  "Live",
        },
        "freshness_prefix": {
            "title": "Last refreshed",
            "body":  "",
            "chip":  "Refreshed",
        },
        "what_changed": {
            "title": "What changed this refresh",
            "body":  "No material change vs. the previous refresh.",
            "chip":  "Change",
        },
        "knowable_then": {
            "title": "What was knowable then",
            "body":  "At that moment the product could only see the evidence below — we do not re-interpret the past with today's knowledge.",
            "chip":  "Knowable then",
        },
        "bounded_ask": {
            "title": "Answers strictly from surfaced evidence",
            "body":  "Ask AI only answers within the evidence the product has already shown.",
            "chip":  "Bounded",
        },
        "next_step": {
            "title": "Next step",
            "body":  "A short list of what to open next — the product never issues buy or sell guidance.",
            "chip":  "Next",
        },
        "out_of_scope": {
            "title": "Outside surfaced evidence",
            "body":  "This question sits outside the evidence the product has already surfaced, so it is not answered.",
            "chip":  "Out of scope",
        },
    },
}

SHARED_WORDING_KINDS: tuple[str, ...] = (
    "sample",
    "preparing",
    "limited_evidence",
    "production",
    "freshness_prefix",
    "what_changed",
    "knowable_then",
    "bounded_ask",
    "next_step",
    "out_of_scope",
)


# ---------------------------------------------------------------------------
# Patch 11 — residual-score semantics product wording
# ---------------------------------------------------------------------------
#
# Brain layer emits three raw slugs per spectrum row (see
# ``src/metis_brain/spectrum_rows_from_validation_v1.py``):
#
#   - ``residual_score_semantics_version`` e.g. ``residual_semantics_v1``
#   - ``recheck_cadence`` e.g. ``monthly_after_new_filing_or_21_trading_days``
#   - ``invalidation_hint`` e.g. ``spectrum_position_crosses_midline``
#
# None of those slugs should reach the customer surface. The helpers
# below normalize them into two short controlled-vocabulary keys
# (``recheck_cadence_key`` and ``invalidation_hint_kind``) plus user-
# facing KO/EN labels. The short keys feed the coherence signature so
# that a recheck-cadence flip or an invalidation-hint change can be
# detected by the Patch 10C fingerprint mechanism.

RECHECK_CADENCE_KINDS: tuple[str, ...] = (
    "monthly",
    "quarterly",
    "semi_annually",
    "annually",
    "unknown",
)

INVALIDATION_HINT_KINDS: tuple[str, ...] = (
    "pit_fail",
    "confidence_drop",
    "midline_cross",
    "return_reversal",
    "unknown",
)

_RAW_RECHECK_TO_KIND: dict[str, str] = {
    "monthly_after_new_filing_or_21_trading_days":       "monthly",
    "quarterly_after_new_filing_or_63_trading_days":     "quarterly",
    "semi_annually_after_new_filing_or_126_trading_days": "semi_annually",
    "annually_after_new_filing_or_252_trading_days":     "annually",
}

_RAW_INVALIDATION_TO_KIND: dict[str, str] = {
    "factor_validation_pit_fail":         "pit_fail",
    "confidence_band_drops_to_low":       "confidence_drop",
    "spectrum_position_crosses_midline":  "midline_cross",
    "horizon_returns_reverse_sign":       "return_reversal",
}

RESIDUAL_WORDING: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "ko": {
        "recheck": {
            "monthly":       {"label": "한 달 주기로 재점검",
                               "body":  "새 공시·가격 데이터가 들어오면 한 달 주기로 이 근거를 다시 확인합니다."},
            "quarterly":     {"label": "한 분기 주기로 재점검",
                               "body":  "이 구간의 근거는 한 분기 주기 또는 새 공시가 들어올 때 다시 확인됩니다."},
            "semi_annually": {"label": "반 년 주기로 재점검",
                               "body":  "장기 근거는 반 년 주기 또는 새 공시 시점에 재점검됩니다."},
            "annually":      {"label": "한 해 주기로 재점검",
                               "body":  "가장 긴 관점의 근거는 한 해 주기 또는 새 공시 시점에 재점검됩니다."},
            "unknown":       {"label": "재점검 주기 미정",
                               "body":  "이 구간의 재점검 주기가 아직 확정되지 않았습니다."},
        },
        "invalidation": {
            "pit_fail":         {"label": "근거 무효 가능",
                                  "body":  "팩터 검증이 PIT (시점 무결성) 를 통과하지 못하면 이 주장은 다시 검증이 필요합니다."},
            "confidence_drop":  {"label": "신뢰 band 하향",
                                  "body":  "보조 지표의 신뢰 band 가 낮음으로 떨어지면 이 주장은 유보됩니다."},
            "midline_cross":    {"label": "스펙트럼 중앙 교차",
                                  "body":  "스펙트럼 위치가 중앙 (0.5) 을 교차하면 이 방향성은 재검토됩니다."},
            "return_reversal":  {"label": "수익 방향 반전",
                                  "body":  "이 구간의 순수익 방향이 반전되면 주장 전체가 무효 처리됩니다."},
            "unknown":          {"label": "무효 조건 없음",
                                  "body":  "이 주장에 대해 명시적 무효 조건이 설정되어 있지 않습니다."},
        },
    },
    "en": {
        "recheck": {
            "monthly":       {"label": "Rechecks monthly",
                               "body":  "This evidence is rechecked on a monthly cadence or when new filings arrive."},
            "quarterly":     {"label": "Rechecks quarterly",
                               "body":  "This evidence is rechecked quarterly or when new filings arrive."},
            "semi_annually": {"label": "Rechecks semi-annually",
                               "body":  "Long-horizon evidence is rechecked semi-annually or on new filings."},
            "annually":      {"label": "Rechecks annually",
                               "body":  "The longest-view evidence is rechecked annually or on new filings."},
            "unknown":       {"label": "Recheck cadence TBD",
                               "body":  "A recheck cadence has not yet been stamped on this horizon."},
        },
        "invalidation": {
            "pit_fail":         {"label": "Claim may invalidate",
                                  "body":  "If the factor validation fails the PIT (point-in-time) gate this claim needs re-validation."},
            "confidence_drop":  {"label": "Confidence band drop",
                                  "body":  "If the companion confidence band drops to low the claim is held."},
            "midline_cross":    {"label": "Crosses spectrum midline",
                                  "body":  "If the spectrum position crosses the midline (0.5) the direction is re-examined."},
            "return_reversal":  {"label": "Return direction reversal",
                                  "body":  "If this horizon's net return direction reverses the claim is invalidated."},
            "unknown":          {"label": "No explicit invalidation rule",
                                  "body":  "No explicit invalidation rule has been registered for this claim."},
        },
    },
}


def normalize_recheck_cadence(raw: str | None) -> str:
    """Return one of :data:`RECHECK_CADENCE_KINDS` for a raw slug.

    Unknown / empty slugs collapse to ``unknown``. Short keys are used
    for coherence signatures and CSS targeting; they never leak as raw
    engineering strings into customer DTOs.
    """
    if not raw:
        return "unknown"
    key = _RAW_RECHECK_TO_KIND.get(str(raw).strip())
    return key or "unknown"


def normalize_invalidation_hint(raw: str | None) -> str:
    """Return one of :data:`INVALIDATION_HINT_KINDS` for a raw slug."""
    if not raw:
        return "unknown"
    key = _RAW_INVALIDATION_TO_KIND.get(str(raw).strip())
    return key or "unknown"


def residual_wording(axis: str, kind: str, *, lang: str) -> dict[str, str]:
    """Return ``{label, body}`` for ``axis`` ∈ {recheck, invalidation}."""
    lg = "ko" if lang == "ko" else "en"
    table = RESIDUAL_WORDING.get(lg, RESIDUAL_WORDING["en"]).get(axis, {})
    block = table.get(kind) or table.get("unknown") or {"label": "", "body": ""}
    return dict(block)


BRAIN_OVERLAY_KINDS: tuple[str, ...] = (
    "regime_shift",
    "hazard_modifier",
    "invalidation_warning",
    "confidence_adjustment",
    "catalyst_window",
)

BRAIN_OVERLAY_WORDING: dict[str, dict[str, dict[str, str]]] = {
    "ko": {
        "regime_shift": {
            "label": "체제 변화 노트",
            "body":  "시장 체제가 바뀌었을 수 있다는 브레인 비정량 주석이 붙어 있습니다.",
        },
        "hazard_modifier": {
            "label": "위험 가중치 조정",
            "body":  "이 구간의 위험 가중치를 비정량적으로 보정하라는 브레인 주석이 있습니다.",
        },
        "invalidation_warning": {
            "label": "무효 경고",
            "body":  "이 주장이 무효화될 수 있는 조건이 관찰되었다는 브레인 비정량 경고가 있습니다.",
        },
        "confidence_adjustment": {
            "label": "신뢰도 조정 노트",
            "body":  "이 구간의 신뢰도를 비정량적으로 낮추라는 브레인 주석이 있습니다.",
        },
        "catalyst_window": {
            "label": "이벤트 창",
            "body":  "가까운 이벤트 창이 열려 있어 결과가 크게 벌어질 수 있다는 브레인 주석이 있습니다.",
        },
    },
    "en": {
        "regime_shift": {
            "label": "Regime-shift note",
            "body":  "A non-quant brain note flags a possible change in market regime.",
        },
        "hazard_modifier": {
            "label": "Hazard modifier",
            "body":  "A non-quant brain note suggests adjusting the hazard weighting on this horizon.",
        },
        "invalidation_warning": {
            "label": "Invalidation warning",
            "body":  "A non-quant brain note warns that this claim may be invalidated by observed conditions.",
        },
        "confidence_adjustment": {
            "label": "Confidence-adjustment note",
            "body":  "A non-quant brain note recommends tempering the confidence band on this horizon.",
        },
        "catalyst_window": {
            "label": "Catalyst window",
            "body":  "A non-quant brain note flags a near-term event window that may widen outcomes.",
        },
    },
}

_OVERLAY_PRIORITY: tuple[str, ...] = (
    "invalidation_warning",
    "regime_shift",
    "catalyst_window",
    "hazard_modifier",
    "confidence_adjustment",
)


def overlay_note_block(
    *,
    bundle: Any,
    horizon_key: str,
    lang: str,
) -> dict[str, Any] | None:
    """Translate overlays bound to ``horizon_key`` into a user-safe note.

    Returns ``None`` when there are no overlays to show. The block
    exposes only short ``kind_key`` keys (from
    :data:`BRAIN_OVERLAY_KINDS`) and localized labels — overlay ids,
    artifact ids, registry entry ids, and the internal
    ``counter_interpretation_present`` flag are preserved only in a
    boolean form.
    """
    if bundle is None:
        return None
    overlays = list(getattr(bundle, "brain_overlays", None) or [])
    if not overlays:
        return None
    # Map active registry entry id + active artifact id for this horizon.
    active_artifact_id = ""
    active_registry_entry_id = ""
    for ent in getattr(bundle, "registry_entries", []) or []:
        if getattr(ent, "status", "") == "active" and getattr(ent, "horizon", "") == horizon_key:
            active_artifact_id = str(getattr(ent, "active_artifact_id", "") or "")
            active_registry_entry_id = str(getattr(ent, "registry_entry_id", "") or "")
            break
    bound: list[dict[str, Any]] = []
    for ov in overlays:
        if not isinstance(ov, dict):
            continue
        ov_art = str(ov.get("artifact_id") or "")
        ov_reg = str(ov.get("registry_entry_id") or "")
        if active_artifact_id and ov_art == active_artifact_id:
            bound.append(ov)
            continue
        if active_registry_entry_id and ov_reg == active_registry_entry_id:
            bound.append(ov)
    if not bound:
        return None
    lg = "ko" if lang == "ko" else "en"
    table = BRAIN_OVERLAY_WORDING.get(lg, BRAIN_OVERLAY_WORDING["en"])
    items: list[dict[str, Any]] = []
    kinds_present: set[str] = set()
    counter_present = False
    for ov in bound:
        kind = str(ov.get("overlay_type") or "")
        if kind not in BRAIN_OVERLAY_KINDS:
            continue
        kinds_present.add(kind)
        if bool(ov.get("counter_interpretation_present")):
            counter_present = True
        block = table.get(kind) or {"label": "", "body": ""}
        items.append({
            "kind_key": kind,
            "label":    block.get("label", ""),
            "body":     block.get("body", ""),
            "counter_interpretation_present": bool(
                ov.get("counter_interpretation_present")
            ),
        })
    if not items:
        return None
    dominant = ""
    for k in _OVERLAY_PRIORITY:
        if k in kinds_present:
            dominant = k
            break
    return {
        "contract_version":         "BRAIN_OVERLAY_NOTE_V1",
        "count":                    len(items),
        "dominant_kind_key":        dominant,
        "items":                    items,
        "counter_interpretation_present": counter_present,
    }


LONG_HORIZON_TIER_KEYS: tuple[str, ...] = ("production", "limited", "sample")


LONG_HORIZON_SUPPORT_WORDING: dict[str, dict[str, dict[str, str]]] = {
    "ko": {
        "production": {"label": "장기 근거 충분",
                        "body":  "이 장기 관점을 뒷받침할 실데이터 근거가 충분히 쌓여 있습니다."},
        "limited":    {"label": "장기 근거 제한적",
                        "body":  "장기 관점의 실데이터 근거가 아직 제한적입니다. 결론을 단정하지 않습니다."},
        "sample":     {"label": "장기 근거 준비 중",
                        "body":  "장기 관점의 실데이터 근거가 충분하지 않아 제품은 이 구간에서 과장된 확신을 드리지 않습니다."},
    },
    "en": {
        "production": {"label": "Long-view evidence ample",
                        "body":  "Enough real-data evidence backs this long-horizon view."},
        "limited":    {"label": "Long-view evidence limited",
                        "body":  "Long-horizon evidence is still thin. No firm conclusion is drawn."},
        "sample":     {"label": "Long-view evidence preparing",
                        "body":  "Long-horizon evidence is not yet sufficient, so the product avoids overconfident claims on this horizon."},
    },
}


def long_horizon_support_note_block(
    *,
    bundle: Any,
    horizon_key: str,
    lang: str,
) -> dict[str, Any] | None:
    """Return a customer-facing note block for ``long_horizon_support[hz]``.

    Returns ``None`` when the bundle carries no support block for the
    horizon (e.g. short / medium, or legacy bundles). The block never
    exposes ``n_rows`` / ``n_symbols`` / ``coverage_ratio`` numbers —
    those are engineering telemetry. Only the localized tier label and
    body are surfaced.
    """
    if bundle is None:
        return None
    support_map = getattr(bundle, "long_horizon_support_by_horizon", None) or {}
    entry = support_map.get(horizon_key) if isinstance(support_map, dict) else None
    if not isinstance(entry, dict):
        return None
    tier = str(entry.get("tier_key") or "").strip()
    if tier not in ("production", "limited", "sample"):
        return None
    lg = "ko" if lang == "ko" else "en"
    table = LONG_HORIZON_SUPPORT_WORDING.get(lg, LONG_HORIZON_SUPPORT_WORDING["en"])
    block = table.get(tier) or table["sample"]
    return {
        "contract_version": "LONG_HORIZON_SUPPORT_V1",
        "tier_key": tier,
        "label": block["label"],
        "body":  block["body"],
    }


def residual_freshness_block(
    row: dict[str, Any] | None,
    *,
    lang: str,
) -> dict[str, Any] | None:
    """Translate spectrum-row residual slugs into a customer-facing block.

    Returns ``None`` when the row carries no residual info (so composers
    can cleanly omit the block). When present the block exposes only
    normalized short keys and localized labels — the raw engineering
    slugs from the Brain layer never reach the DTO.
    """
    if not isinstance(row, dict):
        return None
    raw_version = str(row.get("residual_score_semantics_version") or "").strip()
    raw_recheck = str(row.get("recheck_cadence") or "").strip()
    raw_hint = str(row.get("invalidation_hint") or "").strip()
    if not (raw_version or raw_recheck or raw_hint):
        return None
    recheck_key = normalize_recheck_cadence(raw_recheck)
    hint_kind = normalize_invalidation_hint(raw_hint)
    recheck_block = residual_wording("recheck", recheck_key, lang=lang)
    hint_block = residual_wording("invalidation", hint_kind, lang=lang)
    return {
        "contract_version":      "RESIDUAL_SEMANTICS_V1",
        "recheck_cadence_key":   recheck_key,
        "recheck_cadence_label": recheck_block["label"],
        "recheck_cadence_body":  recheck_block["body"],
        "invalidation_hint_kind":  hint_kind,
        "invalidation_hint_label": hint_block["label"],
        "invalidation_hint_body":  hint_block["body"],
    }


def shared_wording(kind: str, *, lang: str) -> dict[str, str]:
    """Return the shared KO/EN wording block for ``kind``.

    ``kind`` must be one of :data:`SHARED_WORDING_KINDS`. Unknown keys
    return the ``limited_evidence`` block so the UI never displays an
    empty string even if a caller typos the bucket name.
    """
    lg = "ko" if lang == "ko" else "en"
    table = SHARED_WORDING.get(lg, SHARED_WORDING["en"])
    return dict(table.get(kind) or table["limited_evidence"])


# Mapping from ``source_key`` (returned by
# :func:`horizon_provenance_to_confidence`) to the matching shared wording
# bucket. Used by every composer when rendering the degraded / sample /
# preparing banner so the phrasing cannot drift across surfaces.
SOURCE_KEY_TO_WORDING_KIND: dict[str, str] = {
    "live":             "production",
    "live_with_caveat": "limited_evidence",
    "sample":           "sample",
    "preparing":        "preparing",
}


def _short_hash(*parts: str, length: int = 12) -> str:
    """Stable 12-hex SHA-256 fingerprint of the ``|``-joined parts.

    Length is kept at 12 chars on purpose — long enough to avoid
    collisions across a single bundle's focus space, short enough that
    a human can eyeball equality in evidence JSONs. The hash output is
    lowercase hex, which does not match any of the engineering-ID
    patterns the scrubber enforces.
    """
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _quantize_position(position: float | None) -> float:
    """Round ``position`` to two decimals for signature stability.

    Tiny float jitter (1e-12 drift from a float reload) must not
    invalidate the coherence signature. Two decimals preserve the
    grade/stance tier boundaries at ±0.2 / ±0.5 / ±0.8.
    """
    if position is None:
        return 0.0
    try:
        return round(float(position), 2)
    except (TypeError, ValueError):
        return 0.0


def compute_coherence_signature(
    *,
    asset_id: str,
    horizon_key: str,
    position: float | None,
    grade_key: str,
    stance_key: str,
    source_key: str,
    what_changed: str,
    rationale_summary: str,
    recheck_cadence_key: str = "",
    invalidation_hint_kind: str = "",
    overlay_note_kind_key: str = "",
) -> dict[str, Any]:
    """Deterministic, language-independent cross-surface signature.

    Every Product Shell DTO that opines on ``(asset_id, horizon_key)``
    must embed an identical signature — the Patch 10C coherence test
    compares them pairwise.

    Patch 11 extends the fingerprint with three optional short keys
    (``recheck_cadence_key``, ``invalidation_hint_kind``,
    ``overlay_note_kind_key``) derived from the Brain-layer residual
    semantics and overlays. The contract_version stays ``COHERENCE_V1``
    because the extra inputs are concatenated at the tail and collapse
    to an empty string for pre-11 rows — so a Patch 10C signature with
    no residual/overlay information produces the same fingerprint as
    before.
    """
    tkr = (asset_id or "").upper().strip()
    hz = (horizon_key or "").strip()
    pos_q = _quantize_position(position)
    wc_hash = _short_hash(str(what_changed or "").strip(), length=10)
    rs_hash = _short_hash(str(rationale_summary or "").strip(), length=10)
    rc = str(recheck_cadence_key or "").strip()
    ih = str(invalidation_hint_kind or "").strip()
    ov = str(overlay_note_kind_key or "").strip()
    fp = _short_hash(
        tkr, hz, str(pos_q), str(grade_key or ""), str(stance_key or ""),
        str(source_key or ""), wc_hash, rs_hash, rc, ih, ov,
    )
    return {
        "asset_id":            tkr,
        "horizon_key":         hz,
        "position_quantized":  pos_q,
        "grade_key":           str(grade_key or ""),
        "stance_key":          str(stance_key or ""),
        "source_key":          str(source_key or ""),
        "what_changed_digest": wc_hash,
        "rationale_digest":    rs_hash,
        "recheck_cadence_key":    rc,
        "invalidation_hint_kind": ih,
        "overlay_note_kind_key":  ov,
        "fingerprint":         fp,
        "contract_version":    "COHERENCE_V1",
    }


def _row_for_ticker_on_horizon(
    spectrum_by_horizon: dict[str, dict[str, Any]],
    horizon_key: str,
    ticker: str,
) -> dict[str, Any] | None:
    payload = spectrum_by_horizon.get(horizon_key) or {}
    if payload.get("ok") is False:
        return None
    rows = list(payload.get("rows") or [])
    tkr = (ticker or "").upper().strip()
    if not tkr:
        return None
    for r in rows:
        if str(r.get("asset_id") or "").upper() == tkr:
            return r
    return None


def build_shared_focus_block(
    *,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    asset_id: str,
    horizon_key: str,
    lang: str,
    fallback_to_representative: bool = True,
) -> dict[str, Any]:
    """Compose the single presentation block that every surface embeds.

    This is the Patch 10C coherence contract in code form: given the
    same ``(bundle, spectrum, asset_id, horizon_key)``, every composer
    that calls this function receives the *same* presentation dict.

    When the requested ``asset_id`` is not present on the horizon and
    ``fallback_to_representative`` is True, the block uses the
    horizon's representative row (largest ``|spectrum_position|``) so
    the grade/stance still reflect the horizon's strongest signal.
    ``row_matched`` is set to False in that case so callers can render
    a soft disclaimer if needed.

    The block carries its own ``coherence_signature`` so any DTO it is
    embedded in can expose ``dto["coherence_signature"]`` (or an equivalent
    path) without recomputing the hash.
    """
    hz = (horizon_key or "").strip()
    if hz not in HORIZON_KEYS:
        hz = HORIZON_KEYS[0]
    tkr = (asset_id or "").upper().strip()
    lg = "ko" if lang == "ko" else "en"

    caption = HORIZON_CAPTION.get(lg, HORIZON_CAPTION["en"]).get(hz, "")
    label = HORIZON_DEFAULT_LABELS.get(lg, HORIZON_DEFAULT_LABELS["en"]).get(hz, "")
    fam_name = family_alias(bundle, hz, lang=lg)
    prov_entry = (
        (getattr(bundle, "horizon_provenance", {}) or {}).get(hz)
        if bundle is not None else None
    )
    confidence = horizon_provenance_to_confidence(prov_entry, lang=lg)
    source_key = confidence["source_key"]
    row = _row_for_ticker_on_horizon(spectrum_by_horizon, hz, tkr)
    row_matched = row is not None
    if row is None and fallback_to_representative:
        rows = list((spectrum_by_horizon.get(hz) or {}).get("rows") or [])
        row = best_representative_row(rows)
    try:
        pos = float((row or {}).get("spectrum_position") or 0.0)
    except (TypeError, ValueError):
        pos = 0.0
    grade = spectrum_position_to_grade(pos, source_key=source_key)
    stance = spectrum_position_to_stance(pos, lang=lg)
    what_changed = str((row or {}).get("what_changed") or "").strip()
    rationale = str((row or {}).get("rationale_summary") or "").strip()

    # Evidence lineage summary — a compact cross-surface phrasing of
    # "what the product knows right now about this focus". Every
    # surface can render this verbatim; coherence tests assert equality.
    if source_key == "preparing":
        lineage_bucket = shared_wording("preparing", lang=lg)
        summary_body = lineage_bucket["body"]
    elif source_key == "sample":
        lineage_bucket = shared_wording("sample", lang=lg)
        summary_body = lineage_bucket["body"]
    elif not row_matched:
        lineage_bucket = shared_wording("limited_evidence", lang=lg)
        summary_body = lineage_bucket["body"]
    elif what_changed:
        summary_body = what_changed
    elif rationale:
        summary_body = rationale
    else:
        lineage_bucket = shared_wording("limited_evidence", lang=lg)
        summary_body = lineage_bucket["body"]

    residual_block = residual_freshness_block(row, lang=lg) if row_matched else None

    # Patch 11 — Long-horizon support tier surfacing. For medium_long /
    # long horizons the bundle may carry a ``long_horizon_support`` block
    # describing how much real evidence backs the horizon. We lift the
    # tier label into the focus so callers can render an honest
    # "장기 근거 제한적" / "Long-view evidence limited" note without
    # reaching into the bundle themselves.
    long_support_block = long_horizon_support_note_block(
        bundle=bundle, horizon_key=hz, lang=lg,
    )
    # Patch 11 — Brain overlay note. Surfaces bounded non-quant adjustments
    # (catalyst windows / regime shifts / invalidation warnings ...) in
    # the shared focus so Today / Research / Ask AI can reference the
    # same labels without reaching into ``bundle.brain_overlays``.
    overlay_block = overlay_note_block(
        bundle=bundle, horizon_key=hz, lang=lg,
    )

    signature = compute_coherence_signature(
        asset_id=tkr,
        horizon_key=hz,
        position=pos,
        grade_key=grade["key"],
        stance_key=stance["key"],
        source_key=source_key,
        what_changed=what_changed,
        rationale_summary=rationale,
        recheck_cadence_key=(residual_block or {}).get("recheck_cadence_key", ""),
        invalidation_hint_kind=(residual_block or {}).get("invalidation_hint_kind", ""),
        overlay_note_kind_key=(overlay_block or {}).get("dominant_kind_key", ""),
    )

    block: dict[str, Any] = {
        "asset_id":        tkr,
        "horizon_key":     hz,
        "horizon_caption": caption,
        "horizon_label":   label,
        "family_name":     fam_name,
        "grade":           grade,
        "stance":          stance,
        "confidence":      confidence,
        "position":        round(pos, 4),
        "row_matched":     row_matched,
        "evidence_summary": {
            "what_changed":      what_changed,
            "strongest_support": rationale,
            "body":              summary_body,
        },
        "coherence_signature": signature,
    }
    if residual_block is not None:
        block["residual_freshness"] = residual_block
    if long_support_block is not None:
        block["long_horizon_support"] = long_support_block
    if overlay_block is not None:
        block["overlay_note"] = overlay_block
    return block


def evidence_lineage_summary(focus_block: dict[str, Any]) -> dict[str, str]:
    """Extract the shared "what we know right now" paragraph.

    Returns a dict ready to embed as an ``evidence_lineage_summary``
    field on any surface. Keeping this as a separate helper means we
    can evolve the surface-facing shape without changing every
    composer — the coherence tests pin the *semantic* equivalence, not
    the exact nesting.
    """
    ev = focus_block.get("evidence_summary") or {}
    return {
        "what_changed":      str(ev.get("what_changed") or ""),
        "strongest_support": str(ev.get("strongest_support") or ""),
        "body":              str(ev.get("body") or ""),
        "source_key":        str((focus_block.get("confidence") or {}).get("source_key") or ""),
    }
