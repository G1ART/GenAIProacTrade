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
    return "\n".join(lines)


def emit_backfill_report(payload: dict[str, Any], *, output_json: bool) -> None:
    if output_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(format_backfill_status_text(payload))
