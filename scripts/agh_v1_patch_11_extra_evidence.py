"""Patch 11 — supplementary evidence writers.

Emits the three evidence JSONs that the workorder calls out separately
from the runbook / freeze / bridge files already written elsewhere:

- ``patch_11_brain_bundle_v3_evidence.json``
- ``patch_11_long_horizon_truth_evidence.json``
- ``patch_11_signal_quality_accumulation_evidence.json``
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

EVIDENCE_DIR = REPO_ROOT / "data/mvp/evidence"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=False, capture_output=True, text=True,
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


_NOW = "2026-04-23T08:00:00Z"


def _row(with_residual: bool = True) -> dict:
    r = {
        "asset_id":           "AAPL",
        "spectrum_position":  0.42,
        "rank_index":         0,
        "rank_movement":      "up",
        "what_changed":       "Momentum picked up after earnings beat.",
        "rationale_summary":  "Short-term flow and breadth leaning long.",
    }
    if with_residual:
        r["residual_score_semantics_version"] = "residual_semantics_v1"
        r["invalidation_hint"] = "spectrum_position_crosses_midline"
        r["recheck_cadence"] = "monthly_after_new_filing_or_21_trading_days"
    return r


def _build_bundle(short_coverage: int, medium_coverage: int) -> SimpleNamespace:
    return SimpleNamespace(
        as_of_utc=_NOW,
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "insufficient_evidence"},
        },
        registry_entries=[SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"stub_family_{hz}",
            registry_entry_id=f"stub_reg_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
            challenger_artifact_ids=[],
        ) for hz in ("short", "medium", "medium_long", "long")],
        artifacts=[SimpleNamespace(
            artifact_id=f"stub_family_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ) for hz in ("short", "medium", "medium_long", "long")],
        metadata={"graduation_tier": "production",
                  "built_at_utc": _NOW,
                  "source_run_ids": ["run_patch_11_extra"]},
        brain_overlays=[],
        long_horizon_support_by_horizon={
            "medium_long": {
                "contract_version": "LONG_HORIZON_SUPPORT_V1",
                "tier_key":         "limited",
                "n_rows":           25,
                "n_symbols":        10,
                "coverage_ratio":   0.55,
                "as_of_utc":        _NOW,
                "reason":           "limited_evidence",
            },
            "long": {
                "contract_version": "LONG_HORIZON_SUPPORT_V1",
                "tier_key":         "sample",
                "n_rows":           3,
                "n_symbols":        2,
                "coverage_ratio":   0.1,
                "as_of_utc":        _NOW,
                "reason":           "sample",
            },
        },
        spectrum_rows_by_horizon={
            "short":       [_row() for _ in range(short_coverage)]
                             + [_row(with_residual=False) for _ in range(max(0, 10 - short_coverage))],
            "medium":      [_row() for _ in range(medium_coverage)]
                             + [_row(with_residual=False) for _ in range(max(0, 10 - medium_coverage))],
            "medium_long": [_row() for _ in range(5)],
            "long":        [_row(with_residual=False) for _ in range(3)],
        },
    )


def _emit_brain_bundle_v3() -> dict:
    """Assert the BrainBundleV0 contract surfaces Patch 11 additions."""
    from metis_brain.bundle import BrainBundleV0  # type: ignore

    fields = BrainBundleV0.model_fields
    checks = [
        {"id": "bundle_has_long_horizon_support_by_horizon_field",
         "ok": "long_horizon_support_by_horizon" in fields},
        {"id": "bundle_has_brain_overlays_field",
         "ok": "brain_overlays" in fields},
        {"id": "bundle_has_horizon_provenance_field",
         "ok": "horizon_provenance" in fields},
    ]
    return {
        "contract_version":  "PATCH_11_BRAIN_BUNDLE_V3_EVIDENCE_V1",
        "generated_utc":     _iso_now(),
        "git_head_sha":      _git_sha(),
        "checks":            checks,
        "all_ok":            all(c["ok"] for c in checks),
        "field_names":       sorted(fields.keys()),
    }


def _emit_long_horizon_truth() -> dict:
    from metis_brain.long_horizon_evidence_v1 import (  # type: ignore
        long_horizon_support_integrity_errors,
        classify_long_horizon_tier,
    )

    cases = [
        ("production", 0.9, 50),
        ("limited",    0.5, 20),
        ("sample",     0.1, 3),
    ]
    tier_checks = [
        {"input_coverage": cov, "input_n_rows": n,
         "expected": expected, "realised": classify_long_horizon_tier(
             coverage_ratio=cov, n_rows=n,
         ),
         "ok": classify_long_horizon_tier(
             coverage_ratio=cov, n_rows=n,
         ) == expected}
        for expected, cov, n in cases
    ]
    honest = long_horizon_support_integrity_errors(
        horizon_provenance={"long": {"source": "insufficient_evidence"}},
        long_horizon_support_by_horizon={
            "long": {"tier_key": "sample", "n_rows": 2, "n_symbols": 1,
                     "coverage_ratio": 0.1}
        },
    )
    lie = long_horizon_support_integrity_errors(
        horizon_provenance={"long": {"source": "real_derived"}},
        long_horizon_support_by_horizon={
            "long": {"tier_key": "sample", "n_rows": 2, "n_symbols": 1,
                     "coverage_ratio": 0.1}
        },
    )
    return {
        "contract_version": "PATCH_11_LONG_HORIZON_TRUTH_EVIDENCE_V1",
        "generated_utc":    _iso_now(),
        "git_head_sha":     _git_sha(),
        "tier_classification": tier_checks,
        "integrity_checks": [
            {"id": "honest_sample_produces_no_errors",
             "ok": honest == [], "detail": honest},
            {"id": "real_derived_with_sample_flagged_as_lie",
             "ok": bool(lie), "detail": lie},
        ],
        "all_ok": all(t["ok"] for t in tier_checks) and honest == [] and bool(lie),
    }


def _emit_signal_quality_accumulation() -> dict:
    from metis_brain.mvp_spec_survey_v0 import (  # type: ignore
        _q11_signal_quality_accumulation,
    )

    scenarios = []
    # Pass — 8/10 short + 9/10 medium (both >= 0.8).
    ok_bundle = _build_bundle(short_coverage=9, medium_coverage=9)
    q11_ok, q11_detail = _q11_signal_quality_accumulation(ok_bundle)
    scenarios.append({
        "id": "healthy_coverage_passes_q11",
        "ok": q11_ok, "detail": q11_detail,
    })
    # Fail — 3/10 short + 10/10 medium (short below threshold).
    bad_bundle = _build_bundle(short_coverage=3, medium_coverage=10)
    q11_ok_bad, q11_detail_bad = _q11_signal_quality_accumulation(bad_bundle)
    scenarios.append({
        "id": "insufficient_short_coverage_fails_q11",
        "ok": q11_ok_bad is False, "detail": q11_detail_bad,
    })
    return {
        "contract_version": "PATCH_11_SIGNAL_QUALITY_ACCUMULATION_EVIDENCE_V1",
        "generated_utc":    _iso_now(),
        "git_head_sha":     _git_sha(),
        "scenarios":        scenarios,
        "all_ok":           all(s["ok"] for s in scenarios),
    }


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    emitters = {
        "patch_11_brain_bundle_v3_evidence.json":             _emit_brain_bundle_v3,
        "patch_11_long_horizon_truth_evidence.json":          _emit_long_horizon_truth,
        "patch_11_signal_quality_accumulation_evidence.json": _emit_signal_quality_accumulation,
    }
    summary = []
    for name, emit in emitters.items():
        payload = emit()
        path = EVIDENCE_DIR / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary.append({"file": name, "bytes": path.stat().st_size,
                        "all_ok": payload.get("all_ok", True)})
    print(json.dumps({"written": summary}, ensure_ascii=False, indent=2))
    return 0 if all(s["all_ok"] for s in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
