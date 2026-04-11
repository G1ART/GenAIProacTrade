"""Lifecycle updates after Phase 40 family executions (append-only)."""

from __future__ import annotations

from typing import Any

from phase37.hypothesis_registry import HypothesisStatus
from phase39.lifecycle import apply_lifecycle_transition

_FAMILY_HYPOTHESES = (
    ("score_publication_cadence_v1", "hyp_score_publication_cadence_run_grid_lag_v1"),
    ("signal_filing_boundary_v1", "hyp_signal_availability_filing_boundary_v1"),
    ("governance_join_policy_v1", "hyp_governance_safe_alternate_join_policy_v1"),
    ("issuer_sector_reporting_cadence_v1", "hyp_issuer_sector_reporting_cadence_v1"),
)


def apply_phase40_hypothesis_lifecycle(
    hypotheses: list[dict[str, Any]],
    *,
    families_executed: list[dict[str, Any]],
    evidence_ref: str,
) -> dict[str, Any]:
    """
    Draft families that ran under passing leakage -> conditionally_supported.
    If family leakage failed -> deferred (from draft).
    """
    by_fid = {str(f.get("family_id") or ""): f for f in families_executed}
    summary: dict[str, Any] = {"transitions": []}

    for fid, hid in _FAMILY_HYPOTHESES:
        fam = by_fid.get(fid) or {}
        leak_ok = bool((fam.get("leakage_audit") or {}).get("passed"))
        hyp = next((h for h in hypotheses if str(h.get("hypothesis_id") or "") == hid), None)
        if not hyp:
            continue
        st = str(hyp.get("status") or "")
        if st == HypothesisStatus.DRAFT.value:
            if leak_ok:
                apply_lifecycle_transition(
                    hyp,
                    to_status=HypothesisStatus.CONDITIONALLY_SUPPORTED.value,
                    reason=(
                        f"Phase 40: family {fid} executed DB-bound spec(s); shared leakage audit passed; "
                        "see bundle family row_results and summary_counts_by_spec."
                    ),
                    evidence_ref=evidence_ref,
                )
                summary["transitions"].append({"hypothesis_id": hid, "to": "conditionally_supported"})
            else:
                apply_lifecycle_transition(
                    hyp,
                    to_status=HypothesisStatus.DEFERRED.value,
                    reason=f"Phase 40: family {fid} leakage audit failed; defer until pick rules audited.",
                    evidence_ref=evidence_ref,
                )
                summary["transitions"].append({"hypothesis_id": hid, "to": "deferred"})
    return summary
