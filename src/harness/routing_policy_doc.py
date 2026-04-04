"""
Intent routing priority (constitutional — for future message layer / COS orchestration).

1) COS_ONLY first — IR tone, memo rewrite, strategy framing without external mutation.
2) INTERNAL_SUPPORT second — research memos, segmentation notes, scenario drafts as artifacts.
3) EXTERNAL_EXECUTION last — code/db/deploy mutations; requires explicit approval workflow (outside this module).

This file is documentation + constants only; no automatic routing is wired in Phase 7.
"""

COS_ONLY_EXAMPLES = (
    "ir deck rewrite",
    "investor tone",
    "budget framing",
    "strategy memo",
    "document critique",
)

INTERNAL_SUPPORT_EXAMPLES = (
    "competitor teardown",
    "budget scenario draft",
    "investor segmentation note",
)

EXTERNAL_REQUIRES_APPROVAL = (
    "database migration",
    "deploy",
    "production config",
)
