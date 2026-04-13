"""Prospective re-entry vs retrospective material improvement (Phase 45)."""

from __future__ import annotations

from typing import Any


def build_future_reopen_protocol(*, phase44_bundle: dict[str, Any]) -> dict[str, Any]:
    retry = phase44_bundle.get("retry_eligibility") or {}
    used = retry.get("phase43_paths_already_used") or {}

    return {
        "future_reopen_allowed_with_named_source": True,
        "accepted_reopen_axes": [
            "bounded_filing_ingest_alternate_named_path",
            "bounded_sector_fill_alternate_named_provider",
        ],
        "forbidden_reopen_axes": [
            "broad_public_core_filing_index_campaign",
            "broad_metadata_or_universe_wide_sprint",
            "implicit_reopen_from_stale_bundle_recommendation_string",
            "auto_promotion",
            "new_hypothesis_family_without_separate_approval",
        ],
        "required_operator_declaration_fields": [
            "named_filing_source_or_ingestion_path_if_filing_axis",
            "named_sector_provider_or_path_if_sector_axis",
            "material_difference_rationale_vs_phase43_paths",
            "cohort_scope_explicit_cap_default_8_row_fixture",
            "one_shot_bounded_retest_acknowledgement",
        ],
        "max_scope_on_reopen": (
            "single_bounded_cohort_retest_one_shot; preserve 8-row fixture cap unless "
            "documented separate approval expands scope"
        ),
        "reopen_decision_rule": (
            "Prospective: one bounded retest may be authorized when operator registers a concrete "
            "named source/path that is not a duplicate label of Phase 43 paths already used, "
            "and documents why it is materially different. Retrospective: Phase 44 "
            "`material_falsifier_improvement_observed` remains the success criterion after a pass. "
            "These layers are distinct: declaring a new path does not imply prior improvement."
        ),
        "distinction": {
            "observed_material_improvement": (
                "After a bounded pass, Phase 44-style scorecard/gate/discrimination checks "
                "determine whether falsifier usability actually improved."
            ),
            "reopen_eligibility_on_new_named_source": (
                "Before the next pass, operator may register a new named path to satisfy governance "
                "for a single capped retest without requiring improvement to have been observed yet."
            ),
        },
        "phase43_paths_already_used_reference": used,
    }


def build_current_closeout_status(*, authoritative_resolution: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_closeout_status": "closed_pending_new_evidence",
        "authoritative_interpretation": authoritative_resolution.get("authoritative_phase"),
        "summary": (
            "Cohort closed under Phase 44 verdict; no further bounded work until named new "
            "source/path or other new evidence is registered per reopen protocol."
        ),
    }
