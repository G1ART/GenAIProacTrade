"""AGH v1 Patch 3 — layer4_spectrum_refresh_v1 helper tests.

Verifies the four-branch decision tree of refresh_spectrum_rows_for_horizon:

    1. supabase_client is None                 -> carry_over_fixture_fallback
    2. artifact spec unparseable                -> carry_over_fixture_fallback
    3. fetch_joined raises                      -> carry_over_db_unavailable
    4. fetch_joined returns ok=False            -> carry_over_db_unavailable
    5. fetch_joined ok + build yields zero rows -> carry_over_db_unavailable
    6. fetch_joined ok + build yields rows      -> recomputed (rows replaced)
"""

from __future__ import annotations

import pytest

from agentic_harness.agents.layer4_spectrum_refresh_v1 import (
    refresh_spectrum_rows_for_horizon,
)


def _art(aid: str, *, horizon: str = "short", feature_set: str = "factor:demo_factor") -> dict:
    return {
        "artifact_id": aid,
        "horizon": horizon,
        "universe": "large_cap_research_slice_demo_v0",
        "feature_set": feature_set,
        "validation_pointer": f"factor_validation_run:run_{aid}:demo_factor:raw",
    }


def _seed_bundle(
    *,
    aid: str = "art_new_active_v0",
    horizon: str = "short",
    feature_set: str = "factor:demo_factor",
) -> dict:
    return {
        "artifacts": [_art(aid, horizon=horizon, feature_set=feature_set)],
        "spectrum_rows_by_horizon": {
            horizon: [
                {"asset_id": "OLD_A", "spectrum_position": 0.1},
                {"asset_id": "OLD_B", "spectrum_position": 0.5},
            ]
        },
    }


def _common_kwargs() -> dict:
    return dict(
        horizon="short",
        new_active_artifact_id="art_new_active_v0",
        registry_entry_id="reg_short_demo_v0",
        now_iso="2026-04-19T12:00:00+00:00",
        bundle_path="/tmp/bundle.json",
        cited_proposal_packet_id="pkt_proposal_x",
        cited_decision_packet_id="pkt_decision_x",
    )


def test_supabase_client_none_yields_carry_over_fixture_fallback():
    bundle = _seed_bundle()
    res = refresh_spectrum_rows_for_horizon(
        bundle, supabase_client=None, **_common_kwargs()
    )

    assert res["outcome"] == "carry_over_fixture_fallback"
    assert res["refresh_mode"] == "fixture_fallback"
    assert res["needs_db_rebuild"] is True
    assert "supabase_client_missing_or_fixture_mode" in res["blocking_reasons"]
    assert res["before_row_count"] == 2
    assert res["after_row_count"] == 2

    rows = bundle["spectrum_rows_by_horizon"]["short"]
    assert all(r.get("stale_after_active_swap") is True for r in rows)
    assert all(r.get("stale_since_utc") == "2026-04-19T12:00:00+00:00" for r in rows)


def test_unparseable_artifact_spec_yields_fixture_fallback():
    bundle = _seed_bundle(feature_set="legacy_non_factor_feature_set")
    res = refresh_spectrum_rows_for_horizon(
        bundle, supabase_client=object(), **_common_kwargs()
    )

    assert res["outcome"] == "carry_over_fixture_fallback"
    assert any(
        r.startswith("artifact_spec_unparseable_for_refresh:")
        for r in res["blocking_reasons"]
    )
    assert all(
        r.get("stale_after_active_swap") is True
        for r in bundle["spectrum_rows_by_horizon"]["short"]
    )


def test_fetch_joined_raises_yields_db_unavailable():
    bundle = _seed_bundle()

    def boom(_client, _spec):
        raise RuntimeError("supabase connection reset")

    res = refresh_spectrum_rows_for_horizon(
        bundle,
        supabase_client=object(),
        fetch_joined=boom,
        **_common_kwargs(),
    )

    assert res["outcome"] == "carry_over_db_unavailable"
    assert res["needs_db_rebuild"] is True
    assert any(
        r.startswith("fetch_joined_raised:RuntimeError:") for r in res["blocking_reasons"]
    )
    rows = bundle["spectrum_rows_by_horizon"]["short"]
    assert [r["asset_id"] for r in rows] == ["OLD_A", "OLD_B"]
    assert all(r["stale_after_active_swap"] is True for r in rows)


def test_fetch_joined_not_ok_yields_db_unavailable():
    bundle = _seed_bundle()

    def not_ok(_client, _spec):
        return {"ok": False, "error": "rpc_not_configured"}

    res = refresh_spectrum_rows_for_horizon(
        bundle,
        supabase_client=object(),
        fetch_joined=not_ok,
        **_common_kwargs(),
    )

    assert res["outcome"] == "carry_over_db_unavailable"
    assert any(
        "fetch_joined_failed" in r for r in res["blocking_reasons"]
    )


def test_build_returns_zero_rows_yields_db_unavailable():
    bundle = _seed_bundle()

    def ok(_client, _spec):
        return {
            "ok": True,
            "summary_row": {"spearman_rank_corr": 0.1, "sample_count": 0},
            "quantile_rows": [],
            "joined_rows": [],
        }

    def build_empty(**_kwargs):
        return "short", []

    res = refresh_spectrum_rows_for_horizon(
        bundle,
        supabase_client=object(),
        fetch_joined=ok,
        build_spectrum_rows=build_empty,
        **_common_kwargs(),
    )

    assert res["outcome"] == "carry_over_db_unavailable"
    assert "fetch_joined_ok_but_zero_rows_synthesized" in res["blocking_reasons"]


def test_full_recompute_replaces_rows_and_clears_stale():
    bundle = _seed_bundle()

    def ok(_client, _spec):
        return {"ok": True, "summary_row": {}, "joined_rows": []}

    def build_new(**_kwargs):
        return "short", [
            {"asset_id": "NEW_X", "spectrum_position": 0.2},
            {"asset_id": "NEW_Y", "spectrum_position": 0.7},
        ]

    res = refresh_spectrum_rows_for_horizon(
        bundle,
        supabase_client=object(),
        fetch_joined=ok,
        build_spectrum_rows=build_new,
        **_common_kwargs(),
    )

    assert res["outcome"] == "recomputed"
    assert res["refresh_mode"] == "full_recompute_from_validation"
    assert res["needs_db_rebuild"] is False
    assert res["blocking_reasons"] == []
    assert res["before_row_count"] == 2
    assert res["after_row_count"] == 2
    assert res["after_row_asset_ids_sample"] == ["NEW_X", "NEW_Y"]

    rows = bundle["spectrum_rows_by_horizon"]["short"]
    assert [r["asset_id"] for r in rows] == ["NEW_X", "NEW_Y"]
    assert all("stale_after_active_swap" not in r for r in rows)
