"""Phase 13: deterministic public-core cycle quality gate + residual triage evidence."""

from __future__ import annotations

from typing import Any

from db import records as dbrec

# --- Explicit classification thresholds (documented; adjust only with test updates) ---
THIN_INPUT_INSUFFICIENT_FRAC = 0.75
THIN_INPUT_COMBO_INSUFFICIENT_FRAC = 0.50
THIN_INPUT_COMBO_GATING_FRAC = 0.35
STRONG_INSUFFICIENT_FRAC = 0.40
STRONG_MIN_WATCHLIST = 1
STRONG_MIN_CASEBOOK = 1
STRONG_ALT_INSUFFICIENT_FRAC = 0.45
STRONG_ALT_MIN_WATCHLIST = 3
DEGRADED_HARNESS_ERROR_FRAC = 0.15


def _stage_out(stages: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for s in stages:
        if s.get("name") == name:
            o = s.get("out")
            return o if isinstance(o, dict) else {}
    return {}


def _stage_status(stages: list[dict[str, Any]], name: str) -> str:
    for s in stages:
        if s.get("name") == name:
            return str(s.get("status") or "")
    return ""


def collect_cycle_metrics(
    client: Any,
    *,
    state_change_run_id: str,
    stages: list[dict[str, Any]],
) -> dict[str, Any]:
    class_counts = dbrec.fetch_state_change_candidate_class_counts(
        client, run_id=state_change_run_id
    )
    gating_n, n_cand_db = dbrec.fetch_state_change_gating_and_candidate_count(
        client, run_id=state_change_run_id
    )

    cb = _stage_out(stages, "outlier_casebook")
    sc = _stage_out(stages, "scanner_watchlist")
    mem = _stage_out(stages, "investigation_memos")
    har = _stage_out(stages, "harness_inputs")

    candidates_scanned = int(
        cb.get("candidates_scanned")
        or (sc.get("stats") or {}).get("candidates_scanned")
        or n_cand_db
        or 0
    )
    n = max(candidates_scanned, 1)
    insufficient = int(class_counts.get("insufficient_data") or 0)
    usable_classes = (
        int(class_counts.get("investigate_now") or 0)
        + int(class_counts.get("investigate_watch") or 0)
        + int(class_counts.get("recheck_later") or 0)
    )

    memos_touched = int(mem.get("memos_inserted_new_version") or 0) + int(
        mem.get("memos_replaced_in_place") or 0
    )
    harness_built = int(har.get("inputs_built") or 0)
    harness_errs = har.get("errors") or []
    harness_err_n = len(harness_errs) if isinstance(harness_errs, list) else 0

    return {
        "candidates_scanned": candidates_scanned,
        "candidates_in_db": n_cand_db,
        "candidate_class_counts": dict(class_counts),
        "usable_class_count": usable_classes,
        "insufficient_data_count": insufficient,
        "insufficient_data_fraction": insufficient / n,
        "gating_high_missingness_count": gating_n,
        "gating_high_missingness_fraction": gating_n / n,
        "memos_touched": memos_touched,
        "memo_touch_rate": memos_touched / max(harness_built, 1),
        "harness_inputs_built": harness_built,
        "harness_error_count": harness_err_n,
        "harness_error_rate": harness_err_n / max(harness_built, 1) if harness_built else 0.0,
        "casebook_entries_created": int(cb.get("entries_created") or 0),
        "casebook_entry_rate": int(cb.get("entries_created") or 0) / n,
        "watchlist_selected": int(sc.get("watchlist_entries") or 0),
        "watchlist_selection_rate": int(sc.get("watchlist_entries") or 0) / n,
        "stage_status_by_name": {
            s.get("name"): s.get("status") for s in stages if s.get("name")
        },
    }


def classify_cycle_quality(
    *,
    cycle_ok: bool,
    scanner_failed: bool,
    metrics: dict[str, Any],
) -> str:
    if not cycle_ok or scanner_failed:
        return "failed"
    stmap = metrics.get("stage_status_by_name") or {}
    for key in ("harness_inputs", "investigation_memos", "outlier_casebook"):
        if stmap.get(key) == "failed":
            return "degraded"
    if float(metrics.get("harness_error_rate") or 0) > DEGRADED_HARNESS_ERROR_FRAC:
        return "degraded"

    p_ins = float(metrics.get("insufficient_data_fraction") or 0)
    p_gate = float(metrics.get("gating_high_missingness_fraction") or 0)
    wl = int(metrics.get("watchlist_selected") or 0)
    ce = int(metrics.get("casebook_entries_created") or 0)

    if p_ins >= THIN_INPUT_INSUFFICIENT_FRAC or (
        p_ins >= THIN_INPUT_COMBO_INSUFFICIENT_FRAC
        and p_gate >= THIN_INPUT_COMBO_GATING_FRAC
    ):
        return "thin_input"

    if (
        p_ins < STRONG_INSUFFICIENT_FRAC
        and wl >= STRONG_MIN_WATCHLIST
        and ce >= STRONG_MIN_CASEBOOK
    ):
        return "strong"
    if p_ins < STRONG_ALT_INSUFFICIENT_FRAC and wl >= STRONG_ALT_MIN_WATCHLIST:
        return "strong"

    return "usable_with_gaps"


def rank_gap_reasons(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    reasons: list[tuple[float, str, str]] = []
    n = max(int(metrics.get("candidates_scanned") or 0), 1)

    p_ins = float(metrics.get("insufficient_data_fraction") or 0)
    if p_ins > 0:
        reasons.append((p_ins, "high_insufficient_data_fraction", f"{p_ins:.2f} of candidates"))

    p_gate = float(metrics.get("gating_high_missingness_fraction") or 0)
    if p_gate > 0:
        reasons.append((p_gate, "gating_high_missingness", f"{p_gate:.2f} with excluded_reason"))

    wl = int(metrics.get("watchlist_selected") or 0)
    if wl == 0:
        reasons.append((0.35, "empty_watchlist_after_thresholding", "watchlist_selected=0"))

    if float(metrics.get("harness_error_rate") or 0) > 0:
        reasons.append(
            (
                float(metrics.get("harness_error_rate") or 0),
                "harness_materialization_errors",
                f"errors={metrics.get('harness_error_count')}",
            )
        )

    ce = int(metrics.get("casebook_entries_created") or 0)
    if ce == 0 and p_ins < 0.5:
        reasons.append((0.12, "sparse_casebook_entries", "entries_created=0"))

    memo_r = float(metrics.get("memo_touch_rate") or 0)
    if memo_r < 0.2 and int(metrics.get("harness_inputs_built") or 0) > 5:
        reasons.append((0.15 - memo_r, "low_memo_touch_rate", f"rate={memo_r:.2f}"))

    reasons.sort(key=lambda x: -x[0])
    return [
        {"rank": i + 1, "reason_code": c, "detail": d, "weight": round(w, 4)}
        for i, (w, c, d) in enumerate(reasons)
    ]


def transcripts_overlay_coarse(transcripts_overlay: dict[str, Any]) -> str:
    if not transcripts_overlay or transcripts_overlay.get("error") == "row_not_found":
        return "absent"
    a = str(transcripts_overlay.get("availability") or "")
    if a == "available":
        return "available"
    if a == "partial":
        return "partial"
    if "not_configured" in a.lower() or transcripts_overlay.get("error"):
        return "blocked"
    return "absent"


def overlay_status_line(overlay_summary: dict[str, Any]) -> dict[str, Any]:
    tr = overlay_summary.get("transcripts_overlay")
    tr_d = tr if isinstance(tr, dict) else {}
    reg = overlay_summary.get("source_registry_report")
    return {
        "transcripts_coarse": transcripts_overlay_coarse(tr_d),
        "transcripts_raw": tr_d.get("availability"),
        "registry_ok": bool(isinstance(reg, dict) and reg.get("ok")),
    }


def build_residual_triage_summary(
    client: Any, *, state_change_run_id: str, limit_entries: int = 200
) -> dict[str, Any]:
    run = dbrec.fetch_latest_outlier_casebook_run(
        client, state_change_run_id=state_change_run_id
    )
    if not run:
        return {
            "casebook_run_id": None,
            "bucket_counts": {},
            "dominant_bucket": None,
            "dominant_explanation": "No casebook run for this state_change_run_id.",
            "representative_examples": [],
            "unresolved_residual_items": [],
        }
    crid = str(run["id"])
    rows = dbrec.fetch_outlier_casebook_entries_for_run(
        client, casebook_run_id=crid, limit=limit_entries
    )
    bucket_counts: dict[str, int] = {}
    for r in rows:
        b = str(r.get("residual_triage_bucket") or "unresolved_residual")
        bucket_counts[b] = bucket_counts.get(b, 0) + 1
    dominant = max(bucket_counts, key=bucket_counts.get) if bucket_counts else None
    expl = (
        f"Most casebook rows map to `{dominant}` for this run (counts={bucket_counts})."
        if dominant
        else "No entries."
    )
    reps = []
    seen: set[str] = set()
    for r in rows:
        b = str(r.get("residual_triage_bucket") or "")
        if b == dominant and len(reps) < 5:
            k = str(r.get("candidate_id") or "")
            if k in seen:
                continue
            seen.add(k)
            reps.append(
                {
                    "candidate_id": k,
                    "ticker": r.get("ticker"),
                    "as_of_date": str(r.get("as_of_date") or ""),
                    "residual_triage_bucket": b,
                    "message_short_title": (r.get("message_short_title") or "")[:200],
                }
            )

    priority_buckets = (
        "unresolved_residual",
        "contradictory_public_signal",
        "data_missingness_dominated",
        "likely_exogenous_event",
    )
    unresolved_items: list[dict[str, Any]] = []
    for r in rows:
        b = str(r.get("residual_triage_bucket") or "")
        if b in priority_buckets and len(unresolved_items) < 40:
            unresolved_items.append(
                {
                    "candidate_id": str(r.get("candidate_id") or ""),
                    "ticker": r.get("ticker"),
                    "as_of_date": str(r.get("as_of_date") or ""),
                    "residual_bucket": b,
                    "why_unresolved": (r.get("uncertainty_summary") or "")[:500]
                    or "Heuristic casebook row; triage only.",
                    "suggested_premium_overlay": (r.get("premium_overlay_suggestion") or "")[:800],
                }
            )

    return {
        "casebook_run_id": crid,
        "bucket_counts": bucket_counts,
        "dominant_bucket": dominant,
        "dominant_explanation": expl,
        "representative_examples": reps,
        "unresolved_residual_items": unresolved_items,
    }


def compute_cycle_quality_bundle(
    client: Any,
    *,
    universe_name: str,
    state_change_run_id: str,
    cycle_ok: bool,
    scanner_failed: bool,
    stages: list[dict[str, Any]],
    overlay_summary: dict[str, Any],
) -> dict[str, Any]:
    metrics = collect_cycle_metrics(
        client, state_change_run_id=state_change_run_id, stages=stages
    )
    qclass = classify_cycle_quality(
        cycle_ok=cycle_ok, scanner_failed=scanner_failed, metrics=metrics
    )
    gaps = rank_gap_reasons(metrics)
    overlay_line = overlay_status_line(overlay_summary)
    triage = build_residual_triage_summary(client, state_change_run_id=state_change_run_id)
    unresolved = triage.get("unresolved_residual_items") or []

    row = {
        "state_change_run_id": state_change_run_id,
        "universe_name": universe_name,
        "cycle_finished_ok": bool(cycle_ok),
        "quality_class": qclass,
        "metrics_json": metrics,
        "gap_reasons_ranked": gaps,
        "overlay_status_json": overlay_line,
        "residual_triage_json": {k: v for k, v in triage.items() if k != "unresolved_residual_items"},
        "unresolved_residual_items": unresolved,
    }
    return {
        "row_for_insert": row,
        "quality_class": qclass,
        "metrics": metrics,
        "gap_reasons_ranked": gaps,
        "overlay_status_json": overlay_line,
        "residual_triage": {k: v for k, v in triage.items() if k != "unresolved_residual_items"},
        "unresolved_residual_items": unresolved,
    }


def format_operator_quality_section(
    *,
    quality_class: str,
    metrics: dict[str, Any],
    gap_reasons: list[dict[str, Any]],
    overlay_line: dict[str, Any],
    triage: dict[str, Any],
    explicit_unknowns: list[str],
) -> str:
    lines = [
        "## Run substance (Phase 13 quality gate)",
        "",
        f"- **Quality class**: `{quality_class}` (threshold-based; not a performance claim).",
        f"- **Candidates scanned**: {metrics.get('candidates_scanned')}",
        f"- **Insufficient-data fraction**: {float(metrics.get('insufficient_data_fraction') or 0):.2f}",
        f"- **Gating-high-missingness fraction**: {float(metrics.get('gating_high_missingness_fraction') or 0):.2f}",
        f"- **Watchlist selected**: {metrics.get('watchlist_selected')}",
        f"- **Casebook entries**: {metrics.get('casebook_entries_created')}",
        f"- **Memos touched / harness built**: {metrics.get('memos_touched')} / {metrics.get('harness_inputs_built')}",
        "",
        "### Premium overlay seam (observed, not used in scores)",
        "",
        f"- Transcripts (coarse): **{overlay_line.get('transcripts_coarse')}**"
        f" (raw availability: `{overlay_line.get('transcripts_raw')}`).",
        "- When transcripts are absent or blocked, that is **absence of optional evidence**, not a silent “weak” public score.",
        "",
        "### Residual triage (dominant bucket)",
        "",
        f"- **Dominant**: `{triage.get('dominant_bucket')}` — {triage.get('dominant_explanation', '')}",
        f"- **Bucket counts**: `{triage.get('bucket_counts')}`",
        "",
        "### Top gap reasons",
        "",
    ]
    for g in (gap_reasons or [])[:5]:
        lines.append(
            f"- {g.get('rank')}. `{g.get('reason_code')}` — {g.get('detail')} (weight {g.get('weight')})"
        )
    if explicit_unknowns:
        lines.extend(["", "### Explicit unknowns", ""])
        for u in explicit_unknowns:
            lines.append(f"- {u}")
    return "\n".join(lines)
