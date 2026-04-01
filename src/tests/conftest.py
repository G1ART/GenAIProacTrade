"""pytest 공통 설정."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _default_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """대부분의 테스트에 필요한 최소 환경변수."""
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv("EDGAR_IDENTITY", "Test User test@example.com")
