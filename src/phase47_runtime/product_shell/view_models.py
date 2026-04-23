"""Product Shell view-model composers — Today surface (Patch 10A).

Patch 10B moved the shared helpers (strip / grade / stance / confidence /
family alias / horizon constants) into :mod:`.view_models_common` so
they can be reused by Research / Replay / Ask AI composers. This module
now holds only the **Today** composer and its surface-specific helpers.

Product Shell Rebuild v1 non-negotiables enforced here:

- Engineering identifiers NEVER leave this module: any DTO produced
  here is passed through :func:`strip_engineering_ids` as a last-line
  regex scrub.
- Honest degraded language — horizons whose provenance is
  ``template_fallback`` or ``insufficient_evidence`` are surfaced as
  "샘플 시나리오" / "실데이터 준비 중".
- No recommendation / buy / sell imperative copy — stance labels only
  describe direction.

The module offers two entry points:

- :func:`build_today_product_dto` — convenience wrapper that loads the
  brain bundle + per-horizon spectrum payloads from disk and composes
  the DTO. This is what the ``/api/product/today`` route calls.
- :func:`compose_today_product_dto` — pure composer used by the unit
  tests with synthetic bundle/spectrum inputs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metis_brain.bundle import (
    BrainBundleV0,
    try_load_brain_bundle_v0,
)
from phase47_runtime.phase47e_user_locale import normalize_lang
from phase47_runtime.today_spectrum import build_today_spectrum_payload

from .view_models_common import (
    ENG_ID_PATTERNS,
    HORIZON_CAPTION,
    HORIZON_DEFAULT_LABELS,
    HORIZON_KEYS,
    PROVENANCE_TO_SOURCE_KEY,
    best_representative_row,
    family_alias,
    horizon_provenance_to_confidence,
    human_relative_time,
    spectrum_position_to_grade,
    spectrum_position_to_stance,
    strip_engineering_ids,
)

# ---------------------------------------------------------------------------
# Backwards-compatible aliases
# ---------------------------------------------------------------------------
# Patch 10A tests and scripts import the underscored names from this
# module directly. Patch 10B keeps those names working by re-exporting
# them from :mod:`.view_models_common`.

_ENG_ID_PATTERNS = ENG_ID_PATTERNS
_PROVENANCE_TO_SOURCE_KEY = PROVENANCE_TO_SOURCE_KEY
_HORIZON_DEFAULT_LABELS = HORIZON_DEFAULT_LABELS
_HORIZON_CAPTION = HORIZON_CAPTION

_spectrum_position_to_grade = spectrum_position_to_grade
_spectrum_position_to_stance = spectrum_position_to_stance
_horizon_provenance_to_confidence = horizon_provenance_to_confidence
_family_alias = family_alias
_best_representative_row = best_representative_row
_human_relative_time = human_relative_time


# ---------------------------------------------------------------------------
# Today-specific helpers
# ---------------------------------------------------------------------------


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
    hz_label = HORIZON_CAPTION.get(lang, HORIZON_CAPTION["en"]).get(horizon_key, "")
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
    confidence = horizon_provenance_to_confidence(prov_entry, lang=lang)
    source_key = confidence["source_key"]
    rep_row = best_representative_row(rows)
    rep_pos: float | None = None
    if rep_row is not None:
        try:
            rep_pos = float(rep_row.get("spectrum_position") or 0.0)
        except (TypeError, ValueError):
            rep_pos = None
    grade = spectrum_position_to_grade(rep_pos, source_key=source_key)
    stance = spectrum_position_to_stance(rep_pos, lang=lang)
    fam_name = family_alias(bundle, horizon_key, lang=lang)
    rows_count = len(rows)
    story = _story_sentence(
        horizon_key=horizon_key,
        source_key=source_key,
        rows_count=rows_count,
        family_name=fam_name,
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
        "disabled": False,
        "hint":     ("이 구간의 근거·반대 증거를 리서치 페이지에서 열어 보실 수 있습니다."
                     if lang == "ko"
                     else "Open the claim, evidence, and counter-evidence in Research."),
    }
    position_strength = 0.0
    if rep_pos is not None:
        position_strength = max(-1.0, min(1.0, rep_pos))
    return {
        "horizon_key":       horizon_key,
        "horizon_caption":   HORIZON_CAPTION.get(lang, HORIZON_CAPTION["en"]).get(horizon_key, ""),
        "horizon_label":     HORIZON_DEFAULT_LABELS.get(lang, HORIZON_DEFAULT_LABELS["en"]).get(horizon_key, ""),
        "family_name":       fam_name,
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
# Other Today sections
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
    last_built = human_relative_time(built_at, now_utc=now_utc, lang=lang)
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
        grade = spectrum_position_to_grade(pos, source_key=src_key)
        stance = spectrum_position_to_stance(pos, lang=lang)
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
        grade = spectrum_position_to_grade(best_pos, source_key=src_key)
        stance = spectrum_position_to_stance(best_pos, lang=lang)
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
    """Ship Patch 10B surfaces as live panels — no Today-side stubs left."""
    if lang == "ko":
        research = {
            "title": "리서치",
            "body":  "주요 청구와 반대 증거를 horizon 별로 정렬해 보여 드립니다.",
            "eta":   "live",
        }
        replay = {
            "title": "리플레이",
            "body":  "모델 계보와 변경 이력을 타임라인으로 보여 드립니다.",
            "eta":   "live",
        }
        ask_ai = {
            "title": "Ask AI",
            "body":  "노출된 근거 안에서만 답변하는 제품 질의응답 표면입니다.",
            "eta":   "live",
        }
    else:
        research = {
            "title": "Research",
            "body":  "Top claims and counter-evidence sorted by horizon.",
            "eta":   "live",
        }
        replay = {
            "title": "Replay",
            "body":  "Model lineage and changes as a timeline.",
            "eta":   "live",
        }
        ask_ai = {
            "title": "Ask AI",
            "body":  "Product Q&A surface that answers only from surfaced context.",
            "eta":   "live",
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
