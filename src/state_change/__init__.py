"""
Phase 6: deterministic issuer–date state change engine.

입력 SSOT: issuer_quarter_factor_panels, issuer_quarter_snapshots, universe_memberships,
market metadata / risk-free 등 시점 합법 컨텍스트만.

금지: factor_market_validation_panels 의 forward return·excess return·horizon outcome 을
특성(feature) 입력으로 사용하지 않음(검증·감사 전용 테이블).
"""

__all__: tuple[str, ...] = ("CONFIG_VERSION_STATE_CHANGE_V1",)

CONFIG_VERSION_STATE_CHANGE_V1 = "state_change_engine_v1"
