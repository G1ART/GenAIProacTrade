"""Phase 35-C: B에서 결정적으로 수리 가능한 경우에 한해 상한 state_change 재실행."""

from __future__ import annotations

from typing import Any

from db.client import get_supabase_client
from phase33.metrics import collect_phase33_substrate_snapshot
from phase35.join_displacement import report_forward_validation_join_displacement
from phase35.state_change_join_gaps import report_state_change_join_gaps_after_phase34
from state_change.runner import run_state_change

REPAIRABLE_JOIN_BUCKETS = frozenset({"state_change_not_built_for_row"})


def run_state_change_join_refresh_after_phase34(
    settings: Any,
    *,
    universe_name: str,
    phase34_bundle: dict[str, Any] | None = None,
    phase34_bundle_path: str | None = None,
    factor_version: str = "v1",
    max_state_change_issuers: int = 2500,
) -> dict[str, Any]:
    client = get_supabase_client(settings)

    gaps_before = report_state_change_join_gaps_after_phase34(
        client,
        universe_name=universe_name,
        phase34_bundle=phase34_bundle,
        phase34_bundle_path=phase34_bundle_path,
    )
    disp_before = report_forward_validation_join_displacement(
        client,
        universe_name=universe_name,
        phase34_bundle=phase34_bundle,
        phase34_bundle_path=phase34_bundle_path,
    )

    repair_targets = [
        r
        for r in gaps_before.get("rows") or []
        if str(r.get("join_seam_bucket") or "") in REPAIRABLE_JOIN_BUCKETS
    ]
    ciks = sorted(
        {
            str((r.get("reference_from_phase34") or {}).get("cik") or "")
            for r in repair_targets
        }
        - {""}
    )

    snap_before = collect_phase33_substrate_snapshot(
        client, universe_name=universe_name, panel_limit=8000
    )
    j0 = int(snap_before.get("joined_recipe_substrate_row_count") or 0)
    nsc0 = int(
        (snap_before.get("exclusion_distribution") or {}).get("no_state_change_join")
        or 0
    )

    if not repair_targets:
        snap_after = snap_before
        return {
            "ok": True,
            "repair": "state_change_join_refresh_after_phase34",
            "skipped": True,
            "reason": "no_rows_in_repairable_join_buckets",
            "repairable_bucket_allowlist": sorted(REPAIRABLE_JOIN_BUCKETS),
            "state_change_run": {"skipped": True},
            "joined_recipe_unlocked_now_count": 0,
            "no_state_change_join_cleared_count": 0,
            "repaired_rows_count_on_synchronized_set": 0,
            "substrate_before": snap_before,
            "substrate_after": snap_after,
            "displacement_before": disp_before,
        }

    limit = min(
        max_state_change_issuers,
        max(200, 100 + 80 * len(ciks)),
    )
    sc_out = run_state_change(
        client,
        universe_name=universe_name,
        factor_version=factor_version,
        limit=limit,
        dry_run=False,
    )

    snap_after = collect_phase33_substrate_snapshot(
        client, universe_name=universe_name, panel_limit=8000
    )
    j1 = int(snap_after.get("joined_recipe_substrate_row_count") or 0)
    nsc1 = int(
        (snap_after.get("exclusion_distribution") or {}).get("no_state_change_join")
        or 0
    )

    disp_after = report_forward_validation_join_displacement(
        client,
        universe_name=universe_name,
        phase34_bundle=phase34_bundle,
        phase34_bundle_path=phase34_bundle_path,
    )
    inc0 = int(
        (disp_before.get("displacement_counts") or {}).get(
            "included_in_joined_recipe_substrate", 0
        )
    )
    inc1 = int(
        (disp_after.get("displacement_counts") or {}).get(
            "included_in_joined_recipe_substrate", 0
        )
    )

    return {
        "ok": True,
        "repair": "state_change_join_refresh_after_phase34",
        "repair_target_row_count": len(repair_targets),
        "distinct_ciks": ciks,
        "state_change_issuer_limit_used": limit,
        "state_change_run": sc_out,
        "joined_recipe_unlocked_now_count": j1 - j0,
        "no_state_change_join_cleared_count": max(0, nsc0 - nsc1),
        "repaired_rows_count_on_synchronized_set": max(0, inc1 - inc0),
        "substrate_before": snap_before,
        "substrate_after": snap_after,
        "displacement_before": disp_before,
        "displacement_after": disp_after,
    }
