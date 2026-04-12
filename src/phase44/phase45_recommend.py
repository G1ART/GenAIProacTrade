"""Phase 45 fork after Phase 44 truthfulness + retry eligibility."""

from __future__ import annotations

from typing import Any


def recommend_phase45(
    *,
    truth: dict[str, Any],
    retry: dict[str, Any],
    claim_narrowing: dict[str, Any],
) -> dict[str, Any]:
    material = bool(truth.get("material_falsifier_improvement"))
    any_retry = bool(retry.get("filing_retry_eligible") or retry.get("sector_retry_eligible"))
    cohort = (claim_narrowing.get("cohort_claim_limits") or {}).get("claim_status") or ""

    if any_retry:
        return {
            "phase45_recommendation": "execute_declared_bounded_retest_with_named_new_source_v1",
            "rationale": (
                "Material falsifier movement recorded and operator registered a concrete new "
                "filing or sector path; run a capped cohort retest against that path only."
            ),
        }
    if material and not any_retry:
        return {
            "phase45_recommendation": "register_named_source_then_bounded_retest_or_stop_v1",
            "rationale": (
                "Some material signal exists but Phase 44 retry registry blocks another pass until "
                "a named alternative source/path is declared."
            ),
        }
    if cohort == "narrowed" or not material:
        return {
            "phase45_recommendation": "narrow_claims_document_proxy_limits_operator_closeout_v1",
            "rationale": (
                "No material falsifier upgrade under Phase 44 rules; do not reopen broad substrate. "
                "Narrow claims, document proxy limits, and close out unless new evidence appears."
            ),
        }
    return {
        "phase45_recommendation": "narrow_claims_document_proxy_limits_operator_closeout_v1",
        "rationale": "Default conservative closeout after Phase 44 assessment.",
    }
