from __future__ import annotations

import pytest

from config import load_settings


def test_load_settings_success() -> None:
    s = load_settings()
    assert "supabase.co" in s.supabase_url
    assert s.supabase_service_role_key
    assert "@" in s.edgar_identity


@pytest.mark.parametrize(
    "key",
    ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "EDGAR_IDENTITY"],
)
def test_load_settings_missing_required(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    # 프로젝트 .env가 있으면 load_dotenv가 삭제된 키를 다시 채워 실패하므로 파일 로드만 끈다
    monkeypatch.setattr("config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setenv("EDGAR_IDENTITY", "a@b.c")
    monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="필수 환경변수"):
        load_settings()


def test_load_settings_empty_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("SUPABASE_URL", "   ")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setenv("EDGAR_IDENTITY", "a@b.c")
    with pytest.raises(RuntimeError, match="필수 환경변수"):
        load_settings()
