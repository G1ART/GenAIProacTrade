"""Synthesize a ``ModelArtifactPacketV0`` dict from a single factor_validation run.

Inputs:
  * ``summary_row`` — one row of ``factor_validation_summaries`` (selected by factor + return_basis).
  * ``quantile_rows`` — all ``factor_quantile_results`` for the same run/factor/basis.
  * metadata — factor_name, universe_name, bundle horizon, run_id, artifact_id.

Output:
  * dict compatible with ``ModelArtifactPacketV0`` in ``metis_brain.schemas_v0``.

Product spec §6.1 — 18 fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

VALIDATION_HORIZON_TO_BUNDLE: dict[str, str] = {
    "next_month": "short",
    "next_quarter": "medium",
    "next_half_year": "medium_long",
    "next_year": "long",
}


def map_validation_horizon_to_bundle_horizon(horizon_type: str) -> str:
    k = str(horizon_type or "").strip().lower()
    if k in VALIDATION_HORIZON_TO_BUNDLE:
        return VALIDATION_HORIZON_TO_BUNDLE[k]
    raise ValueError(f"unsupported validation horizon_type: {horizon_type!r}")


def _ranking_direction_from_spearman(spearman: float | None) -> str:
    if spearman is None:
        return "unknown_empirical_only:v0"
    if float(spearman) >= 0.0:
        return "higher_more_stretched:v0"
    return "lower_more_stretched:v0"


def _confidence_rule_from_sample(summary_row: dict[str, Any]) -> str:
    sample = int(summary_row.get("sample_count") or 0)
    valid = int(summary_row.get("valid_factor_count") or 0)
    return f"band_from_valid_rows:valid={valid};sample={sample};v0"


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_artifact_from_validation_v1(
    *,
    factor_name: str,
    universe_name: str,
    horizon_type: str,
    return_basis: str,
    artifact_id: str,
    run_id: str,
    summary_row: dict[str, Any],
    quantile_rows: list[dict[str, Any]],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Return a dict that validates against ``ModelArtifactPacketV0``."""
    factor = str(factor_name or "").strip()
    universe = str(universe_name or "").strip()
    basis = str(return_basis or "raw").strip()
    aid = str(artifact_id or "").strip()
    rid = str(run_id or "").strip()
    if not factor or not universe or not aid or not rid:
        raise ValueError("factor_name/universe_name/artifact_id/run_id are required")
    bundle_horizon = map_validation_horizon_to_bundle_horizon(horizon_type)

    spearman = summary_row.get("spearman_rank_corr")
    spearman_f: float | None = None
    try:
        if spearman is not None:
            spearman_f = float(spearman)
    except (TypeError, ValueError):
        spearman_f = None

    n_quantiles = len({int(q["quantile_index"]) for q in quantile_rows if q.get("quantile_index") is not None}) or 0
    banding_rule = (
        f"quintile_from_factor_rank:v0"
        if n_quantiles == 5
        else f"quantile_from_factor_rank_n{n_quantiles}:v0"
    )

    return {
        "artifact_id": aid,
        "created_at": created_at or _now_iso_utc(),
        "created_by": "artifact_from_validation_v1",
        "horizon": bundle_horizon,
        "universe": universe,
        "sector_scope": "multi_sector_v0",
        "thesis_family": f"factor_{factor}_v0",
        "feature_set": f"factor:{factor}",
        "feature_transforms": "identity_v0",
        "weighting_rule": "equal_weight:v0",
        "score_formula": "rank_position_from_spearman_and_quantile:v0",
        "banding_rule": banding_rule,
        "ranking_direction": _ranking_direction_from_spearman(spearman_f),
        "invalidation_conditions": "pit_or_coverage_or_monotonicity_fail:v0",
        "expected_holding_horizon": bundle_horizon,
        "confidence_rule": _confidence_rule_from_sample(summary_row),
        "evidence_requirements": "validation_pointer_required:v0",
        "validation_pointer": f"factor_validation_run:{rid}:{factor}:{basis}",
        "replay_eligibility": "eligible_when_lineage_present:v0",
        "notes_for_message_layer": (
            f"factor={factor};horizon={bundle_horizon};universe={universe};"
            f"return_basis={basis};spearman={spearman_f}"
        ),
    }
