"""Synthesize bundle ``spectrum_rows_by_horizon`` entries from validation-panel + factor-panel rows.

Contract:
  * Input is the join product of ``factor_market_validation_panels`` × ``issuer_quarter_factor_panels``
    restricted to the run's ``universe_name`` and validation ``horizon_type``.
  * Direction convention (spec §5.1 spectrum: left=compressed, right=stretched):
      - spearman >= 0 (higher factor ⇒ higher return): factor is a quality/undervaluation signal
        ⇒ ``position = 1 - rank_pct``
      - spearman <  0 (higher factor ⇒ lower return): factor is an overvaluation/risk signal
        ⇒ ``position = rank_pct``
      - spearman is None (unknown): fall back to ``position = rank_pct``
  * One row per distinct ``asset_id`` (symbol), keeping the latest available fiscal period.

Bundle integrity ([metis_brain.bundle.validate_active_registry_integrity]) only requires
``asset_id`` + ``spectrum_position``. Today UI renders richer fields when present.
"""

from __future__ import annotations

from typing import Any

from metis_brain.artifact_from_validation_v1 import (
    map_validation_horizon_to_bundle_horizon,
)
from phase47_runtime.message_layer_v1 import (
    spectrum_band_from_position,
    spectrum_quintile_from_position,
)

# Residual Score Semantics v1 — see docs/plan/METIS_Residual_Score_Semantics_v1.md.
RESIDUAL_SCORE_SEMANTICS_VERSION = "residual_semantics_v1"

_RECHECK_CADENCE_BY_BUNDLE_HORIZON = {
    "short": "monthly_after_new_filing_or_21_trading_days",
    "medium": "quarterly_after_new_filing_or_63_trading_days",
    "medium_long": "semi_annually_after_new_filing_or_126_trading_days",
    "long": "annually_after_new_filing_or_252_trading_days",
}


def _invalidation_hint_for_row(
    *,
    pit_pass: bool | None,
    confidence_band: str,
    spectrum_position: float,
) -> str:
    """Deterministic string chosen from a fixed vocabulary (no free narrative)."""
    if pit_pass is False:
        return "factor_validation_pit_fail"
    if str(confidence_band or "").lower() == "low":
        return "confidence_band_drops_to_low"
    # Midline-crossing is the most informative default when position is near 0.5.
    if 0.35 <= spectrum_position <= 0.65:
        return "spectrum_position_crosses_midline"
    return "horizon_returns_reverse_sign"


def _recheck_cadence_for_bundle_horizon(bundle_horizon: str) -> str:
    return _RECHECK_CADENCE_BY_BUNDLE_HORIZON.get(
        str(bundle_horizon or "").strip(),
        "monthly_after_new_filing_or_21_trading_days",
    )


def _as_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f


def _period_sort_key(panel: dict[str, Any]) -> tuple[int, str, str]:
    fy = panel.get("fiscal_year")
    fp = panel.get("fiscal_period") or ""
    acc = panel.get("accession_no") or ""
    try:
        fy_i = int(fy) if fy is not None else -1
    except (TypeError, ValueError):
        fy_i = -1
    return (fy_i, str(fp), str(acc))


def _confidence_band_from_sample(
    *, valid_factor_count: int, sample_count: int
) -> str:
    if valid_factor_count >= 96:
        return "high"
    if valid_factor_count >= 24:
        return "medium"
    return "low"


def _valuation_tension_from_position(position: float) -> str:
    if position < 0.2:
        return "compressed"
    if position < 0.4:
        return "leaning_compressed"
    if position <= 0.6:
        return "balanced"
    if position <= 0.8:
        return "leaning_stretched"
    return "stretched"


def _rationale_summary(
    *,
    factor_name: str,
    position: float,
    rank_index: int,
    rank_total: int,
    spearman: float | None,
) -> dict[str, str]:
    direction = "unknown"
    if spearman is not None:
        direction = "quality_like" if spearman >= 0 else "risk_like"
    en = (
        f"Factor '{factor_name}' rank {rank_index}/{rank_total} → "
        f"position={position:.2f} ({direction}). Generated from validation run."
    )
    ko = (
        f"팩터 '{factor_name}' 순위 {rank_index}/{rank_total} → "
        f"position={position:.2f} ({direction}). 검증 런으로부터 생성."
    )
    return {"ko": ko, "en": en}


