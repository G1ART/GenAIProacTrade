"""Phase 31: raw_xbrl bridge, silver seam, issuer mapping, narrow cascade."""

from phase31.issuer_mapping_repair import run_deterministic_empty_cik_issuer_repair
from phase31.orchestrator import run_phase31_raw_facts_bridge_repair
from phase31.phase32_recommend import recommend_phase32_branch
from phase31.raw_facts_gaps import export_raw_facts_gap_targets, report_raw_facts_gap_targets
from phase31.raw_facts_repair import run_raw_facts_backfill_repair
from phase31.review import write_phase31_raw_facts_bridge_review_md
from phase31.silver_seam_repair import (
    report_raw_present_no_silver_targets,
    run_gis_like_silver_materialization_seam_repair,
)

__all__ = [
    "export_raw_facts_gap_targets",
    "recommend_phase32_branch",
    "report_raw_facts_gap_targets",
    "report_raw_present_no_silver_targets",
    "run_deterministic_empty_cik_issuer_repair",
    "run_gis_like_silver_materialization_seam_repair",
    "run_phase31_raw_facts_bridge_repair",
    "run_raw_facts_backfill_repair",
    "write_phase31_raw_facts_bridge_review_md",
]
