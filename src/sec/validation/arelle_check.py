"""
Arelle 기반 교차검증 훅 (Phase 1: 스켈레톤).

Arelle 미설치 시 모든 공개 함수는 graceful skip 구조를 반환한다.
"""

from __future__ import annotations

from typing import Any, Optional

_ARELLE_AVAILABLE: Optional[bool] = None


def _check_arelle() -> bool:
    global _ARELLE_AVAILABLE
    if _ARELLE_AVAILABLE is not None:
        return _ARELLE_AVAILABLE
    try:
        import arelle  # noqa: F401, pylint: disable=unused-import

        _ARELLE_AVAILABLE = True
    except ImportError:
        _ARELLE_AVAILABLE = False
    return _ARELLE_AVAILABLE


def validate_filing_identity(payload: dict[str, Any]) -> dict[str, Any]:
    """
    공시 identity 메타에 대한 검증 자리.
    Arelle 통합 전: 설치 여부만 반영한 placeholder.
    """
    if not _check_arelle():
        return {
            "status": "skipped",
            "reason": "arelle_not_installed",
            "detail": "pip install arelle-xbrl 등으로 설치 후 재시도 (Phase 2+)",
        }
    return {
        "status": "not_implemented",
        "reason": "arelle_installed_but_phase1_skeleton",
        "accession_no": payload.get("accession_no"),
        "cik": payload.get("cik"),
    }


def compare_basic_statement_presence(
    payload: dict[str, Any],
    *,
    expected_forms: Optional[list[str]] = None,
) -> dict[str, Any]:
    """재무제표 존재 여부 등 단순 비교 자리 (미구현)."""
    if not _check_arelle():
        return {"status": "skipped", "reason": "arelle_not_installed"}
    return {
        "status": "not_implemented",
        "form": payload.get("form"),
        "expected_forms": expected_forms or [],
    }
