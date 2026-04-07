"""Classify transient / infra failures so they do not masquerade as research outcomes."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

_INFRA_SUBSTRINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gateway_502", ("502", "503", "504", "bad gateway", "cloudflare")),
    ("gateway_timeout", ("gateway timeout", "504 gateway")),
    ("http_timeout", ("timeout", "timed out", "read timed out", "deadline exceeded")),
    (
        "connection_reset",
        ("connection reset", "econnreset", "broken pipe", "connection aborted"),
    ),
    ("tls_handshake", ("ssl handshake", "tls handshake", "certificate")),
    (
        "remote_closed",
        ("remote end closed", "connection closed unexpectedly", "premature close"),
    ),
)


def classify_infra_failure(message: str | None) -> str | None:
    if not message:
        return None
    m = str(message).lower()
    for cat, needles in _INFRA_SUBSTRINGS:
        if any(n in m for n in needles):
            return cat
    return None


def is_infra_failure_message(message: str | None) -> bool:
    return classify_infra_failure(message) is not None


def is_transient_exception(exc: BaseException) -> bool:
    return classify_infra_failure(str(exc)) is not None


def call_with_transient_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 4,
    base_delay_s: float = 0.35,
    jitter_s: float = 0.12,
) -> T:
    """Retry callable on infra-classified exceptions (e.g. REST 502 surfacing as APIError)."""
    last: BaseException | None = None
    for attempt in range(max(1, int(max_attempts))):
        try:
            return fn()
        except BaseException as ex:  # noqa: BLE001 — boundary for operator tooling
            last = ex
            if attempt >= max_attempts - 1 or not is_transient_exception(ex):
                raise
            delay = base_delay_s * (2**attempt) + random.random() * jitter_s
            time.sleep(delay)
    assert last is not None
    raise last


def annotate_failure_for_audit(exc: BaseException) -> dict[str, Any]:
    raw = str(exc)[:4000]
    cat = classify_infra_failure(raw)
    return {
        "raw_error_preview": raw[:500],
        "infra_class": cat,
        "treated_as_infra": bool(cat),
    }
