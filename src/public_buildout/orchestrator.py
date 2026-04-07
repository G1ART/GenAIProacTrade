"""Reason-aware bounded public substrate build-out."""

from __future__ import annotations

import logging
from typing import Any

from config import Settings
from db import records as dbrec
from db.client import get_supabase_client
from public_buildout.actions import build_action_queue_json
from public_buildout.constants import POLICY_VERSION, TRACKED_EXCLUSION_KEYS
from public_buildout.improvement import compute_buildout_improvement_summary
from public_depth.diagnostics import compute_substrate_coverage

logger = logging.getLogger(__name__)


def _select_targets(
    exclusion_dist: dict[str, int],
    *,
    attack_validation: bool,
    attack_state_change: bool,
    attack_forward_returns: bool,
) -> list[str]:
    """우세 제외 사유 중, 플래그로 허용된 것만 내림차순 건수 정렬."""
    candidates: list[tuple[str, int]] = []
    for r in TRACKED_EXCLUSION_KEYS:
        if int(exclusion_dist.get(r, 0)) <= 0:
            continue
        if r == "no_validation_panel_for_symbol" and not attack_validation:
            continue
        if r == "no_state_change_join" and not attack_state_change:
            continue
        if r == "missing_excess_return_1q" and not attack_forward_returns:
            continue
        candidates.append((r, int(exclusion_dist[r])))
    candidates.sort(key=lambda x: (-x[1], x[0]))
    return [c[0] for c in candidates]


