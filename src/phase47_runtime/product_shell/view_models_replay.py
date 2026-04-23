"""Product Shell view-model composer — Replay surface (Patch 10B).

The Replay surface is **timeline-first**. The internal
governance-lineage chain (proposals → decisions → applied patches →
spectrum refreshes → sandbox followups) is translated into a
horizontal, plain-language timeline of events, with explicit 30-day+
gap annotations and start/end checkpoints. A trio of scenario cards
(``baseline`` / ``weakened_evidence`` / ``stressed``) sits below the
timeline to let the customer see "what the claim looks like if the
supporting evidence wavers" without needing to click into the raw
counterfactual engine.

Non-negotiables shared with Patch 10A:

- Every DTO leaves via :func:`strip_engineering_ids`.
- No engineering identifiers (``art_*`` / ``reg_*`` / ``factor_*`` /
  ``pkt_*`` / raw provenance enums) ever appear in customer-facing
  fields.
- Honest empty-state copy when the lineage chain is thin or missing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    family_alias,
    horizon_provenance_to_confidence,
    human_relative_time,
    spectrum_position_to_grade,
    spectrum_position_to_stance,
    strip_engineering_ids,
)


GAP_MIN_DAYS = 30


# ---------------------------------------------------------------------------
# Chain → timeline events
# ---------------------------------------------------------------------------


def _safe_iso_to_dt(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _payload_snippet(payload: dict[str, Any], lang: str, max_len: int = 180) -> str:
    """Best-effort human sentence from a governance packet payload.

    Strips known engineering fields and keeps only safe free-text:
    ``change_reason_human`` / ``rationale_free_text`` / ``notes``.
    """
    if not isinstance(payload, dict):
        return ""
    for key in ("change_reason_human", "rationale_free_text", "notes",
                "reason_free_text", "summary"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()[:max_len]
    return ""


def _event_title(kind: str, outcome: str, lang: str) -> str:
    ko = {
        "proposal":                "가설 제안",
        "decision":                "채택 결정",
        "applied_applied":         "시장 데이터에 반영",
        "applied_rolled_back":     "반영 롤백",
        "applied":                 "반영 상태 업데이트",
        "spectrum_refresh":        "스펙트럼 갱신",
        "validation_evaluation":   "검증 평가",
        "sandbox_request":         "사이드 실험 요청",
        "sandbox_result_completed":"사이드 실험 완료",
        "sandbox_result_blocked":  "사이드 실험 보류",
        "sandbox_result":          "사이드 실험 결과",
    }
    en = {
        "proposal":                "Proposal",
        "decision":                "Adoption decision",
        "applied_applied":         "Applied to live state",
        "applied_rolled_back":     "Rolled back",
        "applied":                 "Apply state updated",
        "spectrum_refresh":        "Spectrum refresh",
        "validation_evaluation":   "Validation evaluation",
        "sandbox_request":         "Sandbox ask",
        "sandbox_result_completed":"Sandbox completed",
        "sandbox_result_blocked":  "Sandbox blocked",
        "sandbox_result":          "Sandbox result",
    }
    key = kind
    if kind == "applied" and outcome:
        key = f"applied_{outcome}"
    if kind == "sandbox_result" and outcome:
        key = f"sandbox_result_{outcome}"
    table = ko if lang == "ko" else en
    return table.get(key) or table.get(kind) or kind


def _event_tag(kind: str, outcome: str) -> str:
    """Machine-readable event tag for CSS styling & filtering."""
    if kind == "applied" and outcome == "applied":
        return "applied"
    if kind == "applied" and outcome == "rolled_back":
        return "rolled_back"
    if kind == "spectrum_refresh":
        return "refresh"
    if kind == "sandbox_request":
        return "sandbox"
    if kind == "sandbox_result":
        if outcome in ("blocked_insufficient_inputs", "rejected_kind_not_allowed",
                       "errored", "no_change"):
            return "blocked"
        return "completed"
    if kind == "validation_evaluation":
        return "evaluation"
    if kind == "decision":
        return "decision"
    return "proposal"


def _lineage_chain_to_events(
    chain: list[dict[str, Any]],
    *,
    lang: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for step in chain or []:
        for kind in ("proposal", "decision", "applied",
                     "spectrum_refresh", "validation_promotion_evaluation"):
            pkt = step.get(kind)
            if not isinstance(pkt, dict):
                continue
            ts = str(pkt.get("created_at_utc") or "").strip()
            payload = pkt.get("payload") or {}
            outcome = str(payload.get("outcome") or "").strip()
            label_kind = (
                "validation_evaluation" if kind == "validation_promotion_evaluation"
                else kind
            )
            events.append({
                "kind":    label_kind,
                "ts":      ts,
                "title":   _event_title(label_kind, outcome, lang),
                "body":    _payload_snippet(payload, lang) or (
                    "세부 내용은 운영자 화면에서 확인할 수 있습니다." if lang == "ko"
                    else "Details are available in the operator view."),
                "tag":     _event_tag(label_kind, outcome),
            })
    return events


def _sandbox_followups_to_events(
    followups: list[dict[str, Any]],
    *,
    lang: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pair in followups or []:
        req = pair.get("request") or {}
        res = pair.get("result")
        if isinstance(req, dict):
            ts = str(req.get("created_at_utc") or "").strip()
            out.append({
                "kind":  "sandbox_request",
                "ts":    ts,
                "title": _event_title("sandbox_request", "", lang),
                "body":  _payload_snippet(req.get("payload") or {}, lang) or (
                    "바운디드 사이드 실험이 요청되었습니다." if lang == "ko"
                    else "A bounded side-experiment was requested."),
                "tag":   _event_tag("sandbox_request", ""),
            })
        if isinstance(res, dict):
            ts = str(res.get("created_at_utc") or "").strip()
            payload = res.get("payload") or {}
            outcome = str(payload.get("outcome") or "").strip()
            out.append({
                "kind":  "sandbox_result",
                "ts":    ts,
                "title": _event_title("sandbox_result", outcome, lang),
                "body":  _payload_snippet(payload, lang) or (
                    "사이드 실험 결과가 기록되었습니다." if lang == "ko"
                    else "Side-experiment result recorded."),
                "tag":   _event_tag("sandbox_result", outcome),
            })
    return out


def _annotate_gaps(events: list[dict[str, Any]], *, lang: str) -> list[dict[str, Any]]:
    """Insert gap annotations between consecutive events more than
    ``GAP_MIN_DAYS`` apart. Returns a new list — input is not mutated.

    Events are expected to be sorted ascending by ``ts``.
    """
    out: list[dict[str, Any]] = []
    prev_dt: datetime | None = None
    for ev in events:
        cur_dt = _safe_iso_to_dt(str(ev.get("ts") or ""))
        if prev_dt is not None and cur_dt is not None:
            delta_days = (cur_dt - prev_dt).days
            if delta_days >= GAP_MIN_DAYS:
                if lang == "ko":
                    title = f"{delta_days}일 공백"
                    body = "이 구간 동안 제품은 의미 있는 갱신을 기록하지 않았습니다."
                else:
                    title = f"{delta_days}-day gap"
                    body = "No material updates were recorded during this window."
                out.append({
                    "kind":  "gap",
                    "ts":    prev_dt.isoformat().replace("+00:00", "Z"),
                    "ts_to": cur_dt.isoformat().replace("+00:00", "Z"),
                    "days":  delta_days,
                    "title": title,
                    "body":  body,
                    "tag":   "gap",
                })
        out.append(ev)
        if cur_dt is not None:
            prev_dt = cur_dt
    return out


def _checkpoints(
    events: list[dict[str, Any]],
    *,
    lang: str,
) -> list[dict[str, Any]]:
    ts_events = [e for e in events if e.get("kind") != "gap" and e.get("ts")]
    if not ts_events:
        return []
    first = ts_events[0]
    last = ts_events[-1]
    if lang == "ko":
        start_title = "타임라인 시작"
        start_body = "제품이 이 구간의 근거를 기록하기 시작한 시점입니다."
        end_title = "최근 상태"
        end_body = "지금 이 구간의 제품 상태입니다."
    else:
        start_title = "Timeline start"
        start_body = "The moment the product began recording evidence for this horizon."
        end_title = "Most recent state"
        end_body = "Current product state for this horizon."
    return [
        {"kind": "checkpoint", "position": "start", "ts": first.get("ts"),
         "title": start_title, "body": start_body, "tag": "checkpoint"},
        {"kind": "checkpoint", "position": "end", "ts": last.get("ts"),
         "title": end_title, "body": end_body, "tag": "checkpoint"},
    ]


# ---------------------------------------------------------------------------
# Scenario composer
# ---------------------------------------------------------------------------


def _scenario_card(
    *,
    scenario_kind: str,
    baseline_position: float,
    source_key: str,
    lang: str,
) -> dict[str, Any]:
    """Compose a scenario card shifting ``baseline_position`` by the
    scenario-specific delta, then re-grading/restancing.

    Scenario deltas:
    - ``baseline``: 0.0 (current state)
    - ``weakened_evidence``: shift magnitude DOWN by 0.25 (toward neutral)
    - ``stressed``: mirror-reflect a portion of the magnitude to the
      opposite side, simulating a regime shock.
    """
    b = max(-1.0, min(1.0, float(baseline_position or 0.0)))
    if scenario_kind == "baseline":
        pos = b
    elif scenario_kind == "weakened_evidence":
        if b >= 0:
            pos = max(0.0, b - 0.25)
        else:
            pos = min(0.0, b + 0.25)
    elif scenario_kind == "stressed":
        pos = -0.6 * b - 0.1 * (1.0 if b >= 0 else -1.0)
        pos = max(-1.0, min(1.0, pos))
    else:
        pos = b
    grade = spectrum_position_to_grade(pos, source_key=source_key)
    stance = spectrum_position_to_stance(pos, lang=lang)
    if lang == "ko":
        titles = {
            "baseline":           "기준 시나리오",
            "weakened_evidence":  "근거 약화 시나리오",
            "stressed":           "시장 스트레스 시나리오",
        }
        bodies = {
            "baseline":           "현재 기록된 근거만을 사용해 읽었을 때의 상태입니다.",
            "weakened_evidence":  "동반 지표가 기대치에 못 미칠 경우 제품의 읽기가 어떻게 약해지는지 보여 줍니다.",
            "stressed":           "시장이 급격히 반대 국면으로 전환될 경우를 상정한 시나리오입니다.",
        }
        hint_title = "시나리오는 결정이 아니라 감도 확인입니다."
        hint_body = "어떤 시나리오도 매수/매도 권고가 아닙니다."
    else:
        titles = {
            "baseline":           "Baseline scenario",
            "weakened_evidence":  "Weakened-evidence scenario",
            "stressed":           "Market-stress scenario",
        }
        bodies = {
            "baseline":           "Reading produced from the evidence currently on record.",
            "weakened_evidence":  "How the product's reading shifts when companion signals fall below threshold.",
            "stressed":           "A regime-shock scenario where the market flips sharply.",
        }
        hint_title = "Scenarios are sensitivity checks, not decisions."
        hint_body  = "None of these are buy or sell guidance."
    return {
        "kind":     scenario_kind,
        "title":    titles[scenario_kind],
        "body":     bodies[scenario_kind],
        "grade":    grade,
        "stance":   stance,
        "position": round(pos, 4),
        "hint":     {"title": hint_title, "body": hint_body},
    }


def _build_scenarios(
    *,
    baseline_position: float,
    source_key: str,
    lang: str,
) -> list[dict[str, Any]]:
    return [
        _scenario_card(scenario_kind=k, baseline_position=baseline_position,
                       source_key=source_key, lang=lang)
        for k in ("baseline", "weakened_evidence", "stressed")
    ]


# ---------------------------------------------------------------------------
# Focus resolution
# ---------------------------------------------------------------------------


def _pick_focus_horizon(
    bundle: BrainBundleV0 | None,
    horizon_key: str | None,
) -> str:
    hz = (horizon_key or "").strip()
    if hz in HORIZON_KEYS:
        return hz
    if bundle is None:
        return HORIZON_KEYS[0]
    prov = dict(getattr(bundle, "horizon_provenance", {}) or {})
    for h in HORIZON_KEYS:
        entry = prov.get(h) or {}
        if str(entry.get("source") or "") in ("real_derived",
                                              "real_derived_with_degraded_challenger"):
            return h
    return HORIZON_KEYS[0]


def _active_registry_entry_id(
    bundle: BrainBundleV0 | None,
    horizon: str,
) -> str:
    if bundle is None:
        return ""
    for ent in bundle.registry_entries:
        if ent.status == "active" and ent.horizon == horizon:
            return str(getattr(ent, "registry_entry_id", "") or "")
    return ""


# ---------------------------------------------------------------------------
# Public composer
# ---------------------------------------------------------------------------


def compose_replay_product_dto(
    *,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    lineage: dict[str, Any] | None,
    asset_id: str | None,
    horizon_key: str | None,
    lang: str = "ko",
    now_utc: str,
) -> dict[str, Any]:
    """Compose the Replay DTO. ``lineage`` may be None / empty — the
    composer then returns a clean empty-state envelope.
    """
    lg = normalize_lang(lang) or "ko"
    hz = _pick_focus_horizon(bundle, horizon_key)
    tkr = (asset_id or "").upper().strip()
    caption = HORIZON_CAPTION.get(lg, HORIZON_CAPTION["en"]).get(hz, "")
    label = HORIZON_DEFAULT_LABELS.get(lg, HORIZON_DEFAULT_LABELS["en"]).get(hz, "")
    fam_name = family_alias(bundle, hz, lang=lg)
    prov_entry = (
        (getattr(bundle, "horizon_provenance", {}) or {}).get(hz)
        if bundle is not None else None
    )
    confidence = horizon_provenance_to_confidence(prov_entry, lang=lg)
    source_key = confidence["source_key"]

    # Timeline events from lineage.
    events: list[dict[str, Any]] = []
    total_applied = 0
    total_sandbox = 0
    if isinstance(lineage, dict) and lineage.get("ok", True):
        chain = lineage.get("chain") or []
        events.extend(_lineage_chain_to_events(chain, lang=lg))
        events.extend(_sandbox_followups_to_events(
            lineage.get("sandbox_followups") or [], lang=lg))
        summary = lineage.get("summary") or {}
        try:
            total_applied = int(summary.get("total_applied") or 0)
        except (TypeError, ValueError):
            total_applied = 0
        try:
            total_sandbox = int(summary.get("total_sandbox_requests") or 0)
        except (TypeError, ValueError):
            total_sandbox = 0
    events.sort(key=lambda ev: str(ev.get("ts") or ""))
    checkpoints = _checkpoints(events, lang=lg)
    events_with_gaps = _annotate_gaps(events, lang=lg)

    # Scenarios — use the focus asset's spectrum position when available,
    # else fall back to the best representative row on the horizon.
    rows = list((spectrum_by_horizon.get(hz) or {}).get("rows") or [])
    baseline_pos = 0.0
    row_matched = False
    if tkr:
        for r in rows:
            if str(r.get("asset_id") or "").upper() == tkr:
                try:
                    baseline_pos = float(r.get("spectrum_position") or 0.0)
                except (TypeError, ValueError):
                    baseline_pos = 0.0
                row_matched = True
                break
    if not row_matched:
        rep = best_representative_row(rows)
        if rep is not None:
            try:
                baseline_pos = float(rep.get("spectrum_position") or 0.0)
            except (TypeError, ValueError):
                baseline_pos = 0.0
    scenarios = _build_scenarios(
        baseline_position=baseline_pos,
        source_key=source_key,
        lang=lg,
    )

    # Empty-state handling.
    has_any_events = any(e.get("kind") != "gap" for e in events)
    if not has_any_events:
        if lg == "ko":
            empty_state = {
                "kind": "no_lineage",
                "title": "아직 리플레이할 결정 이력이 충분하지 않습니다.",
                "body":  "이 구간은 최근 생성되었거나 안정적으로 유지 중이라 타임라인에 기록된 변화가 적습니다.",
            }
        else:
            empty_state = {
                "kind": "no_lineage",
                "title": "No replay history yet for this horizon.",
                "body":  "This horizon is either new or has been stable, so the timeline has few entries.",
            }
    else:
        empty_state = None

    built_at = (
        str(getattr(bundle, "metadata", {}).get("built_at_utc") or "")
        if bundle is not None else ""
    )
    last_built_label = human_relative_time(built_at, now_utc=now_utc, lang=lg)

    # Headline.
    if empty_state is not None:
        headline = empty_state["title"]
    else:
        if lg == "ko":
            headline = (
                f"{caption} 구간에서 지금까지 기록된 {sum(1 for e in events if e.get('kind') != 'gap')}개의 결정/갱신을 시간 순으로 보여 드립니다."
            )
        else:
            headline = (
                f"Showing {sum(1 for e in events if e.get('kind') != 'gap')} recorded decisions/updates on the {caption.lower()} horizon, in order."
            )

    dto = {
        "contract":         "PRODUCT_REPLAY_V1",
        "lang":             lg,
        "ok":               True,
        "as_of":            (getattr(bundle, "as_of_utc", "") or "") if bundle else "",
        "last_built_label": last_built_label,
        "focus": {
            "asset_id":        tkr,
            "horizon_key":     hz,
            "horizon_caption": caption,
            "horizon_label":   label,
            "family_name":     fam_name,
            "confidence":      confidence,
            "row_matched":     row_matched,
        },
        "headline":         headline,
        "summary_counts": {
            "total_events":            sum(1 for e in events if e.get("kind") != "gap"),
            "total_applied":           total_applied,
            "total_sandbox_requests":  total_sandbox,
        },
        "checkpoints":      checkpoints,
        "timeline":         events_with_gaps,
        "scenarios":        scenarios,
        "empty_state":      empty_state,
        "advanced_disclosure": {
            "label":    "고급 원본 보기" if lg == "ko" else "Advanced raw view",
            "hint":     ("내부 식별자와 원본 payload는 운영자 화면(/ops)에서 열 수 있습니다."
                         if lg == "ko"
                         else "Internal identifiers and raw payload are available in the operator view (/ops)."),
        },
    }
    return strip_engineering_ids(dto)


# ---------------------------------------------------------------------------
# Public disk-backed builder
# ---------------------------------------------------------------------------


def _try_load_lineage(
    *,
    repo_root: Path,
    registry_entry_id: str,
    horizon: str,
) -> dict[str, Any] | None:
    """Best-effort lineage loader. Returns None if the harness store is
    not available or any dependency errors; callers then render the
    empty-state branch."""
    if not registry_entry_id:
        return None
    try:
        from agentic_harness.runtime import build_store
        from phase47_runtime.traceability_replay import (
            api_governance_lineage_for_registry_entry,
        )
    except Exception:  # pragma: no cover — defensive
        return None
    try:
        store = build_store(use_fixture=False)
    except Exception:
        return None
    try:
        return api_governance_lineage_for_registry_entry(
            store, registry_entry_id=registry_entry_id, horizon=horizon, limit=200
        )
    except Exception:
        return None


def build_replay_product_dto(
    *,
    repo_root: Path,
    asset_id: str | None,
    horizon_key: str | None,
    lang: str = "ko",
    now_utc: str | None = None,
    lineage_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Disk-backed convenience wrapper for the ``/api/product/replay`` route.

    ``lineage_override`` is a test-only hook allowing unit/integration
    tests to inject a synthetic governance lineage payload without
    needing a harness store.
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
    focus_hz = _pick_focus_horizon(bundle, horizon_key)
    if lineage_override is not None:
        lineage = lineage_override
    else:
        rid = _active_registry_entry_id(bundle, focus_hz)
        lineage = _try_load_lineage(
            repo_root=repo_root, registry_entry_id=rid, horizon=focus_hz,
        )
    effective_now = now_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return compose_replay_product_dto(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_hz,
        lineage=lineage,
        asset_id=asset_id,
        horizon_key=focus_hz,
        lang=lang,
        now_utc=effective_now,
    )
