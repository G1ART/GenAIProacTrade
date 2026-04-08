"""Phase 27 A: 검증 미적재 심볼의 레지스트리·CIK·별칭 분해."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from db import records as dbrec
from public_depth.diagnostics import compute_substrate_coverage
from research_validation.metrics import norm_cik
from substrate_closure.diagnose import _fetch_validation_rows_for_ciks

_BUCKET_MISSING_REGISTRY = "missing_symbol_in_market_symbol_registry"
_BUCKET_ALIAS = "missing_symbol_alias_mapping"
_BUCKET_SYMBOL_CIK_MISS = "symbol_to_cik_registry_miss"
_BUCKET_ISSUER_ORPHAN_CIK = "issuer_master_missing_for_resolved_cik"
_BUCKET_NO_FACTOR = "factor_panel_missing_for_resolved_cik"
_BUCKET_NORM_MISMATCH = "symbol_normalization_mismatch"
_BUCKET_VALIDATION_OMISSION = "validation_panel_build_omission_for_cik"

# Phase 28·번들 집계용(심볼은 버킷 하나에만 분류됨).
PHASE28_REGISTRY_BUCKETS = frozenset(
    {
        _BUCKET_MISSING_REGISTRY,
        _BUCKET_ALIAS,
        _BUCKET_SYMBOL_CIK_MISS,
        _BUCKET_ISSUER_ORPHAN_CIK,
        _BUCKET_NO_FACTOR,
        _BUCKET_NORM_MISMATCH,
        _BUCKET_VALIDATION_OMISSION,
    }
)


def registry_gap_rollup_for_bundle(
    registry_bucket_counts: dict[str, Any] | None,
) -> dict[str, Any]:
    """Phase 28 recommender·번들용 레지스트리 갭 규모(과소계상 방지)."""
    c = registry_bucket_counts or {}

    def _n(k: str) -> int:
        return int(c.get(k) or 0)

    automation = (
        _n(_BUCKET_MISSING_REGISTRY)
        + _n(_BUCKET_ALIAS)
        + _n(_BUCKET_SYMBOL_CIK_MISS)
        + _n(_BUCKET_NORM_MISMATCH)
    )
    upstream = (
        _n(_BUCKET_ISSUER_ORPHAN_CIK)
        + _n(_BUCKET_NO_FACTOR)
        + _n(_BUCKET_VALIDATION_OMISSION)
    )
    total = sum(_n(k) for k in PHASE28_REGISTRY_BUCKETS)
    return {
        "registry_blocker_symbol_total": total,
        "registry_repair_automation_eligible_count": automation,
        "registry_upstream_or_pipeline_deferred_count": upstream,
        "per_bucket": {k: _n(k) for k in sorted(PHASE28_REGISTRY_BUCKETS)},
    }


def _registry_cik_raw(reg: dict[str, Any] | None) -> str | None:
    if not reg:
        return None
    c = reg.get("cik")
    if c is None or not str(c).strip():
        return None
    return str(c).strip()


def _classify_one(
    su: str,
    *,
    cik_by_symbol: dict[str, str | None],
    registry_by_sym: dict[str, dict[str, Any]],
    mem_cik_raw: str | None,
    registry_syms_by_cik: dict[str, list[str]],
    issuer_ciks_norm_present: set[str],
    ciks_with_factor: set[str],
    val_by_cik: dict[str, list[dict[str, Any]]],
    canonical_for_cik: dict[str, str | None],
) -> str:
    reg = registry_by_sym.get(su)
    raw_im = cik_by_symbol.get(su)
    nc_im = norm_cik(raw_im) if raw_im and str(raw_im).strip() else ""

    if reg is None:
        mck = norm_cik(mem_cik_raw) if mem_cik_raw and str(mem_cik_raw).strip() else ""
        if mck:
            alts = [x for x in registry_syms_by_cik.get(str(mem_cik_raw).strip(), []) if x != su]
            if alts:
                return _BUCKET_ALIAS
        return _BUCKET_MISSING_REGISTRY

    reg_cik = _registry_cik_raw(reg)
    reg_nc = norm_cik(reg_cik) if reg_cik else ""
    if reg_cik and reg_nc and reg_nc not in issuer_ciks_norm_present:
        return _BUCKET_ISSUER_ORPHAN_CIK

    if not reg_cik and (not raw_im or not str(raw_im).strip()):
        return _BUCKET_SYMBOL_CIK_MISS

    nc = nc_im or (norm_cik(reg_cik) if reg_cik else "")
    if not nc:
        return _BUCKET_SYMBOL_CIK_MISS

    if nc not in ciks_with_factor:
        return _BUCKET_NO_FACTOR

    canonical = canonical_for_cik.get(nc) or ""
    cu = canonical.upper().strip()
    rows = val_by_cik.get(nc, [])
    syms_on_rows = {str(r.get("symbol") or "").upper().strip() for r in rows}
    if su in syms_on_rows:
        return _BUCKET_VALIDATION_OMISSION
    if rows and cu and cu != su and cu in syms_on_rows:
        return _BUCKET_NORM_MISMATCH
    return _BUCKET_VALIDATION_OMISSION


def report_validation_registry_gaps(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    queues: dict[str, list[str]] = {}
    metrics, exclusion_distribution = compute_substrate_coverage(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        symbol_queues_out=queues,
    )
    missing = sorted({s.upper().strip() for s in queues.get("no_validation_panel_for_symbol", [])})
    as_of = metrics.get("as_of_date")
    if not as_of or not missing:
        buckets: dict[str, list[str]] = defaultdict(list)
        for sym in missing:
            buckets[_BUCKET_MISSING_REGISTRY].append(sym)
        return {
            "ok": True,
            "universe_name": universe_name,
            "metrics": metrics,
            "exclusion_distribution": exclusion_distribution,
            "missing_symbol_count": len(missing),
            "registry_buckets": {k: sorted(set(v)) for k, v in buckets.items()},
            "registry_bucket_counts": {k: len(set(v)) for k, v in buckets.items()},
            "note": "empty_as_of_or_missing" if not as_of else "no_missing_symbols",
        }

    mem_rows = dbrec.fetch_universe_memberships_for_as_of(
        client, universe_name=universe_name, as_of_date=str(as_of)[:10]
    )
    mem_by_sym = {
        str(r["symbol"]).upper().strip(): r for r in mem_rows if r.get("symbol")
    }

    symbols_all = dbrec.fetch_symbols_universe_as_of(
        client, universe_name=universe_name, as_of_date=str(as_of)[:10]
    )
    cik_by_symbol = dbrec.fetch_cik_map_for_tickers(client, symbols_all)
    registry_by_sym = dbrec.fetch_market_symbol_registry_rows_for_symbols(client, missing)

    mem_ciks = [str(r.get("cik") or "").strip() for r in mem_rows if r.get("cik")]
    registry_syms_by_cik = dbrec.fetch_market_symbol_registry_symbols_by_ciks(client, mem_ciks)

    reg_ciks = [_registry_cik_raw(registry_by_sym.get(s)) for s in missing]
    reg_ciks += [str(cik_by_symbol.get(s) or "").strip() for s in missing]
    reg_ciks = [c for c in reg_ciks if c]
    issuer_ciks_raw = dbrec.fetch_issuer_master_ciks_present(client, reg_ciks)
    issuer_ciks_norm_present = {norm_cik(x) for x in issuer_ciks_raw if x}

    resolved_ciks = {
        norm_cik(c)
        for c in cik_by_symbol.values()
        if c and str(c).strip() and norm_cik(c)
    }
    factor_map = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
        client, ciks=list(resolved_ciks), limit=max(panel_limit, 50_000)
    )
    ciks_with_factor = {norm_cik(k[0]) for k in factor_map}

    val_by_cik: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _fetch_validation_rows_for_ciks(
        client, ciks=list(resolved_ciks), limit=50_000
    ):
        ck = norm_cik(row.get("cik"))
        if ck:
            val_by_cik[ck].append(dict(row))

    canonical_for_cik: dict[str, str | None] = {}
    for ck in resolved_ciks:
        if ck:
            canonical_for_cik[ck] = dbrec.fetch_ticker_for_cik(client, cik=ck)

    buckets = defaultdict(list)
    for su in missing:
        mem = mem_by_sym.get(su)
        mem_cik_raw = str(mem.get("cik") or "").strip() if mem else None
        b = _classify_one(
            su,
            cik_by_symbol=cik_by_symbol,
            registry_by_sym=registry_by_sym,
            mem_cik_raw=mem_cik_raw,
            registry_syms_by_cik=registry_syms_by_cik,
            issuer_ciks_norm_present=issuer_ciks_norm_present,
            ciks_with_factor=ciks_with_factor,
            val_by_cik=val_by_cik,
            canonical_for_cik=canonical_for_cik,
        )
        buckets[b].append(su)

    return {
        "ok": True,
        "universe_name": universe_name,
        "metrics": metrics,
        "exclusion_distribution": exclusion_distribution,
        "missing_symbol_count": len(missing),
        "missing_symbols_sample": missing[:80],
        "registry_buckets": {k: sorted(set(v)) for k, v in buckets.items()},
        "registry_bucket_counts": {k: len(set(v)) for k, v in buckets.items()},
    }


def run_validation_registry_repair(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    from db.client import get_supabase_client

    c = get_supabase_client(settings)
    before = report_validation_registry_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    miss_before = int(before.get("missing_symbol_count") or 0)
    as_of = (before.get("metrics") or {}).get("as_of_date")
    repaired: list[dict[str, Any]] = []
    blocked_actions: list[dict[str, Any]] = []
    deferred_actions: list[dict[str, Any]] = []

    if as_of:
        mem_rows = dbrec.fetch_universe_memberships_for_as_of(
            c, universe_name=universe_name, as_of_date=str(as_of)[:10]
        )
        mem_by_sym = {
            str(r["symbol"]).upper().strip(): r for r in mem_rows if r.get("symbol")
        }
        buckets = before.get("registry_buckets") or {}

        for sym in buckets.get(_BUCKET_MISSING_REGISTRY, []):
            su = sym.upper().strip()
            m = mem_by_sym.get(su)
            if not m or not str(m.get("cik") or "").strip():
                continue
            payload = m.get("source_payload_json") if isinstance(m.get("source_payload_json"), dict) else {}
            name = str(payload.get("name") or "") or None
            now = datetime.now(timezone.utc).isoformat()
            dbrec.upsert_market_symbol_registry(
                c,
                {
                    "symbol": su,
                    "cik": str(m.get("cik")).strip(),
                    "company_name": name,
                    "exchange": None,
                    "currency": "USD",
                    "asset_type": "common_stock",
                    "is_active": True,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "source_name": str(m.get("source_name") or "universe_membership"),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            repaired.append({"symbol": su, "kind": "upsert_registry_from_membership"})

        mem_cik_by_sym = {
            str(r["symbol"]).upper().strip(): str(r.get("cik") or "").strip()
            for r in mem_rows
            if r.get("symbol")
        }
        for sym in buckets.get(_BUCKET_ALIAS, []):
            su = sym.upper().strip()
            cik_m = mem_cik_by_sym.get(su)
            if not cik_m:
                continue
            peers = dbrec.fetch_market_symbol_registry_symbols_by_ciks(c, [cik_m]).get(cik_m, [])
            donor_sym = next((p for p in peers if p != su), None)
            if not donor_sym:
                continue
            donor = dbrec.fetch_market_symbol_registry_rows_for_symbols(c, [donor_sym]).get(donor_sym.upper().strip())
            if not donor:
                continue
            now = datetime.now(timezone.utc).isoformat()
            dbrec.upsert_market_symbol_registry(
                c,
                {
                    "symbol": su,
                    "cik": donor.get("cik"),
                    "company_name": donor.get("company_name"),
                    "exchange": donor.get("exchange"),
                    "currency": donor.get("currency") or "USD",
                    "asset_type": donor.get("asset_type") or "common_stock",
                    "is_active": True,
                    "first_seen_at": donor.get("first_seen_at") or now,
                    "last_seen_at": now,
                    "source_name": str(donor.get("source_name") or "alias_copy"),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            repaired.append(
                {"symbol": su, "kind": "upsert_registry_alias_copy", "from_symbol": donor_sym}
            )

        symbols_univ = dbrec.fetch_symbols_universe_as_of(
            c, universe_name=universe_name, as_of_date=str(as_of)[:10]
        )
        cik_by_symbol = dbrec.fetch_cik_map_for_tickers(c, symbols_univ)

        for sym in buckets.get(_BUCKET_SYMBOL_CIK_MISS, []):
            su = sym.upper().strip()
            m = mem_by_sym.get(su)
            if not m or not str(m.get("cik") or "").strip():
                blocked_actions.append(
                    {
                        "symbol": su,
                        "kind": "repair_blocked_requires_upstream_issuer_materialization",
                        "detail": "symbol_to_cik_miss_no_membership_cik",
                    }
                )
                continue
            payload = m.get("source_payload_json") if isinstance(m.get("source_payload_json"), dict) else {}
            name = str(payload.get("name") or "") or None
            now = datetime.now(timezone.utc).isoformat()
            dbrec.upsert_market_symbol_registry(
                c,
                {
                    "symbol": su,
                    "cik": str(m.get("cik")).strip(),
                    "company_name": name,
                    "exchange": None,
                    "currency": "USD",
                    "asset_type": "common_stock",
                    "is_active": True,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "source_name": str(m.get("source_name") or "universe_membership_cik_fill"),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            repaired.append({"symbol": su, "kind": "upsert_registry_from_membership_for_symbol_to_cik_miss"})

        for sym in buckets.get(_BUCKET_NORM_MISMATCH, []):
            su = sym.upper().strip()
            blocked_actions.append(
                {
                    "symbol": su,
                    "kind": "deferred_symbol_normalization_mismatch",
                    "detail": "requires_validation_build_under_canonical_ticker",
                }
            )

        for sym in buckets.get(_BUCKET_VALIDATION_OMISSION, []):
            su = sym.upper().strip()
            blocked_actions.append(
                {
                    "symbol": su,
                    "kind": "repair_blocked_requires_validation_panel_build_pipeline",
                }
            )

        iss_syms = list(buckets.get(_BUCKET_ISSUER_ORPHAN_CIK, []))
        reg_iss = dbrec.fetch_market_symbol_registry_rows_for_symbols(c, iss_syms)
        for sym in iss_syms:
            su = sym.upper().strip()
            reg_row = reg_iss.get(su)
            cik_r = _registry_cik_raw(reg_row)
            if not cik_r:
                blocked_actions.append(
                    {
                        "symbol": su,
                        "kind": "repair_blocked_requires_upstream_issuer_materialization",
                        "detail": "issuer_orphan_no_registry_cik",
                    }
                )
                continue
            nc = norm_cik(cik_r)
            present_raw = dbrec.fetch_issuer_master_ciks_present(c, [nc])
            if nc in {norm_cik(x) for x in present_raw}:
                deferred_actions.append(
                    {
                        "symbol": su,
                        "cik": nc,
                        "kind": "skipped_issuer_row_now_present_after_reverify",
                    }
                )
                continue
            m = mem_by_sym.get(su)
            mem_cik = str(m.get("cik") or "").strip() if m else ""
            if not mem_cik or norm_cik(mem_cik) != nc:
                blocked_actions.append(
                    {
                        "symbol": su,
                        "cik": nc,
                        "kind": "repair_blocked_requires_upstream_issuer_materialization",
                        "detail": "membership_cik_absent_or_mismatch_registry",
                    }
                )
                continue
            payload = m.get("source_payload_json") if isinstance(m.get("source_payload_json"), dict) else {}
            name = str(payload.get("name") or (reg_row.get("company_name") if reg_row else "") or su)
            now_iso = datetime.now(timezone.utc).isoformat()
            dbrec.upsert_issuer_master(
                c,
                {
                    "cik": nc,
                    "ticker": su,
                    "company_name": name,
                    "sic": None,
                    "sic_description": None,
                    "latest_known_exchange": None,
                    "is_active": True,
                    "first_seen_at": now_iso,
                    "last_seen_at": now_iso,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
            )
            repaired.append(
                {
                    "symbol": su,
                    "kind": "upsert_issuer_master_from_membership_and_registry_cik",
                    "cik": nc,
                }
            )

        for sym in buckets.get(_BUCKET_NO_FACTOR, []):
            su = sym.upper().strip()
            raw_cik = cik_by_symbol.get(su)
            if not raw_cik or not str(raw_cik).strip():
                blocked_actions.append(
                    {
                        "symbol": su,
                        "kind": "repair_blocked_requires_factor_pipeline_or_accession_ingest",
                        "detail": "no_cik_on_issuer_map_for_symbol",
                    }
                )
                continue
            nc = norm_cik(raw_cik)
            fmap = dbrec.fetch_issuer_quarter_factor_panels_for_ciks(
                c, ciks=[nc], limit=max(panel_limit, 50_000)
            )
            if fmap:
                deferred_actions.append(
                    {
                        "symbol": su,
                        "cik": nc,
                        "kind": "skipped_factor_panels_now_present_after_reverify",
                    }
                )
                continue
            blocked_actions.append(
                {
                    "symbol": su,
                    "cik": nc,
                    "kind": "repair_blocked_requires_factor_pipeline_or_accession_ingest",
                }
            )

    after = report_validation_registry_gaps(
        c, universe_name=universe_name, panel_limit=panel_limit
    )
    miss_after = int(after.get("missing_symbol_count") or 0)
    cov_m = after.get("metrics") or {}
    return {
        "ok": True,
        "repair": "validation_registry",
        "universe_name": universe_name,
        "before": {
            "missing_validation_symbol_count": miss_before,
            "registry_bucket_counts": before.get("registry_bucket_counts"),
        },
        "after": {
            "missing_validation_symbol_count": miss_after,
            "registry_bucket_counts": after.get("registry_bucket_counts"),
            "joined_recipe_substrate_row_count": cov_m.get("joined_recipe_substrate_row_count"),
            "n_issuer_with_validation_panel_symbol": cov_m.get(
                "n_issuer_with_validation_panel_symbol"
            ),
            "n_issuer_resolved_cik": cov_m.get("n_issuer_resolved_cik"),
            "n_issuer_with_factor_panel": cov_m.get("n_issuer_with_factor_panel"),
        },
        "repair_actions": repaired,
        "blocked_actions": blocked_actions,
        "deferred_actions": deferred_actions,
    }


def export_validation_registry_gap_symbols(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    out_path: str,
    fmt: str = "json",
) -> dict[str, Any]:
    import csv
    import json
    from pathlib import Path

    rep = report_validation_registry_gaps(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    rows: list[dict[str, Any]] = []
    for bucket, syms in (rep.get("registry_buckets") or {}).items():
        for s in syms:
            rows.append({"symbol": s, "registry_gap_bucket": bucket})

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["symbol", "registry_gap_bucket"])
            w.writeheader()
            w.writerows(rows)
    else:
        p.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"ok": True, "path": str(p), "count": len(rows), "format": fmt}
