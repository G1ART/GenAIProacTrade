"""
Coverage 집계 — `issuer_quarter_factor_panels.coverage_json`·quality 플래그 기반 휴리스틱.
"""

from __future__ import annotations

from typing import Any

from research.validation_registry import ValidationFactorSpec


def aggregate_factor_coverage(
    spec: ValidationFactorSpec,
    factor_panel_rows: list[dict[str, Any]],
    *,
    total_rows_in_slice: int,
) -> dict[str, Any]:
    """
    슬라이스 내 해당 팩터 컬럼 가용성 및 누락 이유(추정) 집계.
    """
    available = 0
    missing = 0
    no_prior = 0
    zero_den = 0
    miss_fields = 0
    col = spec.panel_column
    for fp in factor_panel_rows:
        v = fp.get(col)
        if v is not None:
            available += 1
            continue
        missing += 1
        cov = fp.get("coverage_json") or {}
        fac_cov = cov.get(spec.factor_name)
        if isinstance(fac_cov, dict) and fac_cov.get("missing_fields"):
            miss_fields += 1
        qf = fp.get("quality_flags_json") or {}
        by_f = (qf.get("by_factor") or {}).get(spec.factor_name) or []
        flags_s = " ".join(str(x) for x in by_f).lower()
        if "prior" in flags_s or (
            spec.requires_prior_snapshot and not cov.get("prior_snapshot_found")
        ):
            no_prior += 1
        if "zero" in flags_s and "denom" in flags_s:
            zero_den += 1

    return {
        "factor_name": spec.factor_name,
        "total_rows": total_rows_in_slice,
        "available_rows": available,
        "missing_rows": missing,
        "missing_due_to_no_prior": no_prior,
        "missing_due_to_zero_denominator": zero_den,
        "missing_due_to_missing_fields": miss_fields,
        "coverage_json": {
            "note": "missing reason counts may overlap; descriptive audit only",
            "requires_prior_snapshot": spec.requires_prior_snapshot,
        },
    }
