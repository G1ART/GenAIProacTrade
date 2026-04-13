"""Phase 45 review MD and bundle JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_phase45_canonical_closeout_bundle_json(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(p.resolve())


def write_phase45_canonical_closeout_review_md(path: str, *, bundle: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ar = bundle.get("authoritative_resolution") or {}
    cc = bundle.get("canonical_closeout") or {}
    fr = bundle.get("future_reopen_protocol") or {}
    st = bundle.get("current_closeout_status") or {}
    p46 = bundle.get("phase46") or {}

    cohort = cc.get("cohort") or {}
    rows = cohort.get("rows") or []
    sym_line = ", ".join(f"{r.get('symbol')} ({r.get('cik')})" for r in rows[:16])
    if len(rows) > 16:
        sym_line += ", …"

    lines = [
        "# Phase 45 — Canonical operator closeout & reopen protocol",
        "",
        "> **Phase 44 is the authoritative interpretation layer for the current cohort.**",
        "> **Phase 43 legacy optimistic retry wording in older bundles is non-authoritative historical output.**",
        "",
        f"- Bundle phase: `{bundle.get('phase')}`",
        f"- Generated: `{bundle.get('generated_utc')}`",
        f"- Phase 44 input: `{bundle.get('input_phase44_bundle_path')}`",
        f"- Phase 43 input: `{bundle.get('input_phase43_bundle_path')}`",
        "",
        "## Authoritative resolution",
        "",
        f"- **authoritative_phase**: `{ar.get('authoritative_phase')}`",
        f"- **authoritative_recommendation**: `{ar.get('authoritative_recommendation')}`",
        f"- **rationale**: {ar.get('authoritative_rationale')}",
        "",
        "### Precedence",
        "",
        f"{ar.get('reason_for_precedence')}",
        "",
        "### Superseded (audit only)",
        "",
    ]
    for s in ar.get("superseded_recommendations") or []:
        lines.append(f"- `{s.get('field_path')}` ← `{s.get('prior_value')}` ({s.get('source_artifact')})")
    if not (ar.get("superseded_recommendations") or []):
        lines.append("- _(none recorded)_")

    lines.extend(
        [
            "",
            "## Canonical closeout",
            "",
            f"- **Cohort**: {cohort.get('row_count')} rows — {sym_line}",
            "",
            "### What was attempted",
            "",
            f"- Filing: `{cc.get('what_was_attempted', {}).get('phase43_bounded_filing_path')}`",
            f"- Sector: `{cc.get('what_was_attempted', {}).get('phase43_bounded_sector_path')}`",
            "",
            "### What changed / did not",
            "",
            "See bundle `canonical_closeout.what_changed` and `what_did_not_change`.",
            "",
            "### Unsupported interpretations (explicit)",
            "",
        ]
    )
    for u in cc.get("explicit_unsupported_interpretations") or []:
        lines.append(f"- {u}")
    lines.extend(
        [
            "",
            f"- **Final verdict**: `{cc.get('final_closeout_verdict')}`",
            "",
            "## Current closeout status",
            "",
            f"- **status**: `{st.get('current_closeout_status')}`",
            f"- **summary**: {st.get('summary')}",
            "",
            "## Future reopen protocol",
            "",
            f"- **allowed_with_named_source**: `{fr.get('future_reopen_allowed_with_named_source')}`",
            f"- **max_scope**: {fr.get('max_scope_on_reopen')}",
            "",
            "### Forbidden reopen axes",
            "",
        ]
    )
    for x in fr.get("forbidden_reopen_axes") or []:
        lines.append(f"- `{x}`")
    lines.extend(
        [
            "",
            "### Required operator declarations",
            "",
        ]
    )
    for f in fr.get("required_operator_declaration_fields") or []:
        lines.append(f"- `{f}`")
    lines.extend(
        [
            "",
            "## Phase 46",
            "",
            f"- **`{p46.get('phase46_recommendation')}`** — {p46.get('rationale')}",
            "",
            "---",
            "",
            "_Phase 45 performs no substrate or DB work; governance closeout only._",
            "",
        ]
    )
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p.resolve())
