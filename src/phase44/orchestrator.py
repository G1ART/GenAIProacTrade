"""Assemble Phase 44 bundle from Phase 42 + Phase 43 JSON inputs (no DB)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase44.claim_narrowing import build_claim_narrowing
from phase44.phase45_recommend import recommend_phase45
from phase44.provenance_audit import build_provenance_audit_rows
from phase44.recommendation_truth import assess_phase44_truthfulness
from phase44.retry_eligibility import build_retry_eligibility


def _read_json(path: str) -> dict[str, Any]:
    import json

    p = Path(path)
    return dict(json.loads(p.read_text(encoding="utf-8")))


def run_phase44_claim_narrowing_truthfulness(
    *,
    phase43_bundle_in: str,
    phase42_supabase_bundle_in: str,
    declared_new_filing_source: str | None = None,
    declared_new_sector_source: str | None = None,
) -> dict[str, Any]:
    p43 = _read_json(phase43_bundle_in)
    p42 = _read_json(phase42_supabase_bundle_in)

    scorecard_phase42_supabase_before = dict(p42.get("family_evidence_scorecard") or {})
    scorecard_phase43_after = dict(p43.get("scorecard_after") or {})
    gate_before = dict(p43.get("gate_before") or {})
    gate_after = dict(p43.get("gate_after") or {})

    disc_before = p42.get("discrimination_summary")
    p42_rerun = p43.get("phase42_rerun_after_backfill") or {}
    disc_after = p42_rerun.get("discrimination_summary")

    provenance_audit = build_provenance_audit_rows(phase43_bundle=p43)

    truth = assess_phase44_truthfulness(
        scorecard_before=p43.get("scorecard_before") or {},
        scorecard_after=p43.get("scorecard_after") or {},
        gate_before=gate_before,
        gate_after=gate_after,
        discrimination_before=disc_before if isinstance(disc_before, dict) else None,
        discrimination_after=disc_after if isinstance(disc_after, dict) else None,
    )

    retry = build_retry_eligibility(
        phase43_bundle=p43,
        material_falsifier_improvement=bool(truth.get("material_falsifier_improvement")),
        declared_new_filing_source=declared_new_filing_source,
        declared_new_sector_source=declared_new_sector_source,
    )

    claim_narrowing = build_claim_narrowing(
        truth=truth,
        retry=retry,
        scorecard_before=p43.get("scorecard_before") or {},
        scorecard_after=p43.get("scorecard_after") or {},
    )

    phase45 = recommend_phase45(truth=truth, retry=retry, claim_narrowing=claim_narrowing)

    gen = datetime.now(timezone.utc).isoformat()

    return {
        "ok": True,
        "phase": "phase44_claim_narrowing_truthfulness",
        "generated_utc": gen,
        "input_phase43_bundle_path": str(Path(phase43_bundle_in).resolve()),
        "input_phase42_supabase_bundle_path": str(Path(phase42_supabase_bundle_in).resolve()),
        "provenance_audit": provenance_audit,
        "scorecard_phase42_supabase_before": scorecard_phase42_supabase_before,
        "scorecard_phase43_after": scorecard_phase43_after,
        "gate_before": gate_before,
        "gate_after": gate_after,
        "claim_narrowing": claim_narrowing,
        "retry_eligibility": retry,
        "phase44_truthfulness_assessment": truth,
        "phase45": phase45,
    }
