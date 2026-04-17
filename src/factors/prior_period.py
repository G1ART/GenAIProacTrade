"""
Prior 회계 분기 스냅샷 탐색 (가격/거래일 정렬 없음).

정책:
- 동일 `cik` 내에서만 탐색한다.
- `fiscal_period`는 대문자 정규화 후 `Q1`–`Q4`, `FY` 만 prior 링크를 지원한다.
- `UNSPECIFIED`, `UNKNOWN` 등은 **fiscal 체인 prior 없음** → resolver는 None 반환
  (해당 스냅샷은 asset_growth, average_total_assets 기반 팩터 등에서 prior 필요 시 null).
- 동일 `(fiscal_year, fiscal_period)` 에 accession이 여러 개면 `filed_at` 최신(내림차순)을 대표로 쓴다.
"""

from __future__ import annotations

from typing import Any, Optional


def normalize_fiscal_period(fp: str) -> str:
    return (fp or "").strip().upper()


def prior_fiscal_period(fiscal_year: int, fiscal_period: str) -> Optional[tuple[int, str]]:
    """직전 회계 분기 (FY, FP) 또는 없으면 None."""
    fp = normalize_fiscal_period(fiscal_period)
    if fp == "Q1":
        return fiscal_year - 1, "Q4"
    if fp == "Q2":
        return fiscal_year, "Q1"
    if fp == "Q3":
        return fiscal_year, "Q2"
    if fp == "Q4":
        return fiscal_year, "Q3"
    if fp == "FY":
        return fiscal_year - 1, "FY"
    return None


def prior_fiscal_period_fallbacks(
    fiscal_year: int, fiscal_period: str
) -> list[tuple[int, str]]:
    """
    직전 회계 기간 후보 목록 (우선순위대로).

    주로 Q1 의 경우 10-K 가 `fiscal_period="FY"` 로만 저장되고 `Q4` 분기
    스냅샷이 없는 발행사를 지원한다. FY 의 period-end 는 Q4 period-end 와
    동일하므로 `total_assets` 같은 instant 값은 FY 스냅샷으로 대체 가능하다.
    """
    fp = normalize_fiscal_period(fiscal_period)
    if fp == "Q1":
        return [(fiscal_year - 1, "Q4"), (fiscal_year - 1, "FY")]
    primary = prior_fiscal_period(fiscal_year, fiscal_period)
    return [primary] if primary else []


def _filed_at_sort_key(s: dict[str, Any]) -> str:
    v = s.get("filed_at")
    return str(v or "")


def index_snapshots_by_period(
    snapshots: list[dict[str, Any]],
) -> dict[tuple[int, str], dict[str, Any]]:
    """
    (fiscal_year, normalized_fp) -> 대표 스냅샷 (동일 기간 다 accession 시 filed_at 최신).
    """
    buckets: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for s in snapshots:
        fy = s.get("fiscal_year")
        fp = normalize_fiscal_period(str(s.get("fiscal_period") or ""))
        if fy is None:
            continue
        key = (int(fy), fp)
        buckets.setdefault(key, []).append(s)
    out: dict[tuple[int, str], dict[str, Any]] = {}
    for key, rows in buckets.items():
        rows_sorted = sorted(rows, key=_filed_at_sort_key, reverse=True)
        out[key] = rows_sorted[0]
    return out


def find_prior_snapshot(
    current: dict[str, Any],
    snapshots: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """
    current 스냅샷의 직전 회계 분기에 해당하는 스냅샷 (없으면 None).

    Q1 에 대해서는 `(fy-1, Q4)` → `(fy-1, FY)` 순서로 후보를 탐색한다. 10-K
    만 있는 발행사는 Q4 분기 스냅샷 없이 FY 스냅샷만 존재하기 때문.
    """
    fy = current.get("fiscal_year")
    fp = current.get("fiscal_period")
    if fy is None or fp is None:
        return None
    idx = index_snapshots_by_period(snapshots)
    for candidate in prior_fiscal_period_fallbacks(int(fy), str(fp)):
        hit = idx.get(candidate)
        if hit is not None:
            return hit
    return None
