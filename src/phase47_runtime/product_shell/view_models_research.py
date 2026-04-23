"""Product Shell view-model composer — Research surface (Patch 10B).

The Research surface has two presentations the Product Shell can open:

- **Landing** (``presentation="landing"``): the default entry point. A
  horizon-by-horizon grid of the top N claims so the customer can scan
  "what is the product actually saying today across horizons" in a
  single glance. Each tile has a grade chip + stance label + confidence
  badge + a one-line claim summary, and a "자세히 →" soft link that
  deep-links into the deep-dive presentation.
- **Deep dive** (``presentation="deepdive"``): a 3-rail page for a
  specific ``(asset_id, horizon)`` pair. Rail 1 is the claim (the
  product's statement), Rail 2 is the evidence (5 cards: what changed,
  strongest support, counter / companion weakness, missing or
  preparing, peer context), and Rail 3 is the action (bounded next
  steps that refer to other Product Shell surfaces — never a buy/sell
  imperative).

Non-negotiables shared with Patch 10A:

- Every DTO leaves via :func:`strip_engineering_ids`.
- Honest degraded language; no buy/sell imperatives.
- No engineering identifiers (``art_*`` / ``reg_*`` / ``factor_*`` / raw
  provenance enums) ever appear in customer-facing fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metis_brain.bundle import BrainBundleV0, try_load_brain_bundle_v0
from phase47_runtime.phase47e_user_locale import normalize_lang
from phase47_runtime.today_spectrum import build_today_spectrum_payload

from .view_models_common import (
    HORIZON_CAPTION,
    HORIZON_DEFAULT_LABELS,
    HORIZON_KEYS,
    best_representative_row,
    build_shared_focus_block,
    evidence_lineage_summary,
    family_alias,
    horizon_provenance_to_confidence,
    human_relative_time,
    shared_wording,
    spectrum_position_to_grade,
    spectrum_position_to_stance,
    strip_engineering_ids,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rows_for_horizon(
    spectrum_by_horizon: dict[str, dict[str, Any]],
    horizon: str,
) -> list[dict[str, Any]]:
    payload = spectrum_by_horizon.get(horizon) or {}
    if payload.get("ok") is False:
        return []
    return list(payload.get("rows") or [])


def _claim_sentence(
    *,
    horizon_caption: str,
    family_name: str,
    stance_label: str,
    source_key: str,
    lang: str,
) -> str:
    fam = f" · {family_name}" if family_name else ""
    if source_key == "preparing":
        if lang == "ko":
            return f"{horizon_caption} 구간{fam}: 실데이터 준비 중 — 결론을 유보합니다."
        return f"{horizon_caption} horizon{fam}: live data preparing — no firm reading yet."
    if source_key == "sample":
        if lang == "ko":
            return f"{horizon_caption} 구간{fam}: 샘플 시나리오로 보여 드립니다."
        return f"{horizon_caption} horizon{fam}: shown as a labelled sample scenario."
    if lang == "ko":
        return f"{horizon_caption} 구간{fam} — 현재 읽기: {stance_label}."
    return f"{horizon_caption} horizon{fam} — current reading: {stance_label.lower()}."


def _one_line_summary(
    *,
    row: dict[str, Any] | None,
    source_key: str,
    lang: str,
) -> str:
    if row is None:
        if lang == "ko":
            return "아직 충분한 근거가 수집되지 않았습니다."
        return "Insufficient evidence has been gathered yet."
    wc = str(row.get("what_changed") or "").strip()
    rs = str(row.get("rationale_summary") or "").strip()
    if wc:
        return wc
    if rs:
        return rs
    if source_key == "sample":
        return "샘플 시나리오 기반 요약입니다." if lang == "ko" else "Summary based on a sample scenario."
    if source_key == "preparing":
        return "실데이터 근거가 준비 중입니다." if lang == "ko" else "Live evidence is being prepared."
    return "직전 갱신 대비 유의미한 변화가 기록되지 않았습니다." if lang == "ko" else "No material change vs. the previous refresh."


def _tile_for_row(
    *,
    row: dict[str, Any],
    horizon_key: str,
    horizon_caption: str,
    source_key: str,
    confidence: dict[str, str],
    family_name: str,
    lang: str,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    try:
        pos = float(row.get("spectrum_position") or 0.0)
    except (TypeError, ValueError):
        pos = 0.0
    grade = spectrum_position_to_grade(pos, source_key=source_key)
    stance = spectrum_position_to_stance(pos, lang=lang)
    ticker = str(row.get("asset_id") or "").upper()
    summary = _one_line_summary(row=row, source_key=source_key, lang=lang)
    deeplink = {
        "presentation": "deepdive",
        "asset_id":     ticker,
        "horizon_key":  horizon_key,
        "label":        "자세히 보기" if lang == "ko" else "See details",
    }
    shared_focus = build_shared_focus_block(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_horizon,
        asset_id=ticker,
        horizon_key=horizon_key,
        lang=lang,
    )
    return {
        "ticker":         ticker,
        "horizon_key":    horizon_key,
        "horizon_caption": horizon_caption,
        "family_name":    family_name,
        "grade":          grade,
        "stance":         stance,
        "confidence":     confidence,
        "summary":        summary,
        "deeplink":       deeplink,
        "shared_focus":   shared_focus,
        "coherence_signature": shared_focus["coherence_signature"],
    }


def _horizon_column(
    *,
    bundle: BrainBundleV0 | None,
    horizon_key: str,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    lang: str,
    limit: int,
) -> dict[str, Any]:
    prov_entry = (
        (getattr(bundle, "horizon_provenance", {}) or {}).get(horizon_key)
        if bundle is not None else None
    )
    confidence = horizon_provenance_to_confidence(prov_entry, lang=lang)
    source_key = confidence["source_key"]
    caption = HORIZON_CAPTION.get(lang, HORIZON_CAPTION["en"]).get(horizon_key, "")
    label = HORIZON_DEFAULT_LABELS.get(lang, HORIZON_DEFAULT_LABELS["en"]).get(horizon_key, "")
    fam_name = family_alias(bundle, horizon_key, lang=lang)
    rows = _rows_for_horizon(spectrum_by_horizon, horizon_key)
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            -abs(float(r.get("spectrum_position") or 0.0)),
            int(r.get("rank_index") or 10**9),
        ),
    )
    tiles: list[dict[str, Any]] = []
    for r in rows_sorted[:limit]:
        tiles.append(_tile_for_row(
            row=r,
            horizon_key=horizon_key,
            horizon_caption=caption,
            source_key=source_key,
            confidence=confidence,
            family_name=fam_name,
            lang=lang,
            bundle=bundle,
            spectrum_by_horizon=spectrum_by_horizon,
        ))
    empty_state: dict[str, str] | None = None
    if not tiles:
        if source_key == "preparing":
            empty_state = {
                "kind":  "preparing",
                "title": "실데이터 준비 중" if lang == "ko" else "Live data preparing",
                "body":  ("이 구간의 실데이터 근거는 수집·학습 중입니다."
                          if lang == "ko"
                          else "Evidence for this horizon is still being gathered."),
            }
        elif source_key == "sample":
            empty_state = {
                "kind":  "sample",
                "title": "샘플 시나리오" if lang == "ko" else "Sample scenario",
                "body":  ("표시할 종목이 없는 샘플 구간입니다."
                          if lang == "ko"
                          else "Sample horizon with no assets to show."),
            }
        else:
            empty_state = {
                "kind":  "no_candidates",
                "title": "표시할 후보가 없습니다" if lang == "ko" else "No candidates to show",
                "body":  ("이 구간에서 의미 있는 변화가 관측되지 않았습니다."
                          if lang == "ko"
                          else "No material changes observed in this horizon."),
            }
    claim_headline = _claim_sentence(
        horizon_caption=caption,
        family_name=fam_name,
        stance_label=(tiles[0]["stance"]["label"] if tiles else ""),
        source_key=source_key,
        lang=lang,
    )
    return {
        "horizon_key":     horizon_key,
        "horizon_caption": caption,
        "horizon_label":   label,
        "family_name":     fam_name,
        "confidence":      confidence,
        "claim_headline":  claim_headline,
        "tiles":           tiles,
        "empty_state":     empty_state,
    }


# ---------------------------------------------------------------------------
# Landing composer
# ---------------------------------------------------------------------------


def compose_research_landing_dto(
    *,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    lang: str = "ko",
    now_utc: str,
    top_n_per_horizon: int = 3,
) -> dict[str, Any]:
    """Compose the Research landing DTO (horizon grid of top claims)."""
    lg = normalize_lang(lang) or "ko"
    columns: list[dict[str, Any]] = []
    total_tiles = 0
    any_live = False
    any_preparing_or_sample = False
    for hz in HORIZON_KEYS:
        col = _horizon_column(
            bundle=bundle,
            horizon_key=hz,
            spectrum_by_horizon=spectrum_by_horizon,
            lang=lg,
            limit=top_n_per_horizon,
        )
        total_tiles += len(col["tiles"])
        src = col["confidence"]["source_key"]
        if src in ("live", "live_with_caveat"):
            any_live = True
        if src in ("sample", "preparing"):
            any_preparing_or_sample = True
        columns.append(col)
    if total_tiles == 0:
        headline = ("현재 리서치 표면에 표시할 종목이 없습니다."
                    if lg == "ko"
                    else "No claims to surface in Research right now.")
    elif any_live and any_preparing_or_sample:
        headline = ("실데이터 구간과 샘플/준비 중 구간이 혼재되어 있습니다. 배지로 구분됩니다."
                    if lg == "ko"
                    else "Live and sample/preparing horizons are mixed — badges make it explicit.")
    elif any_live:
        headline = ("모든 구간에서 실데이터 근거로 읽고 있습니다."
                    if lg == "ko"
                    else "All horizons are reading from live evidence.")
    else:
        headline = ("지금 표면에는 샘플/준비 중 구간만 보입니다. 실데이터 준비가 완료되면 자동 전환됩니다."
                    if lg == "ko"
                    else "Only sample/preparing horizons visible right now — they will switch automatically.")
    built_at = (
        str(getattr(bundle, "metadata", {}).get("built_at_utc") or "")
        if bundle is not None else ""
    )
    last_built_label = human_relative_time(built_at, now_utc=now_utc, lang=lg)
    # Patch 10C — cross-surface coherence footer: collect all tile
    # signatures so the coherence test can pick any (asset_id,
    # horizon_key) pair and verify that Research / Replay / Ask AI
    # agree on the same focus.
    focus_candidates: list[dict[str, Any]] = []
    for col in columns:
        for t in col["tiles"]:
            focus_candidates.append({
                "asset_id":    t["shared_focus"]["asset_id"],
                "horizon_key": t["shared_focus"]["horizon_key"],
                "signature":   t["shared_focus"]["coherence_signature"],
            })
    dto = {
        "contract":         "PRODUCT_RESEARCH_LANDING_V1",
        "lang":             lg,
        "presentation":     "landing",
        "as_of":            (getattr(bundle, "as_of_utc", "") or "") if bundle else "",
        "last_built_label": last_built_label,
        "headline":         headline,
        "columns":          columns,
        "hint": {
            "title": "리서치 표면은 노출된 근거 안에서만 답합니다." if lg == "ko" else "Research speaks only from surfaced evidence.",
            "body":  ("각 타일의 '자세히 보기' 에서 근거 5장면을 열어 보실 수 있습니다."
                      if lg == "ko"
                      else "Open the 5-card evidence rail from any tile via ‘See details’."),
        },
        # Cross-surface coherence anchors (Patch 10C).
        "focus_candidates": focus_candidates,
        "coherence_signature": (focus_candidates[0]["signature"]
                                if focus_candidates else None),
        "shared_wording": {
            "bounded_ask":      shared_wording("bounded_ask", lang=lg),
            "limited_evidence": shared_wording("limited_evidence", lang=lg),
            "sample":           shared_wording("sample", lang=lg),
            "preparing":        shared_wording("preparing", lang=lg),
        },
    }
    return strip_engineering_ids(dto)


# ---------------------------------------------------------------------------
# Deep-dive composer
# ---------------------------------------------------------------------------


def _find_row_for_ticker(
    spectrum_by_horizon: dict[str, dict[str, Any]],
    horizon: str,
    ticker: str,
) -> dict[str, Any] | None:
    tkr = (ticker or "").upper().strip()
    if not tkr:
        return None
    for r in _rows_for_horizon(spectrum_by_horizon, horizon):
        if str(r.get("asset_id") or "").upper() == tkr:
            return r
    return None


def _companion_rows(
    *,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    active_horizon: str,
    ticker: str,
    lang: str,
) -> list[dict[str, Any]]:
    """Rows for the same asset on the other horizons — gives the customer
    a quick cross-horizon read-across. Used in the counter-evidence card."""
    out: list[dict[str, Any]] = []
    for hz in HORIZON_KEYS:
        if hz == active_horizon:
            continue
        r = _find_row_for_ticker(spectrum_by_horizon, hz, ticker)
        if r is None:
            continue
        try:
            pos = float(r.get("spectrum_position") or 0.0)
        except (TypeError, ValueError):
            pos = 0.0
        hz_cap = HORIZON_CAPTION.get(lang, HORIZON_CAPTION["en"]).get(hz, "")
        stance = spectrum_position_to_stance(pos, lang=lang)
        out.append({
            "horizon_key":     hz,
            "horizon_caption": hz_cap,
            "stance":          stance,
            "position":        round(pos, 4),
        })
    return out


def _peer_rows(
    rows: list[dict[str, Any]],
    ticker: str,
    *,
    source_key: str,
    lang: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Closest neighbors to ``ticker`` by spectrum_position (excluding self)."""
    tkr = (ticker or "").upper()
    target: float | None = None
    for r in rows:
        if str(r.get("asset_id") or "").upper() == tkr:
            try:
                target = float(r.get("spectrum_position") or 0.0)
            except (TypeError, ValueError):
                target = None
            break
    if target is None:
        return []
    scored: list[tuple[float, dict[str, Any]]] = []
    for r in rows:
        sym = str(r.get("asset_id") or "").upper()
        if not sym or sym == tkr:
            continue
        try:
            pos = float(r.get("spectrum_position") or 0.0)
        except (TypeError, ValueError):
            continue
        scored.append((abs(pos - target), r))
    scored.sort(key=lambda t: t[0])
    out: list[dict[str, Any]] = []
    for _d, r in scored[:limit]:
        try:
            pos = float(r.get("spectrum_position") or 0.0)
        except (TypeError, ValueError):
            pos = 0.0
        out.append({
            "ticker":   str(r.get("asset_id") or "").upper(),
            "stance":   spectrum_position_to_stance(pos, lang=lang),
            "grade":    spectrum_position_to_grade(pos, source_key=source_key),
            "position": round(pos, 4),
        })
    return out


