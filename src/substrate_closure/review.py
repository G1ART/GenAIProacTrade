"""Founder-readable substrate closure scoreboard (Phase 25)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _f(x: Any) -> str:
    if x is None:
        return "null"
    if isinstance(x, float):
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x)


def _excl(d: dict[str, Any], key: str) -> int:
    return int((d.get("exclusion_distribution") or {}).get(key) or 0)


def _metrics(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "thin_input_share": m.get("thin_input_share"),
        "joined_recipe_substrate_row_count": m.get("joined_recipe_substrate_row_count"),
        "n_issuer_with_validation_panel_symbol": m.get(
            "n_issuer_with_validation_panel_symbol"
        ),
        "n_issuer_with_next_quarter_excess": m.get("n_issuer_with_next_quarter_excess"),
        "n_issuer_with_state_change_cik": m.get("n_issuer_with_state_change_cik"),
    }


def write_substrate_closure_review_md(
    *,
    path: str | Path,
    universe_name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    program_id: str | None = None,
    phase26_recommendation: str,
    production_scoring_boundary_note: str = (
        "프로덕션 스코어링 경로는 변경하지 않음; 기판 수리는 연구/공개 파이프라인에만 적용."
    ),
    premium_review_status: str = (
        "프리미엄 자동 오픈 없음; 프리미엄 디스커버리/리뷰는 운영자 명시 승인 전까지 차단 유지."
    ),
) -> Path:
    """
    before/after: `build_substrate_closure_snapshot` 결과 또는 동일 스키마.
    phase26_recommendation: Phase 15/16 재실행 vs 추가 기판 스프린트 문장.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    mb = before.get("metrics") or {}
    ma = after.get("metrics") or {}
    rb = before.get("rerun_readiness") or {}
    ra = after.get("rerun_readiness") or {}

    def dominant(block: dict[str, Any]) -> list[tuple[str, int]]:
        dist = block.get("exclusion_distribution") or {}
        items = [(str(k), int(v)) for k, v in dist.items() if int(v) > 0]
        items.sort(key=lambda x: (-x[1], x[0]))
        return items[:12]

    lines = [
        "# Substrate closure review (Phase 25)",
        "",
        f"- 생성 시각(UTC): `{datetime.now(timezone.utc).isoformat()}`",
        f"- 유니버스: `{universe_name}`",
        f"- 프로그램 ID(게이트): `{program_id or '(미지정)'}`",
        "",
        "## Thin-input & joined substrate",
        "",
        "| 지표 | 이전 | 이후 |",
        "|------|------|------|",
        f"| thin_input_share | {_f(mb.get('thin_input_share'))} | {_f(ma.get('thin_input_share'))} |",
        f"| joined_recipe_substrate_row_count | {_f(mb.get('joined_recipe_substrate_row_count'))} | {_f(ma.get('joined_recipe_substrate_row_count'))} |",
        "",
        "## Coverage (issuer-level counts)",
        "",
        "| 지표 | 이전 | 이후 |",
        "|------|------|------|",
        f"| n_issuer_with_validation_panel_symbol | {_f(mb.get('n_issuer_with_validation_panel_symbol'))} | {_f(ma.get('n_issuer_with_validation_panel_symbol'))} |",
        f"| n_issuer_with_next_quarter_excess | {_f(mb.get('n_issuer_with_next_quarter_excess'))} | {_f(ma.get('n_issuer_with_next_quarter_excess'))} |",
        f"| n_issuer_with_state_change_cik | {_f(mb.get('n_issuer_with_state_change_cik'))} | {_f(ma.get('n_issuer_with_state_change_cik'))} |",
        "",
        "## Dominant exclusions (before)",
        "",
    ]
    for reason, cnt in dominant(before):
        lines.append(f"- `{reason}`: {cnt}")
    lines.extend(["", "## Dominant exclusions (after)", ""])
    for reason, cnt in dominant(after):
        lines.append(f"- `{reason}`: {cnt}")
    lines.extend(
        [
            "",
            "## Phase 24-style trio (row counts)",
            "",
            "| 제외 사유 | 이전 | 이후 | Δ |",
            "|-----------|------|------|---|",
        ]
    )
    for key in (
        "no_validation_panel_for_symbol",
        "missing_excess_return_1q",
        "no_state_change_join",
    ):
        b, a = _excl(before, key), _excl(after, key)
        lines.append(f"| {key} | {b} | {a} | {a - b:+d} |")
    lines.extend(
        [
            "",
            "## Rerun gates (Phase 15 / 16)",
            "",
            "### Before",
            "",
            f"- recommend_rerun_phase15: `{rb.get('recommend_rerun_phase15')}`",
            f"- recommend_rerun_phase16: `{rb.get('recommend_rerun_phase16')}`",
            "",
            "### After",
            "",
            f"- recommend_rerun_phase15: `{ra.get('recommend_rerun_phase15')}`",
            f"- recommend_rerun_phase16: `{ra.get('recommend_rerun_phase16')}`",
            "",
            "### Blockers (after, if still false)",
            "",
        ]
    )
    joined_a = int(ma.get("joined_recipe_substrate_row_count") or 0)
    thin_a = ma.get("thin_input_share")
    th = ra.get("thresholds") or {}
    if not ra.get("recommend_rerun_phase15"):
        lines.append(
            "- Phase 15: joined 또는 thin_input_share 조건 미충족 "
            f"(joined={joined_a}, thin={thin_a}, thresholds={th})."
        )
    else:
        lines.append("- Phase 15: 조건 충족.")
    if not ra.get("recommend_rerun_phase16"):
        lines.append(
            "- Phase 16: joined 또는 thin_input_share 조건 미충족(Phase 15보다 엄격)."
        )
    else:
        lines.append("- Phase 16: 조건 충족.")

    lines.extend(
        [
            "",
            "## Tradeoffs & silent degradation",
            "",
            "수리로 한 지표가 개선되고 다른 제외 건수가 늘면 별도 repair JSON의 "
            "`tradeoffs.silent_degradation` 필드를 확인한다.",
            "",
        "## Production scoring boundary",
        "",
        production_scoring_boundary_note,
        "",
        "## Premium review",
        "",
        premium_review_status,
        "",
        "## Phase 26 권고",
            "",
            phase26_recommendation,
            "",
        ]
    )
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def recommend_phase26_from_gates(after_readiness: dict[str, Any]) -> str:
    """Phase 26: rerun 15/16 vs 한 번 더 기판 스프린트."""
    if not after_readiness.get("ok"):
        return (
            "rerun 게이트를 읽을 수 없어 Phase 26는 수동 판단. "
            "프로그램 ID·유니버스를 확인한 뒤 스냅샷을 다시 수집한다."
        )
    r15 = bool(after_readiness.get("recommend_rerun_phase15"))
    r16 = bool(after_readiness.get("recommend_rerun_phase16"))
    if r15 or r16:
        return (
            "개선된 기판에서 **Phase 15/16 재실행**을 우선 검토한다 "
            f"(phase15={r15}, phase16={r16})."
        )
    return (
        "joined/thin 게이트가 아직 열리지 않았다면 **공개 기판 수리 스프린트를 한 사이클 더** 진행한다."
    )


