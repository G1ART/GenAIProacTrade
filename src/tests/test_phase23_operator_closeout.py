"""Phase 23: operator closeout, migration preflight, chooser, zero-UUID export path."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import state_change.runner as sc_runner
from operator_closeout.closeout import format_guided_operator_error
from operator_closeout.migrations import (
    generate_migration_bundle_file,
    list_local_migration_files,
    report_required_migrations,
)
from operator_closeout.next_step import choose_post_patch_next_action_from_signals
from operator_closeout.phase_state import verify_db_phase_state
from operator_closeout.presets import load_operator_closeout_preset
from public_repair_iteration.depth_iteration import resolve_iteration_series_for_operator


def test_runner_still_no_public_repair_iteration_reference() -> None:
    src = inspect.getsource(sc_runner)
    assert "public_repair_iteration" not in src
    assert "public_repair_campaign" not in src


@pytest.mark.parametrize(
    ("esc", "sig", "verify", "want"),
    [
        ("continue_public_depth", "continue_public_depth_buildout", False, "advance_public_depth_iteration"),
        ("hold_and_repeat_public_repair", "repeat_targeted_public_repair", False, "advance_repair_series"),
        ("continue_public_depth", "public_depth_near_plateau_review_required", False, "hold_for_plateau_review"),
        ("open_targeted_premium_discovery", "continue_public_depth_buildout", False, "hold_for_plateau_review"),
        ("hold_and_repeat_public_repair", "unknown_signal_fallback", False, "advance_public_depth_iteration"),
        ("continue_public_depth", "continue_public_depth_buildout", True, "verify_only"),
    ],
)
def test_chooser_from_signals(esc: str, sig: str, verify: bool, want: str) -> None:
    out = choose_post_patch_next_action_from_signals(
        escalation_recommendation=esc,
        depth_operator_signal=sig,
        verify_only=verify,
    )
    assert out["action"] == want


def test_list_local_migration_files_has_phase22(tmp_path: Path) -> None:
    m = tmp_path / "migrations"
    m.mkdir()
    (m / "20250425100000_phase22_public_depth_iteration.sql").write_text("-- x", encoding="utf-8")
    (m / "20250401000000_early.sql").write_text("-- y", encoding="utf-8")
    rows = list_local_migration_files(m)
    assert [r["filename"] for r in rows] == [
        "20250401000000_early.sql",
        "20250425100000_phase22_public_depth_iteration.sql",
    ]
    assert rows[1]["version"] == "20250425100000"


def _client_schema_migrations(versions: list[str]):
    class _Exec:
        def __init__(self, v: list[str]) -> None:
            self._v = v

        def execute(self):
            r = MagicMock()
            r.data = [{"version": x} for x in self._v]
            return r

    class _Chain:
        def __init__(self, v: list[str]) -> None:
            self._v = v

        def table(self, _name: str):
            return self

        def select(self, _cols: str):
            return _Exec(self._v)

    class _Client:
        def schema(self, _name: str):
            return _Chain(versions)

    return _Client()


def test_report_required_migrations_detects_missing(tmp_path: Path) -> None:
    m = tmp_path / "migrations"
    m.mkdir()
    (m / "20250401000000_a.sql").write_text("-- a", encoding="utf-8")
    (m / "20250402000000_b.sql").write_text("-- b", encoding="utf-8")
    client = _client_schema_migrations(["20250401000000"])
    rep = report_required_migrations(client, migrations_dir=m)
    assert rep["applied_probe_ok"] is True
    assert rep["ok"] is False
    assert len(rep["missing_migrations"]) == 1
    assert rep["missing_migrations"][0]["filename"] == "20250402000000_b.sql"


def test_report_required_migrations_probe_unavailable(tmp_path: Path) -> None:
    class _Bad:
        def schema(self, _n: str):
            raise RuntimeError("no schema in postgrest")

    m = tmp_path / "migrations"
    m.mkdir()
    (m / "20250401000000_a.sql").write_text("-- a", encoding="utf-8")
    rep = report_required_migrations(_Bad(), migrations_dir=m)
    assert rep["applied_probe_ok"] is False
    assert rep["ok"] is False
    assert rep["missing_migrations"] == []


def test_generate_migration_bundle_file_writes(tmp_path: Path) -> None:
    m = tmp_path / "migrations"
    m.mkdir()
    p1 = m / "20250401000000_a.sql"
    p1.write_text("SELECT 1;", encoding="utf-8")
    p2 = m / "20250402000000_b.sql"
    p2.write_text("SELECT 2;", encoding="utf-8")
    rep = {
        "missing_migrations": [
            {"filename": "20250402000000_b.sql", "version": "20250402000000", "reason": "x"}
        ]
    }
    out = tmp_path / "bundle.sql"
    gen = generate_migration_bundle_file(rep, out_path=out, migrations_dir=m)
    assert gen["written"] is True
    text = out.read_text(encoding="utf-8")
    assert "20250402000000_b.sql" in text
    assert "SELECT 2;" in text
    assert "SELECT 1;" not in text


def test_verify_db_phase_state_stops_on_first_error() -> None:
    calls: list[str] = []

    def fail17(_c):
        calls.append("17")
        raise RuntimeError("boom17")

    client = object()
    from operator_closeout import phase_state as ps

    orig = ps._SMOKE_CHAIN
    try:
        ps._SMOKE_CHAIN = [
            ("phase17_public_depth", fail17),
            ("phase18_public_buildout", lambda _c: calls.append("18")),
        ]
        out = verify_db_phase_state(client)
    finally:
        ps._SMOKE_CHAIN = orig
    assert out["ok"] is False
    assert out["failed_at"] == "phase17_public_depth"
    assert calls == ["17"]


def test_format_guided_operator_error_ambiguous_universe() -> None:
    text = format_guided_operator_error(
        {
            "error": "ambiguous_latest_program_need_universe",
            "universes_seen": ["u1", "u2"],
        }
    )
    assert "u1" in text and "u2" in text
    assert "error:" in text


def test_format_guided_operator_error_ambiguous_series() -> None:
    text = format_guided_operator_error(
        {
            "error": "ambiguous_multiple_active_series",
            "series_ids": ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"],
        }
    )
    assert "aaaaaaaa" in text
    assert "error:" in text


def test_resolve_iteration_series_for_operator_program_not_found() -> None:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=None
    )
    # fetch_research_program path — stub via dbrec is heavy; use patch
    from unittest.mock import patch

    with patch("public_repair_iteration.depth_iteration.dbrec.fetch_research_program", return_value=None):
        out = resolve_iteration_series_for_operator(client, program_id="pid", universe_name="u")
    assert out["ok"] is False
    assert out["error"] == "program_not_found"


def test_load_operator_closeout_preset_missing(tmp_path: Path) -> None:
    assert load_operator_closeout_preset(tmp_path / "nope.json") == {}


def test_load_operator_closeout_preset_reads(tmp_path: Path) -> None:
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"universe": "sp500_current", "out_stem": "docs/x"}), encoding="utf-8")
    d = load_operator_closeout_preset(p)
    assert d["universe"] == "sp500_current"


def test_main_registers_phase23_commands() -> None:
    from main import build_parser

    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "choices", None))
    names = set(sub.choices.keys())
    assert "report-required-migrations" in names
    assert "verify-db-phase-state" in names
    assert "run-post-patch-closeout" in names
