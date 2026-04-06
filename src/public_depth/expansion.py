"""Bounded public-depth expansion orchestration + before/after evidence rows."""

from __future__ import annotations

import logging
from typing import Any

from config import Settings
from db import records as dbrec
from db.client import get_supabase_client
from public_depth.constants import POLICY_VERSION
from public_depth.diagnostics import compute_substrate_coverage
from public_depth.uplift import compute_uplift_metrics

logger = logging.getLogger(__name__)


def run_public_depth_expansion(
    settings: Settings,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    run_validation_panels: bool = False,
    run_forward_returns: bool = False,
    validation_panel_limit: int = 2000,
    forward_panel_limit: int = 2000,
    max_universe_factor_builds: int = 0,
) -> dict[str, Any]:
    """
    before → (선택) 전역 패널/선행수익/유니버스 CIK factor 빌드 → after → uplift 적재.
    factor/validation 빌드는 기존 전역 상한 경로를 재사용(유니버스 전용 빌드는 별도 단계).
    """
    client = get_supabase_client(settings)
    run_row = {
        "universe_name": universe_name,
        "policy_version": POLICY_VERSION,
        "status": "running",
        "expansion_summary_json": {
            "run_validation_panels": run_validation_panels,
            "run_forward_returns": run_forward_returns,
            "validation_panel_limit": validation_panel_limit,
            "forward_panel_limit": forward_panel_limit,
            "max_universe_factor_builds": max_universe_factor_builds,
            "panel_limit": panel_limit,
        },
    }
    run_id = dbrec.insert_public_depth_run(client, run_row)
    summary_ops: list[dict[str, Any]] = []

    try:
        before_m, before_ex = compute_substrate_coverage(
            client, universe_name=universe_name, panel_limit=panel_limit
        )
        before_report_id = dbrec.insert_public_depth_coverage_report(
            client,
            {
                "public_depth_run_id": run_id,
                "universe_name": universe_name,
                "snapshot_label": "before",
                "metrics_json": before_m,
                "exclusion_distribution_json": before_ex,
            },
        )

        if run_validation_panels:
            from market.validation_panel_run import run_validation_panel_build

            r = run_validation_panel_build(
                settings, limit_panels=validation_panel_limit
            )
            summary_ops.append({"op": "run_validation_panel_build", "result": r})

        if run_forward_returns:
            from market.forward_returns_run import run_forward_returns_build

            r = run_forward_returns_build(
                settings, limit_panels=forward_panel_limit
            )
            summary_ops.append({"op": "run_forward_returns_build", "result": r})

        if max_universe_factor_builds > 0:
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
            built = 0
            for sym in syms:
                if built >= max_universe_factor_builds:
                    break
                cik = cik_map.get(sym.upper().strip())
                if not cik:
                    continue
                rr = run_factor_panels_for_cik(client, str(cik), ticker_hint=sym)
                summary_ops.append(
                    {"op": "run_factor_panels_for_cik", "symbol": sym, "result": rr}
                )
                built += 1

        after_m, after_ex = compute_substrate_coverage(
            client, universe_name=universe_name, panel_limit=panel_limit
        )
        after_report_id = dbrec.insert_public_depth_coverage_report(
            client,
            {
                "public_depth_run_id": run_id,
                "universe_name": universe_name,
                "snapshot_label": "after",
                "metrics_json": after_m,
                "exclusion_distribution_json": after_ex,
            },
        )

        uplift_payload = compute_uplift_metrics(before_m, after_m)
        uplift_id = dbrec.insert_public_depth_uplift_report(
            client,
            {
                "before_report_id": before_report_id,
                "after_report_id": after_report_id,
                "uplift_metrics_json": uplift_payload,
            },
        )

        expansion_summary = {
            **run_row["expansion_summary_json"],
            "operations": summary_ops,
            "before_report_id": before_report_id,
            "after_report_id": after_report_id,
            "uplift_report_id": uplift_id,
        }
        dbrec.update_public_depth_run(
            client,
            run_id=run_id,
            patch={
                "status": "completed",
                "expansion_summary_json": expansion_summary,
                "error_message": None,
            },
        )
        return {
            "ok": True,
            "public_depth_run_id": run_id,
            "before_report_id": before_report_id,
            "after_report_id": after_report_id,
            "uplift_report_id": uplift_id,
            "uplift": uplift_payload,
            "before_metrics": before_m,
            "after_metrics": after_m,
        }
    except Exception as ex:  # noqa: BLE001
        logger.exception("public depth expansion")
        dbrec.update_public_depth_run(
            client,
            run_id=run_id,
            patch={
                "status": "failed",
                "error_message": str(ex)[:4000],
            },
        )
        return {"ok": False, "public_depth_run_id": run_id, "error": str(ex)}
