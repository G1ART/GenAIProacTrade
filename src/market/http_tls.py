"""urllib HTTPS용 SSL 컨텍스트. macOS 등에서 기본 CA 실패 시 certifi 번들 사용."""

from __future__ import annotations

import ssl


def ssl_context_for_urllib() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()
