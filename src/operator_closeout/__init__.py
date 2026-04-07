"""Phase 23: one-command post-patch closeout, migration preflight, zero-UUID operator paths."""

from operator_closeout.closeout import run_post_patch_closeout
from operator_closeout.migrations import (
    generate_migration_bundle_file,
    list_local_migration_files,
    report_required_migrations,
)
from operator_closeout.next_step import (
    choose_post_patch_next_action,
    choose_post_patch_next_action_from_signals,
)
from operator_closeout.phase_state import verify_db_phase_state

__all__ = [
    "choose_post_patch_next_action",
    "choose_post_patch_next_action_from_signals",
    "generate_migration_bundle_file",
    "list_local_migration_files",
    "report_required_migrations",
    "run_post_patch_closeout",
    "verify_db_phase_state",
]
