"""Long-Horizon Evidence / Support v1 — Patch 11, Scope A.1 + B.2.

Brain Bundle v2 already normalizes horizon keys to
``short / medium / medium_long / long`` and stamps
``horizon_provenance[hz] = {"source": "real_derived" | ...}``. But the
bundle never quantified *how much* evidence backs each horizon, so the
Product Shell confidence badge on ``medium_long`` / ``long`` could only
read a binary provenance label without knowing whether it was thin.

This module adds a light-weight ``LongHorizonSupportV1`` block that the
bundle builder can aggregate per horizon so the Product Shell can tell
operators the truth about long-view coverage:

- ``tier_key = production`` — ample evidence, ready for live customer claims.
- ``tier_key = limited``    — evidence exists but is thin; surface with caveats.
- ``tier_key = sample``     — nearly no evidence; do not make confident claims.

An **integrity lie** is flagged when ``horizon_provenance.source`` is a
``real_derived`` family while ``long_horizon_support.tier_key`` is
``sample`` — that means the bundle claims live data but the evidence is
not there. This catches silent drift without requiring a data backfill.

The thresholds are intentionally conservative: *presence* of residual
semantics is used as the primary coverage signal (those fields are only
populated by the real-data spectrum row synthesizer, see
``src/metis_brain/spectrum_rows_from_validation_v1.py``). A bundle that
template-falls back to insufficient_evidence rows will honestly report
``tier_key = sample`` without requiring the builder to pass extra flags.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

LONG_HORIZON_SUPPORT_CONTRACT_VERSION = "LONG_HORIZON_SUPPORT_V1"

LONG_HORIZON_TIER_KEYS: tuple[str, ...] = ("production", "limited", "sample")

# Provenance buckets that claim live evidence. When provenance is in this
# family but the aggregated tier is ``sample`` the bundle is lying.
_REAL_DERIVED_FAMILY: frozenset[str] = frozenset(
    {"real_derived", "real_derived_with_degraded_challenger"}
)

# Defaults — coverage_ratio is the share of horizon rows that carry the
# Patch 11 residual semantics signature (populated only by the real-data
# synthesizer). n_rows guards against single-row "production" claims.
PRODUCTION_COVERAGE_MIN = 0.8
PRODUCTION_ROW_MIN = 20
LIMITED_COVERAGE_MIN = 0.4
LIMITED_ROW_MIN = 5


class LongHorizonSupportV1(BaseModel):
    """Per-horizon long-view evidence support block.

    Attached at ``BrainBundleV0.long_horizon_support_by_horizon[hz]``.
    Short horizons may omit the block entirely (legacy bundles have no
    field at all). Integrity never *requires* the block — it only flags
    a claim-vs-evidence mismatch when the block IS present.
    """

    contract_version: str = Field(default=LONG_HORIZON_SUPPORT_CONTRACT_VERSION)
    horizon_key: str
    n_rows: int = 0
    n_symbols: int = 0
    coverage_ratio: float = 0.0
    tier_key: str = "sample"
    as_of_utc: str = ""
    reason: str = ""


def classify_long_horizon_tier(*, coverage_ratio: float, n_rows: int) -> str:
    """Return a ``LONG_HORIZON_TIER_KEYS`` entry for ``coverage_ratio`` × ``n_rows``.

    Boundaries are inclusive on the high side (``>=``) so a bundle at
    exactly the production threshold is classified production. An
    otherwise qualifying bundle with too few rows is downgraded to the
    next tier below.
    """
    try:
        cr = float(coverage_ratio)
    except (TypeError, ValueError):
        cr = 0.0
    try:
        n = int(n_rows)
    except (TypeError, ValueError):
        n = 0
    if cr >= PRODUCTION_COVERAGE_MIN and n >= PRODUCTION_ROW_MIN:
        return "production"
    if cr >= LIMITED_COVERAGE_MIN and n >= LIMITED_ROW_MIN:
        return "limited"
    return "sample"


def _row_has_residual_semantics(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    return bool(str(row.get("residual_score_semantics_version") or "").strip())


def summarize_long_horizon_support(
    *,
    spectrum_rows_by_horizon: dict[str, list[dict[str, Any]]],
    as_of_utc: str = "",
    horizons: tuple[str, ...] = ("medium_long", "long"),
) -> dict[str, LongHorizonSupportV1]:
    """Aggregate per-horizon support blocks for ``horizons``.

    The default horizon tuple is ``(medium_long, long)`` because those
    are the two for which the Product Shell most urgently needs an
    honest tier — short / medium already carry production coverage on
    the current bundle. Callers that want full-coverage aggregation can
    pass ``horizons=("short", "medium", "medium_long", "long")``.
    """
    out: dict[str, LongHorizonSupportV1] = {}
    for hz in horizons:
        rows = list((spectrum_rows_by_horizon or {}).get(hz) or [])
        n_rows = len(rows)
        symbols = {
            str(r.get("asset_id") or "").upper().strip()
            for r in rows
            if isinstance(r, dict) and str(r.get("asset_id") or "").strip()
        }
        n_sym = len(symbols)
        supported = sum(1 for r in rows if _row_has_residual_semantics(r))
        coverage = (supported / n_rows) if n_rows else 0.0
        tier = classify_long_horizon_tier(
            coverage_ratio=coverage, n_rows=n_rows,
        )
        reason = ""
        if tier == "sample":
            reason = "insufficient_residual_semantics_coverage"
        elif tier == "limited":
            reason = "residual_semantics_below_production_threshold"
        out[hz] = LongHorizonSupportV1(
            horizon_key=hz,
            n_rows=n_rows,
            n_symbols=n_sym,
            coverage_ratio=round(float(coverage), 4),
            tier_key=tier,
            as_of_utc=str(as_of_utc or "").strip(),
            reason=reason,
        )
    return out


def summarize_long_horizon_support_as_dicts(
    *,
    spectrum_rows_by_horizon: dict[str, list[dict[str, Any]]],
    as_of_utc: str = "",
    horizons: tuple[str, ...] = ("medium_long", "long"),
) -> dict[str, dict[str, Any]]:
    """JSON-friendly variant used by the bundle builder (stores dicts)."""
    return {
        hz: block.model_dump()
        for hz, block in summarize_long_horizon_support(
            spectrum_rows_by_horizon=spectrum_rows_by_horizon,
            as_of_utc=as_of_utc,
            horizons=horizons,
        ).items()
    }


def long_horizon_support_integrity_errors(
    *,
    horizon_provenance: dict[str, dict[str, Any]] | None,
    long_horizon_support_by_horizon: dict[str, Any] | None,
) -> list[str]:
    """Return the list of claim-vs-evidence mismatches.

    A mismatch is: provenance says "real_derived" family but the
    aggregated tier is "sample". The opposite direction (provenance
    says "insufficient_evidence" but tier claims production) is also
    flagged because it would mean the builder under-reported provenance.
    An empty list means the provenance ↔ tier story is honest.
    """
    errs: list[str] = []
    prov = horizon_provenance or {}
    sup = long_horizon_support_by_horizon or {}
    for hz, block in sup.items():
        if not isinstance(block, dict):
            continue
        tier = str(block.get("tier_key") or "").strip()
        if tier not in LONG_HORIZON_TIER_KEYS:
            continue
        prov_entry = prov.get(hz) if isinstance(prov, dict) else None
        src = ""
        if isinstance(prov_entry, dict):
            src = str(prov_entry.get("source") or "").strip()
        claims_real = src in _REAL_DERIVED_FAMILY
        if claims_real and tier == "sample":
            errs.append(
                f"long_horizon_support: horizon {hz!r} provenance={src!r} "
                "claims real_derived but tier=sample (not enough evidence)"
            )
        if (not claims_real) and src and tier == "production":
            errs.append(
                f"long_horizon_support: horizon {hz!r} provenance={src!r} "
                "is degraded but tier=production (over-claim)"
            )
    return errs
