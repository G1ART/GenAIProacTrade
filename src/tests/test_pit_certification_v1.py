"""Tests for canonical PIT certification propagation (:mod:`metis_brain.pit_certification_v1`)."""

from __future__ import annotations

import json

from metis_brain.factor_validation_gate_adapter_v0 import (
    build_metis_gate_summary_from_factor_summary_row,
)
from metis_brain.pit_certification_v1 import (
    PIT_RULE_ID_V0,
    apply_pit_rule_to_summary_json,
    certify_factor_validation_pit_for_runs,
)


def test_apply_pit_rule_merges_flags_into_empty_summary() -> None:
    merged, changed = apply_pit_rule_to_summary_json({})
    assert changed is True
    assert merged["pit_certified"] is True
    assert merged["pit_rule"] == PIT_RULE_ID_V0
    assert "pit_rule_note" in merged


def test_apply_pit_rule_is_idempotent_when_already_certified() -> None:
    existing = {
        "pit_certified": True,
        "pit_rule": PIT_RULE_ID_V0,
        "pit_rule_note": "...",
        "preferred_direction_note": "keep",
    }
    merged, changed = apply_pit_rule_to_summary_json(existing)
    assert changed is False
    assert merged["preferred_direction_note"] == "keep"


def test_apply_pit_rule_force_overwrites() -> None:
    existing = {"pit_certified": True, "pit_rule": PIT_RULE_ID_V0}
    merged, changed = apply_pit_rule_to_summary_json(existing, force=True)
    assert changed is True
    assert merged["pit_rule"] == PIT_RULE_ID_V0


def test_apply_pit_rule_parses_json_string_summary() -> None:
    raw = json.dumps({"preferred_direction_note": "x"})
    merged, changed = apply_pit_rule_to_summary_json(raw)
    assert changed is True
    assert merged["pit_certified"] is True
    assert merged["preferred_direction_note"] == "x"


def test_gate_adapter_propagates_pit_rule_into_reasons() -> None:
    row = {
        "run_id": "run-1",
        "factor_name": "accruals",
        "universe_name": "sp500_current",
        "horizon_type": "next_month",
        "sample_count": 200,
        "valid_factor_count": 100,
        "spearman_rank_corr": 0.2,
        "summary_json": {"pit_certified": True, "pit_rule": PIT_RULE_ID_V0},
    }
    s = build_metis_gate_summary_from_factor_summary_row(row, quantiles=None, return_basis="raw")
    assert s["pit_pass"] is True
    assert f"pit_rule={PIT_RULE_ID_V0}" in s["reasons"]


# ----------------------------------------------------------------------------
# Fake Supabase client for certify_factor_validation_pit_for_runs
# ----------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, runs, summaries):
        self._table = table
        self._runs = runs
        self._summaries = summaries
        self._filters: list[tuple[str, str, object]] = []
        self._order: tuple[str, bool] | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, list(vals)))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def execute(self):
        src = self._runs if self._table == "factor_validation_runs" else self._summaries
        rows = list(src)
        for kind, col, val in self._filters:
            if kind == "eq":
                rows = [r for r in rows if r.get(col) == val]
            elif kind == "in":
                rows = [r for r in rows if r.get(col) in set(val)]
        if self._order is not None:
            col, desc = self._order
            rows.sort(key=lambda r: r.get(col) or "", reverse=bool(desc))
        return _FakeResp(rows)


class _FakeUpdate:
    def __init__(self, client, table, patch):
        self._client = client
        self._table = table
        self._patch = patch
        self._filters: list[tuple[str, object]] = []

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def execute(self):
        for row in self._client._summaries:
            if all(row.get(c) == v for c, v in self._filters):
                sj = row.get("summary_json")
                base = dict(sj) if isinstance(sj, dict) else {}
                base.update(self._patch.get("summary_json") or {})
                row["summary_json"] = base
        return _FakeResp([])


class _FakeTable:
    def __init__(self, client, name):
        self._client = client
        self._name = name

    def select(self, *args, **kwargs):
        return _FakeQuery(self._name, self._client._runs, self._client._summaries).select(*args, **kwargs)

    def update(self, patch):
        return _FakeUpdate(self._client, self._name, patch)


class _FakeClient:
    def __init__(self, runs, summaries):
        self._runs = list(runs)
        self._summaries = [dict(s) for s in summaries]

    def table(self, name):
        return _FakeTable(self, name)


def test_certify_factor_validation_pit_for_runs_updates_only_changed() -> None:
    runs = [
        {
            "id": "r1",
            "status": "completed",
            "completed_at": "2026-04-16T00:00:00Z",
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
        },
        {
            "id": "r2",
            "status": "completed",
            "completed_at": "2026-04-14T00:00:00Z",
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
        },
        {
            "id": "r3",
            "status": "completed",
            "completed_at": "2026-04-10T00:00:00Z",
            "universe_name": "other_universe",
            "horizon_type": "next_month",
        },
    ]
    summaries = [
        {"id": "s1", "run_id": "r1", "factor_name": "accruals", "summary_json": {}},
        {"id": "s2", "run_id": "r1", "factor_name": "gross_profitability", "summary_json": None},
        {
            "id": "s3",
            "run_id": "r2",
            "factor_name": "accruals",
            "summary_json": {"pit_certified": True, "pit_rule": PIT_RULE_ID_V0},
        },
        {"id": "s4", "run_id": "r3", "factor_name": "accruals", "summary_json": {}},
    ]
    client = _FakeClient(runs, summaries)
    report = certify_factor_validation_pit_for_runs(
        client, universe_name="sp500_current", horizon_type="next_month"
    )
    assert report["ok"] is True
    assert report["runs_inspected"] == 2
    assert report["summaries_inspected"] == 3
    assert report["summaries_updated"] == 2
    assert report["summaries_already_certified"] == 1
    assert set(report["updated_ids"]) == {"s1", "s2"}
    # the other-universe row must be untouched
    untouched = next(s for s in client._summaries if s["id"] == "s4")
    assert untouched.get("summary_json") == {}


def test_certify_factor_validation_pit_for_runs_factor_filter() -> None:
    runs = [
        {
            "id": "r1",
            "status": "completed",
            "completed_at": "2026-04-16T00:00:00Z",
            "universe_name": "sp500_current",
            "horizon_type": "next_month",
        }
    ]
    summaries = [
        {"id": "s1", "run_id": "r1", "factor_name": "accruals", "summary_json": {}},
        {"id": "s2", "run_id": "r1", "factor_name": "gross_profitability", "summary_json": {}},
    ]
    client = _FakeClient(runs, summaries)
    report = certify_factor_validation_pit_for_runs(
        client,
        universe_name="sp500_current",
        horizon_type="next_month",
        factor_name="accruals",
    )
    assert report["summaries_inspected"] == 1
    assert report["summaries_updated"] == 1
    assert report["updated_ids"] == ["s1"]


def test_validation_runner_writes_pit_rule_into_summary_json() -> None:
    """Regression: the live pipeline already emits the canonical rule in summary_json."""
    # We don't run the whole pipeline; instead import the module source and
    # assert the constants are present. If someone refactors the writer away,
    # this reminder test will fail. The functional guarantee is covered by
    # test_certify_factor_validation_pit_for_runs_updates_only_changed above.
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "research" / "validation_runner.py"
    text = src.read_text(encoding="utf-8")
    assert "\"pit_certified\": True" in text
    assert "accepted_at_signal_date_pit_rule_v0" in text
