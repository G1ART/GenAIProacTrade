"""동기화 행에 대한 state_change 조인 이음새 상세 감사 (Phase 35-B)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase35.join_displacement import report_forward_validation_join_displacement


def report_state_change_join_gaps_after_phase34(
    client: Any,
    *,
    universe_name: str,
    phase34_bundle: dict[str, Any] | None = None,
    phase34_bundle_path: str | None = None,
    state_change_scores_limit: int = 50_000,
) -> dict[str, Any]:
    base = report_forward_validation_join_displacement(
        client,
        universe_name=universe_name,
        phase34_bundle=phase34_bundle,
        phase34_bundle_path=phase34_bundle_path,
        state_change_scores_limit=state_change_scores_limit,
    )
    enriched: list[dict[str, Any]] = []
    bucket_tally: dict[str, int] = {}

    for r in base.get("rows") or []:
        jb = r.get("join_seam_bucket") or "unspecified"
        jbs = str(jb)
        bucket_tally[jbs] = bucket_tally.get(jbs, 0) + 1
        ref = r.get("reference_from_phase34") or {}
        enriched.append(
            {
                **r,
                "audit": {
                    "cik": ref.get("cik"),
                    "accession_no": ref.get("accession_no"),
                    "factor_version": ref.get("factor_version"),
                    "signal_available_date": ref.get("signal_available_date"),
                    "symbol": ref.get("symbol"),
                    "join_seam_bucket": jbs,
                    "first_state_change_as_of_in_run": r.get(
                        "first_state_change_as_of_in_run"
                    ),
                    "picked_state_change_as_of": r.get("picked_state_change_as_of"),
                },
            }
        )

    return {
        "ok": True,
        "universe_name": universe_name,
        "state_change_run_id": base.get("state_change_run_id"),
        "synchronized_row_count": base.get("synchronized_row_count_from_phase34_bundle"),
        "join_seam_bucket_counts": bucket_tally,
        "rows": enriched,
        "displacement_summary": {
            "hypothesis": base.get("hypothesis_phase34_excess_to_no_state_change_join"),
            "displacement_counts": base.get("displacement_counts"),
        },
    }


def export_state_change_join_gaps_after_phase34(
    rep: dict[str, Any],
    *,
    out_json: str,
) -> str:
    p = Path(out_json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())
