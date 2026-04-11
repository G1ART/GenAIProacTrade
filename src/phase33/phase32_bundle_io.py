"""Phase 32 클로즈아웃 번들에서 터치 심볼·forward 실패 샘플 추출."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_phase32_bundle(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def forward_backfill_section(bundle: dict[str, Any]) -> dict[str, Any]:
    return bundle.get("forward_return_backfill_phase31_touched") or {}


def forward_gap_report_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    fb = forward_backfill_section(bundle)
    return fb.get("forward_gap_report") or bundle.get(
        "forward_gap_report_phase31_touched"
    ) or {}


def phase32_touched_symbols(bundle: dict[str, Any]) -> list[str]:
    gap = forward_gap_report_from_bundle(bundle)
    seen: set[str] = set()
    out: list[str] = []
    for e in gap.get("target_entries") or []:
        s = str(e.get("symbol") or "").upper().strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return sorted(out)


def phase32_insufficient_price_errors_next_q(
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    fb = forward_backfill_section(bundle)
    build = fb.get("forward_build") or {}
    errs = list(build.get("error_sample") or [])
    full = (build.get("error_json") or {}).get("errors")
    if isinstance(full, list):
        errs = full
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for e in errs:
        if str(e.get("error") or "") != "insufficient_price_history":
            continue
        if str(e.get("horizon") or "") != "next_quarter":
            continue
        sym = str(e.get("symbol") or "").upper().strip()
        sig = str(e.get("signal_date") or "")[:10]
        key = (sym, sig)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(e))
    return out


def phase32_bundle_repaired_symbol_count(bundle: dict[str, Any]) -> int:
    fb = forward_backfill_section(bundle)
    return int(fb.get("repaired_to_forward_present") or 0)
