"""Research hypothesis registry + promotion audit (no auto-wiring to production scoring)."""

from research_registry.promotion_rules import assert_no_auto_promotion_wiring
from research_registry.registry import ensure_sample_hypotheses

__all__ = ["assert_no_auto_promotion_wiring", "ensure_sample_hypotheses"]
