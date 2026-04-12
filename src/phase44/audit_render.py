"""Render provenance-separated audit markdown."""

from __future__ import annotations

from typing import Any


def render_phase44_provenance_audit_md(*, rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase 44 — Provenance-separated audit (8-row cohort)",
        "",
        "Three layers per row: **input_bundle_before** (Phase 42 labels), "
        "**runtime_snapshot_before_repair**, **runtime_snapshot_after_repair** (metrics-only inference).",
        "",
    ]
    for r in rows:
        sym = r.get("symbol")
        lines.extend(
            [
                f"## {sym} (CIK `{r.get('cik')}`, signal `{r.get('signal_available_date')}`)",
                "",
                "### input_bundle_before",
                "",
                "| Axis | Value |",
                "| --- | --- |",
                f"| filing | `{r.get('input_bundle_before', {}).get('filing_blocker')}` |",
                f"| sector | `{r.get('input_bundle_before', {}).get('sector_blocker')}` |",
                "",
                "### runtime_snapshot_before_repair",
                "",
                _snapshot_table(r.get("runtime_snapshot_before_repair") or {}),
                "",
                "### runtime_snapshot_after_repair",
                "",
                _snapshot_table(r.get("runtime_snapshot_after_repair") or {}),
                "",
            ]
        )
    return "\n".join(lines)


def _snapshot_table(s: dict[str, Any]) -> str:
    rows_md = [
        "| Field | Value |",
        "| --- | --- |",
        f"| filing_blocker | `{s.get('filing_blocker')}` |",
        f"| filing_index_row_count | {s.get('filing_index_row_count')} |",
        f"| n_10k_10q | {s.get('n_10k_10q')} |",
        f"| any_pre_signal_candidate | {s.get('any_pre_signal_candidate')} |",
        f"| sector_blocker | `{s.get('sector_blocker')}` |",
        f"| raw_row_count | {s.get('raw_row_count')} |",
        f"| sector_present | {s.get('sector_present')} |",
        f"| industry_present | {s.get('industry_present')} |",
    ]
    return "\n".join(rows_md)
