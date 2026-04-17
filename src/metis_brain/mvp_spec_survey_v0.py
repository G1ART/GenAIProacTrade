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
