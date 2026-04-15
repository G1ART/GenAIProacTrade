"""Sprint 1 stub — Today spectrum board payload (frozen seed + horizon switch)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase47_runtime.message_layer_v1 import (
    MESSAGE_LAYER_V1_KEYS,
    build_message_layer_v1_for_row,
    spectrum_band_from_position,
)
from phase47_runtime.phase47e_user_locale import normalize_lang, t

_ALLOWED = frozenset({"short", "medium", "medium_long", "long"})
_HORIZON_LABEL_KEYS = {
    "short": "spectrum.h_short",
    "medium": "spectrum.h_medium",
    "medium_long": "spectrum.h_medium_long",
    "long": "spectrum.h_long",
}
_HORIZON_ORDER = ("short", "medium", "medium_long", "long")


def _seed_path(repo_root: Path) -> Path:
    return repo_root / "data" / "mvp" / "today_spectrum_seed_v1.json"


def _normalize_mock_price_tick(raw: str | None) -> str:
    v = str(raw or "0").strip().lower()
    return "1" if v in ("1", "true", "yes", "on") else "0"


def _apply_mock_price_invert_axis(rows: list[dict[str, Any]]) -> None:
    """Deterministic demo: invert 0–1 axis to simulate a price shock re-rank (not a model)."""
    for rr in rows:
        p = float(rr.get("spectrum_position") or 0.5)
        rr["spectrum_position"] = round(1.0 - p, 4)
        rr["spectrum_band"] = spectrum_band_from_position(rr["spectrum_position"])


def load_today_spectrum_seed(repo_root: Path) -> dict[str, Any] | None:
    p = _seed_path(repo_root)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _watch_alias_path(repo_root: Path) -> Path:
    return repo_root / "data" / "mvp" / "today_spectrum_watch_aliases_v1.json"


def load_spectrum_watch_alias_map(repo_root: Path) -> dict[str, str]:
    """Optional bundle id / symbol → spectrum seed asset_id (demo only)."""
    p = _watch_alias_path(repo_root)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    aliases = raw.get("aliases")
    if not isinstance(aliases, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in aliases.items():
        ks = str(k).strip()
        vs = str(v).strip()
        if ks and vs:
            out[ks] = vs
    return out


def expand_watchlist_for_spectrum_filter(watch_ids: list[str], alias_map: dict[str, str]) -> list[str]:
    """Stable unique list: each watch id plus alias target when present."""
    seen: set[str] = set()
    out: list[str] = []
    for w in watch_ids:
        ws = str(w).strip()
        if not ws or ws in seen:
            continue
        out.append(ws)
        seen.add(ws)
        mapped = alias_map.get(ws)
        if mapped and mapped not in seen:
            out.append(mapped)
            seen.add(mapped)
    return out


def list_spectrum_seed_asset_ids(repo_root: Path) -> list[str]:
    """Stable union of asset_id across all horizons in the spectrum seed (for watch↔seed UX)."""
    raw = load_today_spectrum_seed(repo_root)
    if not raw:
        return []
    seen: set[str] = set()
    out: list[str] = []
    byh = raw.get("rows_by_horizon") or {}
    for hz in _HORIZON_ORDER:
        for r in byh.get(hz) or []:
            if not isinstance(r, dict):
                continue
            aid = str(r.get("asset_id") or "").strip()
            if aid and aid not in seen:
                seen.add(aid)
                out.append(aid)
    return out


def build_today_spectrum_payload(
    *,
    repo_root: Path,
    horizon: str | None,
    lang: str | None = None,
    mock_price_tick: str | None = None,
) -> dict[str, Any]:
    """Demo-grade spectrum rows for one horizon (MVP Sprint 1 vertical slice)."""
    lg = normalize_lang(lang)
    tick = _normalize_mock_price_tick(mock_price_tick)
    raw = load_today_spectrum_seed(repo_root)
    if not raw:
        return {
            "ok": False,
            "error": "spectrum_seed_missing",
            "hint": str(_seed_path(repo_root)),
        }
    hz = (horizon or "short").strip().lower().replace("-", "_")
    if hz not in _ALLOWED:
        return {
            "ok": False,
            "error": "invalid_horizon",
            "allowed": sorted(_ALLOWED),
        }
    byh = raw.get("rows_by_horizon") or {}
    rows_in = byh.get(hz) or []
    families = raw.get("active_model_family_by_horizon") or {}
    out_rows: list[dict[str, Any]] = []
    fam = families.get(hz) or ""
    for r in rows_in:
        if not isinstance(r, dict):
            continue
        rs = r.get("rationale_summary") or {}
        wc = r.get("what_changed") or {}
        rationale_plain = rs.get(lg) or rs.get("en") or rs.get("ko") or ""
        wc_plain = wc.get(lg) or wc.get("en") or wc.get("ko") or ""
        pos = r.get("spectrum_position")
        msg = build_message_layer_v1_for_row(
            row=r,
            horizon=hz,
            lang=lg,
            active_model_family=fam,
            rationale_summary=rationale_plain,
            what_changed=wc_plain,
            confidence_band=str(r.get("confidence_band") or ""),
        )
        out_rows.append(
            {
                "asset_id": r.get("asset_id"),
                "spectrum_position": pos,
                "spectrum_band": spectrum_band_from_position(float(pos) if pos is not None else None),
                "valuation_tension": r.get("valuation_tension"),
                "confidence_band": r.get("confidence_band"),
                "rationale_summary": rationale_plain,
                "what_changed": wc_plain,
                "message": msg,
            }
        )
    out_rows.sort(key=lambda x: float(x.get("spectrum_position") or 0), reverse=True)
    if tick == "1":
        _apply_mock_price_invert_axis(out_rows)
        out_rows.sort(key=lambda x: float(x.get("spectrum_position") or 0), reverse=True)
    horizon_options = [{"id": h, "label": t(lg, _HORIZON_LABEL_KEYS[h])} for h in _HORIZON_ORDER]
    return {
        "ok": True,
        "lang": lg,
        "horizon": hz,
        "horizon_label": t(lg, _HORIZON_LABEL_KEYS[hz]),
        "horizon_options": horizon_options,
        "as_of_utc": raw.get("as_of_utc"),
        "price_layer_note": raw.get("price_layer_note"),
        "mock_price_tick": tick,
        "mock_price_tick_note": t(lg, "spectrum.mock_tick_note") if tick == "1" else "",
        "active_model_family": families.get(hz) or "",
        "rows": out_rows,
        "allowed_horizons": list(_HORIZON_ORDER),
        "message_layer_version": 1,
        "message_layer_keys": list(MESSAGE_LAYER_V1_KEYS),
        "product_stream": "SPRINT1_TODAY_SPECTRUM_ENGINE_V0",
    }


def build_today_spectrum_summary_for_home(
    *,
    repo_root: Path,
    lang: str | None = None,
) -> dict[str, Any] | None:
    """Top 2 spectrum messages for Home feed (short horizon, base tick)."""
    sp = build_today_spectrum_payload(repo_root=repo_root, horizon="short", lang=lang, mock_price_tick="0")
    if not sp.get("ok"):
        return None
    top: list[dict[str, Any]] = []
    for r in (sp.get("rows") or [])[:2]:
        m = r.get("message") or {}
        if not isinstance(m, dict):
            continue
        top.append(
            {
                "asset_id": r.get("asset_id"),
                "spectrum_band": r.get("spectrum_band"),
                "headline": m.get("headline"),
                "one_line_take": m.get("one_line_take"),
            }
        )
    return {
        "horizon": sp.get("horizon"),
        "horizon_label": sp.get("horizon_label"),
        "active_model_family": sp.get("active_model_family"),
        "as_of_utc": sp.get("as_of_utc"),
        "top_messages": top,
    }


def _lang_text(val: Any, lang: str) -> str:
    if isinstance(val, dict):
        return str(val.get(lang) or val.get("en") or val.get("ko") or "").strip()
    return str(val or "").strip()


def _lang_signal_list(items: Any, lang: str) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for it in items:
        if isinstance(it, dict) and ("ko" in it or "en" in it):
            s = _lang_text(it, lang)
        else:
            s = str(it).strip()
        if s:
            out.append(s)
    return out


def _raw_spectrum_row(repo_root: Path, horizon: str, asset_id: str) -> dict[str, Any] | None:
    raw = load_today_spectrum_seed(repo_root)
    if not raw:
        return None
    hz = (horizon or "short").strip().lower().replace("-", "_")
    for r in (raw.get("rows_by_horizon") or {}).get(hz) or []:
        if isinstance(r, dict) and str(r.get("asset_id") or "") == asset_id:
            return r
    return None


def _information_from_seed_or_fallback(
    raw_row: dict[str, Any] | None,
    spectrum_row: dict[str, Any],
    lang: str,
) -> dict[str, Any]:
    il: dict[str, Any] = {}
    if raw_row and isinstance(raw_row.get("information_layer"), dict):
        il = raw_row["information_layer"]
    sup = _lang_signal_list(il.get("supporting_signals"), lang)
    opp = _lang_signal_list(il.get("opposing_signals"), lang)
    ev = _lang_text(il.get("evidence_summary"), lang) if il.get("evidence_summary") is not None else ""
    note = _lang_text(il.get("data_layer_note"), lang) if il.get("data_layer_note") is not None else ""
    if not sup:
        rationale = str(spectrum_row.get("rationale_summary") or "").strip()
        tension = str(spectrum_row.get("valuation_tension") or "").strip()
        if rationale:
            sup.append(rationale)
        if tension:
            sup.append(f"{t(lang, 'today_detail.tension_prefix')}: {tension}")
    if not opp:
        wc = str(spectrum_row.get("what_changed") or "").strip()
        opp.append(wc if wc else t(lang, "today_detail.fallback_opposing"))
    if not ev:
        ev = t(lang, "today_detail.fallback_evidence")
    if not note:
        note = t(lang, "today_detail.fallback_data_note")
    return {
        "supporting_signals": sup,
        "opposing_signals": opp,
        "evidence_summary": ev,
        "data_layer_note": note,
    }


def _research_from_seed_or_fallback(
    raw_row: dict[str, Any] | None,
    spectrum_row: dict[str, Any],
    lang: str,
    active_model_family: str,
    horizon: str,
) -> dict[str, Any]:
    rl: dict[str, Any] = {}
    if raw_row and isinstance(raw_row.get("research_layer"), dict):
        rl = raw_row["research_layer"]
    deeper = _lang_text(rl.get("deeper_rationale"), lang) if rl.get("deeper_rationale") is not None else ""
    mctx = _lang_text(rl.get("model_family_context"), lang) if rl.get("model_family_context") is not None else ""
    if not deeper:
        deeper = str(spectrum_row.get("rationale_summary") or "").strip() or t(lang, "today_detail.fallback_deeper")
    if not mctx:
        mctx = f"{t(lang, 'today_detail.model_stub_prefix')} {active_model_family} ({horizon})."
    return {
        "deeper_rationale": deeper,
        "model_family_context": mctx,
        "links": {
            "open_replay_panel": True,
            "prefill_ask_ai": t(lang, "today_detail.prefill_ranked_here"),
        },
    }


def build_today_object_detail_payload(
    *,
    repo_root: Path,
    asset_id: str,
    horizon: str | None,
    lang: str | None = None,
    mock_price_tick: str | None = None,
) -> dict[str, Any]:
    """Sprint 4 — one object: Message → Information → Research (seed + spectrum context)."""
    lg = normalize_lang(lang)
    aid = (asset_id or "").strip()
    if not aid:
        return {"ok": False, "error": "missing_asset_id"}
    sp = build_today_spectrum_payload(
        repo_root=repo_root,
        horizon=horizon,
        lang=lg,
        mock_price_tick=mock_price_tick,
    )
    if not sp.get("ok"):
        return sp
    hz = str(sp.get("horizon") or "")
    row: dict[str, Any] | None = None
    for r in sp.get("rows") or []:
        if isinstance(r, dict) and str(r.get("asset_id") or "") == aid:
            row = r
            break
    if not row:
        return {
            "ok": False,
            "error": "object_not_found",
            "asset_id": aid,
            "horizon": hz,
            "allowed_hint": "Pick an asset_id from GET /api/today/spectrum rows for this horizon.",
        }
    raw_row = _raw_spectrum_row(repo_root, hz, aid)
    fam = str(sp.get("active_model_family") or "")
    info = _information_from_seed_or_fallback(raw_row, row, lg)
    research = _research_from_seed_or_fallback(raw_row, row, lg, fam, hz)
    return {
        "ok": True,
        "detail_contract": "SPRINT4_MESSAGE_INFORMATION_RESEARCH_V0",
        "lang": lg,
        "horizon": hz,
        "horizon_label": sp.get("horizon_label"),
        "active_model_family": fam,
        "as_of_utc": sp.get("as_of_utc"),
        "mock_price_tick": sp.get("mock_price_tick"),
        "asset_id": aid,
        "spectrum": {
            "spectrum_position": row.get("spectrum_position"),
            "spectrum_band": row.get("spectrum_band"),
            "valuation_tension": row.get("valuation_tension"),
            "rationale_summary": row.get("rationale_summary"),
            "what_changed": row.get("what_changed"),
        },
        "message": row.get("message") or {},
        "information": info,
        "research": research,
    }
