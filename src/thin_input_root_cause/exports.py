"""Unresolved target exports (JSON/CSV) for operators (Phase 26)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Literal

from public_depth.diagnostics import compute_substrate_coverage
from substrate_closure.diagnose import report_forward_return_gaps, report_state_change_join_gaps


def export_unresolved_validation_symbols(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str | Path,
    fmt: Literal["json", "csv"] = "json",
) -> dict[str, Any]:
    queues: dict[str, list[str]] = {}
    compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        symbol_queues_out=queues,
    )
    syms = queues.get("no_validation_panel_for_symbol", [])
    rows = [
        {"symbol": s, "reason": "no_validation_panel_for_symbol", "universe_name": universe_name}
        for s in syms
    ]
    _write_rows(out_path, rows, fmt)
    return {"ok": True, "count": len(rows), "path": str(out_path), "format": fmt}


def export_unresolved_forward_return_rows(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str | Path,
    fmt: Literal["json", "csv"] = "json",
) -> dict[str, Any]:
    rep = report_forward_return_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    rows: list[dict[str, Any]] = []
    for bucket, items in (rep.get("row_reason_buckets") or {}).items():
        for it in items:
            r = dict(it)
            r["bucket"] = bucket
            r["universe_name"] = universe_name
            rows.append(r)
    _write_rows(out_path, rows, fmt)
    return {"ok": True, "count": len(rows), "path": str(out_path), "format": fmt}


def export_unresolved_state_change_joins(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str | Path,
    fmt: Literal["json", "csv"] = "json",
) -> dict[str, Any]:
    rep = report_state_change_join_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    rows: list[dict[str, Any]] = []
    for bucket, items in (rep.get("row_reason_buckets") or {}).items():
        for it in items:
            r = dict(it)
            r["bucket"] = bucket
            r["universe_name"] = universe_name
            rows.append(r)
    _write_rows(out_path, rows, fmt)
    return {"ok": True, "count": len(rows), "path": str(out_path), "format": fmt}


def _write_rows(path: str | Path, rows: list[dict[str, Any]], fmt: str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        p.write_text(
            json.dumps(rows, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    keys = sorted({k for r in rows for k in r})
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in keys})
