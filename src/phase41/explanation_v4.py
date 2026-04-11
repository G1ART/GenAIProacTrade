"""Explanation surface v4 — substrate truthfulness (real vs proxy vs unchanged)."""

from __future__ import annotations

from typing import Any


def render_phase41_explanation_v4_md(*, bundle: dict[str, Any]) -> str:
    pit = bundle.get("pit_execution") or {}
    gate = bundle.get("promotion_gate_phase41") or {}
    p42 = bundle.get("phase42") or {}
    filing = pit.get("filing_substrate") or {}
    sector = pit.get("sector_substrate") or {}
    cmp = bundle.get("family_rerun_before_after") or {}

    lines = [
        "# Research explanation (Phase 41 v4)",
        "",
        "_Supports human judgment only. **Not** investment advice; no buy/sell/hold recommendation._",
        "",
        "## What substrate was wired",
        "",
        "- **Filing**: `filing_index` rows per fixture CIK; per-row classification "
        "`exact_filing_public_ts_available` | `exact_filing_filed_date_available` | "
        "`filing_public_ts_unavailable` (explicit `signal_available_date` proxy when unavailable).",
        "- **Sector**: `market_metadata_latest.sector` (deterministic pick per symbol); "
        "`sector_metadata_available` | `sector_metadata_missing` (stratum `unknown`).",
        "",
        "## Filing substrate summary",
        "",
        f"- `{filing.get('summary', {})}`",
        "",
        "## Sector substrate summary",
        "",
        f"- `{sector.get('summary', {})}`",
        "",
        "## Families re-executed (Phase 41)",
        "",
    ]
    for f in pit.get("families_executed") or []:
        fid = f.get("family_id")
        lines.append(f"### `{fid}`")
        lines.append(f"- **Specs**: {f.get('spec_keys_executed')}")
        lines.append(f"- **Leakage passed**: `{(f.get('leakage_audit') or {}).get('passed')}`")
        lines.append(f"- **Rollups**: `{f.get('summary_counts_by_spec')}`")
        if f.get("sector_stratum_outcome_counts"):
            lines.append(f"- **By sector stratum**: `{f.get('sector_stratum_outcome_counts')}`")
        lines.append("")

    if cmp:
        lines.extend(
            [
                "## Before vs after (vs Phase 40 bundle, if provided)",
                "",
                f"- `{cmp}`",
                "",
            ]
        )

    lines.extend(
        [
            "## What changed vs stayed the same",
            "",
            "- Outcome **counts** may match Phase 40 when bounds coincide; v4 value is **explicit** "
            "filing/sector labels and pick metadata on each cell.",
            "- Rows still on **signal proxy** for filing or **unknown** sector stratum are labeled—not silent.",
            "",
            "## Promotion gate (v4)",
            "",
            f"- **gate_status**: `{gate.get('gate_status')}`",
            f"- **primary_block_category**: `{gate.get('primary_block_category')}`",
            f"- **phase41_context**: `{gate.get('phase41_context')}`",
            "",
            "## Phase 42 (recommended next)",
            "",
            f"- **`{p42.get('phase42_recommendation')}`**",
            f"- {p42.get('rationale', '')}",
            "",
        ]
    )
    return "\n".join(lines)
