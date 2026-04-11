"""DB-free tests for Phase 43 cohort lock, taxonomy, audit MD, Phase 44, Supabase-fresh retest."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from phase42.blocker_taxonomy import classify_filing_blocker_cause, classify_sector_blocker_cause
from phase43 import AUTHORITATIVE_CLOSEOUT_USES_SUPABASE_FRESH_PHASE42
from phase43.before_after_audit import build_before_after_row_audit, render_before_after_audit_md
from phase43.orchestrator import run_phase43_targeted_substrate_backfill
from phase43.phase44_recommend import recommend_phase44_after_phase43
from phase43.target_cohort import EXACT_COHORT_SIZE, load_targets_from_phase42_supabase_bundle, merge_fixture_residual_from_phase41_bundle


def _eight_row_blockers() -> list[dict]:
    base = [
        ("BBY", "0000764478"),
        ("ADSK", "0000769397"),
        ("CRM", "0001108524"),
        ("CRWD", "0001535527"),
        ("DELL", "0000826083"),
        ("DUK", "0001326160"),
        ("NVDA", "0001045810"),
        ("WMT", "0000104169"),
    ]
    return [
        {
            "symbol": sym,
            "cik": cik,
            "signal_available_date": "2024-06-15",
            "filing_blocker_cause": (
                "only_post_signal_filings_available" if sym == "ADSK" else "no_10k_10q_rows_for_cik"
            ),
            "sector_blocker_cause": "no_market_metadata_row_for_symbol",
        }
        for sym, cik in base
    ]


def test_authoritative_closeout_flag_supabase_fresh() -> None:
    assert AUTHORITATIVE_CLOSEOUT_USES_SUPABASE_FRESH_PHASE42 is True


def test_load_targets_exactly_eight_rows() -> None:
    bundle = {"row_level_blockers": _eight_row_blockers()}
    targets = load_targets_from_phase42_supabase_bundle(bundle)
    assert len(targets) == EXACT_COHORT_SIZE
    adsk = next(t for t in targets if t["symbol"] == "ADSK")
    assert adsk["filing_blocker_cause_before"] == "only_post_signal_filings_available"
    assert adsk["sector_blocker_cause_before"] == "no_market_metadata_row_for_symbol"


def test_load_targets_wrong_count_raises() -> None:
    rows = _eight_row_blockers()[:7]
    with pytest.raises(ValueError, match="expected 8"):
        load_targets_from_phase42_supabase_bundle({"row_level_blockers": rows})


def test_load_targets_duplicate_raises() -> None:
    rows = _eight_row_blockers()
    rows[-1] = dict(rows[0])
    with pytest.raises(ValueError, match="duplicate"):
        load_targets_from_phase42_supabase_bundle({"row_level_blockers": rows})


def test_merge_fixture_residual_from_phase41() -> None:
    targets = load_targets_from_phase42_supabase_bundle({"row_level_blockers": _eight_row_blockers()})
    bundle41 = {
        "pit_execution": {
            "families_executed": [
                {
                    "family_id": "signal_filing_boundary_v1",
                    "row_results": [
                        {"symbol": "ADSK", "fixture_residual_join_bucket": "still_join_key_mismatch"},
                    ],
                }
            ]
        }
    }
    merge_fixture_residual_from_phase41_bundle(targets, bundle41)
    adsk = next(t for t in targets if t["symbol"] == "ADSK")
    assert adsk.get("residual_join_bucket") == "still_join_key_mismatch"
    bby = next(t for t in targets if t["symbol"] == "BBY")
    assert bby.get("residual_join_bucket") == "state_change_built_but_join_key_mismatch"


def test_adsk_post_signal_not_collapsed_to_missing_10kq() -> None:
    """10-K/10-Q exist but all filed_at strictly after signal → post-signal-only, not no_10k."""
    sig = "2024-06-15"
    rows = [
        {
            "form": "10-K",
            "filed_at": "2024-12-01T00:00:00Z",
            "accepted_at": "2024-12-01T00:00:00Z",
            "accession_no": "x1",
        }
    ]
    out = classify_filing_blocker_cause(signal_available_date=sig, filing_index_rows=rows)
    assert out["filing_blocker_cause"] == "only_post_signal_filings_available"


def test_sector_no_row_vs_blank_field() -> None:
    no_row = classify_sector_blocker_cause(metadata_row=None)
    assert no_row["sector_blocker_cause"] == "no_market_metadata_row_for_symbol"

    blank = classify_sector_blocker_cause(metadata_row={"symbol": "ZZZ", "sector": "  ", "industry": "x"})
    assert blank["sector_blocker_cause"] == "sector_field_blank_on_metadata_row"

    ok = classify_sector_blocker_cause(metadata_row={"symbol": "ZZZ", "sector": "Tech", "industry": ""})
    assert ok["sector_blocker_cause"] == "sector_available"


def test_before_after_audit_build_and_render() -> None:
    targets = load_targets_from_phase42_supabase_bundle({"row_level_blockers": _eight_row_blockers()})
    z = {
        "filing_blocker_cause": "x",
        "filing_index_row_count": 1,
        "n_10k_10q": 0,
        "any_pre_signal_10kq_candidate": False,
    }
    sz = {
        "sector_blocker_cause": "no_market_metadata_row_for_symbol",
        "raw_row_count": 0,
        "sector_present": False,
        "industry_present": False,
    }
    fb, fa = [dict(z) for _ in targets], [dict(z) for _ in targets]
    sb, sa = [dict(sz) for _ in targets], [dict(sz) for _ in targets]
    rows = build_before_after_row_audit(targets, filing_before=fb, filing_after=fa, sector_before=sb, sector_after=sa)
    assert len(rows) == 8
    md = render_before_after_audit_md(rows=rows)
    assert "ADSK" in md
    assert "filing_blocker" in md


def test_before_after_misaligned_lists_raise() -> None:
    targets = load_targets_from_phase42_supabase_bundle({"row_level_blockers": _eight_row_blockers()})
    one = [{"filing_blocker_cause": "x", "filing_index_row_count": 0, "n_10k_10q": 0, "any_pre_signal_10kq_candidate": False}]
    sz = {"sector_blocker_cause": "x", "raw_row_count": 0, "sector_present": False, "industry_present": False}
    with pytest.raises(ValueError, match="align"):
        build_before_after_row_audit(
            targets,
            filing_before=one,
            filing_after=one,
            sector_before=[sz] * 8,
            sector_after=[sz] * 8,
        )


def test_phase44_recommend_material_change() -> None:
    audit = [
        {
            "filing_blocker_before": "a",
            "filing_blocker_after": "b",
            "sector_blocker_before": "x",
            "sector_blocker_after": "x",
        }
    ]
    out = recommend_phase44_after_phase43(
        before_after_row_audit=audit,
        scorecard_before={},
        scorecard_after={},
        gate_before={},
        gate_after={},
    )
    assert out["phase44_recommendation"] == "continue_bounded_falsifier_retest_or_narrow_claims_v1"


def test_phase44_recommend_no_material_change() -> None:
    audit = [
        {
            "filing_blocker_before": "a",
            "filing_blocker_after": "a",
            "sector_blocker_before": "x",
            "sector_blocker_after": "x",
        }
    ]
    out = recommend_phase44_after_phase43(
        before_after_row_audit=audit,
        scorecard_before={"filing_blocker_distribution": {"exact_public_ts_available": 0}},
        scorecard_after={"filing_blocker_distribution": {"exact_public_ts_available": 0}},
        gate_before={"primary_block_category": "c", "gate_status": "g"},
        gate_after={"primary_block_category": "c", "gate_status": "g"},
    )
    assert out["phase44_recommendation"] == "narrow_claims_or_accept_proxy_limits_no_broad_substrate_v1"


def test_orchestrator_passes_use_supabase_true_to_phase42(tmp_path: Path) -> None:
    p41 = tmp_path / "phase41.json"
    p42_in = tmp_path / "phase42_supabase.json"
    work = tmp_path / "phase43_work"
    work.mkdir()

    p41.write_text(
        json.dumps(
            {
                "pit_execution": {
                    "families_executed": [
                        {
                            "family_id": "signal_filing_boundary_v1",
                            "row_results": [
                                {"symbol": sym, "fixture_residual_join_bucket": "still_join_key_mismatch"}
                                for sym, _ in [
                                    ("BBY", None),
                                    ("ADSK", None),
                                    ("CRM", None),
                                    ("CRWD", None),
                                    ("DELL", None),
                                    ("DUK", None),
                                    ("NVDA", None),
                                    ("WMT", None),
                                ]
                            ],
                        }
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    p42_in.write_text(
        json.dumps(
            {
                "ok": True,
                "phase41_bundle_path": str(p41),
                "row_level_blockers": _eight_row_blockers(),
                "promotion_gate_phase42": {"primary_block_category": "c0", "gate_status": "deferred"},
                "family_evidence_scorecard": {
                    "filing_blocker_distribution": {"exact_public_ts_available": 0},
                    "sector_blocker_distribution": {"sector_available": 0},
                },
                "stable_run_digest": "digest_before",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    snap_filing = {
        "filing_blocker_cause": "no_filing_index_rows_for_cik",
        "filing_index_row_count": 0,
        "n_10k_10q": 0,
        "any_pre_signal_10kq_candidate": False,
    }
    snap_sector = {
        "sector_blocker_cause": "no_market_metadata_row_for_symbol",
        "raw_row_count": 0,
        "sector_present": False,
        "industry_present": False,
    }

    captured: dict[str, object] = {}

    def fake_p42(*_a: object, **kwargs: object) -> dict:
        captured["use_supabase"] = kwargs.get("use_supabase")
        return {
            "ok": True,
            "promotion_gate_phase42": {"primary_block_category": "c0", "gate_status": "deferred"},
            "family_evidence_scorecard": {
                "filing_blocker_distribution": {"exact_public_ts_available": 0},
                "sector_blocker_distribution": {"sector_available": 0},
            },
            "stable_run_digest": "digest_after",
        }

    settings = MagicMock()

    with (
        patch("phase43.orchestrator.get_supabase_client", return_value=MagicMock()),
        patch("phase43.orchestrator.filing_evidence_snapshot", return_value=snap_filing),
        patch("phase43.orchestrator.sector_evidence_snapshot", return_value=snap_sector),
        patch("phase43.orchestrator.run_bounded_filing_backfill_for_cohort", return_value={"attempts": []}),
        patch("phase43.orchestrator.run_bounded_sector_hydration_for_cohort", return_value={"symbols": []}),
        patch(
            "phase43.orchestrator.run_phase41_falsifier_pit",
            return_value={"ok": True, "experiment_id": "e1", "families_executed": []},
        ),
        patch("phase43.orchestrator.run_phase42_evidence_accumulation", side_effect=fake_p42),
        patch("phase43.orchestrator.tempfile.mkdtemp", return_value=str(work)),
        patch("phase43.orchestrator.shutil.rmtree"),
    ):
        out = run_phase43_targeted_substrate_backfill(
            settings,
            phase42_supabase_bundle_in=str(p42_in),
            universe_name="sp500_current",
            phase41_bundle_in=str(p41),
        )

    assert captured.get("use_supabase") is True
    assert out.get("phase42_rerun_used_supabase_fresh") is True
    assert len(out.get("before_after_row_audit") or []) == 8
    assert out.get("ok") is True


def test_orchestrator_rejects_non_ok_phase42_bundle(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"ok": False, "row_level_blockers": _eight_row_blockers()}), encoding="utf-8")
    out = run_phase43_targeted_substrate_backfill(
        MagicMock(),
        phase42_supabase_bundle_in=str(p),
        universe_name="sp500_current",
    )
    assert out.get("ok") is False
    assert out.get("error") == "input_phase42_bundle_not_ok"
