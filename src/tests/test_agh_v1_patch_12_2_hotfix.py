"""Patch 12.2 — hotfixes for Patch 12 / 12.1 integration bugs.

Two issues were caught in production after Patch 12.1 shipped:

* **Fix C — Authorization header dropped by the HTTP glue.**
  ``phase47_runtime.app.make_handler`` rebuilt the header dict for
  ``dispatch_json`` from a short whitelist (``X-User-Language``,
  ``X-Cockpit-Lang`` for GET; ``X-Source-Id`` + webhook headers for POST).
  When Patch 12 added the auth routes the whitelist was never extended, so
  every real browser request reached ``require_auth`` without an
  ``Authorization`` header and bounced back as ``missing_bearer_token`` —
  even though ``curl`` sent a valid Bearer. This file asserts the glue now
  forwards ``Authorization`` on both verbs.

* **Fix D — ``supabase_user_verify`` opened urlopen with the wrong positional
  arg.**  ``urllib.request.urlopen`` takes ``(url, data=None, timeout=...)``
  so ``opener(req, 5.0)`` passed ``5.0`` as ``data`` — which flipped the GET
  into a malformed POST and raised a ``TypeError`` *before* the
  ``URLError`` / ``OSError`` except clauses could catch it. The exception
  escaped ``dispatch_json`` and surfaced at the Railway edge as
  ``502 Application failed to respond``. This file asserts
  1) the default opener hands ``timeout`` through as a keyword, and
  2) a raw ``TypeError`` from an opener no longer escapes — it is converted
     to ``network_error`` so the guard can cleanly return 401.
"""

from __future__ import annotations

import io
import json
from typing import Any
from urllib.parse import urlparse

import pytest

from phase47_runtime.auth.supabase_user_verify import (
    SupabaseUserVerifyResult,
    verify_via_supabase_user_endpoint,
)


# ---------------------------------------------------------------------------
# Fix C — Authorization header passthrough in phase47_runtime/app.py
# ---------------------------------------------------------------------------


class _StubWfile:
    def __init__(self) -> None:
        self.buf = io.BytesIO()

    def write(self, data: bytes) -> int:
        self.buf.write(data)
        return len(data)


class _StubRfile:
    def __init__(self, data: bytes = b"") -> None:
        self.buf = io.BytesIO(data)

    def read(self, n: int = -1) -> bytes:
        return self.buf.read(n) if n != -1 else self.buf.read()


