"""Patch 11 — M1 tests for ``long_horizon_evidence_v1`` module + bundle hook.

Covers:

- ``classify_long_horizon_tier`` boundary conditions (production /
  limited / sample) across coverage × n_rows.
- ``summarize_long_horizon_support`` counts rows / symbols correctly
  and only counts rows carrying ``residual_score_semantics_version``
  as supported evidence.
- Bundle integrity flags the "claim real_derived but tier=sample" lie
  and the opposite "claim insufficient_evidence but tier=production"
  over-claim, but honest combinations stay green.
- ``BrainBundleV0`` accepts the new optional
  ``long_horizon_support_by_horizon`` field and empty map = no claim.
- The Product Shell ``build_shared_focus_block`` exposes
  ``long_horizon_support`` with a localized label and no raw numbers.
"""

from __future__ import annotations

import pytest

from metis_brain.bundle import BrainBundleV0, validate_active_registry_integrity
from metis_brain.long_horizon_evidence_v1 import (
    LONG_HORIZON_SUPPORT_CONTRACT_VERSION,
    LONG_HORIZON_TIER_KEYS,
    LongHorizonSupportV1,
    classify_long_horizon_tier,
    long_horizon_support_integrity_errors,
    summarize_long_horizon_support,
    summarize_long_horizon_support_as_dicts,
)
from phase47_runtime.product_shell.view_models_common import (
    build_shared_focus_block,
    long_horizon_support_note_block,
)


# ---------------------------------------------------------------------------
# classify_long_horizon_tier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "coverage,n_rows,expected",
    [
        (1.0, 50, "production"),
        (0.8, 20, "production"),       # boundary in
        (0.8, 19, "limited"),           # under n_rows threshold → limited
        (0.79, 20, "limited"),          # under coverage threshold → limited
        (0.4, 5,  "limited"),           # boundary in
        (0.4, 4,  "sample"),            # under n_rows
        (0.39, 5, "sample"),            # under coverage
        (0.0, 0,  "sample"),
        (0.95, 0, "sample"),            # no rows at all
    ],
)
def test_classify_long_horizon_tier_boundaries(coverage, n_rows, expected):
    tier = classify_long_horizon_tier(coverage_ratio=coverage, n_rows=n_rows)
    assert tier == expected
    assert tier in LONG_HORIZON_TIER_KEYS


def test_classify_handles_malformed_inputs():
    assert classify_long_horizon_tier(
        coverage_ratio=None, n_rows=None,  # type: ignore[arg-type]
    ) == "sample"
    assert classify_long_horizon_tier(
        coverage_ratio="abc", n_rows="xyz",  # type: ignore[arg-type]
    ) == "sample"


# ---------------------------------------------------------------------------
# summarize_long_horizon_support
# ---------------------------------------------------------------------------


def _rows(*, n_real: int, n_template: int) -> list[dict]:
    rows: list[dict] = []
    for i in range(n_real):
        rows.append({
            "asset_id": f"SYM{i:03d}",
            "spectrum_position": 0.5,
            "residual_score_semantics_version": "residual_semantics_v1",
        })
    for i in range(n_template):
        rows.append({
            "asset_id": f"TPL{i:03d}",
            "spectrum_position": 0.5,
        })
    return rows


def test_summarize_production_coverage():
    spectrum = {
        "medium_long": _rows(n_real=40, n_template=5),
        "long":        _rows(n_real=25, n_template=5),
    }
    blocks = summarize_long_horizon_support(
        spectrum_rows_by_horizon=spectrum, as_of_utc="2026-04-23T00:00:00Z",
    )
    ml = blocks["medium_long"]
    assert isinstance(ml, LongHorizonSupportV1)
    assert ml.contract_version == LONG_HORIZON_SUPPORT_CONTRACT_VERSION
    assert ml.n_rows == 45
    assert ml.n_symbols == 45
    assert abs(ml.coverage_ratio - round(40 / 45, 4)) < 1e-6
    assert ml.tier_key == "production"
    assert blocks["long"].tier_key == "production"


