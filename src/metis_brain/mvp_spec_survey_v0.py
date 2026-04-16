"""Product Spec §10 — programmatic MVP readiness signals (북극성 대비 자동 점검).

Answers are best-effort from repo + bundle + env; some spec questions need human/demo proof.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from metis_brain.bundle import brain_bundle_path, bundle_ready_for_horizon, try_load_brain_bundle_v0
from metis_brain.message_snapshots_store import message_snapshots_path


def _today_source_mode() -> str:
    return (os.environ.get("METIS_TODAY_SOURCE") or "registry").strip().lower()


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
    q5_ok = snap_path.parent.is_dir()  # store dir exists; file may be created on first Today hit

    return {
        "contract": "METIS_MVP_SPEC_SURVEY_V0",
        "doc_ref": "METIS_MVP_Unified_Product_Spec_KR_v1.md §10",
        "today_source_mode": mode,
        "brain_bundle_path": str(brain_bundle_path(root)),
        "brain_bundle_ok": bundle is not None,
        "brain_bundle_errors": brain_errs,
        "horizons_ready": horizons_ready,
        "questions": [
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
        ],
        "manual_or_runtime_proof": [
            "Q6 headline+why_now+rationale — Today UI / object detail",
            "Q7 same ticker different horizon position — spectrum rows",
            "Q8 price overlay rank movement — mock_price_tick=1",
            "Q9 Research hierarchy — object detail + tests",
            "Q10 Replay then/now + outcomes — timeline + counterfactual",
        ],
    }