def build_spectrum_rows_from_validation(
    *,
    factor_name: str,
    horizon_type: str,
    summary_row: dict[str, Any],
    joined_rows: list[dict[str, Any]],
    max_rows: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Return (bundle_horizon, rows).

    ``joined_rows`` — each item has at least ``symbol`` and ``<factor_name>``
    (direct column in factor panel). Rows missing either are skipped. When the
    same symbol appears multiple times, the latest period (by fiscal_year,
    fiscal_period, accession_no) wins.
    """
    factor = str(factor_name or "").strip()
    if not factor:
        raise ValueError("factor_name required")
    bundle_horizon = map_validation_horizon_to_bundle_horizon(horizon_type)

    latest_by_symbol: dict[str, dict[str, Any]] = {}
    for r in joined_rows or []:
        sym = str(r.get("symbol") or "").upper().strip()
        if not sym:
            continue
        fv = _as_float(r.get(factor))
        if fv is None:
            continue
        prev = latest_by_symbol.get(sym)
        if prev is None or _period_sort_key(r) > _period_sort_key(prev):
            latest_by_symbol[sym] = r

    if not latest_by_symbol:
        return bundle_horizon, []

    pairs: list[tuple[str, float, dict[str, Any]]] = [
        (sym, _as_float(r.get(factor)), r)  # type: ignore[misc]
        for sym, r in latest_by_symbol.items()
    ]
    pairs.sort(key=lambda t: t[1])

    n = len(pairs)
    spearman = _as_float(summary_row.get("spearman_rank_corr"))
    higher_is_quality = spearman is not None and spearman >= 0

    valid = int(summary_row.get("valid_factor_count") or 0)
    sample = int(summary_row.get("sample_count") or 0)
    confidence = _confidence_band_from_sample(valid_factor_count=valid, sample_count=sample)
    pit_pass_raw = summary_row.get("pit_pass")
    pit_pass: bool | None
    pit_pass = bool(pit_pass_raw) if pit_pass_raw is not None else None
    recheck_cadence = _recheck_cadence_for_bundle_horizon(bundle_horizon)

    rows: list[dict[str, Any]] = []
    for i, (sym, fv, src) in enumerate(pairs):
        rank_pct = (i + 0.5) / float(n) if n > 0 else 0.5
        position = (1.0 - rank_pct) if higher_is_quality else rank_pct
        position = max(0.0, min(1.0, position))
        tension = _valuation_tension_from_position(position)
        invalidation_hint = _invalidation_hint_for_row(
            pit_pass=pit_pass,
            confidence_band=confidence,
            spectrum_position=position,
        )
        row = {
            "asset_id": sym,
            "spectrum_position": round(position, 6),
            "spectrum_band": spectrum_band_from_position(position),
            "spectrum_quintile": spectrum_quintile_from_position(position),
            "valuation_tension": tension,
            "confidence_band": confidence,
            "residual_score_semantics_version": RESIDUAL_SCORE_SEMANTICS_VERSION,
            "invalidation_hint": invalidation_hint,
            "recheck_cadence": recheck_cadence,
            "rationale_summary": _rationale_summary(
                factor_name=factor,
                position=position,
                rank_index=i + 1,
                rank_total=n,
                spearman=spearman,
            ),
            "what_changed": {
                "ko": "최신 분기 팩터 순위 업데이트.",
                "en": "Latest quarterly factor rank refreshed.",
            },
            "source_period": {
                "fiscal_year": src.get("fiscal_year"),
                "fiscal_period": src.get("fiscal_period"),
                "accession_no": src.get("accession_no"),
                "factor_value": fv,
            },
        }
        rows.append(row)

    if max_rows is not None and max_rows > 0:
        rows = rows[:max_rows]

    return bundle_horizon, rows
