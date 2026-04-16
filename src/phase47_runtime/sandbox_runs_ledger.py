"""Append-only ledger for Custom Research Sandbox v1 runs (Sprint 6 — saved research objects)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_CONTRACT = "SANDBOX_RUNS_LEDGER_V1"
_MAX_RUNS = 200


def default_sandbox_runs_ledger_path(repo_root: Path) -> Path:
    return repo_root / "data" / "product_surface" / "sandbox_runs_ledger_v1.json"


def load_sandbox_runs_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "contract": LEDGER_CONTRACT, "runs": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"schema_version": 1, "contract": LEDGER_CONTRACT, "runs": []}
    if not isinstance(raw, dict):
        return {"schema_version": 1, "contract": LEDGER_CONTRACT, "runs": []}
    runs = raw.get("runs")
    if not isinstance(runs, list):
        raw["runs"] = []
    return raw


def save_sandbox_runs_ledger(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _compact_run_record(sandbox_response: dict[str, Any]) -> dict[str, Any]:
    """Strip to a durable, review-friendly object (no full re-run payload)."""
    res = sandbox_response.get("result") or {}
    scan = res.get("horizon_scan")
    n_scan = len(scan) if isinstance(scan, list) else 0
    sample = scan[:6] if isinstance(scan, list) else None
    bullets = list(res.get("summary_bullets") or [])
    return {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "run_id": sandbox_response.get("run_id"),
        "contract": sandbox_response.get("contract"),
        "lang": sandbox_response.get("lang"),
        "inputs_echo": sandbox_response.get("inputs_echo"),
        "summary_bullets": bullets[:24],
        "horizon_scan_count": n_scan,
        "horizon_scan_sample": sample,
        "pit_note": res.get("pit_note"),
    }


def append_sandbox_run(path: Path, sandbox_response: dict[str, Any]) -> dict[str, Any]:
    if not sandbox_response.get("ok"):
        raise ValueError("cannot append failed sandbox response")
    data = load_sandbox_runs_ledger(path)
    runs = list(data.get("runs") or [])
    entry = _compact_run_record(sandbox_response)
    runs.append(entry)
    if len(runs) > _MAX_RUNS:
        runs = runs[-_MAX_RUNS:]
    data["runs"] = runs
    save_sandbox_runs_ledger(path, data)
    return entry


def list_sandbox_runs(path: Path, *, limit: int = 40) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 100))
    runs = list(load_sandbox_runs_ledger(path).get("runs") or [])
    tail = runs[-lim:]
    return list(reversed(tail))


def get_sandbox_run(path: Path, run_id: str) -> dict[str, Any] | None:
    rid = (run_id or "").strip()
    if not rid or len(rid) > 48:
        return None
    for r in reversed(list(load_sandbox_runs_ledger(path).get("runs") or [])):
        if isinstance(r, dict) and str(r.get("run_id") or "") == rid:
            return dict(r)
    return None