def _make_handler_instance(
    monkeypatch: pytest.MonkeyPatch,
    *,
    path: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    from phase47_runtime import app as app_mod

    captured: list[dict[str, Any]] = []

    def fake_dispatch(state: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
        captured.append({**kwargs})
        return 200, {"ok": True}

    monkeypatch.setattr(app_mod, "dispatch_json", fake_dispatch)

    HandlerCls = app_mod.make_handler(state=object())

    handler = HandlerCls.__new__(HandlerCls)
    handler.path = path
    handler.command = method
    handler.client_address = ("127.0.0.1", 0)
    handler.headers = headers  # dict supports ``.get`` which is what app.py uses
    handler.rfile = _StubRfile(body or b"")
    handler.wfile = _StubWfile()

    def _log_message(_self: Any, *_args: Any, **_kwargs: Any) -> None:
        return None

    def _send_response(_self: Any, *_args: Any, **_kwargs: Any) -> None:
        return None

    def _send_header(_self: Any, *_args: Any, **_kwargs: Any) -> None:
        return None

    def _end_headers(_self: Any) -> None:
        return None

    def _send_error(_self: Any, *_args: Any, **_kwargs: Any) -> None:
        return None

    handler.log_message = _log_message.__get__(handler, HandlerCls)
    handler.send_response = _send_response.__get__(handler, HandlerCls)
    handler.send_header = _send_header.__get__(handler, HandlerCls)
    handler.end_headers = _end_headers.__get__(handler, HandlerCls)
    handler.send_error = _send_error.__get__(handler, HandlerCls)

    return handler, captured


def test_patch_12_2_authorization_passthrough_on_get(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "eyJ" + "a" * 780
    headers = {
        "Authorization": f"Bearer {token}",
        "X-User-Language": "ko",
    }
    handler, captured = _make_handler_instance(
        monkeypatch,
        path="/api/auth/me",
        method="GET",
        headers=headers,
    )
    handler.do_GET()

    assert len(captured) == 1, "dispatch_json should run exactly once"
    fwd = captured[0]["headers"]
    assert fwd.get("Authorization") == f"Bearer {token}", (
        "Patch 12.2 Fix C: /api/auth/me GET must forward the Bearer header "
        "untouched so require_auth can resolve the access token"
    )
    assert fwd.get("X-User-Language") == "ko", "pre-existing X-User-Language must still pass"


def test_patch_12_2_authorization_passthrough_on_post(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "eyJ" + "b" * 780
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Source-Id": "beta",
        "Content-Length": "2",
    }
    handler, captured = _make_handler_instance(
        monkeypatch,
        path="/api/auth/session",
        method="POST",
        headers=headers,
        body=b"{}",
    )
    handler.do_POST()

    assert len(captured) == 1, "dispatch_json should run exactly once"
    fwd = captured[0]["headers"]
    assert fwd.get("Authorization") == f"Bearer {token}", (
        "Patch 12.2 Fix C: /api/auth/session POST must forward the Bearer "
        "header so the session-activation endpoint can verify the token"
    )
    assert fwd.get("X-Source-Id") == "beta"


def test_patch_12_2_missing_authorization_stays_empty_not_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler, captured = _make_handler_instance(
        monkeypatch,
        path="/api/auth/me",
        method="GET",
        headers={},
    )
    handler.do_GET()

    assert captured[0]["headers"].get("Authorization") == "", (
        "when the client omits the header the glue should forward an empty "
        "string, matching the pre-existing convention of the other whitelisted "
        "headers; require_auth maps that to missing_bearer_token"
    )


# ---------------------------------------------------------------------------
# Fix D — urlopen timeout keyword + blanket except to prevent 502
# ---------------------------------------------------------------------------


def test_patch_12_2_default_opener_passes_timeout_as_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, **kwargs: Any) -> Any:
        captured["url"] = getattr(request, "full_url", None)
        captured["method"] = getattr(request, "get_method", lambda: "GET")()
        captured["timeout"] = kwargs.get("timeout")
        captured["kwargs"] = kwargs

        class _Resp:
            status = 200
            code = 200

            def read(self_inner) -> bytes:
                return json.dumps({"id": "abc", "email": "x@y.z"}).encode("utf-8")

            def close(self_inner) -> None:
                return None

        return _Resp()

    import phase47_runtime.auth.supabase_user_verify as mod

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)

    result = verify_via_supabase_user_endpoint(
        "eyJtok",
        supabase_url="https://example.supabase.co",
        anon_key="anon-xyz",
        timeout_s=7.5,
    )

    assert result.ok is True, f"expected ok=True, got reason={result.reason!r}"
    assert captured["method"] == "GET", (
        "Patch 12.2 Fix D: the verifier must issue GET, not POST — a POST "
        "would be the regression that surfaced as Railway 502"
    )
    assert captured["timeout"] == 7.5, (
        "Patch 12.2 Fix D: timeout MUST reach urlopen as the ``timeout=`` "
        "keyword so it is not mis-parsed as ``data``"
    )
    parsed = urlparse(captured["url"] or "")
    assert parsed.path == "/auth/v1/user"


def test_patch_12_2_opener_typeerror_is_caught_as_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 502 in production came from a bare ``TypeError`` escaping this
    module. Assert the blanket ``except Exception`` swallow keeps that case
    to a clean ``network_error`` so the guard returns 401, not 500/502.
    """

    def raise_typeerror(req: Any, timeout: float) -> Any:
        raise TypeError("POST data should be bytes")

    result = verify_via_supabase_user_endpoint(
        "eyJtok",
        supabase_url="https://example.supabase.co",
        anon_key="anon-xyz",
        http_opener=raise_typeerror,
    )

    assert isinstance(result, SupabaseUserVerifyResult)
    assert result.ok is False
    assert result.reason == "network_error", (
        "Patch 12.2 Fix D: unexpected TypeError must be reduced to "
        "network_error; otherwise it escapes dispatch_json and Railway "
        "returns 502 Application failed to respond"
    )


def test_patch_12_2_opener_generic_exception_also_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_runtime(req: Any, timeout: float) -> Any:
        raise RuntimeError("ssl handshake exploded")

    result = verify_via_supabase_user_endpoint(
        "eyJtok",
        supabase_url="https://example.supabase.co",
        anon_key="anon-xyz",
        http_opener=raise_runtime,
    )

    assert result.ok is False
    assert result.reason == "network_error"
