"""환경변수 로딩 및 검증."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# 프로젝트 루트 (src/의 상위)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def ensure_edgar_local_cache() -> None:
    """edgartools가 홈 디렉터리 대신 쓸 수 있는 로컬 캐시 경로를 보장한다."""
    cache = PROJECT_ROOT / ".edgar_cache"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("EDGAR_LOCAL_DATA_DIR", str(cache))


class Settings(BaseModel):
    """런타임 설정. 비밀값은 환경변수에서만 읽는다."""

    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    edgar_identity: str = Field(alias="EDGAR_IDENTITY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    sentry_dsn: Optional[str] = Field(default=None, alias="SENTRY_DSN")
    fmp_api_key: Optional[str] = Field(default=None, alias="FMP_API_KEY")
    transcripts_provider: Optional[str] = Field(default=None, alias="TRANSCRIPTS_PROVIDER")

    model_config = {"populate_by_name": True}

    @field_validator("supabase_url", "supabase_service_role_key", "edgar_identity")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("값이 비어 있으면 안 됩니다.")
        return str(v).strip()


REQUIRED_ENV = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "EDGAR_IDENTITY")


def load_settings(*, env_path: Optional[Path] = None) -> Settings:
    """
    .env 및 프로세스 환경에서 설정을 로드한다.
    필수 키 누락 시 메시지에 어떤 키가 빠졌는지 명시한다.
    """
    path = env_path or (PROJECT_ROOT / ".env")
    # 프로젝트 루트 .env만 로드 (cwd의 다른 .env는 무시해 예측 가능하게 유지)
    if path.exists():
        load_dotenv(path, override=False)

    missing = [k for k in REQUIRED_ENV if not os.getenv(k) or not str(os.getenv(k)).strip()]
    if missing:
        raise RuntimeError(
            "필수 환경변수가 설정되지 않았습니다: "
            + ", ".join(missing)
            + ". 프로젝트 루트의 .env를 참고해 .env.example을 복사·채워 주세요."
        )

    data = {
        "SUPABASE_URL": os.environ["SUPABASE_URL"].strip(),
        "SUPABASE_SERVICE_ROLE_KEY": os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip(),
        "EDGAR_IDENTITY": os.environ["EDGAR_IDENTITY"].strip(),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "").strip() or None,
        "SENTRY_DSN": os.getenv("SENTRY_DSN", "").strip() or None,
        "FMP_API_KEY": os.getenv("FMP_API_KEY", "").strip() or None,
        "TRANSCRIPTS_PROVIDER": os.getenv("TRANSCRIPTS_PROVIDER", "fmp").strip() or None,
    }
    return Settings.model_validate(data)
