"""Phase 36 — metadata reconciliation targets, residual join, freeze, handoff brief."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from phase36.joined_metadata_reconciliation import (
    _classify_reconciliation_bucket,
    _panel_has_missing_market_metadata_flag,
)
from phase36.phase35_bundle_io import (
    load_phase35_bundle,
    newly_joined_references_from_phase35,
)
from phase36.phase37_recommend import recommend_phase37_after_phase36
from phase36.research_handoff_brief import build_research_engine_handoff_brief
from phase36.residual_state_change_join import (
    REPAIRABLE_RESIDUAL_BUCKETS,
    run_residual_state_change_join_repair,
)
from phase36.residual_pit_deferral import build_residual_pit_deferral_summary
from phase36.review import (
    write_phase36_1_complete_narrow_integrity_round_bundle_json,
    write_phase36_1_complete_narrow_integrity_round_review_md,
    write_phase36_substrate_freeze_and_research_handoff_bundle_json,
    write_phase36_substrate_freeze_and_research_handoff_review_md,
)
from phase36.substrate_freeze_readiness import (
    FREEZE_PUBLIC_CORE,
    ONE_MORE_NARROW,
    STILL_BLOCKED,
    report_substrate_freeze_readiness,
)


def test_newly_joined_references_from_phase35_minimal_bundle() -> None:
    bundle = {
        "forward_validation_join_displacement_final": {
            "rows": [
                {
                    "displacement_bucket": "included_in_joined_recipe_substrate",
                    "reference_from_phase34": {
                        "symbol": "AAA",
                        "cik": "0000000001",
                        "accession_no": "0000000001-24-000001",
                        "factor_version": "v1",
                        "signal_available_date": "2024-06-01",
                    },
                }
            ]
        }
    }
    refs = newly_joined_references_from_phase35(bundle)
    assert len(refs) == 1
    assert refs[0]["symbol"] == "AAA"


def test_panel_metadata_flag_detection() -> None:
    assert _panel_has_missing_market_metadata_flag(
        {"panel_json": {"quality_flags": ["missing_market_metadata"]}}
    )
    assert not _panel_has_missing_market_metadata_flag(
        {"panel_json": {"quality_flags": []}}
    )


def test_classify_true_missing_no_meta_row() -> None:
    row = {
        "symbol": "ZZ",
        "cik": "1",
        "signal_available_date": "2024-06-01",
        "panel_json": {"quality_flags": ["missing_market_metadata"]},
    }
    client = MagicMock()
    b, d = _classify_reconciliation_bucket(
        row,
        client=client,
        registry_by_sym={"ZZ": {"symbol": "ZZ"}},
        meta_by_sym={},
    )
    assert b == "true_missing_market_metadata"


def test_classify_metadata_visible_when_asof_before_signal() -> None:
    row = {
        "symbol": "ZZ",
        "cik": "1",
        "signal_available_date": "2024-06-15",
        "panel_json": {"quality_flags": ["missing_market_metadata"]},
    }
    client = MagicMock()
    b, _d = _classify_reconciliation_bucket(
        row,
        client=client,
        registry_by_sym={"ZZ": {}},
        meta_by_sym={"ZZ": {"as_of_date": "2024-06-01"}},
    )
    assert b == "metadata_visible_but_not_selected"


def test_classify_stale_when_asof_ok_and_flag() -> None:
    row = {
        "symbol": "ZZ",
        "cik": "1",
        "signal_available_date": "2024-06-01",
        "panel_json": {"quality_flags": ["missing_market_metadata"]},
    }
    client = MagicMock()
    b, _d = _classify_reconciliation_bucket(
        row,
        client=client,
        registry_by_sym={"ZZ": {}},
        meta_by_sym={"ZZ": {"as_of_date": "2024-06-15"}},
    )
    assert b == "stale_metadata_flag_after_join"


def test_freeze_still_blocked_low_joined() -> None:
    fr = report_substrate_freeze_readiness(
        snapshot_after={
            "joined_recipe_substrate_row_count": 10,
            "thin_input_share": 1.0,
        },
        metadata_reconciliation={"metadata_flags_still_present_count": 0},
        residual_join_report_after={"rows": []},
        gis_outcome=None,
    )
    assert fr["substrate_freeze_recommendation"] == STILL_BLOCKED


def test_freeze_one_more_narrow_meta_or_repairable_sc() -> None:
    fr = report_substrate_freeze_readiness(
        snapshot_after={
            "joined_recipe_substrate_row_count": 266,
            "thin_input_share": 1.0,
        },
        metadata_reconciliation={"metadata_flags_still_present_count": 2},
        residual_join_report_after={"rows": []},
        gis_outcome=None,
    )
    assert fr["substrate_freeze_recommendation"] == ONE_MORE_NARROW

    fr2 = report_substrate_freeze_readiness(
        snapshot_after={
            "joined_recipe_substrate_row_count": 266,
            "thin_input_share": 1.0,
        },
        metadata_reconciliation={"metadata_flags_still_present_count": 0},
        residual_join_report_after={
            "rows": [
                {"residual_join_bucket": "state_change_not_built_for_row"},
            ]
        },
        gis_outcome=None,
    )
    assert fr2["substrate_freeze_recommendation"] == ONE_MORE_NARROW


def test_freeze_public_core_residual_only_non_repairable() -> None:
    fr = report_substrate_freeze_readiness(
        snapshot_after={
            "joined_recipe_substrate_row_count": 266,
            "thin_input_share": 1.0,
        },
        metadata_reconciliation={"metadata_flags_still_present_count": 0},
        residual_join_report_after={
            "rows": [
                {"residual_join_bucket": "state_change_built_but_join_key_mismatch"},
            ]
        },
        gis_outcome="blocked_unmapped_concepts_remain_in_sample",
    )
    assert fr["substrate_freeze_recommendation"] == FREEZE_PUBLIC_CORE


def test_phase37_recommend_tracks_freeze() -> None:
    p37a = recommend_phase37_after_phase36(
        freeze_report={"substrate_freeze_recommendation": FREEZE_PUBLIC_CORE}
    )
    assert "research_engine" in p37a["phase37_recommendation"]
    p37b = recommend_phase37_after_phase36(
        freeze_report={"substrate_freeze_recommendation": STILL_BLOCKED}
    )
    assert "structural" in p37b["phase37_recommendation"]


def test_research_handoff_brief_shape() -> None:
    brief = build_research_engine_handoff_brief(
        universe_name="u",
        closeout_summary={
            "joined_recipe_substrate_row_count": 1,
            "joined_market_metadata_flagged_count": 0,
            "no_state_change_join": 0,
        },
        substrate_freeze_recommendation=FREEZE_PUBLIC_CORE,
        phase37_recommendation="x",
        residual_join_summary={"residual_row_count": 0},
        metadata_reconciliation_summary={},
    )
    assert "next_build_agenda" in brief
    assert "hypothesis_forge" in brief["next_build_agenda"]


def test_repairable_buckets_constant() -> None:
    assert "state_change_not_built_for_row" in REPAIRABLE_RESIDUAL_BUCKETS


@patch("phase36.residual_state_change_join.compute_substrate_coverage")
@patch("phase36.residual_state_change_join.get_supabase_client")
@patch("phase36.residual_state_change_join.run_state_change")
@patch("phase36.residual_state_change_join.report_residual_state_change_join_gaps")
def test_residual_repair_skips_when_no_targets(
    mock_rep: MagicMock,
    mock_sc: MagicMock,
    mock_client: MagicMock,
    mock_cov: MagicMock,
) -> None:
    mock_rep.return_value = {
        "ok": True,
        "rows": [
            {
                "residual_join_bucket": "state_change_built_but_join_key_mismatch",
                "cik": "1",
            }
        ],
    }
    mock_cov.return_value = ({}, {"no_state_change_join": 8})
    mock_client.return_value = MagicMock()
    settings = MagicMock()
    settings.supabase_url = "https://x.test"
    settings.supabase_service_role_key = "k"
    out = run_residual_state_change_join_repair(
        settings, universe_name="sp500_current", panel_limit=100
    )
    assert out.get("skipped") is True
    mock_sc.assert_not_called()


def test_write_phase36_review_and_bundle(tmp_path: Path) -> None:
    bundle = {
        "closeout_summary": {
            "joined_recipe_substrate_row_count": 266,
            "joined_market_metadata_flagged_count": 0,
            "thin_input_share": 1.0,
            "missing_excess_return_1q": 78,
            "missing_validation_symbol_count": 151,
            "missing_quarter_snapshot_for_cik": 148,
            "factor_panel_missing_for_resolved_cik": 148,
            "no_state_change_join": 8,
            "metadata_flags_cleared_now_count": 0,
            "metadata_flags_still_present_count": 0,
            "no_state_change_join_cleared_now_count": 0,
            "residual_join_rows_still_blocked_count": 8,
            "maturity_deferred_symbol_count": 7,
            "gis_outcome": "blocked_unmapped_concepts_remain_in_sample",
        },
        "substrate_freeze_readiness": {
            "substrate_freeze_recommendation": FREEZE_PUBLIC_CORE,
            "rationale": "test",
        },
        "phase37": {
            "phase37_recommendation": "execute_research_engine_backlog_sprint",
            "rationale": "test",
        },
    }
    md = tmp_path / "r.md"
    write_phase36_substrate_freeze_and_research_handoff_review_md(str(md), bundle=bundle)
    assert "Phase 36" in md.read_text(encoding="utf-8")
    jo = tmp_path / "b.json"
    write_phase36_substrate_freeze_and_research_handoff_bundle_json(str(jo), bundle=bundle)
    assert json.loads(jo.read_text(encoding="utf-8"))["phase37"]["phase37_recommendation"]


def test_build_residual_pit_deferral_summary() -> None:
    s = build_residual_pit_deferral_summary(
        {
            "rows": [
                {
                    "symbol": "AB",
                    "residual_join_bucket": "state_change_built_but_join_key_mismatch",
                }
            ],
            "residual_join_bucket_counts": {
                "state_change_built_but_join_key_mismatch": 1
            },
        }
    )
    assert s["deferred_row_count"] == 1
    assert "AB" in s["symbols_deferred"]
    assert s["policy"] == "no_broad_state_change_rerun"


def test_write_phase36_1_review(tmp_path: Path) -> None:
    bundle = {
        "closeout_summary": {
            "joined_recipe_substrate_row_count": 266,
            "joined_market_metadata_flagged_count": 0,
            "no_state_change_join": 8,
            "metadata_flags_cleared_now_count": 23,
            "metadata_flags_still_present_count": 0,
            "validation_rebuild_target_count_after_hydration": 23,
            "metadata_reconciliation_bucket_counts_before": {"stale_metadata_flag_after_join": 23},
            "metadata_reconciliation_bucket_counts_mid": {"stale_metadata_flag_after_join": 23},
            "metadata_reconciliation_bucket_counts_after": {},
            "residual_pit_deferred_row_count": 8,
            "substrate_freeze_recommendation": FREEZE_PUBLIC_CORE,
            "phase37_recommendation": "execute_research_engine_backlog_sprint",
        },
        "substrate_freeze_readiness": {
            "substrate_freeze_recommendation": FREEZE_PUBLIC_CORE,
            "rationale": "test",
        },
        "phase37": {
            "phase37_recommendation": "execute_research_engine_backlog_sprint",
            "rationale": "test",
        },
        "joined_metadata_reconciliation_two_pass": {
            "validation_rebuild_factor_panels_submitted": 23,
        },
        "residual_pit_deferral": {
            "policy": "no_broad_state_change_rerun",
            "deferred_row_count": 8,
            "residual_join_bucket_counts": {"state_change_built_but_join_key_mismatch": 8},
            "symbols_deferred": ["A", "B"],
        },
    }
    md = tmp_path / "p361.md"
    write_phase36_1_complete_narrow_integrity_round_review_md(str(md), bundle=bundle)
    txt = md.read_text(encoding="utf-8")
    assert "Phase 36.1" in txt
    assert "PIT" in txt
    jo = tmp_path / "p361.json"
    write_phase36_1_complete_narrow_integrity_round_bundle_json(str(jo), bundle=bundle)
    out = json.loads(jo.read_text(encoding="utf-8"))
    assert out["closeout_summary"]["metadata_flags_cleared_now_count"] == 23
    assert out["residual_pit_deferral"]["deferred_row_count"] == 8


def test_load_phase35_fixture_if_present() -> None:
    p = Path("docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json")
    if not p.is_file():
        return
    b = load_phase35_bundle(str(p))
    refs = newly_joined_references_from_phase35(b)
    assert len(refs) >= 1
