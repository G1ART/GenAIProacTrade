"""Evidence-backed adversarial review update (Phase 38)."""

from __future__ import annotations

from typing import Any


def build_updated_adversarial_review(
    *,
    original: dict[str, Any],
    pit_result: dict[str, Any],
) -> dict[str, Any]:
    """Preserve challenge; add Phase 38 resolution fields."""
    leakage = pit_result.get("leakage_audit") or {}
    passed = bool(leakage.get("passed"))
    rows = pit_result.get("row_results") or []

    def n_joined(spec_key: str) -> int:
        col = (
            "baseline"
            if spec_key == "baseline"
            else "lag_signal_bound"
            if spec_key == "lag"
            else "alternate_prior_run"
        )
        n = 0
        for r in rows:
            if str((r.get(col) or {}).get("outcome_category") or "") == "reclassified_to_joined":
                n += 1
        return n

    n_base = n_joined("baseline")
    n_lag = n_joined("lag")
    n_alt = n_joined("alternate")
    alt_skipped = True
    for r in rows:
        if (
            str((r.get("alternate_prior_run") or {}).get("outcome_category") or "")
            != "alternate_spec_not_executed"
        ):
            alt_skipped = False
            break

    if not passed:
        resolution_status = "blocked_pending_leakage_audit"
        notes = (
            "PIT runner detected pick vs signal_bound violations; halt promotion until join logic is audited."
        )
    elif n_base > 0:
        resolution_status = "resolved_partial_baseline_joined"
        notes = (
            "Unexpected baseline joined outcomes; reconcile with substrate audit timing and run_id."
        )
    elif n_lag > 0 or n_alt > 0:
        resolution_status = "deferred_with_evidence_some_reclass_under_alternate_or_lag"
        notes = (
            "Leakage audit passed. Lag joined=%s alternate joined=%s. PIT-integrity challenge remains for production baseline."
            % (n_lag, n_alt)
        )
    else:
        resolution_status = "deferred_with_evidence_reinforces_baseline_mismatch"
        alt_msg = (
            "was not executed (single completed run)."
            if alt_skipped
            else "did not yield joined outcomes for this fixture."
        )
        notes = (
            "DB-bound replay preserves join_key_mismatch for fixture under baseline and lag; alternate %s"
            % alt_msg
        )

    out = dict(original)
    out["phase38_resolution_status"] = resolution_status
    out["phase38_evidence_summary"] = notes
    out["phase38_leakage_audit_passed"] = passed
    out["phase38_experiment_id"] = pit_result.get("experiment_id")
    out["original_challenge_preserved"] = True
    return out


def is_fatal_block(status: str) -> bool:
    return status == "blocked_pending_leakage_audit"
