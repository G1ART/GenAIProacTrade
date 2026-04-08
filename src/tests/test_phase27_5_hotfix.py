"""Phase 27.5: fetch_cik_map 청크 버그, rerun wiring, Phase 28 집계, registry repair 로그."""

from __future__ import annotations

import importlib
import inspect
from unittest.mock import MagicMock, patch

from db.records import fetch_cik_map_for_tickers
from targeted_backfill.phase28_recommend import (
    PHASE28_CONTINUE_BACKFILL,
    recommend_phase28_branch,
)
from targeted_backfill.review import _extract_rerun_readiness, build_phase27_evidence_bundle
from targeted_backfill.validation_registry import registry_gap_rollup_for_bundle


def test_fetch_cik_map_for_tickers_multi_chunk_retains_all_rows() -> None:
    tickers = [f"T{i:03d}" for i in range(130)]
    client = MagicMock()
    exec_mock = MagicMock()
    client.table.return_value.select.return_value.in_.return_value.execute = exec_mock

    def _chunk_rows(start: int, end: int) -> list[dict[str, object]]:
        return [{"ticker": f"T{i:03d}", "cik": str(10_000 + i)} for i in range(start, end)]

    exec_mock.side_effect = [
        MagicMock(data=_chunk_rows(0, 120)),
        MagicMock(data=_chunk_rows(120, 130)),
    ]
    out = fetch_cik_map_for_tickers(client, tickers)
    assert out["T000"] == "10000"
    assert out["T129"] == "10129"
    assert sum(1 for v in out.values() if v is not None) == 130


def test_extract_rerun_readiness_from_flat_trigger() -> None:
    rr = _extract_rerun_readiness(
        {
            "ok": True,
            "program_id": "p1",
            "recommend_rerun_phase15": True,
            "recommend_rerun_phase16": False,
        }
    )
    assert rr["recommend_rerun_phase15"] is True
    assert rr["recommend_rerun_phase16"] is False


def test_extract_rerun_readiness_nested_compat() -> None:
    rr = _extract_rerun_readiness(
        {
            "ok": True,
            "rerun_readiness": {
                "recommend_rerun_phase15": False,
                "recommend_rerun_phase16": True,
            },
        }
    )
    assert rr["recommend_rerun_phase16"] is True


def test_registry_gap_rollup_includes_issuer_master_missing() -> None:
    r = registry_gap_rollup_for_bundle({"issuer_master_missing_for_resolved_cik": 188})
    assert r["registry_blocker_symbol_total"] == 188
    assert r["registry_upstream_or_pipeline_deferred_count"] == 188


def test_phase28_continue_when_only_upstream_registry_blockers() -> None:
    out = recommend_phase28_branch(
        recommend_rerun_phase15=False,
        recommend_rerun_phase16=False,
        true_repairable_forward=0,
        joined_metadata_flagged=0,
        pit_backfill_candidates=0,
        registry_blocker_total_count=188,
        thin_input_share_after=1.0,
    )
    assert out["phase28_recommendation"] == PHASE28_CONTINUE_BACKFILL


@patch("targeted_backfill.review.importlib.import_module")
@patch("targeted_backfill.review.report_validation_registry_gaps")
@patch("targeted_backfill.review.report_market_metadata_gap_drivers")
@patch("targeted_backfill.review.report_forward_gap_maturity")
@patch("targeted_backfill.review.report_state_change_pit_gaps")
@patch("targeted_backfill.review.compute_substrate_coverage")
@patch("targeted_backfill.review.build_revalidation_trigger")
def test_build_phase27_bundle_rerun_readiness_not_empty(
    mock_reval: MagicMock,
    mock_cov: MagicMock,
    mock_pit: MagicMock,
    mock_fwd: MagicMock,
    mock_meta: MagicMock,
    mock_reg: MagicMock,
    mock_im: MagicMock,
) -> None:
    mock_mod = MagicMock()
    mock_mod.resolve_program_id = MagicMock(
        return_value={"ok": True, "program_id": "uuid-1"}
    )
    mock_im.return_value = mock_mod
    mock_reg.return_value = {"registry_bucket_counts": {}}
    mock_meta.return_value = {"joined_market_metadata_flagged_count": 0}
    mock_fwd.return_value = {"true_repairable_forward_gap_count": 0}
    mock_pit.return_value = {"historical_backfill_might_help_count": 0}
    mock_cov.return_value = (
        {"thin_input_share": 0.5, "joined_recipe_substrate_row_count": 10},
        {},
    )
    mock_reval.return_value = {
        "ok": True,
        "program_id": "uuid-1",
        "universe_name": "u1",
        "recommend_rerun_phase15": True,
        "recommend_rerun_phase16": False,
        "thresholds": {},
        "notes": "n",
    }
    client = MagicMock()
    bundle = build_phase27_evidence_bundle(
        client, universe_name="u1", panel_limit=100, program_id_raw="latest"
    )
    assert bundle["rerun_readiness"].get("recommend_rerun_phase15") is True
    assert bundle["wiring_warnings"] == []


def test_repair_closeout_no_premium_strings() -> None:
    forbidden = (
        "hypothesis_registry",
        "research_engine",
        "validation_campaign",
        "open_targeted_premium_discovery",
        "public_repair_iteration",
        "public_repair_campaign",
    )
    m = importlib.import_module("targeted_backfill.repair_closeout")
    src = inspect.getsource(m)
    for tok in forbidden:
        assert tok not in src


@patch("targeted_backfill.validation_registry.report_validation_registry_gaps")
@patch("db.client.get_supabase_client")
def test_validation_registry_repair_includes_blocked_for_factor_bucket(
    mock_get_client: MagicMock,
    mock_report: MagicMock,
) -> None:
    from targeted_backfill.validation_registry import run_validation_registry_repair

    mock_report.side_effect = [
        {
            "missing_symbol_count": 3,
            "metrics": {"as_of_date": "2020-01-01"},
            "registry_buckets": {
                "factor_panel_missing_for_resolved_cik": ["AAA", "BBB"],
            },
            "registry_bucket_counts": {"factor_panel_missing_for_resolved_cik": 2},
        },
        {
            "missing_symbol_count": 3,
            "metrics": {"as_of_date": "2020-01-01"},
            "registry_bucket_counts": {"factor_panel_missing_for_resolved_cik": 2},
        },
    ]
    c = MagicMock()
    mock_get_client.return_value = c

    with patch(
        "targeted_backfill.validation_registry.dbrec.fetch_universe_memberships_for_as_of",
        return_value=[],
    ), patch(
        "targeted_backfill.validation_registry.dbrec.fetch_symbols_universe_as_of",
        return_value=["AAA", "BBB"],
    ), patch(
        "targeted_backfill.validation_registry.dbrec.fetch_cik_map_for_tickers",
        return_value={"AAA": "1", "BBB": "2"},
    ), patch(
        "targeted_backfill.validation_registry.dbrec.fetch_issuer_quarter_factor_panels_for_ciks",
        return_value={},
    ):
        out = run_validation_registry_repair(
            MagicMock(), universe_name="u1", panel_limit=8000
        )

    assert "blocked_actions" in out
    assert "deferred_actions" in out
    kinds = {b.get("kind") for b in out["blocked_actions"]}
    assert "repair_blocked_requires_factor_pipeline_or_accession_ingest" in kinds
