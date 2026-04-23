"""Product Shell view-model composers (Patch 10A).

This module is the single translation layer between METIS internal
state (brain bundle, spectrum rows, provenance enums, registry IDs)
and the customer-facing Product Shell DTOs served under
``/api/product/*``.

Product Shell Rebuild v1 non-negotiables enforced here:

- Engineering identifiers NEVER leave this module: any DTO produced
  here is passed through :func:`strip_engineering_ids` as a last-line
  regex scrub. Internal IDs (``art_*``, ``reg_*``, ``factor_*``,
  ``*_v\\d+``, raw packet/registry/artifact IDs, engineering enums
  like ``real_derived`` / ``insufficient_evidence`` / ``template_fallback``)
  are mapped to product-level strings (``live`` / ``live_with_caveat``
  / ``sample`` / ``preparing``) with human-readable labels.
- Honest degraded language — horizons whose provenance is
  ``template_fallback`` or ``insufficient_evidence`` are surfaced as
  "샘플 시나리오" / "실데이터 준비 중" rather than silently rendered as
  if they were live-derived.
- No recommendation / buy / sell imperative copy — stance labels only
  describe direction ("매수 경향" / "중립" / "매도 경향"), never urge
  action.

The module offers two entry points:

- :func:`build_today_product_dto` — convenience wrapper that loads the
  brain bundle + per-horizon spectrum payloads from disk and composes
  the DTO. This is what the ``/api/product/today`` route calls.
- :func:`compose_today_product_dto` — pure composer used by the unit
  tests with synthetic bundle/spectrum inputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from metis_brain.bundle import (
    BrainBundleV0,
    try_load_brain_bundle_v0,
)
from phase47_runtime.phase47e_user_locale import normalize_lang, t
from phase47_runtime.today_spectrum import build_today_spectrum_payload

HORIZON_KEYS: tuple[str, ...] = ("short", "medium", "medium_long", "long")

_HORIZON_DEFAULT_LABELS: dict[str, dict[str, str]] = {
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

_HORIZON_CAPTION: dict[str, dict[str, str]] = {
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

# Provenance enum → product-level tier. Product-facing code never sees
# the raw engineering keys.
_PROVENANCE_TO_SOURCE_KEY: dict[str, str] = {
    "real_derived":                          "live",
    "real_derived_with_degraded_challenger": "live_with_caveat",
    "template_fallback":                     "sample",
    "insufficient_evidence":                 "preparing",
}


# ---------------------------------------------------------------------------
# Engineering-ID scrubber (last-line defense)
# ---------------------------------------------------------------------------

# Patterns that must never appear in DTO values. Keys of the DTO are allowed
# to use product-level names like ``family_name`` / ``source_key`` / ``tier``;
# what we strip is engineering values (free-text tokens, raw IDs).
_ENG_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bart_[A-Za-z0-9_]+\b"),
    re.compile(r"\breg_[A-Za-z0-9_]+\b"),
    re.compile(r"\bfactor_[A-Za-z0-9_]+\b"),
    re.compile(r"\bpkt_[A-Za-z0-9_]+\b"),
    re.compile(r"\bpit:demo:[A-Za-z0-9_:\-]+\b"),
    re.compile(r"\b(?:registry_entry_id|artifact_id|proposal_packet_id|decision_packet_id|replay_lineage_pointer)\b"),
    re.compile(r"\bhorizon_provenance\b"),
    re.compile(r"\b(?:real_derived_with_degraded_challenger|real_derived|insufficient_evidence|template_fallback)\b"),
    re.compile(r"\b[a-zA-Z_]+_v\d+\b"),
)


def strip_engineering_ids(obj: Any) -> Any:
    """Recursively scrub engineering tokens from string values in ``obj``.

    Only *values* are scrubbed — keys are preserved because the DTO schema
    itself uses product-level names. When a token is found, it is replaced
    with ``[redacted]``; this is a defensive measure that should never
    actually fire in a clean DTO (the composers intentionally emit product
    terminology). CI regression in ``test_agh_v1_patch_10a_copy_no_leak``
    asserts that the replacement *never* happens on a live DTO.
    """
    if isinstance(obj, str):
        cleaned = obj
        for pat in _ENG_ID_PATTERNS:
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


@dataclass(frozen=True)
class _GradeBin:
    key: str          # A+ / A / B / C / D / F
    label: str        # user-visible grade text


def _spectrum_position_to_grade(
    position: float | None,
    *,
    source_key: str,
) -> dict[str, str]:
    """Map a representative ``spectrum_position`` into a grade chip.

    Grade encodes **how confidently the product is willing to speak** about
    this horizon — it combines magnitude of the signal with evidence
    quality:

    - F: no reliable evidence (``preparing``) regardless of position.
    - D: sample-only evidence (``sample``) regardless of position.
    - C: real evidence with caveats AND near-neutral position.
    - B: real evidence, moderate conviction (|pos| >= 0.2).
    - A: real evidence, strong conviction (|pos| >= 0.5).
    - A+: real evidence, very strong conviction (|pos| >= 0.8).

    Neutral stances (|pos| < 0.2) can still be B/A when the real-evidence
    source is ``live`` — but in practice a neutral reading with live
    evidence is represented as C (honest about how little the signal
    discriminates). Hence a neutral live reading returns C, not A.
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