def test_summarize_limited_coverage():
    spectrum = {
        "medium_long": _rows(n_real=8, n_template=10),
    }
    blocks = summarize_long_horizon_support(
        spectrum_rows_by_horizon=spectrum, as_of_utc="",
    )
    ml = blocks["medium_long"]
    assert ml.tier_key == "limited"
    assert ml.reason == "residual_semantics_below_production_threshold"


def test_summarize_sample_when_no_residual():
    spectrum = {
        "medium_long": _rows(n_real=0, n_template=30),
        "long":        [],
    }
    blocks = summarize_long_horizon_support(
        spectrum_rows_by_horizon=spectrum, as_of_utc="",
    )
    assert blocks["medium_long"].tier_key == "sample"
    assert blocks["long"].tier_key == "sample"
    # no rows at all should still surface the empty block honestly.
    assert blocks["long"].n_rows == 0


def test_summarize_as_dicts_is_json_friendly():
    spectrum = {"medium_long": _rows(n_real=25, n_template=0)}
    as_dict = summarize_long_horizon_support_as_dicts(
        spectrum_rows_by_horizon=spectrum, as_of_utc="",
    )
    ml = as_dict["medium_long"]
    assert isinstance(ml, dict)
    assert ml["tier_key"] == "production"
    assert ml["contract_version"] == LONG_HORIZON_SUPPORT_CONTRACT_VERSION


# ---------------------------------------------------------------------------
# long_horizon_support_integrity_errors
# ---------------------------------------------------------------------------


def test_integrity_honest_production_claim_has_no_errors():
    errs = long_horizon_support_integrity_errors(
        horizon_provenance={"medium_long": {"source": "real_derived"}},
        long_horizon_support_by_horizon={
            "medium_long": {"tier_key": "production"},
        },
    )
    assert errs == []


def test_integrity_flags_claim_real_but_tier_sample():
    errs = long_horizon_support_integrity_errors(
        horizon_provenance={"medium_long": {"source": "real_derived"}},
        long_horizon_support_by_horizon={
            "medium_long": {"tier_key": "sample"},
        },
    )
    assert len(errs) == 1
    assert "claims real_derived but tier=sample" in errs[0]


def test_integrity_flags_insufficient_provenance_but_production_tier():
    errs = long_horizon_support_integrity_errors(
        horizon_provenance={"long": {"source": "insufficient_evidence"}},
        long_horizon_support_by_horizon={
            "long": {"tier_key": "production"},
        },
    )
    assert len(errs) == 1
    assert "is degraded but tier=production" in errs[0]


def test_integrity_honest_sample_with_degraded_provenance_is_ok():
    errs = long_horizon_support_integrity_errors(
        horizon_provenance={"medium_long": {"source": "insufficient_evidence"}},
        long_horizon_support_by_horizon={
            "medium_long": {"tier_key": "sample"},
        },
    )
    assert errs == []


# ---------------------------------------------------------------------------
# BrainBundleV0 accepts the optional field + integrity runs the check
# ---------------------------------------------------------------------------


def _minimal_bundle(long_horizon_support_by_horizon=None, horizon_provenance=None):
    raw = {
        "schema_version": 1,
        "as_of_utc": "2026-04-23T00:00:00Z",
        "artifacts": [],
        "promotion_gates": [],
        "registry_entries": [],
        "spectrum_rows_by_horizon": {"short": []},
        "horizon_provenance": horizon_provenance or {},
    }
    if long_horizon_support_by_horizon is not None:
        raw["long_horizon_support_by_horizon"] = long_horizon_support_by_horizon
    return BrainBundleV0.model_validate(raw)


def test_bundle_model_accepts_new_optional_field():
    bundle = _minimal_bundle()
    assert bundle.long_horizon_support_by_horizon == {}


def test_bundle_integrity_detects_long_horizon_lie():
    bundle = _minimal_bundle(
        long_horizon_support_by_horizon={
            "medium_long": {"tier_key": "sample"},
        },
        horizon_provenance={"medium_long": {"source": "real_derived"}},
    )
    errs = validate_active_registry_integrity(bundle)
    assert any("tier=sample" in e for e in errs)


