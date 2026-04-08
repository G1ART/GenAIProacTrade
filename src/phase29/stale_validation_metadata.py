"""메타 수화 이후에도 `missing_market_metadata` 플래그가 남은 검증 패널 갱신(상한)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from db import records as dbrec

_FLAG = "missing_market_metadata"


def _panel_has_metadata_flag(panel: dict[str, Any]) -> bool:
    pj = panel.get("panel_json") if isinstance(panel.get("panel_json"), dict) else {}
    flags = pj.get("quality_flags") or []
    if not isinstance(flags, list):
        return False
    return _FLAG in {str(x) for x in flags}


def _natural_key_from_candidate(c: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(c.get("cik") or ""),
        str(c.get("accession_no") or ""),
        str(c.get("factor_version") or ""),
    )


def report_stale_validation_metadata_flags(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    validation_fetch_multiplier: int = 24,
) -> dict[str, Any]:
    as_of = dbrec.fetch_max_as_of_universe(client, universe_name=universe_name)
    if not as_of:
        return {"ok": False, "error": "no_universe_as_of", "universe_name": universe_name}
    as_of_s = str(as_of)[:10]
    syms = dbrec.fetch_symbols_universe_as_of(
        client, universe_name=universe_name, as_of_date=as_of_s
    )
    sym_set = {str(s).upper().strip() for s in syms if s}
    fetch_lim = min(max(panel_limit * validation_fetch_multiplier, 50_000), 200_000)
    panels = dbrec.fetch_factor_market_validation_panels_for_symbols(
        client, symbols=sorted(sym_set), limit=fetch_lim
    )
    candidates: list[dict[str, Any]] = []
    for p in panels:
        if not _panel_has_metadata_flag(p):
            continue
        sym = str(p.get("symbol") or "").upper().strip()
        if sym not in sym_set:
            continue
        fm = dbrec.fetch_market_metadata_latest_row_deterministic(client, symbol=sym)
        if not fm or not str(fm.get("as_of_date") or "").strip():
            continue
        candidates.append(
            {
                "symbol": sym,
                "cik": str(p.get("cik") or ""),
                "accession_no": str(p.get("accession_no") or ""),
                "factor_version": str(p.get("factor_version") or ""),
            }
        )
    return {
        "ok": True,
        "universe_name": universe_name,
        "as_of_date": as_of_s,
        "validation_panels_fetched": len(panels),
        "candidate_validation_rows": len(candidates),
        "candidates_sample": candidates[:60],
        "candidates": candidates,
    }


def _dedupe_candidates_by_key(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for c in candidates:
        k = _natural_key_from_candidate(c)
        if not k[0] or not k[1] or not k[2] or k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out


def count_candidates_still_flagged(client: Any, candidates: list[dict[str, Any]]) -> int:
    n = 0
    for c in _dedupe_candidates_by_key(candidates):
        row = dbrec.fetch_factor_market_validation_panel_one(
            client,
            cik=str(c["cik"]),
            accession_no=str(c["accession_no"]),
            factor_version=str(c["factor_version"]),
        )
        if row and _panel_has_metadata_flag(row):
            n += 1
    return n


def run_validation_refresh_after_metadata_hydration(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_rebuilds: int = 800,
) -> dict[str, Any]:
    from db.client import get_supabase_client
    from market.validation_panel_run import run_validation_panel_build_from_rows

    client = get_supabase_client(settings)
    rep = report_stale_validation_metadata_flags(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    if not rep.get("ok"):
        return {**rep, "repair": "validation_refresh_after_metadata_hydration"}
    candidates: list[dict[str, Any]] = list(rep.get("candidates") or [])
    deduped = _dedupe_candidates_by_key(candidates)
    slice_c = deduped[: max(0, int(max_rebuilds))]
    still_before_slice = (
        count_candidates_still_flagged(client, slice_c) if slice_c else 0
    )
    seen: set[tuple[str, str, str]] = set()
    factor_panels: list[dict[str, Any]] = []
    for c in slice_c:
        key = _natural_key_from_candidate(c)
        if not key[0] or not key[1] or not key[2] or key in seen:
            continue
        seen.add(key)
        fp = dbrec.fetch_issuer_quarter_factor_panel_one(
            client,
            cik=key[0],
            accession_no=key[1],
            factor_version=key[2],
        )
        if fp:
            factor_panels.append(fp)
    build_out: dict[str, Any] = {
        "status": "skipped",
        "rows_upserted": 0,
        "reason": "no_factor_panels_for_candidates",
    }
    if factor_panels:
        build_out = run_validation_panel_build_from_rows(
            settings,
            panels=factor_panels,
            metadata_json={
                "phase29": "validation_refresh_after_metadata_hydration",
                "universe_name": universe_name,
                "n_candidates": len(slice_c),
            },
        )
    still_after_slice = (
        count_candidates_still_flagged(client, slice_c) if slice_c else 0
    )
    cleared = max(0, still_before_slice - still_after_slice)
    return {
        "ok": True,
        "repair": "validation_refresh_after_metadata_hydration",
        "universe_name": universe_name,
        "candidate_validation_rows": len(candidates),
        "candidates_selected_for_rebuild": len(slice_c),
        "factor_panels_submitted": len(factor_panels),
        "validation_panels_rebuilt_for_metadata": int(build_out.get("rows_upserted") or 0),
        "validation_metadata_flags_before_rebuild_on_slice": still_before_slice,
        "validation_metadata_flags_still_present_after": still_after_slice,
        "validation_metadata_flags_cleared_count": cleared,
        "build": build_out,
    }


def export_stale_validation_metadata_rows(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    rep = report_stale_validation_metadata_flags(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    rows = list(rep.get("candidates") or [])
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv" and rows:
        keys = sorted({k for row in rows for k in row})
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    elif fmt == "csv":
        p.write_text("symbol,cik,accession_no,factor_version\n", encoding="utf-8")
    else:
        p.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "path": str(p), "count": len(rows), "format": fmt}
