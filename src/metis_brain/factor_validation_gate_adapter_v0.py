"""Map Phase 5 `factor_validation_summaries` rows → Metis promotion gate summary dict.

PIT is **not** inferred from correlation alone: ``summary_json.pit_certified`` must be true
(or operator post-processes the emitted gate). Monotonicity uses quantile spread when
``quantiles`` is provided; otherwise a weak Spearman magnitude heuristic.

See ``export-metis-gates-from-factor-validation`` CLI (main.py).
"""

from __future__ import annotations

import json
from typing import Any

from research_validation.constants import MIN_SAMPLE_ROWS


def _parse_summary_json(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("summary_json")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            o = json.loads(raw)
            return o if isinstance(o, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _quantile_spread_directional_ok(
    quantiles: list[dict[str, Any]],
    *,
    return_basis: str,
) -> bool | None:
    """Return True if top vs bottom quantile shows a spread; False if flat; None if insufficient."""
    if len(quantiles) < 3:
        return None
    key = "avg_raw_return" if return_basis == "raw" else "avg_excess_return"
    ordered = sorted(quantiles, key=lambda q: int(q.get("quantile_index") or 0))
    lo = ordered[0].get(key)
    hi = ordered[-1].get(key)
    try:
        a = float(lo) if lo is not None else None
        b = float(hi) if hi is not None else None
    except (TypeError, ValueError):
        return None
    if a is None or b is None:
        return None
    return (b - a) != 0.0


def build_metis_gate_summary_from_factor_summary_row(
    row: dict[str, Any],
    *,
    quantiles: list[dict[str, Any]] | None = None,
    return_basis: str = "raw",
) -> dict[str, Any]:
    """Build kwargs-compatible dict for :func:`validation_bridge_v0.promotion_gate_from_validation_summary`."""
    sj = _parse_summary_json(row)
    sample = int(row.get("sample_count") or 0)
    valid = int(row.get("valid_factor_count") or 0)
    coverage_pass = valid >= MIN_SAMPLE_ROWS
    if sample > 0:
        coverage_pass = coverage_pass and valid >= int(0.15 * float(sample))

    spear = row.get("spearman_rank_corr")
    try:
        sp = float(spear) if spear is not None else None
    except (TypeError, ValueError):
        sp = None

    q_ok = _quantile_spread_directional_ok(quantiles or [], return_basis=return_basis)
    if q_ok is not None:
        monotonicity_pass = bool(q_ok)
    else:
        monotonicity_pass = sp is not None and abs(sp) >= 0.05

    pit_pass = bool(sj.get("pit_certified"))
    pit_rule = str(sj.get("pit_rule") or "").strip()

    rid = str(row.get("run_id") or "")
    fn = str(row.get("factor_name") or "")
    un = str(row.get("universe_name") or "")
    hz = str(row.get("horizon_type") or "")
    reasons = (
        f"mapped_from_factor_validation;pit={'certified' if pit_pass else 'not_certified_set_pit_in_summary_json'};"
        f"spearman={sp};quantile_spread_checked={q_ok is not None}"
    )
    if pit_rule:
        reasons = f"{reasons};pit_rule={pit_rule}"
    return {
        "pit_pass": pit_pass,
        "coverage_pass": coverage_pass,
        "monotonicity_pass": monotonicity_pass,
        "approved_by_rule": f"factor_validation_summary_adapter:v0|run={rid}|factor={fn}",
        "regime_notes": f"universe={un} horizon={hz} return_basis={return_basis}",
        "sector_override_notes": "",
        "challenger_or_active": str(sj.get("metis_challenger_or_active") or "active"),
        "reasons": reasons,
        "expiry_or_recheck_rule": "recheck_on_next_factor_validation_run:v0",
    }
