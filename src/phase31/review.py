"""Phase 31 클로즈아웃 MD."""

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


def write_phase31_raw_facts_bridge_review_md(
    out_path: str,
    *,
    bundle: dict[str, Any],
) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    b = bundle.get("before") or {}
    a = bundle.get("after") or {}
    raw = bundle.get("raw_facts_backfill_repair") or {}
    sil = bundle.get("gis_like_silver_seam_repair") or {}
    iss = bundle.get("deterministic_empty_cik_issuer_repair") or {}
    ds = bundle.get("downstream_substrate_retry") or {}
    p32 = bundle.get("phase32") or {}

    cb = b.get("quarter_snapshot_classification_counts") or {}
    ca = a.get("quarter_snapshot_classification_counts") or {}

    lines = [
        "# Phase 31 — Raw-facts bridge after filing-index repair",
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
        "## 분기 스냅샷 분류 (Before → After)",
        "",
    ]
    keys = sorted(set(cb) | set(ca))
    for k in keys:
        lines.append(f"- `{k}`: `{cb.get(k, 0)}` → `{ca.get(k, 0)}`")

    lines += [
        "",
        "## A/B. Raw facts bridge",
        "",
        f"- repaired_to_raw_present_count: `{_f(raw.get('repaired_to_raw_present_count'))}`",
        f"- deferred_external_source_gap_count: `{_f(raw.get('deferred_external_source_gap_count'))}`",
        f"- blocked_mapping_or_schema_seam_count: `{_f(raw.get('blocked_mapping_or_schema_seam_count'))}`",
        f"- facts_extract_attempts: `{_f(raw.get('facts_extract_attempts'))}`",
        "",
        "## C. GIS-like silver seam",
        "",
        f"- actions: `{_f(len(sil.get('actions') or []))}`",
        "",
        "## F. Deterministic issuer (empty_cik / NWSA-class)",
        "",
        f"- applied: `{_f(len(iss.get('deterministic_repairs_applied') or []))}`",
        f"- blocked: `{_f(len(iss.get('blocked') or []))}`",
        "",
        "## D. Downstream retry (raw/issuer touched CIKs)",
        "",
        f"- cik_count: `{_f(ds.get('cik_count'))}`",
        "",
        "## Phase 32 recommendation",
        "",
        f"- **`{p32.get('phase32_recommendation', '')}`**",
        f"- rationale: {p32.get('rationale', '')}",
        "",
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)