def test_bundle_integrity_clean_on_honest_block():
    bundle = _minimal_bundle(
        long_horizon_support_by_horizon={
            "medium_long": {"tier_key": "production"},
        },
        horizon_provenance={"medium_long": {"source": "real_derived"}},
    )
    errs = validate_active_registry_integrity(bundle)
    assert all("tier=" not in e for e in errs)


# ---------------------------------------------------------------------------
# Product Shell — long_horizon_support surfacing
# ---------------------------------------------------------------------------


from types import SimpleNamespace


def _bundle_with_support(tier: str, provenance_source: str = "real_derived"):
    return SimpleNamespace(
        as_of_utc="2026-04-23T00:00:00Z",
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": provenance_source},
            "long":        {"source": provenance_source},
        },
        registry_entries=[
            SimpleNamespace(
                status="active", horizon="medium_long",
                active_artifact_id="art_x", registry_entry_id="reg_x",
                display_family_name_ko="장기모멘텀", display_family_name_en="Long momentum",
            ),
        ],
        artifacts=[
            SimpleNamespace(
                artifact_id="art_x",
                display_family_name_ko="장기모멘텀",
                display_family_name_en="Long momentum",
            ),
        ],
        metadata={"built_at_utc": "2026-04-23T00:00:00Z"},
        long_horizon_support_by_horizon={
            "medium_long": {"tier_key": tier, "n_rows": 10, "n_symbols": 10,
                             "coverage_ratio": 0.5},
        },
    )


def test_long_horizon_support_note_block_exposes_only_labels():
    bundle = _bundle_with_support(tier="limited")
    block_ko = long_horizon_support_note_block(
        bundle=bundle, horizon_key="medium_long", lang="ko",
    )
    assert block_ko is not None
    assert block_ko["tier_key"] == "limited"
    assert block_ko["contract_version"] == "LONG_HORIZON_SUPPORT_V1"
    assert "제한" in block_ko["label"]
    # Raw engineering telemetry must never leak into the block.
    for forbidden in ("n_rows", "n_symbols", "coverage_ratio", "as_of_utc"):
        assert forbidden not in block_ko


def test_long_horizon_support_note_block_absent_for_short_horizon():
    bundle = _bundle_with_support(tier="limited")
    assert long_horizon_support_note_block(
        bundle=bundle, horizon_key="short", lang="ko",
    ) is None


def test_shared_focus_block_embeds_long_horizon_support_when_present():
    bundle = _bundle_with_support(tier="limited", provenance_source="real_derived_with_degraded_challenger")
    spectrum = {
        "short":       {"ok": True, "rows": []},
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": [
            {"asset_id": "AAPL", "spectrum_position": 0.4,
             "residual_score_semantics_version": "residual_semantics_v1",
             "invalidation_hint": "horizon_returns_reverse_sign",
             "recheck_cadence": "semi_annually_after_new_filing_or_126_trading_days"},
        ]},
        "long":        {"ok": True, "rows": []},
    }
    focus = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="medium_long", lang="ko",
    )
    lhs = focus.get("long_horizon_support")
    assert lhs is not None
    assert lhs["tier_key"] == "limited"
    assert "제한" in lhs["label"]


def test_shared_focus_block_no_long_horizon_support_on_legacy_bundle():
    bundle = SimpleNamespace(
        as_of_utc="2026-04-23T00:00:00Z",
        horizon_provenance={"short": {"source": "real_derived"}},
        registry_entries=[
            SimpleNamespace(
                status="active", horizon="short",
                active_artifact_id="art_x", registry_entry_id="reg_x",
                display_family_name_ko="F", display_family_name_en="F",
            ),
        ],
        artifacts=[SimpleNamespace(artifact_id="art_x",
                                   display_family_name_ko="F",
                                   display_family_name_en="F")],
        metadata={},
    )
    spectrum = {
        "short": {"ok": True, "rows": [{"asset_id": "AAPL",
                                         "spectrum_position": 0.5,
                                         "residual_score_semantics_version": "residual_semantics_v1",
                                         "invalidation_hint": "horizon_returns_reverse_sign",
                                         "recheck_cadence": "monthly_after_new_filing_or_21_trading_days"}]},
        "medium": {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long": {"ok": True, "rows": []},
    }
    focus = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    assert "long_horizon_support" not in focus
