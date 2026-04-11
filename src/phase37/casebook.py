"""Residual casebook — persistent entries for deferred tails."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CasebookEntryV1:
    case_id: str
    category: str
    title: str
    why_unresolved: str
    why_not_headline_work: str
    status_change_triggers: list[str]
    linked_symbols: list[str] = field(default_factory=list)
    linked_ciks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def seed_casebook_entries() -> list[dict[str, Any]]:
    pit_syms = ["ADSK", "BBY", "CRM", "CRWD", "DELL", "DUK", "NVDA", "WMT"]
    return [
        CasebookEntryV1(
            case_id="case_pit_no_sc_join_key_mismatch_8",
            category="pit_lab_residual",
            title="no_state_change_join — state_change_built_but_join_key_mismatch (8 symbols)",
            why_unresolved=(
                "Earliest state_change as_of in the referenced score run is after signal_available_date; "
                "default PIT join key does not match — not a missing state_change build."
            ),
            why_not_headline_work=(
                "Broad state_change rerun does not address as-of ordering; would duplicate Phase 36 policy "
                "and risks non-deterministic churn. Belongs in PIT experiment harness, not closure sprint."
            ),
            status_change_triggers=[
                "PIT harness documents a deterministic alternate run spec that clears join without leakage",
                "Governance explicitly changes join_key policy for this bucket",
            ],
            linked_symbols=pit_syms,
            metadata={"residual_join_bucket": "state_change_built_but_join_key_mismatch"},
        ).to_json_dict(),
        CasebookEntryV1(
            case_id="case_gis_unmapped_concept_seam",
            category="gis_narrow_sample",
            title="GIS deterministic inspect — blocked_unmapped_concepts_remain_in_sample",
            why_unresolved=(
                "Sampled raw concepts (e.g. DEI fields) lack deterministic map entries in the concept map."
            ),
            why_not_headline_work=(
                "Phase 36 non-goal: large GIS expansion during substrate closure; low ROI vs joined headline."
            ),
            status_change_triggers=[
                "Targeted concept map PR with regression tests",
                "Explicit product decision to expand GIS coverage for issuer narrative features",
            ],
            metadata={"blocked_reason": "concept_map_misses_for_sampled_raw_concepts", "unmapped_count": 13},
        ).to_json_dict(),
        CasebookEntryV1(
            case_id="case_maturity_immature_nq_7",
            category="forward_window_calendar",
            title="Immature next-quarter forward window — 7 symbols (Phase 34/35 schedule)",
            why_unresolved="Price lookahead window not matured for NQ excess computation at audit as_of.",
            why_not_headline_work=(
                "Time solves a subset; forcing ingest would violate lookahead / PIT calendar policy."
            ),
            status_change_triggers=[
                "matured_forward_retry eligible per report_matured_window_schedule_for_forward",
                "Calendar / lookahead policy update",
            ],
            metadata={
                "symbols_example": ["MCK", "MDT", "MKC", "MU", "NDSN", "NTAP", "NWSA"],
                "note": "Exact set from phase34/35 bundles; verify on refresh.",
            },
        ).to_json_dict(),
        CasebookEntryV1(
            case_id="case_registry_tail_151",
            category="registry_upstream_deferred",
            title="missing_validation_symbol_count — registry / upstream pipeline tail",
            why_unresolved=(
                "Majority bucket factor_panel_missing_for_resolved_cik and filing_index upstream gaps; "
                "not specific to joined recipe closure."
            ),
            why_not_headline_work=(
                "Substrate freeze treats low-ROI registry tail as deferred background; avoids broad filing campaign."
            ),
            status_change_triggers=[
                "Phase-scoped backfill sprint with explicit CIK budget",
                "Product requires full SP500 validation coverage",
            ],
            metadata={
                "missing_validation_symbol_count": 151,
                "factor_panel_missing_for_resolved_cik": 148,
            },
        ).to_json_dict(),
    ]
