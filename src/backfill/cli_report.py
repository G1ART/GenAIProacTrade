"""backfill 상태·커버리지 터미널 출력."""

from __future__ import annotations

import json
from typing import Any


def format_backfill_status_text(payload: dict[str, Any]) -> str:
    lines = ["=== Backfill / coverage status ==="]
    mode = payload.get("mode")
    uni = payload.get("universe_name")
    if mode or uni:
        lines.append(f"mode={mode} universe={uni}")
    cov = payload.get("coverage") or {}
    src = cov.get("source")
    lines.append(f"coverage_source: {src}")
    c = cov.get("counts")
    if isinstance(c, dict):
        for k in sorted(c.keys()):
            lines.append(f"  {k}: {c[k]}")
    orch = payload.get("last_orchestration")
    if orch:
        lines.append(f"last_orch_run: {orch.get('id')} status={orch.get('status')}")
    diag = payload.get("join_diagnostics")
    if diag and isinstance(diag, dict):
        lines.append("join_diagnostics (counts):")
        for key in (
            "missing_issuer_master",
            "issuer_no_filing_index",
            "issuer_no_silver_facts",
            "symbol_no_forward_return_row",
        ):
            v = diag.get(key)
            if isinstance(v, list):
                lines.append(f"  {key}: {len(v)}")
    thin = payload.get("thin_factor_issuers")
    if isinstance(thin, list):
        lines.append(f"thin_factor_issuers (n<{payload.get('thin_threshold', 4)}): {len(thin)} shown")
    cs = payload.get("coverage_stage")
    if cs:
        lines.append(f"coverage_stage: {cs}")
    ck = payload.get("coverage_checkpoint")
    if isinstance(ck, dict):
        lines.append("coverage_checkpoint (subset):")
        for key in (
            "issuer_master_rows",
            "issuer_quarter_factor_panels_distinct_cik",
            "factor_market_validation_panels_distinct_cik",
            "issuer_state_change_scores_distinct_cik",
        ):
            if key in ck:
                lines.append(f"  {key}: {ck[key]}")
    sp = payload.get("sparse_issuer_diagnostics")
    if isinstance(sp, dict):
        lines.append("sparse_issuer_diagnostics (issuer_count):")
        for key in (
            "issuer_master_no_filing_index",
            "filing_index_no_silver_facts",
            "snapshots_no_factor_panels",
            "factor_panels_no_validation",
            "validation_panels_no_state_change_score",
        ):
            block = sp.get(key)
            if isinstance(block, dict) and "issuer_count" in block:
                lines.append(f"  {key}: {block['issuer_count']}")
    return "\n".join(lines)


def emit_backfill_report(payload: dict[str, Any], *, output_json: bool) -> None:
    if output_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(format_backfill_status_text(payload))
