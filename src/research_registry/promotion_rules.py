"""Governance rules: registry is memory + gates, not a production feature store."""

from __future__ import annotations

# Status values must match DB check on hypothesis_registry.research_item_status
ALLOWED_RESEARCH_STATUSES = frozenset(
    {
        "proposed",
        "under_review",
        "blocked_leakage_risk",
        "sandbox_only",
        "approved_for_experiment",
        "rejected",
        "promoted_to_candidate_logic",
    }
)


def describe_production_boundary() -> dict[str, str | list[str]]:
    """Document-only contract; enforced by absence of imports from scoring paths."""
    return {
        "what_can_enter_registry": (
            "연구 가설, 잠재 팩터 정의, 실험 아이디어, 데이터 소스 범위·의도가 명시된 항목."
        ),
        "evidence_proposed_to_experiment": (
            "재현 가능한 스펙(정의·universe·기간), 누출·선행 편향 검토 기록(leakage_review), "
            "운영자/설립자 승인(또는 명시적 actor) 기록."
        ),
        "evidence_experiment_to_production_candidate": (
            "실험 결과 아티팩트 링크(linked_artifacts), promotion_gate_events에 승인 요약, "
            "프로덕션 후보 로직 브랜치/버전에 대한 명시적 연결(코드 변경은 별도 PR)."
        ),
        "who_can_approve": (
            "자동 승인 없음. promotion_gate_events.actor 및 decision_summary에 사람 또는 "
            "운영 절차 식별자를 남김."
        ),
        "rejection_recording": (
            "research_item_status=rejected, rejection_reason 텍스트, promotion_decision=denied 등 "
            "게이트 이벤트에 rationale 저장."
        ),
        "production_scoring_rule": (
            "state_change / factor 패널 스코어링 경로는 hypothesis_registry·research_engine(Phase 14)·"
            "research_validation(Phase 15)·validation_campaign(Phase 16)·public_depth(Phase 17)·"
            "public_buildout(Phase 18)·public_repair_campaign(Phase 19)·public_repair_iteration(Phase 20)을 읽지 않는다. "
            "레지스트리·연구·검증 랩·캠페인·공개 기판 빌드아웃·수리 캠페인·수리 반복/에스컬레이션은 거버넌스·감사·연구 단계 전용."
        ),
    }


def assert_no_auto_promotion_wiring() -> None:
    """Runtime guard for tests: production scoring runner must not touch registry imports."""
    import inspect

    import state_change.runner as sc

    src = inspect.getsource(sc)
    if (
        "hypothesis_registry" in src
        or "research_registry" in src
        or "research_engine" in src
        or "research_validation" in src
        or "validation_campaign" in src
        or "public_depth" in src
        or "public_buildout" in src
        or "public_repair_campaign" in src
        or "public_repair_iteration" in src
    ):
        raise AssertionError(
            "state_change.runner must not reference hypothesis_registry/research_registry/"
            "research_engine/research_validation/validation_campaign/public_depth/public_buildout/"
            "public_repair_campaign/public_repair_iteration "
            "(no auto promotion wiring)."
        )


def validate_status(value: str) -> str:
    if value not in ALLOWED_RESEARCH_STATUSES:
        raise ValueError(f"invalid research_item_status: {value}")
    return value