def _evidence_cards(
    *,
    row: dict[str, Any] | None,
    companion: list[dict[str, Any]],
    peers: list[dict[str, Any]],
    source_key: str,
    confidence: dict[str, str],
    lang: str,
    overlay_note: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """5-card evidence rail. Each card is a small, self-contained block."""
    # Card 1 — what changed
    if row is None or not str(row.get("what_changed") or "").strip():
        what_changed_body = (
            "직전 갱신 대비 유의미한 변화가 기록되지 않았습니다."
            if lang == "ko" else
            "No material change vs. the previous refresh."
        )
    else:
        what_changed_body = str(row.get("what_changed")).strip()
    card_what_changed = {
        "kind":  "what_changed",
        "title": "이번 갱신의 변화" if lang == "ko" else "What changed this refresh",
        "body":  what_changed_body,
    }
    # Card 2 — strongest support
    rationale = str((row or {}).get("rationale_summary") or "").strip()
    if not rationale:
        rationale = (
            "이 구간을 지지하는 근거 문장이 아직 풍부하지 않습니다."
            if lang == "ko" else
            "Supporting evidence for this horizon is still thin."
        )
    card_support = {
        "kind":  "strongest_support",
        "title": "가장 강한 지지 근거" if lang == "ko" else "Strongest support",
        "body":  rationale,
    }
    # Card 3 — counter / companion weakness (other horizons on same asset)
    if companion:
        disagree = [c for c in companion if c["stance"]["key"] in ("short", "strong_short")]
        if disagree and companion[0]["stance"]["key"] in ("long", "strong_long"):
            if lang == "ko":
                body = "다른 구간의 읽기는 다른 방향을 가리킵니다. 단일 horizon 근거로 단정하지 않습니다."
            else:
                body = "Other horizons point differently — single-horizon evidence is not taken as conclusive."
        else:
            items = ", ".join(
                f"{c['horizon_caption']}: {c['stance']['label']}"
                for c in companion
            )
            body = (
                f"다른 구간 동반 읽기 — {items}." if lang == "ko"
                else f"Companion horizon readings — {items}."
            )
    else:
        body = (
            "다른 구간에서 이 종목의 근거가 충분하지 않습니다. 반대 근거 확인 난이도가 높습니다."
            if lang == "ko" else
            "Other horizons do not hold enough evidence for this asset — counter-check is limited."
        )
    # Patch 11 — append a single overlay-sourced counter sentence when a
    # bound brain overlay flags that a counter-interpretation is present.
    if overlay_note and overlay_note.get("counter_interpretation_present"):
        if lang == "ko":
            overlay_sentence = (
                " 브레인 비정량 주석은 이 주장에 대한 반대 해석이 존재한다고 표시합니다."
            )
        else:
            overlay_sentence = (
                " A non-quant brain note flags that a counter-interpretation "
                "is present for this claim."
            )
        body = (body or "") + overlay_sentence
    card_counter = {
        "kind":  "counter_or_companion",
        "title": "반대/동반 근거" if lang == "ko" else "Counter / companion evidence",
        "body":  body,
    }
    # Card 4 — missing or preparing
    if source_key == "preparing":
        card_missing = {
            "kind":  "missing_or_preparing",
            "title": "이 구간은 실데이터 준비 중" if lang == "ko" else "This horizon is preparing live data",
            "body":  confidence.get("tooltip", ""),
        }
    elif source_key == "sample":
        card_missing = {
            "kind":  "missing_or_preparing",
            "title": "이 구간은 샘플 시나리오" if lang == "ko" else "This horizon is a sample scenario",
            "body":  confidence.get("tooltip", ""),
        }
    elif row is None:
        card_missing = {
            "kind":  "missing_or_preparing",
            "title": "해당 종목 데이터가 비어 있습니다" if lang == "ko" else "No row matched for this asset",
            "body":  ("요청한 종목이 이 구간의 스펙트럼에 포함되지 않았습니다."
                      if lang == "ko"
                      else "The asset was not present in this horizon's spectrum."),
        }
    else:
        card_missing = {
            "kind":  "missing_or_preparing",
            "title": "누락/한계" if lang == "ko" else "Known gaps",
            "body":  ("모든 시장 국면을 모형이 똑같이 잘 설명하지는 못합니다. 극단 국면에서 성능이 떨어질 수 있습니다."
                      if lang == "ko"
                      else "The model does not describe every market regime equally well; extreme regimes can degrade performance."),
        }
    # Card 5 — peers
    if peers:
        peer_lines = ", ".join(p["ticker"] for p in peers)
        body = (
            f"유사한 위치에 있는 종목 — {peer_lines}." if lang == "ko"
            else f"Assets in a similar position — {peer_lines}."
        )
    else:
        body = (
            "근접한 피어 종목을 찾지 못했습니다." if lang == "ko"
            else "No nearby peer assets identified."
        )
    card_peers = {
        "kind":  "peer_context",
        "title": "피어 컨텍스트" if lang == "ko" else "Peer context",
        "body":  body,
        "peers": peers,
    }
    return [card_what_changed, card_support, card_counter, card_missing, card_peers]


def _action_rail(*, ticker: str, horizon_key: str, lang: str) -> list[dict[str, Any]]:
    """Bounded next-step suggestions. Never an imperative — only surface jumps."""
    if lang == "ko":
        return [
            {
                "kind":   "open_replay",
                "label":  "이 구간의 리플레이 열기",
                "hint":   "과거에 어떤 결정이 있었는지 타임라인으로 확인합니다.",
                "target": {"surface": "replay", "asset_id": ticker, "horizon_key": horizon_key},
            },
            {
                "kind":   "ask_ai",
                "label":  "Ask AI 에 이 청구를 질문",
                "hint":   "노출된 근거 안에서만 답변하는 제품 질의응답으로 이동합니다.",
                "target": {"surface": "ask_ai", "asset_id": ticker, "horizon_key": horizon_key, "seed_intent": "explain_claim"},
            },
            {
                "kind":   "back_to_today",
                "label":  "Today로 돌아가기",
                "hint":   "이 종목/구간이 오늘의 전체 읽기에서 어디쯤인지 확인합니다.",
                "target": {"surface": "today"},
            },
        ]
    return [
        {
            "kind":   "open_replay",
            "label":  "Open Replay for this horizon",
            "hint":   "See the past decisions that led to the current reading.",
            "target": {"surface": "replay", "asset_id": ticker, "horizon_key": horizon_key},
        },
        {
            "kind":   "ask_ai",
            "label":  "Ask AI about this claim",
            "hint":   "Jump to the bounded Q&A surface that answers only from surfaced evidence.",
            "target": {"surface": "ask_ai", "asset_id": ticker, "horizon_key": horizon_key, "seed_intent": "explain_claim"},
        },
        {
            "kind":   "back_to_today",
            "label":  "Back to Today",
            "hint":   "See where this asset/horizon sits in today's overall reading.",
            "target": {"surface": "today"},
        },
    ]


def compose_research_deepdive_dto(
    *,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    asset_id: str,
    horizon_key: str,
    lang: str = "ko",
    now_utc: str,
) -> dict[str, Any]:
    """Compose the Research deep-dive DTO for ``(asset_id, horizon_key)``."""
    lg = normalize_lang(lang) or "ko"
    hz = (horizon_key or "").strip()
    tkr = (asset_id or "").upper().strip()
    if hz not in HORIZON_KEYS:
        dto = {
            "contract":       "PRODUCT_RESEARCH_DEEPDIVE_V1",
            "lang":           lg,
            "presentation":   "deepdive",
            "ok":             False,
            "error_kind":     "unknown_horizon",
            "error_message": ("알 수 없는 horizon 입니다." if lg == "ko"
                              else "Unknown horizon."),
        }
        return strip_engineering_ids(dto)
    prov_entry = (
        (getattr(bundle, "horizon_provenance", {}) or {}).get(hz)
        if bundle is not None else None
    )
    confidence = horizon_provenance_to_confidence(prov_entry, lang=lg)
    source_key = confidence["source_key"]
    caption = HORIZON_CAPTION.get(lg, HORIZON_CAPTION["en"]).get(hz, "")
    label = HORIZON_DEFAULT_LABELS.get(lg, HORIZON_DEFAULT_LABELS["en"]).get(hz, "")
    fam_name = family_alias(bundle, hz, lang=lg)
    rows = _rows_for_horizon(spectrum_by_horizon, hz)
    row = _find_row_for_ticker(spectrum_by_horizon, hz, tkr)
    if row is None:
        # Fall back to the horizon's representative row but flag that the
        # requested ticker was not present.
        rep = best_representative_row(rows)
    else:
        rep = row
    try:
        pos = float((rep or {}).get("spectrum_position") or 0.0)
    except (TypeError, ValueError):
        pos = 0.0
    grade = spectrum_position_to_grade(pos, source_key=source_key)
    stance = spectrum_position_to_stance(pos, lang=lg)
    claim = {
        "ticker":         tkr,
        "horizon_key":    hz,
        "horizon_caption": caption,
        "horizon_label":  label,
        "family_name":    fam_name,
        "grade":          grade,
        "stance":         stance,
        "confidence":     confidence,
        "summary":        _claim_sentence(
            horizon_caption=caption,
            family_name=fam_name,
            stance_label=stance["label"],
            source_key=source_key,
            lang=lg,
        ),
        "row_matched":    row is not None,
    }
    companion = _companion_rows(
        spectrum_by_horizon=spectrum_by_horizon,
        active_horizon=hz,
        ticker=tkr,
        lang=lg,
    )
    peers = _peer_rows(rows, tkr, source_key=source_key, lang=lg)
    actions = _action_rail(ticker=tkr, horizon_key=hz, lang=lg)
    built_at = (
        str(getattr(bundle, "metadata", {}).get("built_at_utc") or "")
        if bundle is not None else ""
    )
    last_built_label = human_relative_time(built_at, now_utc=now_utc, lang=lg)
    shared_focus = build_shared_focus_block(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_horizon,
        asset_id=tkr,
        horizon_key=hz,
        lang=lg,
    )
    evidence = _evidence_cards(
        row=row,
        companion=companion,
        peers=peers,
        source_key=source_key,
        confidence=confidence,
        lang=lg,
        overlay_note=shared_focus.get("overlay_note"),
    )
    dto = {
        "contract":         "PRODUCT_RESEARCH_DEEPDIVE_V1",
        "lang":             lg,
        "presentation":     "deepdive",
        "ok":               True,
        "as_of":            (getattr(bundle, "as_of_utc", "") or "") if bundle else "",
        "last_built_label": last_built_label,
        "claim":            claim,
        "evidence":         evidence,
        "actions":          actions,
        "companion":        companion,
        "breadcrumbs":      [
            {"surface": "today",    "label": "Today" if lg == "en" else "Today"},
            {"surface": "research", "label": "Research" if lg == "en" else "리서치"},
            {"surface": "research", "label": caption,
             "target":  {"presentation": "deepdive", "asset_id": tkr, "horizon_key": hz}},
        ],
        # Cross-surface coherence anchors (Patch 10C).
        "shared_focus":          shared_focus,
        "coherence_signature":   shared_focus["coherence_signature"],
        "evidence_lineage_summary": evidence_lineage_summary(shared_focus),
        "shared_wording": {
            "bounded_ask":    shared_wording("bounded_ask",    lang=lg),
            "what_changed":   shared_wording("what_changed",   lang=lg),
            "next_step":      shared_wording("next_step",      lang=lg),
        },
    }
    return strip_engineering_ids(dto)


# ---------------------------------------------------------------------------
# Public disk-backed builder (used by the route layer)
# ---------------------------------------------------------------------------


def build_research_product_dto(
    *,
    repo_root: Path,
    presentation: str,
    asset_id: str | None,
    horizon_key: str | None,
    lang: str = "ko",
    now_utc: str | None = None,
    top_n_per_horizon: int = 3,
) -> dict[str, Any]:
    """Load the brain bundle + spectrum payloads and compose a Research DTO.

    ``presentation`` must be ``landing`` or ``deepdive``. For ``deepdive``,
    ``asset_id`` and ``horizon_key`` are required.
    """
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
    if presentation == "deepdive":
        return compose_research_deepdive_dto(
            bundle=bundle,
            spectrum_by_horizon=spectrum_by_hz,
            asset_id=asset_id or "",
            horizon_key=horizon_key or "",
            lang=lang,
            now_utc=effective_now,
        )
    return compose_research_landing_dto(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_hz,
        lang=lang,
        now_utc=effective_now,
        top_n_per_horizon=top_n_per_horizon,
    )
