"""Human-first runtime health payload for founder cockpit API."""

from __future__ import annotations

from typing import Any

from phase51_runtime.runtime_health import build_runtime_health_summary


def build_cockpit_runtime_health_payload(
    *,
    repo_root,
    ingest_registry_path=None,
    audit_path=None,
    control_plane_path=None,
) -> dict[str, Any]:
    from pathlib import Path

    root = Path(repo_root) if not isinstance(repo_root, Path) else repo_root
    raw = build_runtime_health_summary(
        repo_root=root,
        ingest_registry_path=ingest_registry_path,
        audit_path=audit_path,
        control_plane_path=control_plane_path,
    )
    st = raw.get("health_status") or "unknown"
    cp = raw.get("control_plane_excerpt") or {}
    enabled = cp.get("enabled")
    maint = cp.get("maintenance_mode")

    if not enabled:
        headline = "연구 런타임이 꺼져 있습니다."
        sub = "새 사이클은 시작되지 않습니다. 제어 평면에서 활성화할 수 있습니다."
    elif maint:
        headline = "점검(maintenance) 모드입니다."
        sub = "트리거는 기록되지만 사이클 실행이 제한될 수 있습니다."
    elif st == "degraded":
        headline = "런타임은 동작 중이나 최근에 건너뛴 사이클이 있습니다."
        sub = "타이밍·리스·윈도 한도 등을 확인하세요."
    else:
        headline = "런타임 상태가 정상으로 보입니다."
        sub = "최근 감사 요약과 외부 트리거 적재 상태를 아래에서 확인할 수 있습니다."

    last_c = raw.get("last_cycle_audit_excerpt") or {}
    ext = raw.get("external_ingest_counts") or {}
    lines = [
        f"마지막 감사 시각: {last_c.get('timestamp') or '—'}",
        f"마지막 사이클 건너뜀: {'예' if last_c.get('skipped') else '아니오'}",
        f"외부 트리거 적재: 총 {ext.get('total_entries', 0)}건 · 승인 대기 {ext.get('accepted_pending', 0)} · 소비됨 {ext.get('consumed', 0)} · 거절 {ext.get('rejected', 0)} · 중복 제거 {ext.get('deduped', 0)}",
    ]
    la = raw.get("last_accepted_trigger")
    if la:
        lines.append(
            f"최근 승인 트리거: {la.get('normalized_trigger_type')} @ {la.get('received_at', '')[:19]}"
        )
    lr = raw.get("last_rejected_trigger")
    if lr:
        lines.append(f"최근 거절: {lr.get('reason')} ({lr.get('raw_event_type')})")

    skips = raw.get("recent_skip_reasons") or []
    skip_plain = [f"{s.get('why')} @ {str(s.get('timestamp') or '')[:19]}" for s in skips[:5]]

    return {
        "ok": True,
        "headline": headline,
        "subtext": sub,
        "health_status": st,
        "plain_lines": lines,
        "recent_skips_plain": skip_plain,
        "effective_trigger_types": (raw.get("trigger_controls") or {}).get("allowed_trigger_types_effective", []),
        "advanced": raw,
    }
