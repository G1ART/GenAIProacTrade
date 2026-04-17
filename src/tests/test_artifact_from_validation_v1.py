"""Unit tests for ``metis_brain.artifact_from_validation_v1``."""

from __future__ import annotations

import pytest

from metis_brain.artifact_from_validation_v1 import (
    VALIDATION_HORIZON_TO_BUNDLE,
    build_artifact_from_validation_v1,
    map_validation_horizon_to_bundle_horizon,
)
from metis_brain.schemas_v0 import ModelArtifactPacketV0


def _summary_row(**over) -> dict:
    row = {
        "sample_count": 200,
        "valid_factor_count": 40,
        "spearman_rank_corr": -0.12,
        "pearson_corr": -0.08,
    }
    row.update(over)
    return row


def _quantile_rows(n: int = 5) -> list[dict]:
    return [{"quantile_index": i, "mean_return": 0.0} for i in range(n)]


def test_map_validation_horizon_to_bundle_horizon_all_known() -> None:
    for k, v in VALIDATION_HORIZON_TO_BUNDLE.items():
        assert map_validation_horizon_to_bundle_horizon(k) == v


def test_map_validation_horizon_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        map_validation_horizon_to_bundle_horizon("made_up")


def test_build_artifact_validates_against_schema_v0() -> None:
    out = build_artifact_from_validation_v1(
        factor_name="accruals",
        universe_name="sp500_current",
        horizon_type="next_month",
        return_basis="raw",
        artifact_id="art_short_accruals_v1",
        run_id="run_abc_123",
        summary_row=_summary_row(),
        quantile_rows=_quantile_rows(5),
    )
    model = ModelArtifactPacketV0.model_validate(out)
    assert model.feature_set == "factor:accruals"
    assert model.horizon == "short"
    assert model.score_formula == "rank_position_from_spearman_and_quantile:v0"
    assert model.banding_rule == "quintile_from_factor_rank:v0"
    assert model.validation_pointer == "factor_validation_run:run_abc_123:accruals:raw"


def test_build_artifact_ranking_direction_from_spearman_sign() -> None:
    pos = build_artifact_from_validation_v1(
        factor_name="gp",
        universe_name="sp500_current",
        horizon_type="next_month",
        return_basis="raw",
        artifact_id="a1",
        run_id="r1",
        summary_row=_summary_row(spearman_rank_corr=0.3),
        quantile_rows=_quantile_rows(),
    )
    neg = build_artifact_from_validation_v1(
        factor_name="acc",
        universe_name="sp500_current",
        horizon_type="next_month",
        return_basis="raw",
        artifact_id="a2",
        run_id="r1",
        summary_row=_summary_row(spearman_rank_corr=-0.3),
        quantile_rows=_quantile_rows(),
    )
    assert pos["ranking_direction"] == "higher_more_stretched:v0"
    assert neg["ranking_direction"] == "lower_more_stretched:v0"


def test_build_artifact_banding_rule_adapts_to_quantile_count() -> None:
    out3 = build_artifact_from_validation_v1(
        factor_name="x",
        universe_name="u",
        horizon_type="next_month",
        return_basis="raw",
        artifact_id="aid",
        run_id="rid",
        summary_row=_summary_row(),
        quantile_rows=_quantile_rows(3),
    )
    assert out3["banding_rule"] == "quantile_from_factor_rank_n3:v0"


def test_build_artifact_rejects_missing_ids() -> None:
    with pytest.raises(ValueError):
        build_artifact_from_validation_v1(
            factor_name="",
            universe_name="u",
            horizon_type="next_month",
            return_basis="raw",
            artifact_id="a",
            run_id="r",
            summary_row=_summary_row(),
            quantile_rows=[],
        )
    with pytest.raises(ValueError):
        build_artifact_from_validation_v1(
            factor_name="f",
            universe_name="u",
            horizon_type="next_month",
            return_basis="raw",
            artifact_id="",
            run_id="r",
            summary_row=_summary_row(),
            quantile_rows=[],
        )
