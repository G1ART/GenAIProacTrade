"""Cadence definitions for auto-seeded layer jobs.

The scheduler uses these to decide whether a given layer should run in the
current tick. Work-order sec 11.3 / 11.4 pins these defaults.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


DEFAULT_CADENCES: dict[str, timedelta] = {
    "layer1.transcript_ingest": timedelta(hours=6),
    "layer2.coverage_triage": timedelta(hours=12),
    "layer3.challenger_cycle": timedelta(days=1),
    "layer4.registry_proposal": timedelta(days=1),
}


def _parse_iso(s: str) -> Optional[datetime]:
    s = str(s or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def should_run_cadence(
    *,
    cadence_key: str,
    last_run_at_utc: Optional[str],
    now_utc: Optional[datetime] = None,
    cadences: Optional[dict[str, timedelta]] = None,
) -> bool:
    """Return True if the cadence is eligible to run again at ``now_utc``.

    If no cadence is registered for the key the default is ``True`` so new
    cadences fall open - agent authors must add an entry to DEFAULT_CADENCES
    to adopt throttling.
    """

    c = (cadences or DEFAULT_CADENCES).get(cadence_key)
    if c is None:
        return True
    now = now_utc or datetime.now(timezone.utc)
    last = _parse_iso(last_run_at_utc or "")
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last) >= c
