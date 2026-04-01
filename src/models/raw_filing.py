"""raw_sec_filings 행 모델 (Supabase insert 검증용)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class RawSecFilingRow(BaseModel):
    cik: str
    company_name: str
    accession_no: str
    form: str
    filed_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    source_url: Optional[str] = None
    payload_json: dict[str, Any]
    ingested_at: Optional[datetime] = None

    @field_validator("cik", "company_name", "accession_no", "form")
    @classmethod
    def strip_str(cls, v: str) -> str:
        s = str(v).strip()
        if not s:
            raise ValueError("필수 문자열 필드가 비어 있습니다.")
        return s

    def to_supabase_dict(self) -> dict[str, Any]:
        """Supabase REST insert용 dict (ISO8601 문자열)."""
        d = self.model_dump(mode="json", exclude_none=True)
        if self.ingested_at is None:
            d.pop("ingested_at", None)
        return d
