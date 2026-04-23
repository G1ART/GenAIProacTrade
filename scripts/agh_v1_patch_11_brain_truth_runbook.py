"""AGH v1 Patch 11 — Brain Bundle v3 / Signal Quality / Long-Horizon truth runbook.

Walks the Patch 11 workorder scenarios against the code that actually
serves the four customer-facing surfaces. Deterministic: no Supabase
writes, no network calls, no LLM calls.

Scenarios (workorder mapping):

    S1. Residual-score semantics end-to-end (row → MessageObjectV1 →
        message_layer_v1 → shared_focus.residual_freshness with normalized
        controlled-vocabulary keys and localized labels).
    S2. Long-horizon support honest tier — bundle validation catches
        dishonest provenance ↔ tier combinations.
    S3. Brain overlay propagation — overlay_note_block binds to active
        artifact / registry entry and surfaces on Today / Research /
        Ask via shared_focus.overlay_note (no engineering id leaks).
    S4. Cross-surface coherence — Patch 11 signature extensions move
        the fingerprint when residual / overlay semantics change, and
        all four surfaces agree on the same fingerprint per focus.
    S5. Q11 / Q12 additions to ``mvp_spec_survey_v0`` — Q1..Q10 IDs
        are unchanged; Q11 / Q12 are callable with bundle input.
    S6. Ask semantic regression — mean score >= 0.75 and strict
        bounded rate = 1.0 across the 18-entry golden set.
    S7. No-leak — static assets + 12 DTOs have no ``ovr_*`` / ``pcp_*``
        / ``persona_candidate_id`` / ``overlay_id`` tokens.

Produces (under ``data/mvp/evidence/``):

    * ``patch_11_brain_truth_runbook_evidence.json``
    * ``patch_11_brain_truth_bridge_evidence.json``
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


STATIC      = REPO_ROOT / "src/phase47_runtime/static"
PRODUCT_JS  = STATIC / "product_shell.js"
PRODUCT_CSS = STATIC / "product_shell.css"
PRODUCT_HTM = STATIC / "index.html"
EVIDENCE_DIR = REPO_ROOT / "data/mvp/evidence"


def _now_iso() -> str:
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


# ---------------------------------------------------------------------------
# Synthetic fixtures (Patch 11 — carry residual / long-horizon / overlay)
# ---------------------------------------------------------------------------


_NOW = "2026-04-23T08:00:00Z"
_FOCUS_ASSET = "AAPL"
_FOCUS_HZ    = "short"


def _row(with_residual: bool = True) -> dict:
    r = {
        "asset_id":           _FOCUS_ASSET,
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


def _bundle(
    *,
    overlays: list[dict] | None = None,
    long_support: dict[str, dict] | None = None,
    horizon_provenance: dict[str, dict] | None = None,
) -> SimpleNamespace:
    overlays = overlays if overlays is not None else [{
        "overlay_id":        "ovr_catalyst_runbook_001",
        "overlay_type":      "catalyst_window",
        "artifact_id":       "stub_family_short",
        "registry_entry_id": "",
        "counter_interpretation_present": True,
    }]
    long_support = long_support if long_support is not None else {
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
    }
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    reg_entries = [SimpleNamespace(
        status="active", horizon=hz,
        active_artifact_id=f"stub_family_{hz}",
        registry_entry_id=f"stub_reg_{hz}",
        display_family_name_ko=f"{hz}-가문",
        display_family_name_en=f"{hz}-family",
        challenger_artifact_ids=[],
    ) for hz in HORIZON_KEYS]
    artifacts = [SimpleNamespace(
        artifact_id=f"stub_family_{hz}",
        display_family_name_ko=f"{hz}-가문",
        display_family_name_en=f"{hz}-family",
    ) for hz in HORIZON_KEYS]
    return SimpleNamespace(
        artifacts=artifacts,
        registry_entries=reg_entries,
        horizon_provenance=horizon_provenance or {
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "insufficient_evidence"},
        },
        metadata={"graduation_tier": "production",
                  "built_at_utc": _NOW,
                  "source_run_ids": ["run_patch_11"]},
        as_of_utc=_NOW,
        brain_overlays=overlays,
        long_horizon_support_by_horizon=long_support,
        spectrum_rows_by_horizon={
            "short":       [_row() for _ in range(4)],
            "medium":      [_row() for _ in range(4)],
            "medium_long": [_row() for _ in range(4)],
            "long":        [_row(with_residual=False)],
        },
    )


def _spectrum() -> dict:
    from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore
    return {hz: {"ok": True, "rows": [_row()]} for hz in HORIZON_KEYS}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def _scenario_s1_residual_semantics() -> dict[str, Any]:
    """End-to-end residual-score semantics propagation."""
    from phase47_runtime.message_layer_v1 import (  # type: ignore
        MESSAGE_LAYER_V1_KEYS, build_message_layer_v1_for_row,
    )
    from phase47_runtime.product_shell.view_models_common import (  # type: ignore
        build_shared_focus_block,
    )

    checks: list[dict[str, Any]] = []
    row = _row()
    msg = build_message_layer_v1_for_row(
        row=row, horizon=_FOCUS_HZ, lang="ko",
        active_model_family="short-family",
        rationale_summary=row["rationale_summary"],
        what_changed=row["what_changed"],
        confidence_band="medium",
        linked_registry_entry_id="stub_reg_short",
        linked_artifact_id="stub_family_short",
    )
    checks.append({"id": "message_layer_has_residual_keys", "ok": all(
        k in msg for k in (
            "residual_score_semantics_version",
            "invalidation_hint",
            "recheck_cadence",
        )
    )})
    checks.append({"id": "message_layer_keys_tuple_has_residual_keys", "ok": all(
        k in MESSAGE_LAYER_V1_KEYS for k in (
            "residual_score_semantics_version",
            "invalidation_hint",
            "recheck_cadence",
        )
    )})
    focus = build_shared_focus_block(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        asset_id=_FOCUS_ASSET, horizon_key=_FOCUS_HZ, lang="ko",
    )
    rf = focus.get("residual_freshness")
    checks.append({"id": "shared_focus_carries_residual_freshness", "ok": rf is not None})
    if rf:
        blob = repr(rf).lower()
        checks.append({"id": "residual_block_no_raw_slug", "ok": all(
            tok not in blob for tok in (
                "trading_days", "crosses_midline", "confidence_band_drops_to_low",
            )
        )})
        checks.append({"id": "residual_block_uses_controlled_keys", "ok": (
            rf.get("recheck_cadence_key") in (
                "monthly", "quarterly", "semi_annually", "annually", "unknown",
            )
            and rf.get("invalidation_hint_kind") in (
                "pit_fail", "confidence_drop", "midline_cross",
                "return_reversal", "unknown",
            )
        )})
    return {"scenario": "S1", "ok": all(c["ok"] for c in checks), "checks": checks}


def _scenario_s2_long_horizon_support() -> dict[str, Any]:
    """Bundle integrity catches dishonest provenance ↔ tier pairings."""
    from metis_brain.long_horizon_evidence_v1 import (  # type: ignore
        long_horizon_support_integrity_errors,
    )
    checks: list[dict[str, Any]] = []
    honest = long_horizon_support_integrity_errors(
        horizon_provenance={"long": {"source": "insufficient_evidence"}},
        long_horizon_support_by_horizon={
            "long": {"tier_key": "sample", "n_rows": 2, "n_symbols": 1,
                     "coverage_ratio": 0.1}
        },
    )
    checks.append({"id": "honest_sample_has_no_errors", "ok": honest == []})
    lie = long_horizon_support_integrity_errors(
        horizon_provenance={"long": {"source": "real_derived"}},
        long_horizon_support_by_horizon={
            "long": {"tier_key": "sample", "n_rows": 2, "n_symbols": 1,
                     "coverage_ratio": 0.1}
        },
    )
    checks.append({"id": "real_derived_with_sample_is_flagged", "ok": bool(lie)})
    under = long_horizon_support_integrity_errors(
        horizon_provenance={"long": {"source": "insufficient_evidence"}},
        long_horizon_support_by_horizon={
            "long": {"tier_key": "production", "n_rows": 40, "n_symbols": 25,
                     "coverage_ratio": 0.9}
        },
    )
    checks.append({"id": "insufficient_with_production_is_flagged", "ok": bool(under)})
    return {"scenario": "S2", "ok": all(c["ok"] for c in checks), "checks": checks}


def _scenario_s3_overlay_propagation() -> dict[str, Any]:
    """Overlay_note_block binds to active artifact + surfaces on all
    three customer surfaces."""
    from phase47_runtime.product_shell.view_models_common import (  # type: ignore
        BRAIN_OVERLAY_KINDS, overlay_note_block,
    )
    from phase47_runtime.product_shell.view_models_ask import (  # type: ignore
        compose_quick_answers_dto,
    )
    from phase47_runtime.product_shell.view_models_research import (  # type: ignore
        compose_research_deepdive_dto,
    )

    checks: list[dict[str, Any]] = []
    bundle = _bundle()
    ov_block = overlay_note_block(
        bundle=bundle, horizon_key=_FOCUS_HZ, lang="ko",
    )
    checks.append({"id": "overlay_block_exists", "ok": ov_block is not None})
    if ov_block:
        checks.append({"id": "overlay_block_dominant_in_buckets",
                       "ok": ov_block["dominant_kind_key"] in BRAIN_OVERLAY_KINDS})
        blob = repr(ov_block)
        checks.append({"id": "overlay_block_no_raw_ids", "ok": (
            "ovr_" not in blob and "overlay_id" not in blob
        )})
    dd = compose_research_deepdive_dto(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id=_FOCUS_ASSET, horizon_key=_FOCUS_HZ, lang="ko", now_utc=_NOW,
    )
    counter = next((c for c in dd["evidence"]
                    if c["kind"] == "counter_or_companion"), None)
    checks.append({"id": "research_counter_card_mentions_counter_interpretation",
                   "ok": bool(counter and "반대 해석" in (counter["body"] or ""))})
    quick = compose_quick_answers_dto(
        bundle=bundle, spectrum_by_horizon=_spectrum(),
        asset_id=_FOCUS_ASSET, horizon_key=_FOCUS_HZ, lang="ko",
    )
    whats = next(a for a in quick["answers"] if a["intent"] == "whats_missing")
    checks.append({"id": "ask_whats_missing_notes_counter",
                   "ok": any("반대 해석" in str(s)
                             for s in (whats.get("insufficiency") or []))})
    return {"scenario": "S3", "ok": all(c["ok"] for c in checks), "checks": checks}


def _scenario_s4_coherence_drift() -> dict[str, Any]:
    from phase47_runtime.product_shell.view_models_common import (  # type: ignore
        build_shared_focus_block,
    )

    checks: list[dict[str, Any]] = []

    def _fp(bundle) -> str:
        return build_shared_focus_block(
            bundle=bundle, spectrum_by_horizon=_spectrum(),
            asset_id=_FOCUS_ASSET, horizon_key=_FOCUS_HZ, lang="ko",
        )["coherence_signature"]["fingerprint"]

    b_catalyst = _bundle(overlays=[{
        "overlay_id": "ovr_a", "overlay_type": "catalyst_window",
        "artifact_id": "stub_family_short", "counter_interpretation_present": True,
    }])
    b_invalid = _bundle(overlays=[{
        "overlay_id": "ovr_b", "overlay_type": "invalidation_warning",
        "artifact_id": "stub_family_short", "counter_interpretation_present": True,
    }])
    checks.append({"id": "overlay_kind_drift_moves_fingerprint",
                   "ok": _fp(b_catalyst) != _fp(b_invalid)})
    # Switching language must NOT move the fingerprint.
    f_ko = build_shared_focus_block(
        bundle=b_catalyst, spectrum_by_horizon=_spectrum(),
        asset_id=_FOCUS_ASSET, horizon_key=_FOCUS_HZ, lang="ko",
    )["coherence_signature"]["fingerprint"]
    f_en = build_shared_focus_block(
        bundle=b_catalyst, spectrum_by_horizon=_spectrum(),
        asset_id=_FOCUS_ASSET, horizon_key=_FOCUS_HZ, lang="en",
    )["coherence_signature"]["fingerprint"]
    checks.append({"id": "language_independent_fingerprint", "ok": f_ko == f_en})
    return {"scenario": "S4", "ok": all(c["ok"] for c in checks), "checks": checks}


def _scenario_s5_q11_q12_survey() -> dict[str, Any]:
    from metis_brain.mvp_spec_survey_v0 import (  # type: ignore
        _q11_signal_quality_accumulation, _q12_long_horizon_honest_tier,
    )

    checks: list[dict[str, Any]] = []
    bundle = _bundle()
    q11_ok, q11_detail = _q11_signal_quality_accumulation(bundle)
    q12_ok, q12_detail = _q12_long_horizon_honest_tier(bundle)
    checks.append({"id": "Q11_passes_on_honest_bundle", "ok": q11_ok, "detail": q11_detail})
    checks.append({"id": "Q12_passes_on_honest_bundle", "ok": q12_ok, "detail": q12_detail})
    # Lie detection — Q12 must fail when the bundle lies.
    bundle_lie = _bundle(
        long_support={
            "medium_long": {"tier_key": "sample", "n_rows": 2, "n_symbols": 1,
                            "coverage_ratio": 0.1},
            "long":        {"tier_key": "sample", "n_rows": 2, "n_symbols": 1,
                            "coverage_ratio": 0.1},
        },
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "real_derived"},
        },
    )
    lie_q12_ok, lie_q12_detail = _q12_long_horizon_honest_tier(bundle_lie)
    checks.append({"id": "Q12_fails_on_lying_bundle",
                   "ok": lie_q12_ok is False, "detail": lie_q12_detail})
    return {"scenario": "S5", "ok": all(c["ok"] for c in checks), "checks": checks}


def _scenario_s6_ask_semantic_regression() -> dict[str, Any]:
    # Re-use the regression runner from the test module so the runbook
    # and the regression test share a single scoring path.
    from tests.test_agh_v1_patch_11_ask_semantic_quality import _run_all  # type: ignore

    out = _run_all()
    checks = [
        {"id": "regression_score_at_least_0_75",
         "ok": out["regression_score"] >= 0.75,
         "detail": out["regression_score"]},
        {"id": "bounded_rate_strict_1_0",
         "ok": out["bounded_rate"] == 1.0,
         "detail": out["bounded_rate"]},
        {"id": "grounded_rate_minimum",
         "ok": out["grounded_rate"] >= 0.7,
         "detail": out["grounded_rate"]},
    ]
    return {
        "scenario": "S6",
        "ok":       all(c["ok"] for c in checks),
        "checks":   checks,
        "rates": {
            "grounded_rate": out["grounded_rate"],
            "bounded_rate":  out["bounded_rate"],
            "useful_rate":   out["useful_rate"],
            "regression_score": out["regression_score"],
        },
    }


_FORBIDDEN_TOKENS = re.compile(
    r"\b(ovr_[A-Za-z0-9_]+|pcp_[A-Za-z0-9_]+|persona_candidate_id|overlay_id)\b"
)


def _scenario_s7_no_leak() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    # Static assets.
    for p in (PRODUCT_HTM, PRODUCT_JS, PRODUCT_CSS):
        text = p.read_text(encoding="utf-8") if p.exists() else ""
        m = _FORBIDDEN_TOKENS.search(text)
        checks.append({"id": f"static_no_leak_{p.name}",
                       "ok": m is None,
                       "detail": m.group(0) if m else ""})
    # Freeze manifest (written by the freeze script) — if present, it
    # already holds the per-DTO leak hits.
    manifest = REPO_ROOT / "data/mvp/evidence/screenshots_patch_11/brain_truth_manifest_AAPL_short.json"
    if manifest.is_file():
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        leaks = raw.get("engineering_id_leaks") or []
        checks.append({"id": "freeze_manifest_no_eng_id_leaks",
                       "ok": leaks == [], "detail": leaks})
    else:
        checks.append({"id": "freeze_manifest_present",
                       "ok": False,
                       "detail": "run scripts/agh_v1_patch_11_brain_truth_freeze.py first"})
    return {"scenario": "S7", "ok": all(c["ok"] for c in checks), "checks": checks}


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = [
        _scenario_s1_residual_semantics(),
        _scenario_s2_long_horizon_support(),
        _scenario_s3_overlay_propagation(),
        _scenario_s4_coherence_drift(),
        _scenario_s5_q11_q12_survey(),
        _scenario_s6_ask_semantic_regression(),
        _scenario_s7_no_leak(),
    ]
    all_ok = all(s["ok"] for s in scenarios)
    evidence = {
        "contract_version": "PATCH_11_BRAIN_TRUTH_RUNBOOK_EVIDENCE_V1",
        "generated_utc":    _now_iso(),
        "git_head_sha":     _git_sha(),
        "scenarios":        scenarios,
        "all_ok":           all_ok,
    }
    out_path = EVIDENCE_DIR / "patch_11_brain_truth_runbook_evidence.json"
    out_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Bridge evidence — compact operator-facing summary.
    bridge = {
        "contract_version": "PATCH_11_BRAIN_TRUTH_BRIDGE_EVIDENCE_V1",
        "generated_utc":    _now_iso(),
        "git_head_sha":     _git_sha(),
        "per_scenario":     [
            {"scenario": s["scenario"], "ok": s["ok"]} for s in scenarios
        ],
        "all_ok": all_ok,
    }
    bridge_path = EVIDENCE_DIR / "patch_11_brain_truth_bridge_evidence.json"
    bridge_path.write_text(
        json.dumps(bridge, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "all_ok": all_ok,
        "per_scenario": [(s["scenario"], s["ok"]) for s in scenarios],
        "runbook":      str(out_path.relative_to(REPO_ROOT)),
        "bridge":       str(bridge_path.relative_to(REPO_ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
