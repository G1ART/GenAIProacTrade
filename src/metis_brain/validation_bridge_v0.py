"""Factor validation excerpt → Metis promotion gate record (Build Plan: Heart output → Brain gate).

Does not hit the database. Callers pass a small ``summary`` dict (from an export
pipeline, test fixture, or future `research_validation` adapter) so gate rows are
not only hand-maintained JSON.

Next P0 slice: wire `research_validation.service` / DB rows into this summary shape
and append artifacts + spectrum rows from validated kernels (replace stub bundle).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from metis_brain.schemas_v0 import PromotionGateRecordV0


def promotion_gate_from_validation_summary(
    *,
    artifact_id: str,
    evaluation_run_id: str,
    summary: dict[str, Any],
) -> PromotionGateRecordV0:
    """Map explicit booleans / notes into Product Spec §6.2 gate record."""
    pit = bool(summary.get("pit_pass", summary.get("pit_ok", False)))
    cov = bool(summary.get("coverage_pass", summary.get("coverage_ok", False)))
    mono = bool(summary.get("monotonicity_pass", summary.get("monotonicity_ok", False)))
    approved_by = str(summary.get("approved_by_rule") or "").strip() or "factor_validation_summary:v0"
    role = str(summary.get("challenger_or_active") or "active").strip() or "active"
    reasons = str(summary.get("reasons") or "").strip() or "mapped_from_validation_summary_v0"
    regime = str(summary.get("regime_notes") or "").strip()
    sector_ov = str(summary.get("sector_override_notes") or "").strip()
    expiry = str(summary.get("expiry_or_recheck_rule") or "recheck_on_next_validation_run:v0").strip()
    approved_at = str(summary.get("approved_at") or "").strip()
    if not approved_at:
        approved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    supersedes = str(summary.get("supersedes_registry_entry") or "").strip()
    return PromotionGateRecordV0(
        artifact_id=str(artifact_id).strip(),
        evaluation_run_id=str(evaluation_run_id).strip(),
        pit_pass=pit,
        coverage_pass=cov,
        monotonicity_pass=mono,
        regime_notes=regime,
        sector_override_notes=sector_ov,
        challenger_or_active=role,
        approved_by_rule=approved_by,
        approved_at=approved_at,
        supersedes_registry_entry=supersedes,
        reasons=reasons,
        expiry_or_recheck_rule=expiry,
    )