def format_rerun_gate_report(
    rerun_readiness: dict[str, Any],
) -> str:
    """CLI용 짧은 게이트 요약."""
    if not rerun_readiness.get("ok"):
        return (
            "Phase 15 rerun gate: blocked (readiness unavailable)\n"
            "Phase 16 rerun gate: blocked (readiness unavailable)\n"
            f"Blocker: {rerun_readiness.get('error') or rerun_readiness.get('reason') or 'unknown'}"
        )
    r15 = rerun_readiness.get("recommend_rerun_phase15")
    r16 = rerun_readiness.get("recommend_rerun_phase16")
    m = rerun_readiness.get("substrate_snapshot") or {}
    joined = m.get("joined_recipe_substrate_row_count")
    thin = m.get("thin_input_share")
    th = rerun_readiness.get("thresholds") or {}
    lines = [
        f"Phase 15 rerun gate: {'opened' if r15 else 'still blocked'}",
        f"Phase 16 rerun gate: {'opened' if r16 else 'still blocked'}",
    ]
    if not r15:
        lines.append(
            f"Phase 15 blocker: joined={joined} (need>={th.get('joined_phase15')}), "
            f"thin_input_share={thin} (must be < {th.get('thin_share_max_phase15')} if set)"
        )
    if not r16:
        lines.append(
            f"Phase 16 blocker: joined={joined} (need>={th.get('joined_phase16')}), "
            f"thin_input_share={thin} (must be < {th.get('thin_share_max_phase16')} if set)"
        )
    return "\n".join(lines)