def run_targeted_public_buildout(
    settings: Settings,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_symbols_factor: int = 50,
    validation_panel_limit: int = 2000,
    forward_panel_limit: int = 2000,
    state_change_limit: int = 400,
    attack_validation: bool = True,
    attack_state_change: bool = True,
    attack_forward_returns: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    client = get_supabase_client(settings)
    targeted = []  # filled after first coverage pass

    run_row = {
        "universe_name": universe_name,
        "policy_version": POLICY_VERSION,
        "status": "running",
        "targeted_exclusions_json": targeted,
        "attempted_actions_json": [],
        "summary_json": {
            "panel_limit": panel_limit,
            "max_symbols_factor": max_symbols_factor,
            "validation_panel_limit": validation_panel_limit,
            "forward_panel_limit": forward_panel_limit,
            "state_change_limit": state_change_limit,
            "attack_validation": attack_validation,
            "attack_state_change": attack_state_change,
            "attack_forward_returns": attack_forward_returns,
            "dry_run": dry_run,
        },
    }
    run_id = dbrec.insert_public_buildout_run(client, run_row)
    attempted: list[dict[str, Any]] = []

    try:
        sym_queues: dict[str, list[str]] = {}
        before_m, before_ex = compute_substrate_coverage(
            client,
            universe_name=universe_name,
            panel_limit=panel_limit,
            symbol_queues_out=sym_queues,
        )
        targeted = _select_targets(
            before_ex,
            attack_validation=attack_validation,
            attack_state_change=attack_state_change,
            attack_forward_returns=attack_forward_returns,
        )
        dbrec.update_public_buildout_run(
            client,
            run_id=run_id,
            patch={"targeted_exclusions_json": targeted},
        )

        if dry_run:
            summary = {
                **run_row["summary_json"],
                "operations": [],
                "dry_run": True,
                "targeted_exclusions": targeted,
            }
            dbrec.update_public_buildout_run(
                client,
                run_id=run_id,
                patch={
                    "status": "completed",
                    "attempted_actions_json": [],
                    "summary_json": summary,
                },
            )
            return {
                "ok": True,
                "dry_run": True,
                "public_buildout_run_id": run_id,
                "targeted_exclusions": targeted,
                "before_metrics": before_m,
                "before_exclusion": before_ex,
            }

        if "missing_excess_return_1q" in targeted:
            from market.forward_returns_run import run_forward_returns_build

            r = run_forward_returns_build(
                settings, limit_panels=forward_panel_limit
            )
            attempted.append({"op": "run_forward_returns_build", "result": r})

        if "no_validation_panel_for_symbol" in targeted:
            from factors.panel_build import run_factor_panels_for_cik

            as_of = dbrec.fetch_max_as_of_universe(client, universe_name=universe_name)
            syms = (
                dbrec.fetch_symbols_universe_as_of(
                    client, universe_name=universe_name, as_of_date=as_of
                )
                if as_of
                else []
            )
            cik_map = dbrec.fetch_cik_map_for_tickers(client, syms)
            want = set(sym_queues.get("no_validation_panel_for_symbol") or [])
            built = 0
            for sym in syms:
                if built >= max_symbols_factor:
                    break
                u = sym.upper().strip()
                if u not in want:
                    continue
                cik = cik_map.get(u)
                if not cik:
                    continue
                rr = run_factor_panels_for_cik(client, str(cik), ticker_hint=sym)
                attempted.append(
                    {"op": "run_factor_panels_for_cik", "symbol": sym, "result": rr}
                )
                built += 1

            from market.validation_panel_run import run_validation_panel_build

            rv = run_validation_panel_build(
                settings, limit_panels=validation_panel_limit
            )
            attempted.append({"op": "run_validation_panel_build", "result": rv})

        if "no_state_change_join" in targeted:
            from state_change.runner import run_state_change

            rs = run_state_change(
                client,
                universe_name=universe_name,
                limit=max(1, state_change_limit),
                dry_run=False,
            )
            attempted.append({"op": "run_state_change", "result": rs})

        after_sym_queues: dict[str, list[str]] = {}
        after_m, after_ex = compute_substrate_coverage(
            client,
            universe_name=universe_name,
            panel_limit=panel_limit,
            symbol_queues_out=after_sym_queues,
        )
        imp = compute_buildout_improvement_summary(
            before_m, after_m, before_ex, after_ex
        )
        imp_id = dbrec.insert_public_buildout_improvement_report(
            client,
            {
                "public_buildout_run_id": run_id,
                "before_metrics_json": before_m,
                "after_metrics_json": after_m,
                "exclusion_before_json": before_ex,
                "exclusion_after_json": after_ex,
                "improvement_summary_json": imp,
            },
        )

        summary = {
            **run_row["summary_json"],
            "operations": attempted,
            "targeted_exclusions": targeted,
            "improvement_report_id": imp_id,
        }
        dbrec.update_public_buildout_run(
            client,
            run_id=run_id,
            patch={
                "status": "completed",
                "attempted_actions_json": attempted,
                "summary_json": summary,
            },
        )
        return {
            "ok": True,
            "public_buildout_run_id": run_id,
            "improvement_report_id": imp_id,
            "targeted_exclusions": targeted,
            "before_metrics": before_m,
            "after_metrics": after_m,
            "before_exclusion": before_ex,
            "after_exclusion": after_ex,
            "improvement": imp,
        }
    except Exception as ex:  # noqa: BLE001
        logger.exception("targeted public buildout")
        dbrec.update_public_buildout_run(
            client,
            run_id=run_id,
            patch={
                "status": "failed",
                "error_message": str(ex)[:4000],
                "attempted_actions_json": attempted,
            },
        )
        return {"ok": False, "public_buildout_run_id": run_id, "error": str(ex)}


def _exclusion_dict_from_json(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def report_buildout_improvement_from_coverage_ids(
    client: Any, *, before_report_id: str, after_report_id: str
) -> dict[str, Any]:
    br = dbrec.fetch_public_depth_coverage_report(
        client, report_id=before_report_id
    )
    ar = dbrec.fetch_public_depth_coverage_report(
        client, report_id=after_report_id
    )
    if not br or not ar:
        return {
            "ok": False,
            "error": "coverage_report_not_found",
            "before_report_id": before_report_id,
            "after_report_id": after_report_id,
            "before_found": bool(br),
            "after_found": bool(ar),
        }
    bm = br.get("metrics_json") if isinstance(br.get("metrics_json"), dict) else {}
    am = ar.get("metrics_json") if isinstance(ar.get("metrics_json"), dict) else {}
    bex = _exclusion_dict_from_json(br.get("exclusion_distribution_json"))
    aex = _exclusion_dict_from_json(ar.get("exclusion_distribution_json"))
    imp = compute_buildout_improvement_summary(bm, am, bex, aex)
    return {
        "ok": True,
        "before_report_id": before_report_id,
        "after_report_id": after_report_id,
        "improvement": imp,
    }


def build_public_exclusion_actions_payload(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    sym_queues: dict[str, list[str]] = {}
    metrics, ex_dist = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        symbol_queues_out=sym_queues,
    )
    queue = build_action_queue_json(ex_dist, sym_queues)
    return {
        "ok": True,
        "universe_name": universe_name,
        "policy_version": POLICY_VERSION,
        "metrics": metrics,
        "exclusion_distribution": ex_dist,
        "action_queue": queue,
    }
