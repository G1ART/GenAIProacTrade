"""Aggregate branch distributions across compatible iteration series (Phase 24)."""

from __future__ import annotations

import json
from typing import Any

from db import records as dbrec
from public_buildout.revalidation import build_revalidation_trigger
from public_repair_iteration.constants import ITERATION_POLICY_VERSION
from public_repair_iteration.depth_iteration import export_public_depth_series_brief
from public_repair_iteration.service import collect_plateau_snapshots_for_series


def _merge_count_maps(dst: dict[str, int], src: dict[str, Any]) -> None:
    for k, v in (src or {}).items():
        key = str(k)
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        dst[key] = dst.get(key, 0) + n


def aggregate_census_from_series_rows(
    triples: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
    *,
    program_id: str,
    universe_name: str,
    active_series_id: str | None,
    exclusions: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Pure aggregation for tests — each triple is (series_row, brief_export_payload, coll_payload).
    `brief_export_payload` is the full return of export_public_depth_series_brief or `{"brief": {...}}`.
    """
    agg_branch: dict[str, int] = {}
    agg_signal: dict[str, int] = {}
    agg_cls: dict[str, int] = {}
    sum_included = 0
    sum_infra_excluded = 0
    sum_other_excluded = 0
    dominant_keys_merged: list[str] = []
    seen_depth: set[str] = set()
    deduped_classification_contrib: dict[str, int] = {}

    for srow, brief_pack, coll in triples:
        brief = brief_pack.get("brief") or {}
        if not isinstance(brief, dict):
            brief = {}
        _merge_count_maps(agg_branch, brief.get("persisted_escalation_branch_counts") or {})

        sig = str(brief.get("public_depth_operator_signal") or "")
        if sig:
            agg_signal[sig] = agg_signal.get(sig, 0) + 1

        _merge_count_maps(agg_cls, brief.get("improvement_classification_counts") or {})

        if coll.get("ok"):
            sum_included += int(coll.get("included_run_count") or 0)
            sum_infra_excluded += int(coll.get("excluded_infra_failure_count") or 0)
            sum_other_excluded += int(coll.get("excluded_other_count") or 0)

        dom = brief.get("dominant_exclusions_latest_after") or []
        if isinstance(dom, list) and dom:
            dominant_keys_merged.extend(str(x) for x in dom[:8])

        cls_order = brief.get("improvement_classifications_in_order") or []
        depth_ids_order = brief.get("public_depth_run_ids_for_classifications") or []
        if isinstance(cls_order, list):
            for i, c in enumerate(cls_order):
                c = str(c or "")
                if not c:
                    continue
                if isinstance(depth_ids_order, list) and i < len(depth_ids_order):
                    key = f"depth:{depth_ids_order[i]}"
                else:
                    key = f"series:{srow.get('id')}:idx:{i}"
                if key in seen_depth:
                    continue
                seen_depth.add(key)
                deduped_classification_contrib[c] = deduped_classification_contrib.get(c, 0) + 1

    active_snap: dict[str, Any] = {}
    for srow, brief_pack, _coll in triples:
        if str(srow.get("id")) == str(active_series_id or ""):
            b = brief_pack.get("brief") or {}
            active_snap = {
                "series_id": srow.get("id"),
                "status": srow.get("status"),
                "escalation_recommendation_current": b.get("escalation_recommendation_current"),
                "public_depth_operator_signal": b.get("public_depth_operator_signal"),
                "improvement_classification_counts": b.get("improvement_classification_counts"),
                "included_run_count": b.get("included_run_count"),
            }
            break

    return {
        "program_id": program_id,
        "universe_name": universe_name,
        "series_included_count": len(triples),
        "exclusions": exclusions,
        "aggregated_persisted_escalation_branch_counts": agg_branch,
        "aggregated_depth_operator_signal_counts": agg_signal,
        "aggregated_improvement_classification_counts": agg_cls,
        "deduped_improvement_classification_counts": deduped_classification_contrib,
        "sum_included_run_count": sum_included,
        "sum_excluded_infra_failure_count": sum_infra_excluded,
        "sum_excluded_other_count": sum_other_excluded,
        "latest_dominant_exclusion_keys_merged": dominant_keys_merged[:24],
        "active_series_snapshot": active_snap,
    }


def build_public_first_branch_census(
    client: Any,
    *,
    program_id: str,
    universe_name: str,
    series_scan_limit: int = 30,
    include_closed_series: bool = False,
) -> dict[str, Any]:
    """
    Scan recent iteration series for (program, universe); compatible policy only.
    Aggregates brief fields with infra quarantine defaults; lists all exclusions.
    """
    exclusions: list[dict[str, Any]] = []
    uni = str(universe_name or "").strip()
    rows_all = dbrec.list_public_repair_iteration_series_for_program(
        client, program_id=program_id, limit=max(series_scan_limit, 5)
    )

    included_rows: list[dict[str, Any]] = []
    for s in rows_all:
        sid = str(s.get("id") or "")
        st = str(s.get("status") or "")
        su = str(s.get("universe_name") or "")
        pol = str(s.get("policy_version") or "")

        if su != uni:
            exclusions.append(
                {
                    "series_id": sid,
                    "reason": "universe_mismatch",
                    "series_universe": su,
                    "requested_universe": uni,
                }
            )
            continue
        if pol != ITERATION_POLICY_VERSION:
            exclusions.append(
                {
                    "series_id": sid,
                    "reason": "incompatible_policy_version",
                    "series_policy_version": pol,
                    "expected_policy_version": ITERATION_POLICY_VERSION,
                }
            )
            continue
        if st == "paused":
            exclusions.append({"series_id": sid, "reason": "series_paused_excluded"})
            continue
        if st == "closed" and not include_closed_series:
            exclusions.append(
                {
                    "series_id": sid,
                    "reason": "series_closed_excluded",
                    "hint": "pass include_closed_series to include",
                }
            )
            continue
        included_rows.append(dict(s))

    actives = [r for r in included_rows if str(r.get("status") or "") == "active"]
    active_series_id: str | None = None
    if len(actives) == 1:
        active_series_id = str(actives[0]["id"])
    elif len(actives) > 1:
        exclusions.append(
            {
                "reason": "ambiguous_multiple_active_series_for_program_universe",
                "series_ids": [str(x["id"]) for x in actives],
            }
        )

    seen_r: set[str] = set()
    seen_d: set[str] = set()
    dedup_skipped: list[dict[str, Any]] = []
    triples: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []

    for srow in included_rows:
        sid = str(srow["id"])
        eb = export_public_depth_series_brief(client, series_id=sid)
        if not eb.get("ok"):
            exclusions.append(
                {"series_id": sid, "reason": "brief_export_failed", "detail": eb}
            )
            continue

        brief = dict(eb.get("brief") or {})
        members = dbrec.list_public_repair_iteration_members_for_series(
            client, series_id=sid
        )
        cls_order: list[str] = []
        depth_ids_order: list[str] = []
        for m in members:
            mk = str(m.get("member_kind") or "repair_campaign")
            if mk != "public_depth" and not m.get("public_depth_run_id"):
                continue
            dr = str(m.get("public_depth_run_id") or "")
            if dr:
                if dr in seen_d:
                    dedup_skipped.append(
                        {
                            "series_id": sid,
                            "public_depth_run_id": dr,
                            "reason": "duplicate_depth_run_id_across_census",
                        }
                    )
                    continue
                seen_d.add(dr)
            snap = dict(m.get("trend_snapshot_json") or {})
            led = snap.get("phase22_ledger")
            if isinstance(led, dict):
                cls = str(led.get("improvement_classification") or "")
                if cls:
                    cls_order.append(cls)
                    depth_ids_order.append(dr or f"series:{sid}:seq:{m.get('sequence_number')}")

        brief["improvement_classifications_in_order"] = cls_order
        brief["public_depth_run_ids_for_classifications"] = depth_ids_order

        for m in members:
            mk = str(m.get("member_kind") or "repair_campaign")
            if mk == "public_depth" or m.get("public_depth_run_id"):
                continue
            rid = str(m.get("repair_campaign_run_id") or "")
            if not rid:
                continue
            if rid in seen_r:
                dedup_skipped.append(
                    {
                        "series_id": sid,
                        "repair_campaign_run_id": rid,
                        "reason": "duplicate_repair_run_id_across_census",
                    }
                )
            else:
                seen_r.add(rid)

        coll = collect_plateau_snapshots_for_series(
            client, series_id=sid, exclude_infra_default=True
        )
        triples.append((srow, {"brief": brief, "ok": True}, coll if isinstance(coll, dict) else {"ok": False}))

    if dedup_skipped:
        exclusions.append(
            {
                "reason": "deduplication_skipped_duplicate_artifacts",
                "items": dedup_skipped[:50],
                "n_total": len(dedup_skipped),
            }
        )

    agg = aggregate_census_from_series_rows(
        triples,
        program_id=program_id,
        universe_name=uni,
        active_series_id=active_series_id,
        exclusions=exclusions,
    )

    trig = build_revalidation_trigger(client, program_id=program_id)
    agg["latest_rerun_readiness"] = trig
    agg["series_ids_included"] = [str(t[0]["id"]) for t in triples]
    agg["ok"] = True
    return agg


def census_to_markdown(census: dict[str, Any]) -> str:
    """Compact founder-readable view."""
    lines = [
        "# Public-first branch census (Phase 24)",
        "",
        f"- **Program**: `{census.get('program_id')}`",
        f"- **Universe**: `{census.get('universe_name')}`",
        f"- **Series included**: {census.get('series_included_count', 0)}",
        f"- **Included runs (sum)**: {census.get('sum_included_run_count')}",
        f"- **Excluded infra (sum)**: {census.get('sum_excluded_infra_failure_count')}",
        "",
        "## Aggregated escalation branches",
        "",
        "```json",
        json.dumps(census.get("aggregated_persisted_escalation_branch_counts") or {}, indent=2),
        "```",
        "",
        "## Depth operator signals (count per series)",
        "",
        "```json",
        json.dumps(census.get("aggregated_depth_operator_signal_counts") or {}, indent=2),
        "```",
        "",
        "## Deduped improvement classifications",
        "",
        "```json",
        json.dumps(census.get("deduped_improvement_classification_counts") or {}, indent=2),
        "```",
        "",
        "## Exclusions",
        "",
        "```json",
        json.dumps(census.get("exclusions") or [], indent=2, ensure_ascii=False, default=str)[:8000],
        "```",
        "",
    ]
    return "\n".join(lines)