def _spectrum_position_to_stance(
    position: float | None,
    *,
    lang: str,
) -> dict[str, str]:
    """Map a representative ``spectrum_position`` into a directional label.

    Stance describes direction only — never urges action. The chosen
    taxonomy is symmetric around zero and monotonic in position.
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


def _horizon_provenance_to_confidence(
    provenance_entry: dict[str, Any] | None,
    *,
    lang: str,
) -> dict[str, str]:
    """Translate a ``horizon_provenance[hz]`` block into a confidence badge.

    The DTO carries ``source_key`` for machine-readable CSS targeting and
    ``label`` / ``tooltip`` for user-visible text. The raw engineering
    enum (``real_derived`` etc.) is deliberately dropped.
    """
    raw_src = ""
    if provenance_entry is not None and isinstance(provenance_entry, dict):
        raw_src = str(provenance_entry.get("source") or "").strip()
    source_key = _PROVENANCE_TO_SOURCE_KEY.get(raw_src, "preparing")
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


def _best_representative_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the row with the largest ``|spectrum_position|`` — this is the
    model's strongest statement in the horizon and drives grade/stance.
    """
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


def _family_alias(
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


def _sparkline_points(
    rows: list[dict[str, Any]],
    *,
    source_key: str,
    representative_position: float | None,
) -> dict[str, Any]:
    """Synthesize a compact sparkline series from spectrum positions.

    For horizons with real evidence we plot the sorted-by-rank positions
    (top-N) so the sparkline traces "how strongly the model is speaking
    across the top of the distribution". For degraded horizons we return
    an empty envelope so the UI renders a muted placeholder.
    """
    if source_key in ("preparing",):
        return {"points": [], "direction": "neutral"}
    pts: list[float] = []
    for r in sorted(
        rows or [],
        key=lambda rr: rr.get("rank_index", 10**9),
    )[:24]:
        try:
            pts.append(round(float(r.get("spectrum_position") or 0.0), 4))
        except (TypeError, ValueError):
            continue
    direction = "neutral"
    if representative_position is not None:
        if representative_position >= 0.2:
            direction = "up"
        elif representative_position <= -0.2:
            direction = "down"
    return {"points": pts, "direction": direction}


def _story_sentence(
    *,
    horizon_key: str,
    source_key: str,
    rows_count: int,
    family_name: str,
    representative_position: float | None,
    lang: str,
) -> str:
    """Compose a single-line story for a hero card.

    Story must:
    - never include a buy/sell imperative,
    - be honest about degraded / preparing states,
    - avoid raw factor / family slug tokens.
    """
    hz_label = _HORIZON_CAPTION.get(lang, _HORIZON_CAPTION["en"]).get(horizon_key, "")
    fam = family_name.strip() if family_name else ""
    if source_key == "preparing":
        if lang == "ko":
            return f"{hz_label} 구간은 아직 실데이터가 충분하지 않아 결론을 유보합니다."
        return f"The {hz_label.lower()} horizon is still gathering live evidence; no firm reading yet."
    if source_key == "sample":
        if lang == "ko":
            return f"{hz_label} 구간은 샘플 시나리오 기준으로 보여 드립니다. 실데이터 대체는 순차 적용됩니다."
        return f"The {hz_label.lower()} horizon is shown as a labelled sample; live-data replacement rolls in by horizon."
    mag = abs(representative_position or 0.0)
    if mag >= 0.5:
        tone_ko, tone_en = "뚜렷한", "distinct"
    elif mag >= 0.2:
        tone_ko, tone_en = "완만한", "moderate"
    else:
        tone_ko, tone_en = "약한", "muted"
    fam_phrase_ko = f" ({fam})" if fam else ""
    fam_phrase_en = f" ({fam})" if fam else ""
    if lang == "ko":
        return (
            f"{hz_label} 구간에서{fam_phrase_ko} {tone_ko} 신호가 읽힙니다. "
            f"{rows_count} 개 종목 근거에서 파생된 결과입니다."
        )
    return (
        f"{hz_label} horizon{fam_phrase_en} shows a {tone_en} reading, "
        f"derived from {rows_count} asset rows."
    )


def _evidence_block(
    *,
    representative_row: dict[str, Any] | None,
    rows: list[dict[str, Any]],
    source_key: str,
    confidence: dict[str, str],
    lang: str,
) -> dict[str, str]:
    """Build the three-line evidence block shown in the inline drawer (R1)."""
    if representative_row is None:
        if lang == "ko":
            return {
                "what_changed":      "아직 유의한 변화가 관측되지 않았습니다.",
                "strongest_support": "근거 데이터가 준비 중입니다.",
                "why_confidence":    confidence.get("tooltip", ""),
            }
        return {
            "what_changed":      "No significant change observed yet.",
            "strongest_support": "Evidence data is still being prepared.",
            "why_confidence":    confidence.get("tooltip", ""),
        }
    wc = str(representative_row.get("what_changed") or "").strip()
    rationale = str(representative_row.get("rationale_summary") or "").strip()
    if not wc:
        wc = "직전 갱신 대비 의미 있는 변화가 기록되지 않았습니다." if lang == "ko" else "No material change vs. previous refresh."
    if not rationale:
        rationale = "이 구간을 지지하는 근거 문장이 아직 풍부하지 않습니다." if lang == "ko" else "Supporting evidence for this horizon is still thin."
    return {
        "what_changed":      wc,
        "strongest_support": rationale,
        "why_confidence":    confidence.get("tooltip", ""),
    }


# ---------------------------------------------------------------------------
# Hero card composer
# ---------------------------------------------------------------------------


def _build_hero_card(
    *,
    bundle: BrainBundleV0 | None,
    horizon_key: str,
    spectrum_payload: dict[str, Any] | None,
    lang: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if spectrum_payload and spectrum_payload.get("ok") is not False:
        rows = list(spectrum_payload.get("rows") or [])
    prov_entry: dict[str, Any] | None = None
    if bundle is not None:
        prov_entry = (bundle.horizon_provenance or {}).get(horizon_key)
    confidence = _horizon_provenance_to_confidence(prov_entry, lang=lang)
    source_key = confidence["source_key"]
    rep_row = _best_representative_row(rows)
    rep_pos: float | None = None
    if rep_row is not None:
        try:
            rep_pos = float(rep_row.get("spectrum_position") or 0.0)
        except (TypeError, ValueError):
            rep_pos = None
    grade = _spectrum_position_to_grade(rep_pos, source_key=source_key)
    stance = _spectrum_position_to_stance(rep_pos, lang=lang)
    family_name = _family_alias(bundle, horizon_key, lang=lang)
    rows_count = len(rows)
    story = _story_sentence(
        horizon_key=horizon_key,
        source_key=source_key,
        rows_count=rows_count,
        family_name=family_name,
        representative_position=rep_pos,
        lang=lang,
    )
    sparkline = _sparkline_points(
        rows, source_key=source_key, representative_position=rep_pos
    )
    evidence = _evidence_block(
        representative_row=rep_row,
        rows=rows,
        source_key=source_key,
        confidence=confidence,
        lang=lang,
    )
    cta_primary = {
        "kind":  "open_evidence_drawer",
        "label": "근거 보기" if lang == "ko" else "Open evidence",
    }
    cta_secondary = {
        "kind":     "open_research",
        "label":    "리서치 열기" if lang == "ko" else "Open Research",
        "disabled": True,
        "hint":     ("리서치 표면은 Patch 10B에서 정식 재설계됩니다."
                     if lang == "ko"
                     else "Research surface is being rebuilt in Patch 10B."),
    }
    position_strength = 0.0
    if rep_pos is not None:
        position_strength = max(-1.0, min(1.0, rep_pos))
    return {
        "horizon_key":       horizon_key,
        "horizon_caption":   _HORIZON_CAPTION.get(lang, _HORIZON_CAPTION["en"]).get(horizon_key, ""),
        "horizon_label":     _HORIZON_DEFAULT_LABELS.get(lang, _HORIZON_DEFAULT_LABELS["en"]).get(horizon_key, ""),
        "family_name":       family_name,
        "story":             story,
        "grade":             grade,
        "stance":            stance,
        "confidence":        confidence,
        "position_strength": position_strength,
        "sparkline":         sparkline,
        "evidence":          evidence,
        "cta_primary":       cta_primary,
        "cta_secondary":     cta_secondary,
        "rows_count":        rows_count,
    }


# ---------------------------------------------------------------------------
# Other sections
# ---------------------------------------------------------------------------


def _build_trust_strip(
    bundle: BrainBundleV0 | None,
    *,
    lang: str,
    now_utc: str,
) -> dict[str, Any]:
    meta = dict(getattr(bundle, "metadata", {}) or {}) if bundle else {}
    graduation_tier = str(meta.get("graduation_tier") or "").strip().lower()
    built_at = str(meta.get("built_at_utc") or "").strip()
    prov = dict(getattr(bundle, "horizon_provenance", {}) or {}) if bundle else {}
    has_degraded = False
    has_any_real = False
    for hz in HORIZON_KEYS:
        entry = prov.get(hz) or {}
        src = str(entry.get("source") or "")
        if src in ("real_derived", "real_derived_with_degraded_challenger"):
            has_any_real = True
        if src in ("template_fallback", "insufficient_evidence"):
            has_degraded = True
    if bundle is None:
        tier_kind, tier_label_ko, tier_label_en = "sample", "샘플 데모", "Sample demo"
    elif graduation_tier == "production" and has_any_real and not has_degraded:
        tier_kind, tier_label_ko, tier_label_en = "production", "실데이터 파이프라인", "Live data pipeline"
    elif has_any_real and has_degraded:
        tier_kind, tier_label_ko, tier_label_en = "degraded", "실데이터 + 일부 준비 중", "Live + partial preparing"
    elif has_degraded and not has_any_real:
        tier_kind, tier_label_ko, tier_label_en = "sample", "샘플 데모", "Sample demo"
    else:
        tier_kind, tier_label_ko, tier_label_en = "sample", "샘플 데모", "Sample demo"
    last_built = _human_relative_time(built_at, now_utc=now_utc, lang=lang)
    tier_tooltip_ko = {
        "production": "실제 시장 데이터로 학습된 모델 번들입니다.",
        "degraded":   "일부 구간은 실데이터 근거이지만, 다른 구간은 아직 준비 중입니다. 제품은 과장된 확신을 드리지 않습니다.",
        "sample":     "이 화면은 샘플 시나리오입니다. 실데이터 번들이 준비되면 자동으로 전환됩니다.",
    }
    tier_tooltip_en = {
        "production": "Model bundle trained on real market data.",
        "degraded":   "Some horizons are live-derived; others are still preparing. No overconfident claim.",
        "sample":     "This view is a labelled sample scenario; live evidence will replace it when ready.",
    }
    tooltip = (
        tier_tooltip_ko[tier_kind] if lang == "ko" else tier_tooltip_en[tier_kind]
    )
    label = tier_label_ko if lang == "ko" else tier_label_en
    return {
        "tier_kind":        tier_kind,
        "tier_label":       label,
        "tier_tooltip":     tooltip,
        "last_built_label": last_built,
    }


def _human_relative_time(utc_str: str, *, now_utc: str, lang: str) -> str:
    if not utc_str:
        return "—"
    try:
        # Accept ``Z`` suffix as UTC.
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


def _build_today_at_a_glance(
    hero_cards: list[dict[str, Any]],
    *,
    lang: str,
) -> dict[str, Any]:
    live_cards = [
        hc for hc in hero_cards
        if hc.get("confidence", {}).get("source_key") in ("live", "live_with_caveat")
    ]
    degraded_cards = [
        hc for hc in hero_cards
        if hc.get("confidence", {}).get("source_key") in ("sample", "preparing")
    ]
    if not live_cards and degraded_cards:
        headline = ("오늘은 제품이 과장된 확신을 드릴 수 있는 구간이 없습니다."
                    if lang == "ko" else
                    "Today we cannot responsibly speak with conviction.")
    else:
        strongest = max(
            live_cards,
            key=lambda hc: abs(float(hc.get("position_strength") or 0.0)),
            default=None,
        )
        if strongest is None:
            headline = ("오늘은 중립적인 읽기입니다."
                        if lang == "ko" else "Today reads broadly neutral.")
        else:
            hz_cap = strongest.get("horizon_caption", "")
            stance = strongest.get("stance", {}).get("label", "")
            if lang == "ko":
                headline = f"오늘 가장 또렷한 흐름은 {hz_cap} 구간의 {stance} 입니다."
            else:
                headline = f"Clearest reading today: a {stance.lower()} on the {hz_cap.lower()} horizon."
    bullets: list[str] = []
    for hc in hero_cards:
        src = hc.get("confidence", {}).get("source_key")
        hz_cap = hc.get("horizon_caption", "")
        stance_label = hc.get("stance", {}).get("label", "")
        grade_label = hc.get("grade", {}).get("label", "")
        if src in ("live", "live_with_caveat"):
            if lang == "ko":
                bullets.append(f"{hz_cap}: {stance_label} · 신호 강도 {grade_label}")
            else:
                bullets.append(f"{hz_cap}: {stance_label} — strength {grade_label}")
        elif src == "sample":
            if lang == "ko":
                bullets.append(f"{hz_cap}: 샘플 시나리오 기준")
            else:
                bullets.append(f"{hz_cap}: sample scenario")
        else:
            if lang == "ko":
                bullets.append(f"{hz_cap}: 실데이터 준비 중")
            else:
                bullets.append(f"{hz_cap}: live data preparing")
    degraded_note: str | None = None
    if degraded_cards and live_cards:
        if lang == "ko":
            degraded_note = "일부 구간은 아직 실데이터 근거가 준비 중입니다. 해당 구간은 회색 톤으로 구분됩니다."
        else:
            degraded_note = "Some horizons are still preparing live evidence and are muted in the UI."
    elif degraded_cards and not live_cards:
        if lang == "ko":
            degraded_note = "이 페이지 전체가 샘플/준비 중 상태로 표시됩니다. 실데이터 번들이 준비되면 자동 전환됩니다."
        else:
            degraded_note = "This entire view is in sample / preparing mode until a live bundle is ready."
    return {
        "title":         "오늘의 한 줄 요약" if lang == "ko" else "Today at a glance",
        "headline":      headline,
        "bullets":       bullets,
        "degraded_note": degraded_note,
    }


def _build_selected_movers(
    hero_cards: list[dict[str, Any]],
    spectrum_by_hz: dict[str, dict[str, Any]],
    *,
    lang: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    cand: list[tuple[float, str, dict[str, Any], dict[str, Any]]] = []
    for hc in hero_cards:
        hz = hc["horizon_key"]
        payload = spectrum_by_hz.get(hz) or {}
        rows = list(payload.get("rows") or [])
        for r in rows:
            try:
                mag = abs(float(r.get("spectrum_position") or 0.0))
            except (TypeError, ValueError):
                continue
            if r.get("rank_movement") in ("up", "down") and mag >= 0.2:
                cand.append((mag, str(r.get("asset_id") or ""), r, hc))
    cand.sort(key=lambda tup: tup[0], reverse=True)
    seen_tickers: set[str] = set()
    movers: list[dict[str, Any]] = []
    for mag, ticker, row, hc in cand:
        if not ticker or ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)
        try:
            pos = float(row.get("spectrum_position") or 0.0)
        except (TypeError, ValueError):
            pos = 0.0
        src_key = hc.get("confidence", {}).get("source_key", "preparing")
        grade = _spectrum_position_to_grade(pos, source_key=src_key)
        stance = _spectrum_position_to_stance(pos, lang=lang)
        direction = str(row.get("rank_movement") or "")
        if lang == "ko":
            reason = f"{hc.get('horizon_caption','')} 구간에서 순위 {'상승' if direction == 'up' else '하락'} · {stance['label']}"
        else:
            reason = f"{hc.get('horizon_caption','')} horizon rank {direction} — {stance['label'].lower()}"
        movers.append({
            "ticker":         ticker,
            "horizon_key":    hc["horizon_key"],
            "horizon_label":  hc.get("horizon_label", ""),
            "reason":         reason,
            "grade":          grade,
            "stance":         stance,
        })
        if len(movers) >= limit:
            break
    return movers


def _build_watchlist_strip(
    watchlist_tickers: list[str] | None,
    hero_cards: list[dict[str, Any]],
    spectrum_by_hz: dict[str, dict[str, Any]],
    *,
    lang: str,
) -> dict[str, Any]:
    tickers = list(watchlist_tickers or [])
    out_tickers: list[dict[str, Any]] = []
    for tkr in tickers:
        best_hc: dict[str, Any] | None = None
        best_pos: float | None = None
        for hc in hero_cards:
            hz = hc["horizon_key"]
            payload = spectrum_by_hz.get(hz) or {}
            for r in payload.get("rows") or []:
                if str(r.get("asset_id") or "").upper() != tkr.upper():
                    continue
                try:
                    pos = float(r.get("spectrum_position") or 0.0)
                except (TypeError, ValueError):
                    continue
                if best_pos is None or abs(pos) > abs(best_pos):
                    best_pos = pos
                    best_hc = hc
        if best_hc is None:
            out_tickers.append({
                "ticker":       tkr,
                "grade":        {"key": "f", "label": "—"},
                "stance":       {"key": "neutral", "label": "—"},
                "horizon_key":  "",
                "horizon_caption": "",
                "has_data":     False,
            })
            continue
        src_key = best_hc.get("confidence", {}).get("source_key", "preparing")
        grade = _spectrum_position_to_grade(best_pos, source_key=src_key)
        stance = _spectrum_position_to_stance(best_pos, lang=lang)
        out_tickers.append({
            "ticker":         tkr,
            "grade":          grade,
            "stance":         stance,
            "horizon_key":    best_hc["horizon_key"],
            "horizon_caption":best_hc.get("horizon_caption", ""),
            "has_data":       True,
        })
    return {
        "title":    "내 관심종목" if lang == "ko" else "Your watchlist",
        "caption":  ("관심종목은 참고용 스트립입니다. 상단 히어로 카드가 우선 시각 초점입니다."
                     if lang == "ko" else
                     "Watchlist is a reference strip — hero cards above hold the primary focus."),
        "tickers":  out_tickers,
    }


def _build_stubs(lang: str) -> dict[str, Any]:
    if lang == "ko":
        research = {
            "title":  "리서치 표면은 재설계 중입니다",
            "body":   "히어로 카드에서 바로 근거를 여는 동작이 기본이며, 리서치 페이지는 Patch 10B 에서 제품 톤으로 정식 재설계됩니다.",
            "eta":    "Patch 10B",
        }
        replay = {
            "title":  "리플레이 표면은 재설계 중입니다",
            "body":   "과거 결정과 현재 결정을 비교하는 리플레이는 Patch 10B 에서 제품 계보 뷰로 재설계됩니다.",
            "eta":    "Patch 10B",
        }
        ask_ai = {
            "title":  "Ask AI 는 재설계 중입니다",
            "body":   "내부 작업 로그가 아닌 제품 질의응답 톤으로 Patch 10B 에서 정식 공개됩니다. 현재는 히어로 카드의 근거 보기로 대부분의 질문에 답할 수 있습니다.",
            "eta":    "Patch 10B",
        }
    else:
        research = {
            "title":  "Research surface is being rebuilt",
            "body":   "Opening evidence from a hero card is the default path; a fully redesigned Research surface ships in Patch 10B.",
            "eta":    "Patch 10B",
        }
        replay = {
            "title":  "Replay surface is being rebuilt",
            "body":   "The lineage comparison view will return as a product-toned Replay surface in Patch 10B.",
            "eta":    "Patch 10B",
        }
        ask_ai = {
            "title":  "Ask AI is being rebuilt",
            "body":   "Ask AI will return in Patch 10B in a product-Q&A tone. Most of today's questions can be answered via the evidence drawer on each hero card.",
            "eta":    "Patch 10B",
        }
    return {"research": research, "replay": replay, "ask_ai": ask_ai}


# ---------------------------------------------------------------------------
# Public composers
# ---------------------------------------------------------------------------


def compose_today_product_dto(
    *,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    lang: str = "ko",
    watchlist_tickers: list[str] | None = None,
    now_utc: str,
) -> dict[str, Any]:
    """Pure composer used by unit tests. Always passes its output through
    :func:`strip_engineering_ids` as a final defense.
    """
    lg = normalize_lang(lang) or "ko"
    hero_cards: list[dict[str, Any]] = []
    for hz in HORIZON_KEYS:
        hc = _build_hero_card(
            bundle=bundle,
            horizon_key=hz,
            spectrum_payload=spectrum_by_horizon.get(hz),
            lang=lg,
        )
        hero_cards.append(hc)
    trust_strip = _build_trust_strip(bundle, lang=lg, now_utc=now_utc)
    glance = _build_today_at_a_glance(hero_cards, lang=lg)
    movers = _build_selected_movers(hero_cards, spectrum_by_horizon, lang=lg)
    watchlist = _build_watchlist_strip(
        watchlist_tickers, hero_cards, spectrum_by_horizon, lang=lg
    )
    stubs = _build_stubs(lg)
    dto = {
        "contract":           "PRODUCT_TODAY_V1",
        "lang":               lg,
        "as_of":              (getattr(bundle, "as_of_utc", "") or "") if bundle else "",
        "trust_strip":        trust_strip,
        "today_at_a_glance":  glance,
        "hero_cards":         hero_cards,
        "selected_movers":    movers,
        "watchlist_strip":    watchlist,
        "advanced_disclosure": {
            "label": "고급 세부 보기" if lg == "ko" else "Advanced details",
            "hint":  ("운영자 전용 세부 로그는 /ops 에서 확인할 수 있습니다."
                      if lg == "ko"
                      else "Operator-only detail is available at /ops."),
        },
        "stubs":              stubs,
    }
    return strip_engineering_ids(dto)


def build_today_product_dto(
    *,
    repo_root: Path,
    lang: str = "ko",
    watchlist_tickers: list[str] | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Disk-backed convenience wrapper for the ``/api/product/today`` route."""
    bundle, _errs = try_load_brain_bundle_v0(repo_root)
    spectrum_by_hz: dict[str, dict[str, Any]] = {}
    for hz in HORIZON_KEYS:
        try:
            spectrum_by_hz[hz] = build_today_spectrum_payload(
                repo_root=repo_root, horizon=hz, lang=lang, rows_limit=200
            )
        except Exception as e:  # pragma: no cover — defensive
            spectrum_by_hz[hz] = {"ok": False, "error": f"build_failure:{e.__class__.__name__}"}
    effective_now = now_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return compose_today_product_dto(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_hz,
        lang=lang,
        watchlist_tickers=watchlist_tickers,
        now_utc=effective_now,
    )
