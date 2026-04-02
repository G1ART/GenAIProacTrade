"""Phase 5: research metrics, universe slices, quantiles, runner (네트워크 없음)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from research.metrics import (
    hit_rate_same_sign,
    ols_simple_slope_intercept,
    pearson_correlation,
    spearman_rank_correlation,
)
from research.quantiles import (
    bucket_descriptive_spread,
    build_quantile_buckets,
    choose_quantile_count,
)
from research.standardize import winsorize, zscore
from research.summaries import aggregate_factor_coverage
from research.universe_slices import (
    UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1,
    UNIVERSE_PROXY_CANDIDATES,
    UNIVERSE_SP500_CURRENT,
    resolve_slice_symbols,
)
from research.validation_registry import VALIDATION_FACTORS_V1, get_factor_spec
from research.validation_runner import run_factor_validation_research


def test_pearson_perfect_positive() -> None:
    xs = [1.0, 2.0, 3.0, 4.0]
    ys = [2.0, 4.0, 6.0, 8.0]
    assert pearson_correlation(xs, ys) == pytest.approx(1.0)


def test_spearman_inverse() -> None:
    xs = [1.0, 2.0, 3.0, 4.0]
    ys = [4.0, 3.0, 2.0, 1.0]
    assert spearman_rank_correlation(xs, ys) == pytest.approx(-1.0)


def test_hit_rate_same_sign() -> None:
    f = [1.0, -2.0, 3.0]
    r = [0.1, -0.2, -0.3]
    assert hit_rate_same_sign(f, r) == pytest.approx(2 / 3)


def test_ols_simple() -> None:
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0, 4.0, 6.0, 8.0, 10.0]
    o = ols_simple_slope_intercept(xs, ys)
    assert o is not None
    assert o["slope"] == pytest.approx(2.0)
    assert o["intercept"] == pytest.approx(0.0, abs=1e-9)


def test_zscore_and_winsorize() -> None:
    z = zscore([1.0, 2.0, 3.0, 4.0, 5.0])
    assert z[0] is not None
    assert abs(sum(zi for zi in z if zi is not None)) < 1e-9
    w = winsorize([1.0, 2.0, 100.0], lower_pct=0.0, upper_pct=0.66)
    assert max(w) < 100.0


def test_choose_quantile_count_small_sample() -> None:
    assert choose_quantile_count(3, preferred=5) == 2
    assert choose_quantile_count(1, preferred=5) is None


def test_assign_quantile_and_buckets() -> None:
    f = [0.1, 0.5, 0.2, 0.9, 0.3]
    r = [0.01, 0.02, 0.03, 0.04, 0.05]
    e = [0.0, 0.01, 0.02, 0.03, 0.04]
    buckets, meta = build_quantile_buckets(f, r, e, n_quantiles=5)
    assert buckets is not None
    assert len(buckets) == 5
    assert meta.get("n_quantiles") == 5
    sp = bucket_descriptive_spread(buckets, return_basis="raw")
    assert "descriptive_spread_top_minus_bottom" in sp


def test_aggregate_coverage() -> None:
    spec = get_factor_spec("accruals")
    assert spec is not None
    fp = {
        "accruals": 0.1,
        "coverage_json": {"accruals": {"missing_fields": []}},
        "quality_flags_json": {"by_factor": {"accruals": []}},
    }
    out = aggregate_factor_coverage(spec, [fp], total_rows_in_slice=2)
    assert out["available_rows"] == 1
    assert out["total_rows"] == 2


def test_validation_registry_has_six() -> None:
    assert len(VALIDATION_FACTORS_V1) == 6
    assert get_factor_spec("financial_strength_score_v1") is not None


class _MemResult:
    def __init__(self, data: list[dict[str, Any]] | None = None):
        self.data = data or []


class _MemQuery:
    def __init__(self, store: dict[str, list[dict[str, Any]]], table: str):
        self._store = store
        self._table = table
        self._filters: list[tuple[str, str, Any]] = []
        self._limit: int | None = None
        self._order: tuple[str, bool] | None = None
        self._update_payload: dict[str, Any] | None = None
        self._insert_row: dict[str, Any] | None = None

    def select(self, *_a: Any, **_k: Any) -> _MemQuery:
        return self

    def eq(self, col: str, val: Any) -> _MemQuery:
        self._filters.append(("eq", col, val))
        return self

    def order(self, _col: str, desc: bool = False) -> _MemQuery:
        self._order = (_col, desc)
        return self

    def limit(self, n: int) -> _MemQuery:
        self._limit = n
        return self

    def in_(self, col: str, vals: list[Any]) -> _MemQuery:
        self._filters.append(("in", col, vals))
        return self

    def insert(self, row: dict[str, Any]) -> _MemQuery:
        self._insert_row = dict(row)
        return self

    def update(self, upd: dict[str, Any]) -> _MemQuery:
        self._update_payload = dict(upd)
        return self

    def execute(self) -> _MemResult:
        if self._insert_row is not None:
            r = dict(self._insert_row)
            if "id" not in r:
                r["id"] = str(uuid.uuid4())
            self._store.setdefault(self._table, []).append(r)
            self._insert_row = None
            return _MemResult([r])
        if self._update_payload is not None:
            rows = self._store.get(self._table, [])
            for row in rows:
                ok = all(row.get(c) == v for op, c, v in self._filters if op == "eq")
                if ok:
                    row.update(self._update_payload)
            return _MemResult([])
        rows = list(self._store.get(self._table, []))
        for op, col, val in self._filters:
            if op == "eq":
                rows = [r for r in rows if r.get(col) == val]
            elif op == "in":
                rows = [r for r in rows if r.get(col) in val]
        if self._order:
            _, desc = self._order
            rows = sorted(rows, key=lambda r: r.get("completed_at") or "", reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return _MemResult(rows)


class _MemClient:
    def __init__(self, store: dict[str, list[dict[str, Any]]]):
        self._store = store

    def table(self, name: str) -> _MemQuery:
        return _MemQuery(self._store, name)


def test_resolve_universe_combined() -> None:
    rows = [
        {"symbol": "ZZZ", "as_of_date": "2024-01-02", "universe_name": UNIVERSE_SP500_CURRENT},
        {"symbol": "AAA", "as_of_date": "2024-01-02", "universe_name": UNIVERSE_SP500_CURRENT},
        {"symbol": "BBB", "as_of_date": "2024-01-02", "universe_name": UNIVERSE_PROXY_CANDIDATES},
    ]
    client = _MemClient({"universe_memberships": rows})
    out = resolve_slice_symbols(client, UNIVERSE_COMBINED_LARGECAP_RESEARCH_V1)
    assert out == ["AAA", "BBB", "ZZZ"]


def test_run_factor_validation_mock_rerun_shape() -> None:
    """Mock DB: 2심볼·팩터·검증패널 — runner가 요약·분위·커버리지 insert 호출."""
    store: dict[str, list[dict[str, Any]]] = {
        "universe_memberships": [
            {
                "symbol": "A",
                "as_of_date": "2024-01-01",
                "universe_name": UNIVERSE_SP500_CURRENT,
            },
            {
                "symbol": "B",
                "as_of_date": "2024-01-01",
                "universe_name": UNIVERSE_SP500_CURRENT,
            },
        ],
        "factor_market_validation_panels": [
            {
                "cik": "1",
                "symbol": "A",
                "accession_no": "a1",
                "factor_version": "v1",
                "raw_return_1m": 0.01,
                "excess_return_1m": 0.005,
                "raw_return_1q": 0.02,
                "excess_return_1q": 0.01,
                "panel_json": {},
            },
            {
                "cik": "2",
                "symbol": "B",
                "accession_no": "b1",
                "factor_version": "v1",
                "raw_return_1m": -0.01,
                "excess_return_1m": -0.005,
                "raw_return_1q": -0.02,
                "excess_return_1q": -0.01,
                "panel_json": {},
            },
        ],
        "issuer_quarter_factor_panels": [
            {
                "cik": "1",
                "accession_no": "a1",
                "factor_version": "v1",
                "accruals": 0.1,
                "gross_profitability": 0.2,
                "asset_growth": 0.05,
                "capex_intensity": 0.03,
                "rnd_intensity": 0.04,
                "financial_strength_score": 3.0,
                "coverage_json": {},
                "quality_flags_json": {"by_factor": {}},
            },
            {
                "cik": "2",
                "accession_no": "b1",
                "factor_version": "v1",
                "accruals": -0.1,
                "gross_profitability": 0.1,
                "asset_growth": 0.02,
                "capex_intensity": 0.01,
                "rnd_intensity": 0.02,
                "financial_strength_score": 2.0,
                "coverage_json": {},
                "quality_flags_json": {"by_factor": {}},
            },
        ],
        "factor_validation_runs": [],
        "factor_validation_summaries": [],
        "factor_quantile_results": [],
        "factor_coverage_reports": [],
    }
    client = _MemClient(store)
    out = run_factor_validation_research(
        client,
        universe_name=UNIVERSE_SP500_CURRENT,
        horizon_type="next_month",
        factor_version="v1",
        panel_limit=100,
        include_ols=True,
        n_quantiles=2,
    )
    assert out["status"] == "completed"
    assert out["factors_ok"] == 6
    assert len(store["factor_validation_summaries"]) == 12
    assert len(store["factor_coverage_reports"]) == 6
    assert len(store["factor_quantile_results"]) == 24


def test_argparse_run_factor_validation_registered() -> None:
    from main import build_parser

    p = build_parser()
    a = p.parse_args(
        [
            "run-factor-validation",
            "--universe",
            "sp500_current",
            "--horizon",
            "next_month",
        ]
    )
    assert a.command == "run-factor-validation"
    assert a.universe == "sp500_current"
