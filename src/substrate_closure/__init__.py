"""Phase 25: targeted substrate gap diagnosis and repair (validation, forward, state-change join)."""

from substrate_closure.diagnose import (
    report_forward_return_gaps,
    report_state_change_join_gaps,
    report_validation_panel_coverage_gaps,
)
from substrate_closure.repair import (
    run_forward_return_backfill_repair,
    run_state_change_join_repair,
    run_validation_panel_coverage_repair,
)
from substrate_closure.review import write_substrate_closure_review_md
from substrate_closure.snapshot import build_substrate_closure_snapshot

__all__ = [
    "build_substrate_closure_snapshot",
    "report_forward_return_gaps",
    "report_state_change_join_gaps",
    "report_validation_panel_coverage_gaps",
    "run_forward_return_backfill_repair",
    "run_state_change_join_repair",
    "run_validation_panel_coverage_repair",
    "write_substrate_closure_review_md",
]
