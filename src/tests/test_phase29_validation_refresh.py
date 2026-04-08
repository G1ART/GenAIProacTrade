"""Phase 29: 결정적 메타 선택, stale 검증 갱신, 분기 스냅샷 분류."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from db.records import pick_best_market_metadata_row


def test_pick_best_market_metadata_row_prefers_newer_as_of() -> None:
    rows = [
        {"as_of_date": "2024-01-01", "avg_daily_volume": 1e6},
        {"as_of_date": "2024-06-01", "avg_daily_volume": 1e6},
    ]
    b = pick_best_market_metadata_row(rows)
    assert b is not None
    assert str(b.get("as_of_date"))[:10] == "2024-06-01"


def test_pick_best_market_metadata_row_tiebreak_liquidity() -> None:
    rows = [
        {"as_of_date": "2024-06-01", "avg_daily_volume": None, "market_cap": None},
        {"as_of_date": "2024-06-01", "avg_daily_volume": 100.0, "market_cap": None},
    ]
    b = pick_best_market_metadata_row(rows)
    assert b is not None
    assert b.get("avg_daily_volume") == 100.0


@patch("market.validation_panel_run.fetch_market_metadata_latest_row_deterministic")
@patch("market.validation_panel_run._fetch_forward_map")
def test_validation_build_uses_deterministic_metadata(
    mock_fwd: MagicMock,
    mock_meta: MagicMock,
) -> None:
    import market.validation_panel_run as vpr

    mock_meta.return_value = {
        "symbol": "ZZZ",
        "as_of_date": "2024-05-01",
        "avg_daily_volume": 1.0,
        "market_cap": None,
    }
    mock_fwd.return_value = {
        "next_month": {"raw_forward_return": 0.01, "excess_forward_return": 0.0},
        "next_quarter": {"raw_forward_return": 0.02, "excess_forward_return": 0.0},
    }
    client = MagicMock()
    panel = {
        "cik": "1",
        "accession_no": "a1",
        "factor_version": "v1",
        "fiscal_year": 2024,
        "fiscal_period": "Q1",
        "id": "fp1",
    }
    with patch("market.validation_panel_run.fetch_ticker_for_cik", return_value="ZZZ"), patch(
        "market.validation_panel_run.fetch_quarter_snapshot_by_accession",
        return_value={"cik": "1", "fiscal_year": 2024, "fiscal_period": "Q1"},
    ), patch(
        "market.validation_panel_run.signal_available_date_from_snapshot",
        return_value=__import__("datetime").date(2024, 5, 15),
    ), patch(
        "market.validation_panel_run.upsert_factor_market_validation_panel"
    ) as mock_upsert, patch(
        "market.validation_panel_run.ingest_run_finalize"
    ), patch("market.validation_panel_run.ingest_run_create_started", return_value="rid"):
        vpr._validation_panel_build_loop(client, "rid", [panel])
    mock_meta.assert_called()
    mock_upsert.assert_called()
    call_kw = mock_upsert.call_args[0][1]
    pj = call_kw.get("panel_json") or {}
    flags = pj.get("quality_flags") or []
    assert "missing_market_metadata" not in flags


def test_classify_cik_no_filing_index() -> None:
    from phase29.quarter_snapshot_gaps import classify_cik_quarter_snapshot_gap

    client = MagicMock()

    def _table(name: str) -> MagicMock:
        m = MagicMock()
        m.select.return_value = m
        m.eq.return_value = m
        m.limit.return_value = m
        if name == "issuer_quarter_snapshots":
            m.execute.return_value = MagicMock(data=[])
        elif name == "filing_index":
            m.execute.return_value = MagicMock(data=[])
        elif name == "raw_xbrl_facts":
            m.execute.return_value = MagicMock(data=[])
        elif name == "silver_xbrl_facts":
            m.execute.return_value = MagicMock(data=[])
        return m

    client.table.side_effect = _table
    assert classify_cik_quarter_snapshot_gap(client, cik="0001234567") == "no_filing_index_for_cik"


@patch("phase29.orchestrator.run_factor_panel_materialization_repair")
@patch("phase29.orchestrator.run_quarter_snapshot_backfill_repair")
@patch("phase29.orchestrator.run_validation_refresh_after_metadata_hydration")
@patch("phase29.orchestrator.run_market_metadata_hydration_repair")
@patch("phase29.orchestrator.get_supabase_client")
def test_phase29_orchestrator_call_order(
    mock_client: MagicMock,
    mock_meta: MagicMock,
    mock_stale: MagicMock,
    mock_q: MagicMock,
    mock_fac: MagicMock,
) -> None:
    order: list[str] = []

    def _meta(*_a: object, **_k: object) -> dict:
        order.append("hydration")
        return {"ok": True}

    def _stale(*_a: object, **_k: object) -> dict:
        order.append("stale")
        return {"validation_metadata_flags_cleared_count": 0}

    def _q(*_a: object, **_k: object) -> dict:
        order.append("quarter")
        return {"cik_repairs_succeeded": 0}

    def _fac(*_a: object, **_k: object) -> dict:
        order.append("factor")
        return {"ok": True}

    mock_meta.side_effect = _meta
    mock_stale.side_effect = _stale
    mock_q.side_effect = _q
    mock_fac.side_effect = _fac

    snap = {
        "joined_market_metadata_flagged_count": 10,
        "missing_quarter_snapshot_for_cik": 5,
        "missing_validation_symbol_count": 3,
        "thin_input_share": 1.0,
        "joined_recipe_substrate_row_count": 1,
        "exclusion_distribution": {},
        "registry_gap_rollup": {},
        "quarter_snapshot_classification_counts": {},
    }

    reg_mock = MagicMock(
        return_value={
            "missing_symbol_count": 3,
            "registry_bucket_counts": {},
        }
    )
    with patch(
        "phase29.orchestrator.compute_substrate_coverage",
        return_value=(dict(snap), {}),
    ), patch(
        "phase29.orchestrator.report_market_metadata_gap_drivers",
        return_value={"joined_market_metadata_flagged_count": 10},
    ), patch(
        "phase29.orchestrator.report_validation_registry_gaps",
        reg_mock,
    ), patch(
        "phase29.orchestrator.report_quarter_snapshot_backfill_gaps",
        return_value={"classification_counts": {}},
    ), patch(
        "phase29.orchestrator.report_factor_panel_materialization_gaps",
        return_value={"materialization_bucket_counts": {"missing_quarter_snapshot_for_cik": 5}},
    ):
        from phase29.orchestrator import run_phase29_validation_refresh_and_snapshot_backfill

        run_phase29_validation_refresh_and_snapshot_backfill(
            object(),
            universe_name="u",
            panel_limit=100,
        )

    assert order == ["hydration", "stale", "quarter", "factor"]
    assert reg_mock.call_count == 2


def test_phase29_orchestrator_progress_tags_on_stdout(capsys) -> None:
    snap = {
        "joined_market_metadata_flagged_count": 0,
        "missing_quarter_snapshot_for_cik": 0,
        "missing_validation_symbol_count": 0,
        "thin_input_share": 0.0,
        "joined_recipe_substrate_row_count": 0,
        "exclusion_distribution": {},
        "registry_gap_rollup": {},
        "quarter_snapshot_classification_counts": {},
    }

    def _noop(*_a: object, **_k: object) -> dict:
        return {"ok": True}

    with patch(
        "phase29.orchestrator.get_supabase_client",
        return_value=MagicMock(),
    ), patch(
        "phase29.orchestrator.compute_substrate_coverage",
        return_value=(dict(snap), {}),
    ), patch(
        "phase29.orchestrator.report_market_metadata_gap_drivers",
        return_value={"joined_market_metadata_flagged_count": 0},
    ), patch(
        "phase29.orchestrator.report_validation_registry_gaps",
        return_value={"missing_symbol_count": 0, "registry_bucket_counts": {}},
    ), patch(
        "phase29.orchestrator.report_quarter_snapshot_backfill_gaps",
        return_value={"classification_counts": {}},
    ), patch(
        "phase29.orchestrator.report_factor_panel_materialization_gaps",
        return_value={
            "materialization_bucket_counts": {"missing_quarter_snapshot_for_cik": 0}
        },
    ), patch(
        "phase29.orchestrator.run_market_metadata_hydration_repair",
        side_effect=_noop,
    ), patch(
        "phase29.orchestrator.run_validation_refresh_after_metadata_hydration",
        return_value={"validation_metadata_flags_cleared_count": 0},
    ), patch(
        "phase29.orchestrator.run_quarter_snapshot_backfill_repair",
        return_value={"cik_repairs_succeeded": 0},
    ), patch(
        "phase29.orchestrator.run_factor_panel_materialization_repair",
        side_effect=_noop,
    ):
        from phase29.orchestrator import run_phase29_validation_refresh_and_snapshot_backfill

        run_phase29_validation_refresh_and_snapshot_backfill(
            object(),
            universe_name="u",
            panel_limit=10,
        )

    out = capsys.readouterr().out
    for tag in (
        "phase29_snapshot_before_started",
        "phase29_snapshot_before_validation_registry_done",
        "phase29_metadata_hydration_done",
        "phase29_stale_validation_refresh_done",
        "phase29_quarter_snapshot_backfill_done",
        "phase29_factor_materialization_done",
        "phase29_snapshot_after_started",
        "phase29_snapshot_after_validation_registry_done",
    ):
        assert tag in out
