"""Product Spec §10 — programmatic MVP readiness signals (북극성 대비 자동 점검).

Q1-Q5: derived from bundle/env. Q6-Q10: derived by building the Today spectrum
payloads for every horizon (and with ``mock_price_tick=1`` for Q8) and by auditing
the persisted ``message_snapshots_v0.json`` store for the Replay lineage join.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from metis_brain.bundle import brain_bundle_path, bundle_ready_for_horizon, try_load_brain_bundle_v0
from metis_brain.message_snapshots_store import message_snapshots_path


def _today_source_mode() -> str:
    return (os.environ.get("METIS_TODAY_SOURCE") or "registry").strip().lower()


def _safe_str(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _has_headline_and_why_now_and_rationale(row: dict[str, Any]) -> bool:
    msg = row.get("message") if isinstance(row.get("message"), dict) else {}
    headline = _safe_str(msg.get("headline"))
    why_now = _safe_str(msg.get("why_now"))
    rs = row.get("rationale_summary")
    if isinstance(rs, dict):
        rationale = _safe_str(rs.get("en") or rs.get("ko"))
    else:
        rationale = _safe_str(rs)
    return bool(headline and why_now and rationale)


def _has_research_and_information(row_or_object: dict[str, Any]) -> bool:
    info = (
        row_or_object.get("information_layer")
        if isinstance(row_or_object.get("information_layer"), dict)
        else row_or_object.get("information") if isinstance(row_or_object.get("information"), dict) else {}
    )
    supporting = info.get("supporting_signals") if isinstance(info, dict) else None
    supporting_ok = isinstance(supporting, list) and len(supporting) >= 1
    research = (
        row_or_object.get("research_layer")
        if isinstance(row_or_object.get("research_layer"), dict)
        else row_or_object.get("research") if isinstance(row_or_object.get("research"), dict) else {}
    )
    deep = research.get("deeper_rationale") if isinstance(research, dict) else None
    if isinstance(deep, dict):
        deep_ok = bool(_safe_str(deep.get("en") or deep.get("ko")))
    else:
        deep_ok = bool(_safe_str(deep))
    return supporting_ok and deep_ok


def _load_spectrum_payloads_all_horizons(
    repo_root: Path, *, mock_price_tick: str = "0", lang: str = "en"
) -> dict[str, dict[str, Any]]:
    from phase47_runtime.today_spectrum import _HORIZON_ORDER, build_today_spectrum_payload

    out: dict[str, dict[str, Any]] = {}
    for hz in _HORIZON_ORDER:
        try:
            sp = build_today_spectrum_payload(
                repo_root=repo_root,
                horizon=hz,
                lang=lang,
                mock_price_tick=mock_price_tick,
            )
        except Exception as e:  # noqa: BLE001
            sp = {"ok": False, "error": f"exception:{type(e).__name__}:{e}"}
        out[hz] = sp
    return out


def _q6_any_row_has_headline_and_why_now_and_rationale(
    payloads_by_horizon: dict[str, dict[str, Any]]
) -> tuple[bool, str]:
    for hz, sp in payloads_by_horizon.items():
        if not sp.get("ok"):
            continue
        for r in sp.get("rows") or []:
            if isinstance(r, dict) and _has_headline_and_why_now_and_rationale(r):
                return True, f"horizon={hz};asset_id={r.get('asset_id')}"
    return False, "no_row_with_headline_why_now_rationale"


def _q7_any_asset_differs_across_horizons(
    payloads_by_horizon: dict[str, dict[str, Any]]
) -> tuple[bool, str]:
    positions_by_asset: dict[str, dict[str, float]] = {}
    for hz, sp in payloads_by_horizon.items():
        if not sp.get("ok"):
            continue
        for r in sp.get("rows") or []:
            if not isinstance(r, dict):
                continue
            aid = _safe_str(r.get("asset_id"))
            pos = r.get("spectrum_position")
            if not aid or pos is None:
                continue
            try:
                positions_by_asset.setdefault(aid, {})[hz] = float(pos)
            except (TypeError, ValueError):
                continue
    for aid, by_h in positions_by_asset.items():
        if len(by_h) >= 2 and len({round(v, 6) for v in by_h.values()}) >= 2:
            return True, f"asset_id={aid};horizons={sorted(by_h)}"
    return False, "no_cross_horizon_position_divergence"


def _q8_any_rank_movement_up_or_down(tick_payloads: dict[str, dict[str, Any]]) -> tuple[bool, str]:
    for hz, sp in tick_payloads.items():
        if not sp.get("ok"):
            continue
        for r in sp.get("rows") or []:
            if isinstance(r, dict) and r.get("rank_movement") in {"up", "down"}:
                return True, f"horizon={hz};asset_id={r.get('asset_id')};movement={r.get('rank_movement')}"
    return False, "no_up_or_down_rank_movement_at_tick_1"


def _q9_any_object_has_info_and_research_layers(
    repo_root: Path,
    payloads_by_horizon: dict[str, dict[str, Any]],
    *,
    lang: str = "en",
) -> tuple[bool, str]:
    """Research hierarchy lives on the object-detail payload; probe a sample row per horizon."""
    from phase47_runtime.today_spectrum import build_today_object_detail_payload

    for hz, sp in payloads_by_horizon.items():
        if not sp.get("ok"):
            continue
        for r in sp.get("rows") or []:
            if not isinstance(r, dict):
                continue
            aid = _safe_str(r.get("asset_id"))
            if not aid:
                continue
            try:
                obj = build_today_object_detail_payload(
                    repo_root=repo_root,
                    asset_id=aid,
                    horizon=hz,
                    lang=lang,
                    mock_price_tick="0",
                )
            except Exception:  # noqa: BLE001
                continue
            if obj.get("ok") and _has_research_and_information(obj):
                return True, f"horizon={hz};asset_id={aid}"
    return False, "no_object_detail_with_information_and_research_layers"


# ---------------------------------------------------------------------------
# Patch 11 — Q11 / Q12
#
# Q1..Q10 above are frozen (the Product Spec §10 contract). Q11 and Q12
# are *additions* that measure the gaps Patch 11 targets: (a) whether
# signal quality is accumulating in the bundle (residual semantics
# populated per-row on horizons that claim evidence), and (b) whether
# the long-horizon evidence tier + provenance are honestly aligned.
# ---------------------------------------------------------------------------

Q11_MIN_COVERAGE_SHORT_MEDIUM = 0.8


def _row_has_residual_semantics(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    if str(row.get("residual_score_semantics_version") or "").strip():
        return True
    msg = row.get("message") if isinstance(row.get("message"), dict) else {}
    if isinstance(msg, dict):
        if str(msg.get("residual_score_semantics_version") or "").strip():
            return True
    return False


def _q11_signal_quality_accumulation(bundle) -> tuple[bool, str]:
    """Signal-quality accumulation survey.

    For each short / medium horizon: at least
    ``Q11_MIN_COVERAGE_SHORT_MEDIUM`` of spectrum rows must carry the
    Patch 11 residual-score semantics fields.

    For medium_long / long: the horizon is only audited when the
    bundle's ``long_horizon_support`` tier for that horizon is at
    ``limited`` or ``production`` — honest sample tiers are exempt
    because we do not expect signal-quality density there.
    """
    if bundle is None:
        return False, "no_bundle"
    support = getattr(bundle, "long_horizon_support_by_horizon", None) or {}
    details: list[str] = []
    failing: list[str] = []
    for hz in ("short", "medium", "medium_long", "long"):
        rows = (getattr(bundle, "spectrum_rows_by_horizon", {}) or {}).get(hz) or []
        if not isinstance(rows, list) or not rows:
            details.append(f"{hz}:empty")
            continue
        covered = sum(1 for r in rows if _row_has_residual_semantics(r))
        ratio = covered / float(len(rows))
        details.append(f"{hz}:{covered}/{len(rows)}")
        if hz in ("short", "medium"):
            if ratio < Q11_MIN_COVERAGE_SHORT_MEDIUM:
                failing.append(f"{hz}_coverage_{ratio:.2f}<{Q11_MIN_COVERAGE_SHORT_MEDIUM}")
        else:
            entry = support.get(hz) if isinstance(support, dict) else None
            tier = str((entry or {}).get("tier_key") or "sample").strip()
            if tier in ("limited", "production"):
                if ratio < Q11_MIN_COVERAGE_SHORT_MEDIUM:
                    failing.append(
                        f"{hz}_tier={tier}_coverage_{ratio:.2f}<{Q11_MIN_COVERAGE_SHORT_MEDIUM}"
                    )
    if failing:
        return False, "; ".join(failing)
    return True, "; ".join(details) or "no_rows"


def _q12_long_horizon_honest_tier(bundle) -> tuple[bool, str]:
    """Long-horizon honest-tier survey.

    Returns true when the bundle has a ``long_horizon_support_by_horizon``
    block for medium_long + long AND the provenance ↔ tier combination
    is not an over-claim or an under-claim for either horizon. An
    honest sample tier (provenance=insufficient_evidence, tier=sample)
    is true. A lie (provenance=real_derived, tier=sample) is false.
    """
    if bundle is None:
        return False, "no_bundle"
    support = getattr(bundle, "long_horizon_support_by_horizon", None) or {}
    provenance = getattr(bundle, "horizon_provenance", {}) or {}

    def _prov_source(hz: str) -> str:
        return str(((provenance.get(hz) or {}) if isinstance(provenance, dict) else {}).get("source") or "")

    if not isinstance(support, dict) or not support:
        # Absence-is-honesty: when the bundle makes no long-horizon claim AND
        # provenance for medium_long/long explicitly says ``insufficient_evidence``
        # there is nothing to lie about. An absent block with a ``real_derived``
        # provenance IS a lie (over-claim by silence) and must fail.
        details: list[str] = []
        for hz in ("medium_long", "long"):
            src = _prov_source(hz)
            if src not in ("insufficient_evidence", "template_fallback", ""):
                return False, f"real_derived_provenance_without_support_block:{hz}:{src}"
            details.append(f"{hz}:source={src or 'missing'};tier=absent")
        return True, "; ".join(details)
    from metis_brain.long_horizon_evidence_v1 import (
        long_horizon_support_integrity_errors,
    )

    errs = long_horizon_support_integrity_errors(
        horizon_provenance=provenance,
        long_horizon_support_by_horizon=support,
    )
    if errs:
        return False, "; ".join(errs)
    details = []
    for hz in ("medium_long", "long"):
        entry = support.get(hz)
        src = _prov_source(hz)
        if not isinstance(entry, dict):
            # Missing entry but block present: honest only when provenance says absent.
            if src not in ("insufficient_evidence", "template_fallback", ""):
                return False, f"missing_support_for_{hz}_with_{src}_provenance"
            details.append(f"{hz}:source={src or 'missing'};tier=absent")
            continue
        tier = str(entry.get("tier_key") or "")
        details.append(f"{hz}:tier={tier};source={src}")
    return True, "; ".join(details)


def _q10_snapshot_store_has_lineage(
    repo_root: Path,
    payloads_by_horizon: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    path = message_snapshots_path(repo_root)
    if not path.is_file():
        return False, f"message_snapshot_store_not_found:{path}"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return False, f"message_snapshot_store_unreadable:{type(e).__name__}"
    snaps = raw.get("snapshots")
    if not isinstance(snaps, dict):
        return False, "message_snapshot_store_no_snapshots"

    active_registry_ids: set[str] = set()
    for hz, sp in payloads_by_horizon.items():
        rid = _safe_str(sp.get("registry_entry_id"))
        if rid:
            active_registry_ids.add(rid)

    for sid, rec in snaps.items():
        if not isinstance(rec, dict):
            continue
        sid_s = _safe_str(sid)
        rid = _safe_str(rec.get("registry_entry_id"))
        if sid_s and rid:
            if not active_registry_ids or rid in active_registry_ids:
                return True, f"snapshot_id={sid_s};registry_entry_id={rid}"
    return False, "no_snapshot_with_both_message_snapshot_id_and_registry_entry_id"


def build_mvp_spec_survey_v0(repo_root: Path) -> dict[str, Any]:
    """Return stable keys for UI / health JSON (KO labels live in phase51 copy if needed)."""
    root = Path(repo_root)
    mode = _today_source_mode()
    bundle, brain_errs = try_load_brain_bundle_v0(root)
    hz_all = ("short", "medium", "medium_long", "long")
    horizons_ready = (
        {h: bundle_ready_for_horizon(bundle, h) for h in hz_all} if bundle is not None else {h: False for h in hz_all}
    )
    all_ready = bundle is not None and all(horizons_ready.values())

    # §10 Q1 — Today가 registry 기반 스펙트럼만 쓰는가: seed 금지 + 번들 4지평 무결 시 registry/auto 모두 번들 경로만 탐.
    q1_ok = bool(bundle is not None and all_ready and mode in ("registry", "auto") and mode != "seed")
    if mode == "seed":
        q1_ok = False

    active_entries = [e for e in (bundle.registry_entries if bundle else []) if str(getattr(e, "status", "")) == "active"]
    horizons_with_active = {str(e.horizon) for e in active_entries}

    # §10 Q2 / Q3
    q2_ok = len(horizons_with_active & set(hz_all)) >= 4
    q3_ok = any(len(getattr(e, "challenger_artifact_ids", []) or []) > 0 for e in active_entries)

    # §10 Q4 — artifacts back every active id
    by_art = {a.artifact_id for a in (bundle.artifacts if bundle else [])} if bundle else set()
    q4_ok = bool(bundle) and all(str(e.active_artifact_id) in by_art for e in active_entries)

    snap_path = message_snapshots_path(root)
    q5_ok = snap_path.parent.is_dir()

    # §10 Q6-Q10 auto signals — derived from Today payloads + message snapshot store.
    payloads_by_horizon = _load_spectrum_payloads_all_horizons(root, mock_price_tick="0")
    payloads_tick_1 = _load_spectrum_payloads_all_horizons(root, mock_price_tick="1")

    q6_ok, q6_detail = _q6_any_row_has_headline_and_why_now_and_rationale(payloads_by_horizon)
    q7_ok, q7_detail = _q7_any_asset_differs_across_horizons(payloads_by_horizon)
    q8_ok, q8_detail = _q8_any_rank_movement_up_or_down(payloads_tick_1)
    q9_ok, q9_detail = _q9_any_object_has_info_and_research_layers(root, payloads_by_horizon)
    q10_ok, q10_detail = _q10_snapshot_store_has_lineage(root, payloads_by_horizon)
    # Patch 11 — Q11 + Q12 additions (Q1..Q10 above are unchanged).
    q11_ok, q11_detail = _q11_signal_quality_accumulation(bundle)
    q12_ok, q12_detail = _q12_long_horizon_honest_tier(bundle)

    questions = [
        {
            "id": "Q1_today_registry_only",
            "spec": "Today가 registry만 읽는가?",
            "ok": bool(q1_ok and bundle is not None),
            "detail": f"METIS_TODAY_SOURCE={mode!r}; bundle_valid={bundle is not None}",
        },
        {
            "id": "Q2_active_family_per_horizon",
            "spec": "각 시간축에 active family가 존재하는가?",
            "ok": q2_ok,
            "detail": f"active_horizons={sorted(horizons_with_active)}",
        },
        {
            "id": "Q3_challenger_active_distinction",
            "spec": "challenger/active 구분이 존재하는가?",
            "ok": q3_ok,
            "detail": "at least one registry entry has challenger_artifact_ids",
        },
        {
            "id": "Q4_artifact_required_for_active",
            "spec": "artifact packet 없이 모델이 Today에 올라갈 수 없는가?",
            "ok": q4_ok,
            "detail": "each active_artifact_id resolves in bundle.artifacts",
        },
        {
            "id": "Q5_message_store_path",
            "spec": "message snapshot 1급 저장 경로 준비",
            "ok": q5_ok,
            "detail": str(snap_path.parent),
        },
        {
            "id": "Q6_message_headline_why_now_rationale",
            "spec": "spectrum row가 headline + why_now + rationale_summary 를 모두 채우는가?",
            "ok": q6_ok,
            "detail": q6_detail,
        },
        {
            "id": "Q7_same_ticker_different_horizon_position",
            "spec": "동일 ticker가 horizon별로 다른 spectrum_position 을 갖는가?",
            "ok": q7_ok,
            "detail": q7_detail,
        },
        {
            "id": "Q8_rank_movement_on_mock_price_tick",
            "spec": "mock_price_tick=1 실행 시 rank_movement 에 up 또는 down 이 1건 이상 등장하는가?",
            "ok": q8_ok,
            "detail": q8_detail,
        },
        {
            "id": "Q9_information_and_research_layers_present",
            "spec": "object 단면에 information.supporting_signals >=1 + research.deeper_rationale 가 존재하는가?",
            "ok": q9_ok,
            "detail": q9_detail,
        },
        {
            "id": "Q10_replay_lineage_join_present",
            "spec": "persisted snapshot에 message_snapshot_id + registry_entry_id 가 동시에 존재하는가?",
            "ok": q10_ok,
            "detail": q10_detail,
        },
        {
            "id": "Q11_signal_quality_accumulation",
            "spec": (
                "각 horizon의 spectrum_row가 residual-score 의미(잔존 의미 버전 + "
                "invalidation_hint + recheck_cadence) 필드를 채우며 신호 품질이 "
                "축적되는가? (short/medium은 항상, medium_long/long은 tier가 "
                "limited/production 일 때 감사)"
            ),
            "ok": q11_ok,
            "detail": q11_detail,
        },
        {
            "id": "Q12_long_horizon_honest_tier",
            "spec": (
                "medium_long/long horizon에 long_horizon_support 블록이 존재하며, "
                "horizon_provenance ↔ tier_key 사이에 과장(real_derived+sample) 또는 "
                "저평가(insufficient_evidence+production) 부정합이 없는가?"
            ),
            "ok": q12_ok,
            "detail": q12_detail,
        },
    ]

    all_ok = all(q["ok"] for q in questions)

    return {
        "contract": "METIS_MVP_SPEC_SURVEY_V0",
        "doc_ref": "METIS_MVP_Unified_Product_Spec_KR_v1.md §10",
        "today_source_mode": mode,
        "brain_bundle_path": str(brain_bundle_path(root)),
        "brain_bundle_ok": bundle is not None,
        "brain_bundle_errors": brain_errs,
        "horizons_ready": horizons_ready,
        "questions": questions,
        "all_automated_ok": all_ok,
        "manual_or_runtime_proof": [],
    }
