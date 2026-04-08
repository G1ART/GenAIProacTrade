"""Phase 28: Yahoo 메타데이터, 수화 차단·카운터, 팩터 물질화 리포트."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from market.price_ingest import _metadata_row_current_enough, _symbol_still_missing_avg_meta
from market.providers.base import MarketMetadataRow
from market.providers.yahoo_chart_provider import YahooChartMarketProvider


def test_metadata_row_current_enough_volume_tolerance() -> None:
    m = MarketMetadataRow(
        symbol="X",
        as_of_date=date(2024, 6, 1),
        avg_daily_volume=100.0,
    )
    ex = {"as_of_date": "2024-06-01", "avg_daily_volume": 100.4}
    assert _metadata_row_current_enough(ex, m) is True


def test_symbol_still_missing_avg_meta() -> None:
    assert _symbol_still_missing_avg_meta(None) is True
    assert _symbol_still_missing_avg_meta({"avg_daily_volume": None}) is True
    assert _symbol_still_missing_avg_meta({"avg_daily_volume": 1.0}) is False


@patch("market.providers.yahoo_chart_provider._http_get_json")
def test_yahoo_fetch_market_metadata_from_chart(mock_http: MagicMock) -> None:
    ts = 1_700_000_000
    mock_http.return_value = {
        "chart": {
            "result": [
                {
                    "timestamp": [ts, ts + 86400],
                    "meta": {"exchangeName": "NYSE"},
                    "indicators": {
                        "quote": [
                            {
                                "open": [10.0, 11.0],
                                "high": [10.5, 11.5],
                                "low": [9.5, 10.5],
                                "close": [10.2, 11.0],
                                "volume": [1_000_000.0, 2_000_000.0],
                            }
                        ],
                        "adjclose": [{}],
                    },
                }
            ]
        }
    }
    y = YahooChartMarketProvider()
    rows = y.fetch_market_metadata(["ABC"])
    assert len(rows) == 1
    assert rows[0].symbol == "ABC"
    assert rows[0].avg_daily_volume == 1_500_000.0
    assert rows[0].exchange == "NYSE"


@patch("market.price_ingest.ingest_run_finalize")
@patch("market.price_ingest.ingest_run_create_started", return_value="rid")
@patch("market.price_ingest.fetch_market_metadata_latest_rows_for_symbols")
@patch("market.price_ingest.fetch_max_as_of_universe", return_value="2024-01-01")
@patch("market.price_ingest.fetch_symbols_universe_as_of", return_value=["ZZZ"])
@patch("market.price_ingest.get_market_provider")
@patch("market.price_ingest.get_supabase_client")
def test_hydration_blocked_when_provider_returns_no_rows(
    mock_client: MagicMock,
    mock_gp: MagicMock,
    _fsym: MagicMock,
    _fasof: MagicMock,
    mock_fetch_meta: MagicMock,
    _create: MagicMock,
    _fin: MagicMock,
) -> None:
    mock_fetch_meta.return_value = {}
    prov = MagicMock()
    prov.name = "noop_provider"
    prov.fetch_market_metadata.return_value = []
    mock_gp.return_value = prov
    mock_client.return_value = MagicMock()

    from market.price_ingest import run_market_metadata_hydration_for_symbols

    out = run_market_metadata_hydration_for_symbols(
        object(),
        universe_name="u1",
        symbols=["ZZZ"],
    )
    assert out["status"] == "blocked"
    assert out["blocked_reason"] == "provider_returned_zero_metadata_rows"
    assert out["provider_rows_returned"] == 0


@patch("phase28.factor_materialization.report_validation_registry_gaps")
def test_factor_materialization_report_decomposes_factor_bucket(
    mock_reg: MagicMock,
) -> None:
    mock_reg.return_value = {
        "ok": True,
        "metrics": {"as_of_date": "2024-01-15"},
        "registry_buckets": {
            "factor_panel_missing_for_resolved_cik": ["S1", "S2"],
            "validation_panel_build_omission_for_cik": [],
        },
        "registry_bucket_counts": {},
    }
    client = MagicMock()

    def _sym_universe(*_a: object, **_k: object) -> list[str]:
        return ["S1", "S2"]

    def _cik_map(_c: object, syms: list[str]) -> dict[str, str]:
        return {"S1": "0000000001", "S2": "0000000002"}

    snaps_by_cik: dict[str, list] = {"0000000001": [{"cik": "0000000001"}], "0000000002": []}

    with patch(
        "phase28.factor_materialization.dbrec.fetch_symbols_universe_as_of",
        side_effect=_sym_universe,
    ), patch(
        "phase28.factor_materialization.dbrec.fetch_cik_map_for_tickers",
        side_effect=_cik_map,
    ), patch(
        "phase28.factor_materialization.dbrec.fetch_issuer_quarter_snapshots_for_cik",
        side_effect=lambda _cl, cik: list(snaps_by_cik.get(str(cik), [])),
    ):
        from phase28.factor_materialization import report_factor_panel_materialization_gaps

        rep = report_factor_panel_materialization_gaps(
            client, universe_name="sp500_current", panel_limit=100
        )
    mb = rep["materialization_bucket_counts"]
    assert mb["missing_quarter_snapshot_for_cik"] == 1
    assert mb["snapshot_present_but_factor_panel_missing"] == 1


@patch("phase28.factor_materialization.report_validation_registry_gaps")
def test_factor_materialization_uses_registry_report_without_requery(
    mock_reg: MagicMock,
) -> None:
    pre = {
        "ok": True,
        "metrics": {"as_of_date": "2024-01-15"},
        "registry_buckets": {
            "factor_panel_missing_for_resolved_cik": [],
            "validation_panel_build_omission_for_cik": [],
        },
        "registry_bucket_counts": {},
    }
    client = MagicMock()
    with patch(
        "phase28.factor_materialization.dbrec.fetch_symbols_universe_as_of",
        return_value=[],
    ), patch(
        "phase28.factor_materialization.dbrec.fetch_cik_map_for_tickers",
        return_value={},
    ):
        from phase28.factor_materialization import report_factor_panel_materialization_gaps

        report_factor_panel_materialization_gaps(
            client,
            universe_name="sp500_current",
            panel_limit=100,
            registry_report=pre,
        )
    mock_reg.assert_not_called()
