"""Phase 11.1 hardening + Phase 12 public-core cycle tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sources.transcripts_normalizer import normalize_fmp_earning_call_payload


def test_normalize_revision_id_is_full_sha256() -> None:
    row = normalize_fmp_earning_call_payload(
        ticker="A",
        fiscal_year=2020,
        fiscal_quarter=1,
        http_status=200,
        payload=[{"content": "abc", "date": "2020-01-01"}],
        raw_payload_fmp_id=None,
        issuer_id=None,
        ingest_run_id="ir1",
    )
    assert row is not None
    assert len(row["revision_id"] or "") == 64
    assert row["provenance_json"].get("refresh_audit", {}).get("ingest_run_id") == "ir1"


def test_archive_raw_inserts_history_when_prior_exists() -> None:
    from db.records import archive_raw_transcript_payload_fmp_before_upsert

    hist_ids: list[str] = []

    def fake_fetch(*_a, **_k):
        return {"id": "old-uuid", "http_status": 200, "raw_response_json": {"a": 1}}

    def fake_hist(_client, **_kw):
        hist_ids.append("ok")
        return "new-hist-id"

    client = MagicMock()
    with patch(
        "db.records.fetch_raw_transcript_payload_fmp", side_effect=fake_fetch
    ), patch(
        "db.records.insert_raw_transcript_payload_fmp_history", side_effect=fake_hist
    ):
        archive_raw_transcript_payload_fmp_before_upsert(
            client, symbol="AAPL", fiscal_year=2020, fiscal_quarter=3, ingest_run_id="r1"
        )
    assert hist_ids == ["ok"]


def test_probe_marks_registry_inactive_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    from config import Settings

    s = Settings.model_validate(
        {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "k",
            "EDGAR_IDENTITY": "a@b.c",
        }
    )
    acts: list[str] = []

    def track(_c, *, source_id: str, activation_status: str) -> None:
        acts.append(activation_status)

    with patch(
        "sources.transcripts_ingest.dbrec.merge_update_source_overlay_availability"
    ), patch("sources.transcripts_ingest.dbrec.insert_source_overlay_run_row"), patch(
        "sources.transcripts_ingest.dbrec.patch_data_source_registry_activation",
        side_effect=track,
    ):
        from sources.transcripts_ingest import run_fmp_probe_and_update_overlay

        run_fmp_probe_and_update_overlay(MagicMock(), s)
    assert "inactive" in acts


def test_ingest_blocked_still_enters_operational_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://t.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setenv("EDGAR_IDENTITY", "a@b.c")
    monkeypatch.delenv("FMP_API_KEY", raising=False)

    entered: dict[str, object] = {}

    class FakeOp:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            entered["entered"] = True
            self.operational_run_id = "00000000-0000-0000-0000-000000000099"
            return self

        def __exit__(self, *a):
            return False

        def finish_failed(self, **kw):
            entered["failure_category"] = kw.get("failure_category")

    with patch("db.client.get_supabase_client", return_value=MagicMock()):
        with patch("observability.run_logger.OperationalRunSession", FakeOp):
            from types import SimpleNamespace

            from main import _cmd_ingest_transcripts_sample

            rc = _cmd_ingest_transcripts_sample(
                SimpleNamespace(symbol="AAPL", year=2020, quarter=3)
            )
    assert entered.get("entered") is True
    assert entered.get("failure_category") == "configuration_error"
    assert rc == 1


def test_run_public_core_cycle_empty_watchlist_still_ok(tmp_path: Path) -> None:
    from public_core.cycle import run_public_core_cycle

    with patch(
        "db.records.fetch_latest_state_change_run_id", return_value="sc-run-1"
    ), patch(
        "state_change.reports.build_state_change_run_report",
        return_value={"ok": True},
    ), patch(
        "harness.input_materializer.materialize_inputs_for_run",
        return_value={"inputs_built": 0, "errors": []},
    ), patch(
        "harness.run_batch.generate_memos_for_run",
        return_value={"memos_inserted_new_version": 0, "errors": []},
    ), patch(
        "casebook.build_run.run_outlier_casebook_build",
        return_value={"entries_created": 0, "casebook_run_id": "cb1"},
    ), patch(
        "scanner.daily_build.run_daily_scanner_build",
        return_value={
            "watchlist_entries": 0,
            "scanner_run_id": "sr1",
            "stats": {"candidates_scanned": 5},
        },
    ), patch(
        "sources.transcripts_ingest.report_transcripts_overlay_status",
        return_value={"availability": "not_available_yet"},
    ), patch(
        "sources.reporting.build_source_registry_report", return_value={"ok": True}
    ), patch("db.records.fetch_operational_runs_recent", return_value=[]):
        out = run_public_core_cycle(
            MagicMock(),
            MagicMock(),
            universe="sp500_current",
            out_dir=tmp_path,
        )
    assert out.get("ok") is True
    assert (tmp_path / "cycle_summary.json").is_file()


def test_run_public_core_cycle_fails_without_run(tmp_path: Path) -> None:
    from public_core.cycle import run_public_core_cycle

    with patch("db.records.fetch_latest_state_change_run_id", return_value=None):
        out = run_public_core_cycle(
            MagicMock(),
            MagicMock(),
            universe="sp500_current",
            ensure_state_change=False,
            out_dir=tmp_path,
        )
    assert out.get("ok") is False


def test_phase12_cli_registered() -> None:
    from main import build_parser

    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    names = set(sub.choices.keys())
    assert "run-public-core-cycle" in names
    assert "report-public-core-cycle" in names
