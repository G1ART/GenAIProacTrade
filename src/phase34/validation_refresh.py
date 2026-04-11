"""forward NQ excess는 있는데 validation excess만 null인 행에 한해 패널 재빌드."""

from __future__ import annotations

from typing import Any

from db import records as dbrec
from market.validation_panel_run import run_validation_panel_build_from_rows
from phase33.metric_truth_audit import report_forward_metric_truth_audit
from phase33.phase32_bundle_io import load_phase32_bundle
from phase34.propagation_audit import report_forward_validation_propagation_gaps
from research_validation.constants import EXCESS_FIELD
from research_validation.metrics import norm_cik, safe_float


def _factor_key_from_gap_row(r: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(r.get("cik") or ""),
        str(r.get("accession_no") or ""),
        str(r.get("factor_version") or ""),
    )


def run_validation_refresh_after_forward_propagation(
    settings: Any,
    client: Any,
    *,
    universe_name: str,
    phase32_bundle: dict[str, Any] | None = None,
    phase32_bundle_path: str | None = None,
    panel_limit: int = 8000,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    bundle = phase32_bundle
    if bundle is None:
        if not phase32_bundle_path:
            raise ValueError("phase32_bundle or phase32_bundle_path required")
        bundle = load_phase32_bundle(phase32_bundle_path)

    gap = report_forward_validation_propagation_gaps(
        client,
        phase32_bundle=bundle,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    targets = [
        r
        for r in gap.get("rows") or []
        if r.get("classification") == "forward_present_validation_not_refreshed"
    ]
    keys: set[tuple[str, str, str]] = set()
    for r in targets:
        k = _factor_key_from_gap_row(r)
        if k[0] and k[1] and k[2]:
            keys.add(k)

    truth_before = report_forward_metric_truth_audit(
        client,
        universe_name=universe_name,
        phase32_bundle=bundle,
        panel_limit=panel_limit,
    )

    def _excess_ok(key: tuple[str, str, str]) -> bool:
        row = dbrec.fetch_factor_market_validation_panel_one(
            client,
            cik=key[0],
            accession_no=key[1],
            factor_version=key[2],
        )
        return row is not None and safe_float(row.get(EXCESS_FIELD)) is not None

    before_filled = sum(1 for k in keys if _excess_ok(k))

    if not keys:
        truth_after = truth_before
        return {
            "ok": True,
            "repair": "validation_refresh_after_forward_propagation",
            "skipped": True,
            "reason": "no_forward_present_validation_not_refreshed_rows",
            "target_factor_key_count": 0,
            "validation_panel_build": {"skipped": True},
            "validation_excess_filled_now_count": 0,
            "validation_excess_still_null_after_refresh_count": 0,
            "refresh_failed_keys": [],
            "metric_truth_before": truth_before,
            "metric_truth_after": truth_after,
            "symbol_cleared_from_missing_excess_queue_count_before": int(
                truth_before.get("symbol_cleared_from_missing_excess_queue_count") or 0
            ),
            "symbol_cleared_from_missing_excess_queue_count_after": int(
                truth_after.get("symbol_cleared_from_missing_excess_queue_count") or 0
            ),
            "joined_recipe_unlocked_now_count": 0,
        }

    ciks = sorted({k[0] for k in keys})
    fmap = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=ciks, limit=max(50_000, panel_limit)
    )
    fmap_n = {
        (norm_cik(a), str(b), str(c)): v for (a, b, c), v in fmap.items()
    }
    panels: list[dict[str, Any]] = []
    missing_factor: list[tuple[str, str, str]] = []
    for k in sorted(keys):
        prow = fmap_n.get(k)
        if prow:
            panels.append(prow)
        else:
            missing_factor.append(k)

    if not panels:
        truth_after = report_forward_metric_truth_audit(
            client,
            universe_name=universe_name,
            phase32_bundle=bundle,
            panel_limit=panel_limit,
        )
        ja = int(truth_after.get("joined_recipe_substrate_row_count_live") or 0)
        jb = int(truth_before.get("joined_recipe_substrate_row_count_live") or 0)
        return {
            "ok": True,
            "repair": "validation_refresh_after_forward_propagation",
            "target_factor_key_count": len(keys),
            "panels_refreshed": 0,
            "factor_panel_missing_for_keys": missing_factor[:50],
            "validation_panel_build": {
                "skipped": True,
                "reason": "no_issuer_quarter_factor_panel_rows_for_target_keys",
            },
            "validation_excess_filled_now_count": 0,
            "validation_excess_still_null_after_refresh_count": len(keys),
            "refresh_failed_keys": missing_factor[:100],
            "metric_truth_before": truth_before,
            "metric_truth_after": truth_after,
            "symbol_cleared_from_missing_excess_queue_count_before": int(
                truth_before.get("symbol_cleared_from_missing_excess_queue_count") or 0
            ),
            "symbol_cleared_from_missing_excess_queue_count_after": int(
                truth_after.get("symbol_cleared_from_missing_excess_queue_count") or 0
            ),
            "joined_recipe_unlocked_now_count": ja - jb,
            "gap_report_snapshot": {
                "forward_row_present_count": gap.get("forward_row_present_count"),
                "classification_counts": gap.get("classification_counts"),
            },
        }

    build_out = run_validation_panel_build_from_rows(
        settings,
        panels=panels,
        metadata_json={
            "phase34": "validation_refresh_after_forward_propagation",
            "n_factor_keys": len(keys),
            "n_panels": len(panels),
        },
    )

    still_bad = [k for k in keys if not _excess_ok(k)]
    refresh_failed_keys = list(missing_factor) + [
        k for k in still_bad if k not in set(missing_factor)
    ]

    after_filled = sum(1 for k in keys if _excess_ok(k))
    validation_excess_filled_now_count = max(0, after_filled - before_filled)
    still_null = len(keys) - after_filled

    truth_after = report_forward_metric_truth_audit(
        client,
        universe_name=universe_name,
        phase32_bundle=bundle,
        panel_limit=panel_limit,
    )

    jb = int(truth_before.get("joined_recipe_substrate_row_count_live") or 0)
    ja = int(truth_after.get("joined_recipe_substrate_row_count_live") or 0)

    return {
        "ok": True,
        "repair": "validation_refresh_after_forward_propagation",
        "target_factor_key_count": len(keys),
        "panels_refreshed": len(panels),
        "factor_panel_missing_for_keys": missing_factor[:50],
        "validation_panel_build": build_out,
        "validation_excess_filled_now_count": validation_excess_filled_now_count,
        "validation_excess_still_null_after_refresh_count": still_null,
        "refresh_failed_keys": refresh_failed_keys[:100],
        "metric_truth_before": truth_before,
        "metric_truth_after": truth_after,
        "symbol_cleared_from_missing_excess_queue_count_before": int(
            truth_before.get("symbol_cleared_from_missing_excess_queue_count") or 0
        ),
        "symbol_cleared_from_missing_excess_queue_count_after": int(
            truth_after.get("symbol_cleared_from_missing_excess_queue_count") or 0
        ),
        "joined_recipe_unlocked_now_count": ja - jb,
        "gap_report_snapshot": {
            "forward_row_present_count": gap.get("forward_row_present_count"),
            "classification_counts": gap.get("classification_counts"),
        },
    }
