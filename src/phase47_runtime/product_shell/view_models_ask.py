"""Product Shell view-model composer — Ask AI surface (Patch 10B).

Ask AI is a **bounded decision assistant** surface, not a free-form
chatbot. It has three user-visible elements:

1. A *context card* summarizing the current focus (asset / horizon /
   confidence) so the customer knows what the product "sees" when they
   ask a question.
2. Six *quick-action* chips. Each chip is answered deterministically
   from surfaced context only (brain bundle + spectrum) — no LLM call
   is made for these. This is the product's retrieval-grounded
   contract: the chips are what we guarantee a *surfaced* answer for.
3. A *free-text* box that wraps :func:`api_conversation` /
   :func:`process_governed_prompt`. Engineering identifiers are
   scrubbed before the LLM sees the context, and again on the way out.
   When the LLM layer is unavailable or refuses, the surface returns a
   clearly labelled degraded response pointing the customer back to
   surfaced evidence.

A sidebar lists recent *request-state* cards (sandbox ask followups)
so the customer can see that questions they (or the operator) sent
were received, are running, or have blocked/completed — without
exposing any internal packet IDs.
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
    family_alias,
    horizon_provenance_to_confidence,
    human_relative_time,
    spectrum_position_to_grade,
    spectrum_position_to_stance,
    strip_engineering_ids,
)


# ---------------------------------------------------------------------------
# Context card
# ---------------------------------------------------------------------------


def _focus_context_card(
    *,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    asset_id: str,
    horizon_key: str,
    lang: str,
) -> dict[str, Any]:
    hz = (horizon_key or "").strip()
    if hz not in HORIZON_KEYS:
        hz = HORIZON_KEYS[0]
    tkr = (asset_id or "").upper().strip()
    caption = HORIZON_CAPTION.get(lang, HORIZON_CAPTION["en"]).get(hz, "")
    label = HORIZON_DEFAULT_LABELS.get(lang, HORIZON_DEFAULT_LABELS["en"]).get(hz, "")
    fam_name = family_alias(bundle, hz, lang=lang)
    prov_entry = (
        (getattr(bundle, "horizon_provenance", {}) or {}).get(hz)
        if bundle is not None else None
    )
    confidence = horizon_provenance_to_confidence(prov_entry, lang=lang)
    source_key = confidence["source_key"]
    rows = list((spectrum_by_horizon.get(hz) or {}).get("rows") or [])
    row: dict[str, Any] | None = None
    if tkr:
        for r in rows:
            if str(r.get("asset_id") or "").upper() == tkr:
                row = r
                break
    rep = row if row is not None else best_representative_row(rows)
    try:
        pos = float((rep or {}).get("spectrum_position") or 0.0)
    except (TypeError, ValueError):
        pos = 0.0
    grade = spectrum_position_to_grade(pos, source_key=source_key)
    stance = spectrum_position_to_stance(pos, lang=lang)
    if lang == "ko":
        frame = (
            f"지금 Ask AI 는 {caption} 구간" + (f", {tkr} 종목" if tkr else "")
            + " 의 근거 안에서만 답변합니다."
        )
    else:
        frame = (
            f"Ask AI will answer strictly from evidence for the {caption.lower()} horizon"
            + (f" / {tkr}" if tkr else "")
            + "."
        )
    return {
        "asset_id":        tkr,
        "horizon_key":     hz,
        "horizon_caption": caption,
        "horizon_label":   label,
        "family_name":     fam_name,
        "grade":           grade,
        "stance":          stance,
        "confidence":      confidence,
        "frame":           frame,
        "row_matched":     row is not None,
    }


# ---------------------------------------------------------------------------
# Quick actions — deterministic, retrieval-grounded responses
# ---------------------------------------------------------------------------


_QUICK_ACTION_ORDER: tuple[str, ...] = (
    "explain_claim",
    "show_support",
    "show_counter",
    "other_horizons",
    "why_confidence",
    "whats_missing",
)


def _quick_label(intent: str, lang: str) -> str:
    ko = {
        "explain_claim":   "이 청구를 더 설명해 주세요",
        "show_support":    "지지 근거 보여 주세요",
        "show_counter":    "반대 근거는 무엇인가요?",
        "other_horizons":  "다른 구간은 어떻게 읽고 있나요?",
        "why_confidence": "신뢰도는 왜 이 수준인가요?",
        "whats_missing":  "빠진 근거는 무엇인가요?",
    }
    en = {
        "explain_claim":   "Explain this claim",
        "show_support":    "Show the supporting evidence",
        "show_counter":    "What is the counter-evidence?",
        "other_horizons":  "What do other horizons say?",
        "why_confidence": "Why this confidence level?",
        "whats_missing":  "What evidence is missing?",
    }
    return (ko if lang == "ko" else en).get(intent, intent)


def _quick_answer(
    intent: str,
    *,
    context: dict[str, Any],
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    lang: str,
) -> dict[str, Any]:
    """Produce a structured answer for a quick-action intent.

    Shape mirrors the free-text answer: ``{claim, evidence, insufficiency}``
    where each field is a list of strings.
    """
    hz = context["horizon_key"]
    tkr = context["asset_id"]
    caption = context["horizon_caption"]
    fam = context.get("family_name") or ""
    stance_label = context["stance"]["label"]
    conf_label = context["confidence"]["label"]
    conf_tip = context["confidence"]["tooltip"]
    src_key = context["confidence"]["source_key"]
    rows = list((spectrum_by_horizon.get(hz) or {}).get("rows") or [])
    row: dict[str, Any] | None = None
    if tkr:
        for r in rows:
            if str(r.get("asset_id") or "").upper() == tkr:
                row = r
                break
    rationale = str((row or {}).get("rationale_summary") or "").strip()
    wc = str((row or {}).get("what_changed") or "").strip()

    def _pair(ko: str, en: str) -> str:
        return ko if lang == "ko" else en

    claim: list[str] = []
    evidence: list[str] = []
    insufficiency: list[str] = []

    if intent == "explain_claim":
        claim.append(_pair(
            f"{caption} 구간의 현재 읽기는 {stance_label} 입니다.",
            f"The {caption.lower()} horizon currently reads: {stance_label.lower()}.",
        ))
        if fam:
            claim.append(_pair(
                f"이 신호는 {fam} 계열 모델에서 나온 것입니다.",
                f"The signal originates from the {fam} model family.",
            ))
        if rationale:
            evidence.append(rationale)
        if wc:
            evidence.append(_pair(f"변화: {wc}", f"Change: {wc}"))
        if not evidence:
            insufficiency.append(_pair(
                "이 종목/구간에 대해 표시할 상세 근거 문장이 아직 풍부하지 않습니다.",
                "Detailed narrative evidence for this asset/horizon is still thin.",
            ))
    elif intent == "show_support":
        if rationale:
            evidence.append(rationale)
        else:
            insufficiency.append(_pair(
                "이 종목/구간에 대해 표시할 지지 근거 문장이 아직 풍부하지 않습니다.",
                "Supporting evidence narrative is still thin for this asset/horizon.",
            ))
        if src_key == "sample":
            insufficiency.append(_pair(
                "이 구간은 샘플 시나리오 기준이라 실데이터 기반 지지 근거는 제한적입니다.",
                "This horizon is running on a sample scenario, so live-evidence support is limited.",
            ))
        elif src_key == "preparing":
            insufficiency.append(_pair(
                "이 구간은 실데이터 근거를 수집 중이라 지지 문장을 아직 제시해 드리지 않습니다.",
                "Live evidence for this horizon is still being gathered.",
            ))
    elif intent == "show_counter":
        # Counter-evidence = the opposite-direction spectrum reading
        # for the same asset on other horizons, plus a general caveat.
        other_readings: list[str] = []
        for other in HORIZON_KEYS:
            if other == hz:
                continue
            for r in (spectrum_by_horizon.get(other) or {}).get("rows") or []:
                if str(r.get("asset_id") or "").upper() != tkr:
                    continue
                try:
                    p = float(r.get("spectrum_position") or 0.0)
                except (TypeError, ValueError):
                    continue
                oc = HORIZON_CAPTION.get(lang, HORIZON_CAPTION["en"]).get(other, "")
                os_label = spectrum_position_to_stance(p, lang=lang)["label"]
                other_readings.append(_pair(
                    f"{oc}: {os_label}",
                    f"{oc}: {os_label.lower()}",
                ))
        if other_readings:
            evidence.append(_pair(
                "다른 구간 읽기 — " + ", ".join(other_readings) + ".",
                "Other horizons — " + ", ".join(other_readings) + ".",
            ))
        insufficiency.append(_pair(
            "모든 시장 국면을 모형이 똑같이 잘 설명하지는 못합니다. 극단 국면에서 성능이 떨어질 수 있습니다.",
            "The model does not describe every market regime equally well; extreme regimes can degrade performance.",
        ))
    elif intent == "other_horizons":
        for other in HORIZON_KEYS:
            if other == hz:
                continue
            oc = HORIZON_CAPTION.get(lang, HORIZON_CAPTION["en"]).get(other, "")
            prov = (
                (getattr(bundle, "horizon_provenance", {}) or {}).get(other)
                if bundle is not None else None
            )
            oconf = horizon_provenance_to_confidence(prov, lang=lang)
            rows_o = (spectrum_by_horizon.get(other) or {}).get("rows") or []
            row_o = None
            if tkr:
                for rr in rows_o:
                    if str(rr.get("asset_id") or "").upper() == tkr:
                        row_o = rr
                        break
            if row_o is None:
                rep_o = best_representative_row(rows_o)
            else:
                rep_o = row_o
            try:
                p = float((rep_o or {}).get("spectrum_position") or 0.0)
            except (TypeError, ValueError):
                p = 0.0
            s_label = spectrum_position_to_stance(p, lang=lang)["label"]
            evidence.append(_pair(
                f"{oc}: {s_label} (신뢰도 — {oconf['label']}).",
                f"{oc}: {s_label.lower()} (confidence — {oconf['label'].lower()}).",
            ))
    elif intent == "why_confidence":
        claim.append(_pair(
            f"이 구간의 신뢰도는 '{conf_label}' 입니다.",
            f"Confidence for this horizon is '{conf_label}'.",
        ))
        evidence.append(conf_tip)
    elif intent == "whats_missing":
        if src_key == "preparing":
            insufficiency.append(conf_tip)
        elif src_key == "sample":
            insufficiency.append(conf_tip)
        elif not rationale and not wc:
            insufficiency.append(_pair(
                "이 종목/구간에 대한 상세 근거 문장이 아직 풍부하지 않습니다.",
                "Detailed narrative evidence is still thin for this asset/horizon.",
            ))
        else:
            insufficiency.append(_pair(
                "모든 규제/거시 이벤트를 모형이 실시간으로 반영하지는 못합니다.",
                "The model cannot incorporate every regulatory/macro event in real time.",
            ))
    else:
        insufficiency.append(_pair(
            "이 질문은 노출된 근거 안에서 답변 드릴 수 없습니다.",
            "This question cannot be answered from surfaced evidence.",
        ))
    return {
        "intent": intent,
        "label":  _quick_label(intent, lang),
        "claim":         claim,
        "evidence":      evidence,
        "insufficiency": insufficiency,
        "grounded":      bool(claim or evidence) and not (
            len(claim) + len(evidence) == 0
        ),
    }


def compose_quick_answers_dto(
    *,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    asset_id: str | None,
    horizon_key: str | None,
    lang: str = "ko",
) -> dict[str, Any]:
    lg = normalize_lang(lang) or "ko"
    ctx = _focus_context_card(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_horizon,
        asset_id=asset_id or "",
        horizon_key=horizon_key or "",
        lang=lg,
    )
    answers = [
        _quick_answer(intent,
                      context=ctx, bundle=bundle,
                      spectrum_by_horizon=spectrum_by_horizon, lang=lg)
        for intent in _QUICK_ACTION_ORDER
    ]
    dto = {
        "contract": "PRODUCT_ASK_QUICK_V1",
        "lang":     lg,
        "context":  ctx,
        "answers":  answers,
    }
    return strip_engineering_ids(dto)


# ---------------------------------------------------------------------------
# Free-text answer wrapper (grounded, degraded-safe)
# ---------------------------------------------------------------------------


def _degraded_answer(*, context: dict[str, Any], prompt: str, lang: str) -> dict[str, Any]:
    if lang == "ko":
        banner = "지금 제품 LLM 계층이 응답할 수 없어 자동 답변으로 전환했습니다."
        claim = f"노출된 근거 안에서만 답변합니다 — 현재 초점: {context.get('horizon_caption','')}."
        evidence = (
            "상단 컨텍스트 카드의 신뢰도와 근거 요약을 참고하시거나, 6개의 quick-action 중 가장 가까운 질문을 선택해 주세요."
        )
        insufficiency = "자유 입력 질문은 지금 처리되지 않습니다."
    else:
        banner = "The product LLM layer could not respond; switching to an automatic answer."
        claim = f"Answering strictly from surfaced evidence — current focus: {context.get('horizon_caption','')}."
        evidence = (
            "Consult the confidence and evidence summary in the context card above, or pick the closest quick-action."
        )
        insufficiency = "Free-text questions cannot be answered right now."
    return {
        "kind":   "degraded",
        "banner": banner,
        "claim":  [claim],
        "evidence":      [evidence],
        "insufficiency": [insufficiency],
        "grounded": False,
    }


def _scrub_prompt(prompt: str) -> str:
    """Bound customer free-text to a safe ceiling length; keep as-is."""
    return (prompt or "").strip()[:400]


def scrub_free_text_answer(
    *,
    prompt: str,
    context: dict[str, Any],
    conversation_callable,
    lang: str,
) -> dict[str, Any]:
    """Wrap a conversation-layer callable with Product-Shell contracts.

    ``conversation_callable`` is a zero-argument thunk returning a
    governed-conversation packet or ``None``. When it fails or returns
    an insufficient packet, a structured ``degraded`` answer is returned
    instead. All returned fields go through :func:`strip_engineering_ids`.
    """
    safe_prompt = _scrub_prompt(prompt)
    if not safe_prompt:
        return strip_engineering_ids({
            "kind": "empty_prompt",
            "banner": ("질문이 비어 있습니다." if lang == "ko"
                       else "No question was entered."),
            "claim": [],
            "evidence": [],
            "insufficiency": [
                "빈 질문으로는 답변 드릴 수 없습니다." if lang == "ko"
                else "An empty question cannot be answered."
            ],
            "grounded": False,
        })
    try:
        out = conversation_callable()
    except Exception:
        return strip_engineering_ids(_degraded_answer(
            context=context, prompt=safe_prompt, lang=lang
        ))
    if not isinstance(out, dict) or not out.get("ok"):
        return strip_engineering_ids(_degraded_answer(
            context=context, prompt=safe_prompt, lang=lang
        ))
    response_obj = out.get("response") or {}
    body = str(response_obj.get("body") or "").strip()
    if not body:
        return strip_engineering_ids(_degraded_answer(
            context=context, prompt=safe_prompt, lang=lang
        ))
    # Basic structuring — put the body sentence into claim and rely on
    # strip_engineering_ids to redact any internal tokens the LLM may
    # have echoed.
    if lang == "ko":
        banner = "노출된 근거 안에서만 답변했습니다."
    else:
        banner = "Answer strictly constrained to surfaced evidence."
    return strip_engineering_ids({
        "kind":   "grounded",
        "banner": banner,
        "claim":       [body],
        "evidence":    [],
        "insufficiency": [],
        "grounded": True,
    })


# ---------------------------------------------------------------------------
# Request-state card formatter
# ---------------------------------------------------------------------------


def _request_state_card(pair: dict[str, Any], *, lang: str) -> dict[str, Any]:
    req = pair.get("request") or {}
    res = pair.get("result")
    req_ts = str(req.get("created_at_utc") or "")
    req_payload = req.get("payload") or {}
    kind = str(req_payload.get("kind") or "").strip()
    outcome = ""
    res_ts = ""
    if isinstance(res, dict):
        res_ts = str(res.get("created_at_utc") or "")
        outcome = str((res.get("payload") or {}).get("outcome") or "")
    if not outcome:
        status_key = "running"
    elif outcome == "completed":
        status_key = "completed"
    elif outcome in ("blocked_insufficient_inputs", "rejected_kind_not_allowed",
                     "errored", "no_change"):
        status_key = "blocked"
    else:
        status_key = "completed"
    if lang == "ko":
        status_label_ko = {
            "running":   "진행 중",
            "completed": "완료",
            "blocked":   "보류",
        }
        status_label = status_label_ko.get(status_key, "—")
        kind_label = "사이드 실험 요청" if kind == "validation_rerun" else "요청"
        summary = f"{kind_label}: {status_label}"
    else:
        status_label_en = {
            "running":   "Running",
            "completed": "Completed",
            "blocked":   "Blocked",
        }
        status_label = status_label_en.get(status_key, "—")
        kind_label = "Sandbox ask" if kind == "validation_rerun" else "Request"
        summary = f"{kind_label}: {status_label}"
    return {
        "status_key":    status_key,
        "status_label":  status_label,
        "summary":       summary,
        "requested_at":  req_ts,
        "resolved_at":   res_ts,
    }


def compose_request_state_dto(
    followups: list[dict[str, Any]] | None,
    *,
    lang: str = "ko",
) -> dict[str, Any]:
    lg = normalize_lang(lang) or "ko"
    cards = [
        _request_state_card(pair, lang=lg)
        for pair in (followups or [])
    ]
    dto = {
        "contract": "PRODUCT_REQUEST_STATE_V1",
        "lang":     lg,
        "cards":    cards,
        "empty_state": None if cards else {
            "title": "보낸 요청이 없습니다." if lg == "ko" else "No requests yet.",
            "body":  ("Ask AI 나 사이드 실험을 통해 요청을 보내면 상태가 여기 기록됩니다."
                      if lg == "ko" else
                      "Requests from Ask AI or a sandbox ask will appear here."),
        },
    }
    return strip_engineering_ids(dto)


# ---------------------------------------------------------------------------
# Landing DTO (context + quick actions preview + request list)
# ---------------------------------------------------------------------------


def compose_ask_product_dto(
    *,
    bundle: BrainBundleV0 | None,
    spectrum_by_horizon: dict[str, dict[str, Any]],
    asset_id: str | None,
    horizon_key: str | None,
    followups: list[dict[str, Any]] | None = None,
    lang: str = "ko",
    now_utc: str,
) -> dict[str, Any]:
    lg = normalize_lang(lang) or "ko"
    ctx = _focus_context_card(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_horizon,
        asset_id=asset_id or "",
        horizon_key=horizon_key or "",
        lang=lg,
    )
    quick_chips = [
        {"intent": intent, "label": _quick_label(intent, lg)}
        for intent in _QUICK_ACTION_ORDER
    ]
    requests = compose_request_state_dto(followups, lang=lg)
    built_at = (
        str(getattr(bundle, "metadata", {}).get("built_at_utc") or "")
        if bundle is not None else ""
    )
    last_built_label = human_relative_time(built_at, now_utc=now_utc, lang=lg)
    dto = {
        "contract":         "PRODUCT_ASK_V1",
        "lang":             lg,
        "ok":               True,
        "as_of":            (getattr(bundle, "as_of_utc", "") or "") if bundle else "",
        "last_built_label": last_built_label,
        "context":          ctx,
        "quick_chips":      quick_chips,
        "free_text": {
            "placeholder_ko": "노출된 근거 안에서 답변 드립니다. 무엇이 궁금한가요?",
            "placeholder_en": "I answer strictly from surfaced evidence. What would you like to know?",
            "max_length":     400,
        },
        "requests":         requests,
        "contract_banner": {
            "title": "Ask AI 는 노출된 근거 안에서만 답변합니다." if lg == "ko"
                     else "Ask AI answers strictly from surfaced evidence.",
            "body":  ("quick-action 6개는 항상 답이 있습니다. 자유 입력은 LLM 계층이 준비되지 않았을 때 안전 모드로 전환됩니다."
                      if lg == "ko" else
                      "The six quick-actions always have an answer. Free-text falls back to a safe mode when the LLM layer is unavailable."),
        },
    }
    return strip_engineering_ids(dto)


# ---------------------------------------------------------------------------
# Public disk-backed builder
# ---------------------------------------------------------------------------


def build_ask_product_dto(
    *,
    repo_root: Path,
    asset_id: str | None,
    horizon_key: str | None,
    lang: str = "ko",
    now_utc: str | None = None,
    followups_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Disk-backed convenience wrapper for ``GET /api/product/ask``."""
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
    followups: list[dict[str, Any]] = []
    if followups_override is not None:
        followups = list(followups_override)
    else:
        # Best-effort attempt to attach recent sandbox followups; swallow
        # errors and render an empty list if the harness store is absent.
        try:
            from agentic_harness.runtime import build_store  # type: ignore
            from phase47_runtime.traceability_replay import (  # type: ignore
                api_governance_lineage_for_registry_entry,
            )
            store = build_store(use_fixture=False)
            rid = ""
            if bundle is not None:
                for ent in bundle.registry_entries:
                    if ent.status == "active" and ent.horizon == (horizon_key or HORIZON_KEYS[0]):
                        rid = str(getattr(ent, "registry_entry_id", "") or "")
                        break
            if rid:
                res = api_governance_lineage_for_registry_entry(
                    store, registry_entry_id=rid, horizon=horizon_key or "", limit=50
                )
                followups = list(res.get("sandbox_followups") or [])
        except Exception:
            followups = []
    return compose_ask_product_dto(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_hz,
        asset_id=asset_id,
        horizon_key=horizon_key,
        followups=followups,
        lang=lang,
        now_utc=effective_now,
    )


def build_quick_answers_product_dto(
    *,
    repo_root: Path,
    asset_id: str | None,
    horizon_key: str | None,
    lang: str = "ko",
) -> dict[str, Any]:
    """Disk-backed convenience wrapper for ``GET /api/product/ask/quick``."""
    bundle, _errs = try_load_brain_bundle_v0(repo_root)
    spectrum_by_hz: dict[str, dict[str, Any]] = {}
    for hz in HORIZON_KEYS:
        try:
            spectrum_by_hz[hz] = build_today_spectrum_payload(
                repo_root=repo_root, horizon=hz, lang=lang, rows_limit=200
            )
        except Exception:  # pragma: no cover — defensive
            spectrum_by_hz[hz] = {"ok": False, "error": "build_failure"}
    return compose_quick_answers_dto(
        bundle=bundle,
        spectrum_by_horizon=spectrum_by_hz,
        asset_id=asset_id,
        horizon_key=horizon_key,
        lang=lang,
    )
