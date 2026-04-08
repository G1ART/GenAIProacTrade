"""Phase 30 클로즈아웃 MD."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _f(x: Any) -> str:
    if x is None:
        return "null"
    if isinstance(x, float):
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return str(x)


def write_phase30_validation_substrate_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    b = bundle.get("before") or {}
    a = bundle.get("after") or {}
    fi = bundle.get("filing_index_backfill_repair") or {}
    sil = bundle.get("silver_facts_materialization_repair") or {}
    ec = bundle.get("empty_cik_cleanup") or {}
    cas = bundle.get("downstream_substrate_cascade") or {}
    p31 = bundle.get("phase31") or {}

    lines = [
        "# Phase 30 — Upstream validation substrate (filing / silver / snapshot chain)",
        "",
        f"_Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`_",
        "",
        "## 핵심 지표 (Before → After)",
        "",
        "| 지표 | Before | After |",
        "| --- | --- | --- |",
        f"| joined_recipe_substrate_row_count | `{_f(b.get('joined_recipe_substrate_row_count'))}` | `{_f(a.get('joined_recipe_substrate_row_count'))}` |",
        f"| thin_input_share | `{_f(b.get('thin_input_share'))}` | `{_f(a.get('thin_input_share'))}` |",
        f"| missing_validation_symbol_count | `{_f(b.get('missing_validation_symbol_count'))}` | `{_f(a.get('missing_validation_symbol_count'))}` |",
        f"| missing_quarter_snapshot_for_cik | `{_f(b.get('missing_quarter_snapshot_for_cik'))}` | `{_f(a.get('missing_quarter_snapshot_for_cik'))}` |",
        f"| factor_panel_missing_for_resolved_cik | `{_f(b.get('factor_panel_missing_for_resolved_cik'))}` | `{_f(a.get('factor_panel_missing_for_resolved_cik'))}` |",
        "",
        "## 분기 스냅샷 분류 counts (Before → After)",
        "",
    ]
    cb = b.get("quarter_snapshot_classification_counts") or {}
    ca = a.get("quarter_snapshot_classification_counts") or {}
    keys = sorted(set(cb) | set(ca))
    for k in keys:
        lines.append(
            f"- `{k}`: `{cb.get(k, 0)}` → `{ca.get(k, 0)}`"
        )

    lines += [
        "",
        "## A. Filing index gap repair",
        "",
        f"- preflight_unique_targets: `{_f(fi.get('preflight_unique_targets_count'))}`",
        f"- repaired_now_count: `{_f(fi.get('repaired_now_count'))}`",
        f"- deferred_external_source_gap_count: `{_f(fi.get('deferred_external_source_gap_count'))}`",
        f"- blocked_identity_or_mapping_issue_count: `{_f(fi.get('blocked_identity_or_mapping_issue_count'))}`",
        f"- network_ingest_attempts: `{_f(fi.get('network_ingest_attempts'))}`",
        "",
        "## B. Silver facts materialization (`raw_present_no_silver_facts`)",
        "",
        f"- cik_repairs_attempted: `{_f(sil.get('cik_repairs_attempted'))}`",
        f"- actions rows: `{_f(len(sil.get('actions') or []))}`",
        "",
        "## C. Empty CIK / normalization",
        "",
        f"- note: `{ec.get('note', '')}`",
        f"- diagnoses: `{_f(len((ec.get('report') or {}).get('diagnoses') or []))}`",
        "",
        "## D. Downstream cascade (touched CIKs only)",
        "",
        f"- cik_count: `{_f(cas.get('cik_count'))}`",
        "",
        "## Phase 31 recommendation",
        "",
        f"- **`{p31.get('phase31_recommendation', '')}`**",
        f"- rationale: {p31.get('rationale', '')}",
        "",
    ]
    text = "\n".join(lines) + "\n"
    p.write_text(text, encoding="utf-8")
    return str(p)
