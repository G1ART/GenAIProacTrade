"""Phase 30: upstream SEC substrate (filing index, silver facts, narrow cascade)."""

from phase30.empty_cik_cleanup import report_empty_cik_gaps, run_empty_cik_cleanup_repair
from phase30.filing_index_gaps import (
    export_filing_index_gap_targets,
    report_filing_index_gap_targets,
    run_filing_index_backfill_repair,
)
from phase30.metrics import collect_validation_substrate_snapshot
from phase30.orchestrator import run_phase30_validation_substrate_repair
from phase30.review import write_phase30_validation_substrate_review_md
from phase30.silver_materialization import (
    report_silver_facts_materialization_gaps,
    run_silver_facts_materialization_repair,
)

__all__ = [
    "collect_validation_substrate_snapshot",
    "export_filing_index_gap_targets",
    "report_empty_cik_gaps",
    "report_filing_index_gap_targets",
    "report_silver_facts_materialization_gaps",
    "run_empty_cik_cleanup_repair",
    "run_filing_index_backfill_repair",
    "run_phase30_validation_substrate_repair",
    "run_silver_facts_materialization_repair",
    "write_phase30_validation_substrate_review_md",
]
