"""DB orchestration: build outlier casebook for a state_change run."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from casebook.outlier_builder import DETECTION_LOGIC_VERSION, detect_outliers_for_candidate
from db import records as dbrec
from sources.provenance import build_overlay_awareness_snapshot


def run_outlier_casebook_build(
    client: Any,
    *,
    state_change_run_id: str,
    universe_name: str,
    candidate_limit: int = 600,
) -> dict[str, Any]:
    run = dbrec.fetch_state_change_run(client, run_id=state_change_run_id)
    if not run:
        return {"error": "state_change_run_not_found", "run_id": state_change_run_id}

    crid = dbrec.insert_outlier_casebook_run(
        client,
        state_change_run_id=state_change_run_id,
        universe_name=universe_name,
        detection_logic_version=DETECTION_LOGIC_VERSION,
        policy_json={"candidate_limit": candidate_limit},
    )

    candidates = dbrec.fetch_state_change_candidates_for_run(
        client, run_id=state_change_run_id, limit=candidate_limit
    )
    overlay_snap = build_overlay_awareness_snapshot(client)
    total_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for cand in candidates:
        cid = str(cand.get("id") or "")
        cik = str(cand.get("cik") or "")
        as_of = str(cand.get("as_of_date") or "")
        iid = cand.get("issuer_id")
        try:
            score = dbrec.fetch_state_change_score_for_cik_date(
                client,
                run_id=state_change_run_id,
                cik=cik,
                as_of_date=as_of,
            )
            comps = dbrec.fetch_state_change_components_for_cik_date(
                client,
                run_id=state_change_run_id,
                cik=cik,
                as_of_date=as_of,
            )
            vpan = dbrec.fetch_validation_panel_best_before(
                client, cik=cik, as_of_date=as_of
            )
            ticker = str(cand.get("ticker") or "").strip().upper() or None
            fwd = None
            if ticker:
                fwd = dbrec.fetch_forward_return_for_signal(
                    client,
                    symbol=ticker,
                    signal_date=as_of,
                    horizon_type="next_month",
                )
            memo = dbrec.fetch_latest_memo_for_candidate(client, candidate_id=cid)
            harness = dbrec.fetch_ai_harness_input_for_candidate(
                client,
                candidate_id=cid,
                contract_version="ai_harness_input_v1",
            )
            company_name = dbrec.fetch_issuer_company_name(client, issuer_id=iid)
            rows = detect_outliers_for_candidate(
                candidate=cand,
                score=score,
                validation_panel=vpan,
                forward_row=fwd,
                memo=memo,
                harness_row=harness,
                components=comps,
                company_name=company_name or ticker or cik,
            )
            for row in rows:
                row["casebook_run_id"] = crid
                row["updated_at"] = datetime.now(timezone.utc).isoformat()
                row["overlay_awareness_json"] = overlay_snap
                total_rows.append(row)
        except Exception as ex:  # noqa: BLE001
            errors.append({"candidate_id": cid, "error": str(ex)})

    dbrec.insert_outlier_casebook_entries_batch(client, total_rows)
    dbrec.finalize_outlier_casebook_run(
        client, casebook_run_id=crid, entries_created=len(total_rows)
    )
    return {
        "casebook_run_id": crid,
        "entries_created": len(total_rows),
        "candidates_scanned": len(candidates),
        "errors": errors,
    }
