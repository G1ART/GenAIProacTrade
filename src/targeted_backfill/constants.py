"""Phase 27 결정적 상수(달력 프록시·PIT 분해 경계)."""

from __future__ import annotations

# next_quarter ≈ 63 거래일에 대응하는 달력일 상한(운영일·휴장 버퍼 포함, 고정값).
CALENDAR_DAYS_1Q_MATURITY_PROXY = 95

# PIT: state_change as_of가 시그널 직후 소수 일 안이면 정렬/주말 의심.
PIT_ALIGNMENT_SLACK_CALENDAR_DAYS = 7

# 그보다 크고 이 값 이하면 역사 윈도우 확장이 레버리지일 수 있음으로 태깅.
PIT_HISTORY_SHORT_MAX_CALENDAR_DAYS = 120
