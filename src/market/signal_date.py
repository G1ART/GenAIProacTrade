"""
공시 시점 → 시그널 가용일(보수적 다음 거래일).

규칙: accepted_at 이 있으면 그 날짜(UTC 캘린더일) 이후 첫 평일.
없으면 filed_at 동일. 둘 다 없으면 ValueError.
인트라데이 해석 없음; same-day 가격 사용 금지.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from market.trading_calendar import next_weekday_strictly_after


def _to_date_utc(value: Any) -> date:
    if value is None:
        raise ValueError("날짜 값이 없습니다.")
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    if isinstance(value, str):
        s = value.strip()
        if "T" in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date()
        return date.fromisoformat(s[:10])
    raise TypeError(f"지원하지 않는 날짜 타입: {type(value)!r}")


def signal_available_date_from_snapshot(snap: dict[str, Any]) -> date:
    """issuer_quarter_snapshots (또는 동일 필드) 행에서 시그널 가용일."""
    acc = snap.get("accepted_at")
    filed = snap.get("filed_at")
    if acc:
        event = _to_date_utc(acc)
    elif filed:
        event = _to_date_utc(filed)
    else:
        raise ValueError("accepted_at 과 filed_at 이 모두 없어 시그널일을 정할 수 없습니다.")
    return next_weekday_strictly_after(event)
