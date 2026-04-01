"""silver_sec_filings 행 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class SilverSecFilingRow(BaseModel):
    cik: str
    company_name: str
    accession_no: str
    form: str
    filed_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    normalized_summary_json: dict[str, Any]
    revision_no: int = Field(default=1, ge=1)
    created_at: Optional[datetime] = None

    @field_validator("cik", "company_name", "accession_no", "form")
    @classmethod
    def strip_str(cls, v: str) -> str:
        s = str(v).strip()
        if not s:
            raise ValueError("필수 문자열 필드가 비어 있습니다.")
        return s

    def to_supabase_dict(self) -> dict[str, Any]:
        d = self.model_dump(mode="json", exclude_none=True)
        if self.created_at is None:
            d.pop("created_at", None)
        return d
