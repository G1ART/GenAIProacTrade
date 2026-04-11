"""Phase 34 동기화 23행 → joined recipe 기판 배치 감사."""

from __future__ import annotations

import bisect
import json
from pathlib import Path
from typing import Any

from db import records as dbrec
from public_depth.constants import DEFAULT_STATE_CHANGE_SCORES_LIMIT
from research_validation.constants import EXCESS_FIELD
from research_validation.metrics import (
    norm_cik,
    norm_signal_date,
    safe_float,
    state_change_rows_by_cik_sorted,
)

from phase35.phase34_bundle_io import (
    load_phase34_bundle,
    synchronized_rows_from_phase34,
)


def _state_change_pick_with_reason(
    by_cik: dict[str, list[tuple[str, dict[str, Any]]]],
    *,
    cik: str,
    signal_date: str,
) -> tuple[dict[str, Any] | None, str]:
    ck = norm_cik(cik)
    pairs = by_cik.get(ck)
    if not pairs:
        return None, "state_change_not_built_for_row"
    dates = [p[0] for p in pairs]
    idx = bisect.bisect_right(dates, signal_date) - 1
    if idx < 0:
        return None, "state_change_built_but_join_key_mismatch"
    return pairs[idx][1], "picked"


def classify_displacement_for_validation_panel(
    panel: dict[str, Any] | None,
    *,
    by_cik: dict[str, list[tuple[str, dict[str, Any]]]],
) -> dict[str, Any]:
    if not panel:
        return {
            "displacement_bucket": "excluded_other_reason",
            "detail": "validation_panel_row_missing_in_db",
            "join_seam_bucket": None,
        }
    sym = str(panel.get("symbol") or "").upper().strip()
    excess = safe_float(panel.get(EXCESS_FIELD))
    if excess is None:
        return {
            "displacement_bucket": "excluded_other_reason",
            "detail": "missing_excess_return_1q_on_panel",
            "join_seam_bucket": None,
            "symbol": sym,
        }
    cik = norm_cik(panel.get("cik"))
    sig = norm_signal_date(panel.get("signal_available_date"))
    if not cik or not sig:
        return {
            "displacement_bucket": "excluded_other_reason",
            "detail": "missing_cik_or_signal_date",
            "join_seam_bucket": None,
            "symbol": sym,
        }
    sc_row, reason = _state_change_pick_with_reason(
        by_cik, cik=cik, signal_date=sig
    )
    if sc_row is None:
        return {
            "displacement_bucket": "excluded_no_state_change_join",
            "detail": reason,
            "join_seam_bucket": reason,
            "symbol": sym,
            "cik": cik,
            "signal_available_date": sig,
            "first_state_change_as_of_in_run": (
                by_cik.get(cik, [])[0][0] if by_cik.get(cik) else None
            ),
        }
    sc_score = safe_float(sc_row.get("state_change_score_v1"))
    if sc_score is None:
        return {
            "displacement_bucket": "excluded_other_reason",
            "detail": "missing_state_change_score_after_pick",
            "join_seam_bucket": "state_change_built_but_as_of_or_pit_mismatch",
            "symbol": sym,
            "cik": cik,
            "signal_available_date": sig,
            "picked_state_change_as_of": str(sc_row.get("as_of_date") or "")[:10],
        }
    return {
        "displacement_bucket": "included_in_joined_recipe_substrate",
        "detail": "joined",
        "join_seam_bucket": "joined_now",
        "symbol": sym,
        "cik": cik,
        "signal_available_date": sig,
        "picked_state_change_as_of": str(sc_row.get("as_of_date") or "")[:10],
        "state_change_score_v1": sc_score,
    }


def report_forward_validation_join_displacement(
    client: Any,
    *,
    universe_name: str,
    phase34_bundle: dict[str, Any] | None = None,
    phase34_bundle_path: str | None = None,
    state_change_scores_limit: int = DEFAULT_STATE_CHANGE_SCORES_LIMIT,
) -> dict[str, Any]:
    if phase34_bundle is None:
        if not phase34_bundle_path:
            raise ValueError("phase34_bundle or phase34_bundle_path required")
        phase34_bundle = load_phase34_bundle(phase34_bundle_path)

    sync_rows = synchronized_rows_from_phase34(phase34_bundle)
    state_run_id = dbrec.fetch_latest_state_change_run_id(
        client, universe_name=universe_name
    )
    scores: list[dict[str, Any]] = []
    if state_run_id:
        scores = dbrec.fetch_state_change_scores_for_run(
            client, run_id=state_run_id, limit=state_change_scores_limit
        )
    by_cik = state_change_rows_by_cik_sorted(scores)

    out_rows: list[dict[str, Any]] = []
    disp_counts: dict[str, int] = {}
    join_counts: dict[str, int] = {}

    for ref in sync_rows:
        cik = str(ref.get("cik") or "")
        acc = str(ref.get("accession_no") or "")
        fv = str(ref.get("factor_version") or "")
        panel = dbrec.fetch_factor_market_validation_panel_one(
            client, cik=cik, accession_no=acc, factor_version=fv
        )
        cls = classify_displacement_for_validation_panel(panel, by_cik=by_cik)
        bucket = str(cls.get("displacement_bucket") or "")
        disp_counts[bucket] = disp_counts.get(bucket, 0) + 1
        jb = cls.get("join_seam_bucket")
        if jb:
            jbs = str(jb)
            join_counts[jbs] = join_counts.get(jbs, 0) + 1
        out_rows.append(
            {
                "reference_from_phase34": {
                    "symbol": ref.get("symbol"),
                    "cik": cik,
                    "accession_no": acc,
                    "factor_version": fv,
                    "signal_available_date": ref.get("signal_available_date"),
                },
                **cls,
            }
        )

    n = len(sync_rows)
    in_joined = disp_counts.get("included_in_joined_recipe_substrate", 0)
    no_sc = disp_counts.get("excluded_no_state_change_join", 0)
    other = disp_counts.get("excluded_other_reason", 0)

    hypothesis = (
        "23 rows removed from missing_excess_return_1q largely reappear as "
        "no_state_change_join when excess is present"
    )
    hypothesis_supported = n > 0 and no_sc >= max(1, int(0.5 * n))

    return {
        "ok": True,
        "universe_name": universe_name,
        "state_change_run_id": state_run_id,
        "state_change_scores_loaded": len(scores),
        "synchronized_row_count_from_phase34_bundle": n,
        "displacement_counts": disp_counts,
        "join_seam_counts_on_synchronized_set": join_counts,
        "symbol_level": {
            "included_distinct_symbols": sorted(
                {
                    str(r.get("symbol") or "")
                    for r in out_rows
                    if r.get("displacement_bucket")
                    == "included_in_joined_recipe_substrate"
                    and r.get("symbol")
                }
            ),
            "excluded_no_sc_distinct_symbols": sorted(
                {
                    str(r.get("symbol") or "")
                    for r in out_rows
                    if r.get("displacement_bucket") == "excluded_no_state_change_join"
                    and r.get("symbol")
                }
            ),
        },
        "hypothesis_phase34_excess_to_no_state_change_join": {
            "statement": hypothesis,
            "supported_by_counts": hypothesis_supported,
            "included_in_joined_recipe_substrate": in_joined,
            "excluded_no_state_change_join": no_sc,
            "excluded_other_reason": other,
        },
        "rows": out_rows,
    }


def export_forward_validation_join_displacement(
    rep: dict[str, Any],
    *,
    out_json: str,
) -> str:
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())
