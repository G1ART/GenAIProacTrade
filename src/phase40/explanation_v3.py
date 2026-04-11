"""Explanation v3 — family-comparative, execution-driven, non-recommendation."""

from __future__ import annotations

from typing import Any


def render_phase40_explanation_v3_md(*, bundle: dict[str, Any]) -> str:
    pit = bundle.get("pit_execution") or {}
    fams = pit.get("families_executed") or []
    gate = bundle.get("promotion_gate_phase40") or {}
    p41 = bundle.get("phase41") or {}
    life = bundle.get("lifecycle_after") or {}

    lines = [
        "# Research explanation (Phase 40 v3)",
        "",
        "_This document supports human judgment. It is **not** a buy, sell, or hold recommendation "
        "and does not constitute investment advice._",
        "",
        "## What ran (families)",
        "",
    ]
    for f in fams:
        fid = f.get("family_id")
        keys = f.get("spec_keys_executed") or []
        leak = (f.get("leakage_audit") or {}).get("passed")
        joined = f.get("joined_any_row")
        summ = f.get("summary_counts_by_spec") or {}
        lines.append(f"### `{fid}`")
        lines.append(f"- **Specs**: {keys}")
        lines.append(f"- **Leakage audit passed**: `{leak}`")
        lines.append(f"- **Any row joined under this family**: `{joined}`")
        lines.append(f"- **Rollups by spec**: `{summ}`")
        lines.append("")

    lines.extend(
        [
            "## Which families changed outcomes vs Phase 38 baseline?",
            "",
            "Compare `summary_counts_by_spec` to the `pit_as_of_boundary_v1` family (legacy trio). "
            "For this fixture, many single-spec replays intentionally mirror baseline or use bounded "
            "signal caps; **no automatic claim of economic resolution**.",
            "",
            "## Untested or proxy-limited",
            "",
            "- **Filing boundary** family uses `signal_available_date` as a **documented proxy** when EDGAR "
            "public timestamps are absent.",
            "- **Sector cadence** family currently replays the **same pick rule** on the fixture cohort only; "
            "it does not yet stratify by GICS.",
            "",
            "## Lifecycle snapshot (after Phase 40)",
            "",
            f"- `{life}`",
            "",
            "## Promotion gate",
            "",
            f"- **gate_status**: `{gate.get('gate_status')}`",
            f"- **primary_block_category**: `{gate.get('primary_block_category')}`",
            f"- **phase40_context**: `{gate.get('phase40_context')}`",
            "",
            "## Phase 41 (recommended next)",
            "",
            f"- **`{p41.get('phase41_recommendation')}`**",
            f"- {p41.get('rationale', '')}",
            "",
        ]
    )
    return "\n".join(lines)
