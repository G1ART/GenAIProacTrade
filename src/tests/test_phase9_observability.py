"""Phase 9: operational run session, registry boundary, reporting helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from main import build_parser

from observability.run_logger import OperationalRunSession
from research_registry.promotion_rules import (
    assert_no_auto_promotion_wiring,
    describe_production_boundary,
    validate_status,
)
from research_registry.registry import ensure_sample_hypotheses


def test_validate_status_ok() -> None:
    assert validate_status("sandbox_only") == "sandbox_only"


def test_validate_status_bad() -> None:
    with pytest.raises(ValueError):
        validate_status("not_a_real_status")


def test_describe_boundary_has_scoring_rule() -> None:
    d = describe_production_boundary()
    assert "production_scoring_rule" in d
    assert "hypothesis_registry" in str(d["production_scoring_rule"])


def test_assert_no_auto_promotion_wiring() -> None:
    assert_no_auto_promotion_wiring()


def test_operational_run_session_success_finishes_once() -> None:
    client = MagicMock()
    with patch("observability.run_logger.dbrec") as m:
        m.insert_operational_run_started.return_value = "op-uuid-1"
        with OperationalRunSession(client, run_type="t", component="c") as op:
            assert op.operational_run_id == "op-uuid-1"
            op.finish_success(rows_read=3, rows_written=2, warnings_count=0)
        assert m.finalize_operational_run.call_count == 1
        m.insert_operational_failure.assert_not_called()


def test_operational_run_session_abandon_marks_failed() -> None:
    client = MagicMock()
    with patch("observability.run_logger.dbrec") as m:
        m.insert_operational_run_started.return_value = "op-uuid-2"
        with OperationalRunSession(client, run_type="t", component="c"):
            pass
        assert m.finalize_operational_run.call_count == 1
        fin = m.finalize_operational_run.call_args.kwargs
        assert fin["status"] == "failed"
        assert fin["error_code"] == "no_finish_called"
        m.insert_operational_failure.assert_called_once()


def test_operational_run_session_exception() -> None:
    client = MagicMock()
    with patch("observability.run_logger.dbrec") as m:
        m.insert_operational_run_started.return_value = "op-uuid-3"
        with pytest.raises(RuntimeError):
            with OperationalRunSession(client, run_type="t", component="c"):
                raise RuntimeError("boom")
        assert m.finalize_operational_run.call_count == 1
        assert m.insert_operational_failure.call_count == 1


def test_finish_empty_valid_no_failure_row() -> None:
    client = MagicMock()
    with patch("observability.run_logger.dbrec") as m:
        m.insert_operational_run_started.return_value = "op-uuid-4"
        with OperationalRunSession(client, run_type="t", component="c") as op:
            op.finish_empty_valid(rows_read=0, trace_json={"k": 1})
        m.insert_operational_failure.assert_not_called()
        assert m.finalize_operational_run.call_args.kwargs["status"] == "empty_valid"


def test_phase9_cli_registered() -> None:
    p = build_parser()
    sub = next(
        a for a in p._actions if getattr(a, "dest", None) == "command"
    )
    names = set(sub.choices.keys())
    for c in (
        "smoke-phase9-observability",
        "report-run-health",
        "report-failures",
        "report-research-registry",
        "seed-phase9-research-samples",
    ):
        assert c in names, f"missing CLI {c}"


def test_ensure_sample_hypotheses_idempotent() -> None:
    client = MagicMock()
    with patch("research_registry.registry.dbrec") as m:
        m.hypothesis_exists_by_title.return_value = True
        out = ensure_sample_hypotheses(client)
        assert out["created"] == []
        assert len(out["skipped"]) == 2
        m.insert_research_hypothesis.assert_not_called()
