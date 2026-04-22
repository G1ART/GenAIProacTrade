"""Sprint 1 stub — Today spectrum board payload (frozen seed + horizon switch).

Stage 0 (Unified Build Plan): when `data/mvp/metis_brain_bundle_v0.json` validates,
Today reads **Active Horizon Model Registry** + inline spectrum rows from that bundle.
Seed JSON is fallback for `METIS_TODAY_SOURCE=auto` or `seed`; **`registry` is the default when unset** (MVP Spec §3.3); `auto` tries bundle then seed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from metis_brain.bundle import BrainBundleV0, brain_bundle_path, bundle_ready_for_horizon, try_load_brain_bundle_v0
from metis_brain.schemas_v0 import ActiveHorizonRegistryEntryV0
from metis_brain.message_object_v1 import SEED_UNLINKED_ARTIFACT_ID, SEED_UNLINKED_REGISTRY_ID
from metis_brain.message_snapshots_store import upsert_message_snapshot
from metis_brain.replay_lineage_v1 import SEED_REPLAY_LINEAGE_POINTER, message_snapshot_id_v1
from phase47_runtime.message_layer_v1 import (
    MESSAGE_LAYER_V1_KEYS,
    build_message_layer_v1_for_row,
    spectrum_band_from_position,
    spectrum_quintile_from_position,
)
from phase47_runtime.phase47e_user_locale import normalize_lang, t

_ALLOWED = frozenset({"short", "medium", "medium_long", "long"})

# AGH v1 Patch 7 C2b — explicit row cap for Today spectrum payload so the
# UI JSON does not balloon linearly with universe size. Default matches
# previous ~200-ticker operational envelope; hard cap protects against
# operator-supplied overrides that would defeat the purpose.
TODAY_SPECTRUM_DEFAULT_ROWS_LIMIT = 200
TODAY_SPECTRUM_MAX_ROWS_LIMIT = 1000


def _emit_perf_log(*, fn: str, ms: float, extra: dict[str, Any] | None = None) -> None:
    """AGH v1 Patch 7 C2d — single-line structured perf log to stderr.

    See ``docs/plan/METIS_Scale_Readiness_Note_Patch7_v1.md`` §3. Keeps
    instrumentation side-channel (never raises).
    """
    try:
        rec = {
            "kind": "metis_perf",
            "fn": fn,
            "ms": round(float(ms), 3),
        }
        if extra:
            rec.update(extra)
        sys.stderr.write(json.dumps(rec, sort_keys=True) + "\n")
    except Exception:  # pragma: no cover - defensive
        pass


def _normalize_rows_limit(rows_limit: Any) -> int:
    """Coerce an operator-supplied ``rows_limit`` into the hard envelope.

    None/invalid -> default; ``<=0`` -> default; values above
    ``TODAY_SPECTRUM_MAX_ROWS_LIMIT`` are capped. Returned value is the
    *effective* limit applied to row slicing.
    """
    if rows_limit is None:
        return TODAY_SPECTRUM_DEFAULT_ROWS_LIMIT
    try:
        v = int(rows_limit)
    except (TypeError, ValueError):
        return TODAY_SPECTRUM_DEFAULT_ROWS_LIMIT
    if v <= 0:
        return TODAY_SPECTRUM_DEFAULT_ROWS_LIMIT
    if v > TODAY_SPECTRUM_MAX_ROWS_LIMIT:
        return TODAY_SPECTRUM_MAX_ROWS_LIMIT
    return v

# AGH v1 Patch 3 — bounded FIFO surfaced to Today for governed-apply badges.
# Today reads the bundle's ``recent_governed_applies`` (written atomically by
# ``registry_patch_executor``) and exposes the last N slice relevant to this
# horizon so the surface can render "a governed apply landed" badges without
# needing a new worker or a new packet stream.
_RECENT_GOVERNED_APPLIES_PER_HORIZON_CAP = 5


def _recent_governed_applies_for_horizon(
    bundle: BrainBundleV0, *, horizon: str
) -> list[dict[str, Any]]:
    raw = list(getattr(bundle, "recent_governed_applies", None) or [])
    out: list[dict[str, Any]] = []
    for ev in raw:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("horizon") or "") != horizon:
            continue
        out.append(
            {
                "target": str(ev.get("target") or ""),
                "horizon": str(ev.get("horizon") or ""),
                "registry_entry_id": str(ev.get("registry_entry_id") or ""),
                "proposal_packet_id": str(ev.get("proposal_packet_id") or ""),
                "decision_packet_id": str(ev.get("decision_packet_id") or ""),
                "applied_packet_id": str(ev.get("applied_packet_id") or ""),
                "from_active_artifact_id": str(
                    ev.get("from_active_artifact_id") or ""
                ),
                "to_active_artifact_id": str(
                    ev.get("to_active_artifact_id") or ""
                ),
                "applied_at_utc": str(ev.get("applied_at_utc") or ""),
                "spectrum_refresh_outcome": str(
                    ev.get("spectrum_refresh_outcome") or ""
                ),
                "spectrum_refresh_needs_db_rebuild": bool(
                    ev.get("spectrum_refresh_needs_db_rebuild")
                ),
            }
        )
    out.sort(key=lambda e: e.get("applied_at_utc") or "", reverse=True)
    return out[:_RECENT_GOVERNED_APPLIES_PER_HORIZON_CAP]


def _registry_surface_v1_from_bundle_entry(bundle: BrainBundleV0, ent: ActiveHorizonRegistryEntryV0) -> dict[str, Any]:
    """Product Spec §6.3 — active vs challenger artifacts surfaced for Today / Research (read-only)."""
    by_art = {a.artifact_id: a for a in bundle.artifacts}
    active_art = by_art.get(ent.active_artifact_id)
    ch_resolved: list[dict[str, Any]] = []
    for cid in list(ent.challenger_artifact_ids or []):
        ca = by_art.get(cid)
        if ca is None:
            continue
        ch_resolved.append(
            {
                "artifact_id": cid,
                "horizon": ca.horizon,
                "thesis_family": ca.thesis_family,
                "created_by": ca.created_by,
            }
        )
    # Founder-facing alias layer (Real Bundle Generalization v1 §F). Prefer the
    # active artifact's alias, then fall back to the registry entry's alias,
    # then to the raw model family name. Raw demo id stays exposed under
    # ``active_artifact_id`` for debugging.
    display_family_ko = (
        (getattr(active_art, "display_family_name_ko", "") if active_art else "")
        or str(getattr(ent, "display_family_name_ko", "") or "")
    )
    display_family_en = (
        (getattr(active_art, "display_family_name_en", "") if active_art else "")
        or str(getattr(ent, "display_family_name_en", "") or "")
    )
    display_id = (
        (getattr(active_art, "display_id", "") if active_art else "")
        or str(getattr(ent, "display_id", "") or "")
    )
    # Pragmatic Brain Absorption v1 — Milestone C. Bounded overlay influence
    # for this registry entry + its active artifact. Today surfaces overlay
    # ids (not free narrative) so founders can trace non-quant adjustments.
    overlays_raw = list(getattr(bundle, "brain_overlays", []) or [])
    brain_overlay_ids: list[str] = []
    bound_overlays: list[dict[str, Any]] = []
    for ov in overlays_raw:
        if not isinstance(ov, dict):
            continue
        ov_art = str(ov.get("artifact_id") or "")
        ov_reg = str(ov.get("registry_entry_id") or "")
        if ov_reg == ent.registry_entry_id or (
            ov_art and ov_art == ent.active_artifact_id
        ):
            oid = str(ov.get("overlay_id") or "")
            if oid:
                brain_overlay_ids.append(oid)
                bound_overlays.append(ov)
    brain_overlay_summary = _build_today_overlay_summary(bound_overlays)
    return {
        "contract": "TODAY_REGISTRY_SURFACE_V1",
        "registry_entry_id": ent.registry_entry_id,
        "horizon": ent.horizon,
        "status": ent.status,
        "active_model_family_name": ent.active_model_family_name,
        "active_artifact_id": ent.active_artifact_id,
        "active_thesis_family": active_art.thesis_family if active_art else "",
        "display_id": display_id,
        "display_family_name_ko": display_family_ko,
        "display_family_name_en": display_family_en,
        "challenger_artifact_ids": list(ent.challenger_artifact_ids or []),
        "challengers_resolved": ch_resolved,
        "universe": ent.universe,
        "scoring_endpoint_contract": ent.scoring_endpoint_contract,
        "replay_lineage_pointer": str(ent.replay_lineage_pointer or ""),
        "brain_overlay_ids": brain_overlay_ids,
        "brain_overlay_summary": brain_overlay_summary,
    }


# Bounded Non-Quant Cash-Out v1 — BNCO-2. Compact, card-ready summary emitted
# alongside ``brain_overlay_ids``. Labels come from the locale dictionary and
# never include recommendation / buy / sell wording.
_OVERLAY_SHORT_LABEL_KEYS: dict[str, str] = {
    "regime_shift": "overlay.short.regime_shift",
    "confidence_adjustment": "overlay.short.confidence_adjustment",
    "invalidation_warning": "overlay.short.invalidation_warning",
    "catalyst_window": "overlay.short.catalyst_window",
    "hazard_modifier": "overlay.short.hazard_modifier",
}


def _build_today_overlay_summary(
    bound_overlays: list[dict[str, Any]],
) -> dict[str, Any]:
    labels: list[dict[str, Any]] = []
    by_type: dict[str, int] = {}
    for ov in bound_overlays or []:
        otype = str(ov.get("overlay_type") or "")
        by_type[otype] = by_type.get(otype, 0) + 1
        key = _OVERLAY_SHORT_LABEL_KEYS.get(otype, "")
        short_ko = t("ko", key) if key else ""
        short_en = t("en", key) if key else ""
        labels.append(
            {
                "overlay_id": str(ov.get("overlay_id") or ""),
                "overlay_type": otype,
                "short_label_ko": short_ko,
                "short_label_en": short_en,
                "confidence": ov.get("confidence"),
                "expiry_or_recheck_rule": str(ov.get("expiry_or_recheck_rule") or ""),
                "expected_direction_hint": str(ov.get("expected_direction_hint") or ""),
            }
        )
    return {
        "contract": "TODAY_BRAIN_OVERLAY_SUMMARY_V1",
        "total": len(labels),
        "count_by_type": by_type,
        "labels": labels,
    }


def _registry_surface_v1_seed_fixture(*, hz: str, fam: str) -> dict[str, Any]:
    return {
        "contract": "TODAY_REGISTRY_SURFACE_V1",
        "registry_entry_id": SEED_UNLINKED_REGISTRY_ID,
        "horizon": hz,
        "status": "seed_fixture",
        "active_model_family_name": fam,
        "active_artifact_id": SEED_UNLINKED_ARTIFACT_ID,
        "active_thesis_family": "",
        "challenger_artifact_ids": [],
        "challengers_resolved": [],
        "universe": "",
        "scoring_endpoint_contract": "seed_inline_v0",
        "replay_lineage_pointer": SEED_REPLAY_LINEAGE_POINTER,
    }
_HORIZON_LABEL_KEYS = {
    "short": "spectrum.h_short",
    "medium": "spectrum.h_medium",
    "medium_long": "spectrum.h_medium_long",
    "long": "spectrum.h_long",
}
_HORIZON_ORDER = ("short", "medium", "medium_long", "long")


def _horizon_lens_compare(
    *,
    repo_root: Path,
    asset_id: str,
    current_horizon: str,
    lang: str,
    mock_price_tick: str | None,
) -> list[dict[str, Any]]:
    """Other horizons for the same asset (Stage 3 — lens compare, bounded to known spectrum rows)."""
    aid = (asset_id or "").strip()
    out: list[dict[str, Any]] = []
    tick = _normalize_mock_price_tick(mock_price_tick)
    for h in _HORIZON_ORDER:
        if h == current_horizon:
            continue
        sp = build_today_spectrum_payload(repo_root=repo_root, horizon=h, lang=lang, mock_price_tick=tick)
        if not sp.get("ok"):
            continue
        for rr in sp.get("rows") or []:
            if isinstance(rr, dict) and str(rr.get("asset_id") or "").strip() == aid:
                m = rr.get("message") if isinstance(rr.get("message"), dict) else {}
                out.append(
                    {
                        "horizon": h,
                        "horizon_label": sp.get("horizon_label"),
                        "spectrum_position": rr.get("spectrum_position"),
                        "spectrum_quintile": rr.get("spectrum_quintile"),
                        "spectrum_band": rr.get("spectrum_band"),
                        "rank_index": rr.get("rank_index"),
                        "rank_total": rr.get("rank_total"),
                        "headline": str(m.get("headline") or m.get("one_line_take") or "")[:220],
                    }
                )
                break
    return out


def _disagreement_preserving_note(
    *,
    spectrum_quintile: str,
    valuation_tension: str,
    msg: dict[str, Any],
    lang: str,
) -> str:
    """Short tension note — preserves uncertainty (no buy/sell)."""
    ten = str(valuation_tension or "").lower()
    q = str(spectrum_quintile or "neutral")
    if q in ("extreme_overpriced", "overpriced") and "compressed" in ten:
        return t(lang, "research.disagreement_stretch_vs_compression")
    if q in ("extreme_underpriced", "underpriced") and "stretched" in ten:
        return t(lang, "research.disagreement_value_vs_momentum")
    unproven = str(msg.get("what_remains_unproven") or "").strip()
    if unproven:
        return t(lang, "research.disagreement_anchor_unproven")
    return t(lang, "research.disagreement_balanced")


def _today_source_mode() -> str:
    v = (os.environ.get("METIS_TODAY_SOURCE") or "registry").strip().lower()
    if v in ("auto", "registry", "seed"):
        return v
    return "registry"


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
    """Stable union of asset_id across validated brain bundle rows and/or spectrum seed (watch UX)."""
    seen: set[str] = set()
    out: list[str] = []
    bundle, _errs = try_load_brain_bundle_v0(repo_root)
    if bundle is not None:
        for hz in _HORIZON_ORDER:
            if not bundle_ready_for_horizon(bundle, hz):
                continue
            for r in bundle.spectrum_rows_by_horizon.get(hz) or []:
                if not isinstance(r, dict):
                    continue
                aid = str(r.get("asset_id") or "").strip()
                if aid and aid not in seen:
                    seen.add(aid)
                    out.append(aid)
    raw = load_today_spectrum_seed(repo_root)
    if not raw:
        return out
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


def _build_spectrum_out_rows(
    *,
    rows_in: list[Any],
    hz: str,
    lg: str,
    fam: str,
    linked_registry_entry_id: str,
    linked_artifact_id: str,
    replay_lineage_pointer: str,
    as_of_utc: str,
) -> list[dict[str, Any]]:
    out_rows: list[dict[str, Any]] = []
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
            linked_registry_entry_id=linked_registry_entry_id,
            linked_artifact_id=linked_artifact_id,
        )
        snap = message_snapshot_id_v1(
            message_id=str(msg.get("message_id") or ""),
            registry_entry_id=linked_registry_entry_id,
            artifact_id=linked_artifact_id,
            horizon=hz,
            asset_id=str(r.get("asset_id") or ""),
            as_of_utc=as_of_utc,
        )
        out_rows.append(
            {
                "asset_id": r.get("asset_id"),
                "spectrum_position": pos,
                "valuation_tension": r.get("valuation_tension"),
                "confidence_band": r.get("confidence_band"),
                "rationale_summary": rationale_plain,
                "what_changed": wc_plain,
                "message": msg,
                "replay_lineage_pointer": replay_lineage_pointer,
                "message_snapshot_id": snap,
            }
        )
    out_rows.sort(key=lambda x: float(x.get("spectrum_position") or 0), reverse=True)
    return out_rows


def _finalize_spectrum_payload(
    *,
    hz: str,
    lg: str,
    tick: str,
    out_rows: list[dict[str, Any]],
    as_of_utc: Any,
    price_layer_note: Any,
    fam: str,
    product_stream: str,
    extra: dict[str, Any] | None = None,
    rows_limit: int | None = None,
) -> dict[str, Any]:
    pre_rank_by_asset: dict[str, int] = {}
    if tick == "1":
        pre_rank_by_asset = {str(r.get("asset_id") or "").strip(): i + 1 for i, r in enumerate(out_rows) if str(r.get("asset_id") or "").strip()}
        _apply_mock_price_invert_axis(out_rows)
        out_rows.sort(key=lambda x: float(x.get("spectrum_position") or 0), reverse=True)
    for i, r in enumerate(out_rows):
        p = float(r.get("spectrum_position") or 0)
        r["spectrum_band"] = spectrum_band_from_position(p)
        r["spectrum_quintile"] = spectrum_quintile_from_position(p)
        r["rank_index"] = i + 1
        r["rank_total"] = len(out_rows)
        aid = str(r.get("asset_id") or "").strip()
        if tick == "1" and aid and aid in pre_rank_by_asset:
            pr = pre_rank_by_asset[aid]
            po = i + 1
            if po < pr:
                r["rank_movement"] = "up"
            elif po > pr:
                r["rank_movement"] = "down"
            else:
                r["rank_movement"] = "unchanged"
        else:
            r["rank_movement"] = "steady"
    total_rows = len(out_rows)
    truncated = False
    sliced_rows = out_rows
    if rows_limit is not None and total_rows > rows_limit:
        sliced_rows = out_rows[:rows_limit]
        truncated = True
    horizon_options = [{"id": h, "label": t(lg, _HORIZON_LABEL_KEYS[h])} for h in _HORIZON_ORDER]
    base: dict[str, Any] = {
        "ok": True,
        "lang": lg,
        "horizon": hz,
        "horizon_label": t(lg, _HORIZON_LABEL_KEYS[hz]),
        "horizon_options": horizon_options,
        "as_of_utc": as_of_utc,
        "price_layer_note": price_layer_note,
        "mock_price_tick": tick,
        "mock_price_tick_note": t(lg, "spectrum.mock_tick_note") if tick == "1" else "",
        "active_model_family": fam,
        "rows": sliced_rows,
        "total_rows": total_rows,
        "truncated": truncated,
        "rows_limit": rows_limit if rows_limit is not None else total_rows,
        "allowed_horizons": list(_HORIZON_ORDER),
        "message_layer_version": 1,
        "message_layer_keys": list(MESSAGE_LAYER_V1_KEYS),
        "message_object_contract": "METIS_PRODUCT_SPEC_6_4_V1",
        "replay_lineage_join_contract": "REPLAY_LINEAGE_JOIN_V1",
        "spectrum_scoring_surface": "underpriced_overpriced_index_v1",
        "product_stream": product_stream,
    }
    if extra:
        base.update(extra)
    return base


def _message_snapshot_pair_v0(
    *,
    spectrum_payload: dict[str, Any],
    row: dict[str, Any],
    lang: str,
) -> tuple[str, dict[str, Any]] | None:
    """One persisted snapshot for Replay ↔ Today (Product Spec §5.3, §6.4)."""
    snap_id = str(row.get("message_snapshot_id") or "").strip()
    if not snap_id:
        return None
    msg = row.get("message") if isinstance(row.get("message"), dict) else {}
    aid = str(row.get("asset_id") or "").strip()
    hz = str(spectrum_payload.get("horizon") or "")
    fam = str(spectrum_payload.get("active_model_family") or "")
    rj = {
        "contract": str(spectrum_payload.get("replay_lineage_join_contract") or "REPLAY_LINEAGE_JOIN_V1"),
        "replay_lineage_pointer": str(row.get("replay_lineage_pointer") or ""),
        "message_snapshot_id": snap_id,
        "linked_registry_entry_id": str(msg.get("linked_registry_entry_id") or ""),
        "linked_artifact_id": str(msg.get("linked_artifact_id") or ""),
        "today_input_source": spectrum_payload.get("today_input_source"),
        "registry_entry_id": spectrum_payload.get("registry_entry_id"),
    }
    snap_record: dict[str, Any] = {
        "asset_id": aid,
        "horizon": hz,
        "lang": lang,
        "active_model_family": fam,
        "as_of_utc": spectrum_payload.get("as_of_utc"),
        "mock_price_tick": spectrum_payload.get("mock_price_tick"),
        "today_input_source": spectrum_payload.get("today_input_source"),
        "registry_entry_id": spectrum_payload.get("registry_entry_id"),
        "message": msg,
        "spectrum": {
            "spectrum_position": row.get("spectrum_position"),
            "spectrum_band": row.get("spectrum_band"),
            "spectrum_quintile": row.get("spectrum_quintile"),
            "rank_index": row.get("rank_index"),
            "rank_total": row.get("rank_total"),
            "rank_movement": row.get("rank_movement"),
            "valuation_tension": row.get("valuation_tension"),
            "rationale_summary": row.get("rationale_summary"),
            "what_changed": row.get("what_changed"),
        },
        "replay_lineage_join_v1": rj,
    }
    _rs = spectrum_payload.get("registry_surface_v1")
    if isinstance(_rs, dict):
        snap_record["registry_surface_v1"] = _rs
    return snap_id, snap_record


def persist_message_snapshots_for_spectrum_payload(repo_root: Path, spectrum_payload: dict[str, Any]) -> None:
    """Persist all row snapshots so Replay can resolve IDs without opening object detail first.

    AGH v1 Patch 9 C·C — callers are encouraged to persist lazily via
    ``persist_message_snapshot_for_spectrum_row`` when the operator
    actually opens an object detail. This full-sweep helper is retained
    for backfill / one-shot evidence scripts (so the Replay ID space can
    be primed deliberately) but is no longer called from the Today
    spectrum build path, which at 500-ticker scale paid the write cost
    on every /api/today/spectrum hit.
    """
    if not spectrum_payload.get("ok"):
        return
    lg = normalize_lang(str(spectrum_payload.get("lang") or "en"))
    for row in spectrum_payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        pair = _message_snapshot_pair_v0(spectrum_payload=spectrum_payload, row=row, lang=lg)
        if pair:
            sid, rec = pair
            upsert_message_snapshot(repo_root, sid, rec)


def persist_message_snapshot_for_spectrum_row(
    repo_root: Path,
    spectrum_payload: dict[str, Any],
    row: dict[str, Any],
) -> str | None:
    """AGH v1 Patch 9 C·C — persist exactly one row's snapshot.

    Called from ``build_today_object_detail_payload`` when an operator
    opens a specific asset; the rest of the spectrum remains untouched
    on disk. Returns the snapshot id on success, or ``None`` when the
    pair cannot be built (identical to the full-sweep contract).
    """
    if not spectrum_payload.get("ok"):
        return None
    if not isinstance(row, dict):
        return None
    lg = normalize_lang(str(spectrum_payload.get("lang") or "en"))
    pair = _message_snapshot_pair_v0(spectrum_payload=spectrum_payload, row=row, lang=lg)
    if not pair:
        return None
    sid, rec = pair
    upsert_message_snapshot(repo_root, sid, rec)
    return sid


def build_today_spectrum_payload(
    *,
    repo_root: Path,
    horizon: str | None,
    lang: str | None = None,
    mock_price_tick: str | None = None,
    rows_limit: int | None = None,
) -> dict[str, Any]:
    """Spectrum rows for one horizon — registry bundle first when valid, else seed (mode-dependent).

    AGH v1 Patch 7 C2b: ``rows_limit`` is an **optional** response-size
    guardrail. When None, behaves exactly as before except the output now
    declares ``total_rows`` / ``truncated`` so clients can surface the
    truth. When a positive int, rows are sliced to at most
    ``min(rows_limit, TODAY_SPECTRUM_MAX_ROWS_LIMIT)`` AFTER all business
    logic has run (rank/quintile/movement are computed against the full
    population so top-N slicing does not lie about rank).
    """
    t0 = perf_counter()
    lg = normalize_lang(lang)
    tick = _normalize_mock_price_tick(mock_price_tick)
    hz = (horizon or "short").strip().lower().replace("-", "_")
    if hz not in _ALLOWED:
        return {
            "ok": False,
            "error": "invalid_horizon",
            "allowed": sorted(_ALLOWED),
        }
    effective_limit = _normalize_rows_limit(rows_limit)
    mode = _today_source_mode()
    brain_skip_reasons: list[str] = []

    if mode != "seed":
        bundle, errs = try_load_brain_bundle_v0(repo_root)
        if bundle is not None and bundle_ready_for_horizon(bundle, hz):
            ent = next(e for e in bundle.registry_entries if e.status == "active" and e.horizon == hz)
            rows_in = bundle.spectrum_rows_by_horizon[hz]
            fam = ent.active_model_family_name
            out_rows = _build_spectrum_out_rows(
                rows_in=rows_in,
                hz=hz,
                lg=lg,
                fam=fam,
                linked_registry_entry_id=ent.registry_entry_id,
                linked_artifact_id=ent.active_artifact_id,
                replay_lineage_pointer=str(ent.replay_lineage_pointer or ""),
                as_of_utc=str(bundle.as_of_utc or ""),
            )
            out = _finalize_spectrum_payload(
                hz=hz,
                lg=lg,
                tick=tick,
                out_rows=out_rows,
                as_of_utc=bundle.as_of_utc,
                price_layer_note=bundle.price_layer_note,
                fam=fam,
                product_stream="METIS_BRAIN_REGISTRY_V0",
                extra={
                    "today_input_source": "active_horizon_model_registry_v0",
                    "registry_entry_id": ent.registry_entry_id,
                    "active_artifact_id": ent.active_artifact_id,
                    "replay_lineage_pointer": ent.replay_lineage_pointer,
                    "scoring_endpoint_contract": ent.scoring_endpoint_contract,
                    "registry_surface_v1": _registry_surface_v1_from_bundle_entry(bundle, ent),
                    "recent_governed_applies_for_horizon": (
                        _recent_governed_applies_for_horizon(bundle, horizon=hz)
                    ),
                },
                rows_limit=effective_limit,
            )
            # AGH v1 Patch 9 C·C — snapshot persistence moved to
            # ``build_today_object_detail_payload``. The spectrum build
            # no longer issues N disk writes per /api/today/spectrum hit.
            _emit_perf_log(
                fn="today_spectrum.build_today_spectrum_payload",
                ms=(perf_counter() - t0) * 1000.0,
                extra={
                    "horizon": hz,
                    "source": "registry",
                    "total_rows": out.get("total_rows"),
                    "truncated": out.get("truncated"),
                },
            )
            return out
        if mode == "registry":
            p = brain_bundle_path(repo_root)
            if not p.is_file():
                return {
                    "ok": False,
                    "error": "brain_bundle_missing",
                    "hint": str(p),
                }
            return {
                "ok": False,
                "error": "brain_bundle_invalid",
                "details": errs or ["unknown"],
                "hint": str(p),
            }
        brain_skip_reasons = errs or []

    raw = load_today_spectrum_seed(repo_root)
    if not raw:
        if brain_skip_reasons:
            return {
                "ok": False,
                "error": "spectrum_seed_missing_and_brain_bundle_invalid",
                "brain_bundle_details": brain_skip_reasons,
                "hint": str(_seed_path(repo_root)),
            }
        return {
            "ok": False,
            "error": "spectrum_seed_missing",
            "hint": str(_seed_path(repo_root)),
        }
    byh = raw.get("rows_by_horizon") or {}
    rows_in = byh.get(hz) or []
    families = raw.get("active_model_family_by_horizon") or {}
    fam = families.get(hz) or ""
    out_rows = _build_spectrum_out_rows(
        rows_in=rows_in,
        hz=hz,
        lg=lg,
        fam=fam,
        linked_registry_entry_id=SEED_UNLINKED_REGISTRY_ID,
        linked_artifact_id=SEED_UNLINKED_ARTIFACT_ID,
        replay_lineage_pointer=SEED_REPLAY_LINEAGE_POINTER,
        as_of_utc=str(raw.get("as_of_utc") or ""),
    )
    extra: dict[str, Any] = {
        "today_input_source": "today_spectrum_seed_v1",
        "registry_surface_v1": _registry_surface_v1_seed_fixture(hz=hz, fam=fam),
    }
    if brain_skip_reasons:
        extra["brain_bundle_skipped"] = {"reasons": brain_skip_reasons}
    out = _finalize_spectrum_payload(
        hz=hz,
        lg=lg,
        tick=tick,
        out_rows=out_rows,
        as_of_utc=raw.get("as_of_utc"),
        price_layer_note=raw.get("price_layer_note"),
        fam=fam,
        product_stream="SPRINT1_TODAY_SPECTRUM_ENGINE_V0",
        extra=extra,
        rows_limit=effective_limit,
    )
    # AGH v1 Patch 9 C·C — snapshot persistence moved to
    # ``build_today_object_detail_payload`` (lazy, per-row).
    _emit_perf_log(
        fn="today_spectrum.build_today_spectrum_payload",
        ms=(perf_counter() - t0) * 1000.0,
        extra={
            "horizon": hz,
            "source": "seed",
            "total_rows": out.get("total_rows"),
            "truncated": out.get("truncated"),
        },
    )
    return out


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
    hz = (horizon or "short").strip().lower().replace("-", "_")
    bundle, _errs = try_load_brain_bundle_v0(repo_root)
    if bundle is not None and bundle_ready_for_horizon(bundle, hz):
        for r in bundle.spectrum_rows_by_horizon.get(hz) or []:
            if isinstance(r, dict) and str(r.get("asset_id") or "") == asset_id:
                return r
    raw = load_today_spectrum_seed(repo_root)
    if not raw:
        return None
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


def _overlay_explanations_for_surface(
    *,
    repo_root: Path,
    registry_surface: dict[str, Any],
) -> list[dict[str, Any]]:
    """Bounded Non-Quant Cash-Out v1 — BNCO-3.

    Emit per-asset overlay explanations by pulling full overlay records from
    the current bundle and filtering to the ids surfaced on
    ``registry_surface_v1.brain_overlay_ids``. Every string is sourced from
    the bundled overlay record (or its direct seed fields) — we never
    synthesize free-text here. ``fact_vs_interpretation`` is hard-pinned to
    ``"interpretation"`` so UI treats the block as opinion, never as fact.
    """

    overlay_ids = [str(x) for x in (registry_surface.get("brain_overlay_ids") or []) if x]
    if not overlay_ids:
        return []
    bundle, _errs = try_load_brain_bundle_v0(repo_root)
    if bundle is None:
        return []
    by_id: dict[str, dict[str, Any]] = {}
    for ov in getattr(bundle, "brain_overlays", []) or []:
        if not isinstance(ov, dict):
            continue
        oid = str(ov.get("overlay_id") or "")
        if oid:
            by_id[oid] = ov
    out: list[dict[str, Any]] = []
    for oid in overlay_ids:
        ov = by_id.get(oid)
        if not ov:
            continue
        refs = ov.get("source_artifact_refs") or []
        first_ref_summary = ""
        if isinstance(refs, list) and refs:
            first = refs[0]
            if isinstance(first, dict):
                first_ref_summary = str(first.get("summary") or "")
        source_summary = (
            str(ov.get("source_artifact_refs_summary") or "") or first_ref_summary
        )
        reasons = ov.get("reasons") or []
        reasons_text = "; ".join(str(r) for r in reasons if isinstance(r, str)) if reasons else ""
        pit = ov.get("pit_timestamp_window") or {}
        out.append(
            {
                "overlay_id": oid,
                "overlay_type": str(ov.get("overlay_type") or ""),
                "why_exists": reasons_text,
                "source_artifact_ref_summary": source_summary,
                "what_it_changes": str(ov.get("what_it_changes") or ""),
                "recheck_rule": str(ov.get("expiry_or_recheck_rule") or ""),
                "confidence": ov.get("confidence"),
                "counter_interpretation_present": bool(
                    ov.get("counter_interpretation_present")
                ),
                "expected_direction_hint": str(
                    ov.get("expected_direction_hint") or ""
                ),
                "pit_window": {
                    "starts_at": str(pit.get("starts_at") or "") if isinstance(pit, dict) else "",
                    "ends_at": str(pit.get("ends_at") or "") if isinstance(pit, dict) else "",
                },
                "fact_vs_interpretation": "interpretation",
            }
        )
    return out


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


def _sandbox_options_v1_from_registry_surface(
    registry_surface: dict[str, Any] | None,
    bundle: BrainBundleV0 | None,
) -> dict[str, Any]:
    """AGH v1 Patch 5 — deterministic catalog of bounded sandbox options
    available for a registry entry.

    The catalog is derived purely from the brain bundle: each
    ``research_factor_bindings_v1`` binding on the active
    ``registry_entry`` becomes one ``validation_rerun`` option.
    Operators can pass the resulting ``target_spec`` verbatim to the
    ``harness-sandbox-request`` CLI. Today surfaces the options but
    NEVER triggers the job — the active registry remains operator-gated.
    """

    if not isinstance(registry_surface, dict):
        return {
            "contract": "TODAY_SANDBOX_OPTIONS_V1",
            "supported_kinds": ["validation_rerun"],
            "options": [],
            "registry_entry_id": None,
        }
    rid = str(registry_surface.get("registry_entry_id") or "")
    horizon = str(registry_surface.get("horizon") or "")
    universe = str(registry_surface.get("universe") or "")
    bindings: list[dict[str, str]] = []
    if bundle is not None and rid:
        for ent in bundle.registry_entries:
            if str(ent.registry_entry_id or "") != rid:
                continue
            for b in list(getattr(ent, "research_factor_bindings_v1", []) or []):
                if not isinstance(b, dict):
                    continue
                bindings.append(
                    {
                        "factor_name": str(b.get("factor_name") or "").strip(),
                        "return_basis": str(b.get("return_basis") or "").strip(),
                    }
                )
            break

    HORIZON_TO_HORIZON_TYPE = {
        "short": "next_month",
        "medium": "next_quarter",
        "medium_long": "next_half_year",
        "long": "next_year",
    }
    hz_type_hint = HORIZON_TO_HORIZON_TYPE.get(horizon, "")

    options: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for b in bindings:
        fname = b["factor_name"]
        rb = b["return_basis"] or "raw"
        if not fname:
            continue
        key = (fname, universe, hz_type_hint, rb)
        if key in seen:
            continue
        seen.add(key)
        options.append(
            {
                "sandbox_kind": "validation_rerun",
                "registry_entry_id": rid,
                "horizon": horizon,
                "target_spec": {
                    "factor_name": fname,
                    "universe_name": universe,
                    "horizon_type": hz_type_hint,
                    "return_basis": rb,
                },
                "label_ko": (
                    f"{fname} 재검증 ({rb}) · {universe} · {hz_type_hint}"
                ),
                "label_en": (
                    f"Rerun {fname} validation ({rb}) · {universe} · {hz_type_hint}"
                ),
            }
        )

    return {
        "contract": "TODAY_SANDBOX_OPTIONS_V1",
        "supported_kinds": ["validation_rerun"],
        "registry_entry_id": rid or None,
        "horizon": horizon or None,
        "universe": universe or None,
        "horizon_type_hint": hz_type_hint or None,
        "options": options,
        "operator_gated_note_ko": (
            "샌드박스 옵션은 운영자 승인 후에만 실행됩니다. "
            "Today 활성 레지스트리는 이 경로로 변경되지 않습니다."
        ),
        "operator_gated_note_en": (
            "Sandbox options run only after operator approval. "
            "The active Today registry is never mutated from this path."
        ),
    }


def _research_status_badges_v1_from_bundle(
    registry_surface: dict[str, Any] | None,
    bundle: BrainBundleV0 | None,
) -> dict[str, Any]:
    """AGH v1 Patch 5 — deterministic research status badges derived
    from the brain bundle + the cited ``registry_surface``.

    Badges surfaced:
      * ``active_artifact_recently_applied`` — most-recent
        ``recent_governed_applies`` entry for this registry_entry shows
        ``target == "registry_entry_artifact_promotion"``.
      * ``spectrum_refresh_needs_db_rebuild`` — most-recent entry's
        ``spectrum_refresh_needs_db_rebuild`` is true; the Today
        rationale rows may still reflect the prior artifact.
      * ``has_research_factor_bindings`` — the registry entry declares
        at least one factor binding, so ``sandbox_options_v1`` is
        populated.

    Badges are simple ``{code, severity, label_ko, label_en}`` dicts; the
    surface never embeds free-form copy from the LLM.
    """

    badges: list[dict[str, Any]] = []
    rid = str((registry_surface or {}).get("registry_entry_id") or "")
    horizon = str((registry_surface or {}).get("horizon") or "")
    entry = None
    if bundle is not None and rid:
        for e in bundle.registry_entries:
            if str(e.registry_entry_id or "") == rid:
                entry = e
                break

    has_bindings = bool(
        entry is not None
        and list(getattr(entry, "research_factor_bindings_v1", []) or [])
    )
    if has_bindings:
        badges.append(
            {
                "code": "has_research_factor_bindings",
                "severity": "info",
                "label_ko": "재검증 샌드박스 옵션 있음",
                "label_en": "Validation rerun sandbox options available",
            }
        )
    else:
        badges.append(
            {
                "code": "no_research_factor_bindings",
                "severity": "neutral",
                "label_ko": "재검증 샌드박스 바인딩 없음",
                "label_en": "No validation rerun bindings configured",
            }
        )

    recent_applies = list(getattr(bundle, "recent_governed_applies", []) or []) if bundle is not None else []
    matching_apply: dict[str, Any] | None = None
    for tail in reversed(recent_applies):
        if not isinstance(tail, dict):
            continue
        if str(tail.get("registry_entry_id") or "") != rid:
            continue
        if horizon and str(tail.get("horizon") or "") != horizon:
            continue
        matching_apply = tail
        break

    if matching_apply is not None:
        badges.append(
            {
                "code": "active_artifact_recently_applied",
                "severity": "info",
                "label_ko": "최근 활성 아티팩트가 거버넌스로 교체됨",
                "label_en": "Active artifact recently swapped via governance",
                "applied_at_utc": str(matching_apply.get("applied_at_utc") or ""),
                "from_active_artifact_id": str(
                    matching_apply.get("from_active_artifact_id") or ""
                ),
                "to_active_artifact_id": str(
                    matching_apply.get("to_active_artifact_id") or ""
                ),
            }
        )
        if bool(matching_apply.get("spectrum_refresh_needs_db_rebuild")):
            badges.append(
                {
                    "code": "spectrum_refresh_needs_db_rebuild",
                    "severity": "warning",
                    "label_ko": "스펙트럼 설명 row가 구 아티팩트 기준일 수 있음 (재빌드 필요)",
                    "label_en": "Spectrum rationale rows may still reflect prior artifact (db rebuild needed)",
                }
            )
    else:
        badges.append(
            {
                "code": "no_recent_governed_apply",
                "severity": "neutral",
                "label_ko": "최근 거버넌스 적용 기록 없음",
                "label_en": "No recent governed apply recorded",
            }
        )

    return {
        "contract": "TODAY_RESEARCH_STATUS_BADGES_V1",
        "registry_entry_id": rid or None,
        "horizon": horizon or None,
        "badges": badges,
    }


def _latest_research_structured_v1_for_asset(
    *,
    repo_root: Path,
    asset_id: str,
    horizon: str,
) -> dict[str, Any] | None:
    """AGH v1 Patch 6 — best-effort lookup of the latest
    ``UserQueryActionPacketV1.payload.llm_response.research_structured_v1``
    for the given ``asset_id``.

    Returns ``None`` when:
      * the harness store is not configured (fresh clones / dev),
      * no UserQueryActionPacket exists for this asset,
      * the latest packet's LLM response has no structured block, OR
      * ``asset_id`` is empty.

    Never raises — the Today surface renders an empty state instead.
    """

    aid = str(asset_id or "").strip()
    if not aid:
        return None
    try:
        from agentic_harness.runtime import build_store
    except Exception:
        return None
    try:
        store = build_store()
    except Exception:
        return None
    try:
        packets = list(
            store.list_packets(packet_type="UserQueryActionPacketV1", limit=200)
            or []
        )
    except Exception:
        return None

    def _sort_key(p: dict[str, Any]) -> str:
        return str(p.get("created_at_utc") or "")

    packets.sort(key=_sort_key, reverse=True)
    for p in packets:
        ts = (p.get("target_scope") or {}) if isinstance(p.get("target_scope"), dict) else {}
        if str(ts.get("asset_id") or "") != aid:
            continue
        payload = p.get("payload") or {}
        llm = payload.get("llm_response") or {}
        if not isinstance(llm, dict):
            continue
        rs = llm.get("research_structured_v1")
        if not isinstance(rs, dict):
            continue
        rs = dict(rs)
        rs.setdefault("cited_packet_ids", list(llm.get("cited_packet_ids") or []))
        rs.setdefault("_source_packet_id", p.get("packet_id"))
        rs.setdefault("_routed_kind", str(payload.get("routed_kind") or ""))
        rs.setdefault("_horizon_hint", horizon)
        return rs
    return None


def build_today_object_detail_payload(
    *,
    repo_root: Path,
    asset_id: str,
    horizon: str | None,
    lang: str | None = None,
    mock_price_tick: str | None = None,
) -> dict[str, Any]:
    """Sprint 4 — one object: Message → Information → Research (seed + spectrum context)."""
    t0 = perf_counter()
    lg = normalize_lang(lang)
    aid = (asset_id or "").strip()
    if not aid:
        return {"ok": False, "error": "missing_asset_id"}
    # AGH v1 Patch 7 C2b: object detail needs the *full* population so it
    # can locate any asset regardless of the operator-visible row cap.
    sp = build_today_spectrum_payload(
        repo_root=repo_root,
        horizon=horizon,
        lang=lg,
        mock_price_tick=mock_price_tick,
        rows_limit=TODAY_SPECTRUM_MAX_ROWS_LIMIT,
    )
    if not sp.get("ok"):
        _emit_perf_log(
            fn="today_spectrum.build_today_object_detail_payload",
            ms=(perf_counter() - t0) * 1000.0,
            extra={"asset_id": aid, "ok": False},
        )
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
    # AGH v1 Patch 9 C·C — snapshot lazy generation. Only at the moment
    # an operator opens an object detail do we persist that row's
    # message snapshot. The Today spectrum build path no longer pays
    # this IO cost for every row on every hit.
    try:
        persist_message_snapshot_for_spectrum_row(repo_root, sp, row)
    except Exception:  # pragma: no cover — snapshot IO must not break detail
        pass
    raw_row = _raw_spectrum_row(repo_root, hz, aid)
    fam = str(sp.get("active_model_family") or "")
    info = _information_from_seed_or_fallback(raw_row, row, lg)
    research = _research_from_seed_or_fallback(raw_row, row, lg, fam, hz)
    rlinks = research.get("links")
    if isinstance(rlinks, dict):
        rlinks = {**rlinks, "replay_highlight_asset_id": aid}
        research = {**research, "links": rlinks}
    msg = row.get("message") or {}
    qz = str(row.get("spectrum_quintile") or "neutral")
    snap_id = str(row.get("message_snapshot_id") or "").strip()
    research = {
        **research,
        "message_snapshot_id": snap_id,
        "horizon_lens_compare": _horizon_lens_compare(
            repo_root=repo_root,
            asset_id=aid,
            current_horizon=hz,
            lang=lg,
            mock_price_tick=mock_price_tick,
        ),
        "disagreement_preserving": {
            "note": _disagreement_preserving_note(
                spectrum_quintile=qz,
                valuation_tension=str(row.get("valuation_tension") or ""),
                msg=msg if isinstance(msg, dict) else {},
                lang=lg,
            )
        },
        "overlay_explanations": _overlay_explanations_for_surface(
            repo_root=repo_root,
            registry_surface=sp.get("registry_surface_v1") or {},
        ),
    }

    rj = {
        "contract": str(sp.get("replay_lineage_join_contract") or "REPLAY_LINEAGE_JOIN_V1"),
        "replay_lineage_pointer": str(row.get("replay_lineage_pointer") or ""),
        "message_snapshot_id": snap_id,
        "linked_registry_entry_id": str(msg.get("linked_registry_entry_id") or ""),
        "linked_artifact_id": str(msg.get("linked_artifact_id") or ""),
        "today_input_source": sp.get("today_input_source"),
        "registry_entry_id": sp.get("registry_entry_id"),
    }
    pair = _message_snapshot_pair_v0(spectrum_payload=sp, row=row, lang=lg)
    if pair:
        upsert_message_snapshot(repo_root, pair[0], pair[1])

    registry_surface = sp.get("registry_surface_v1") or {}
    bundle_for_surface, _bundle_errs = try_load_brain_bundle_v0(repo_root)
    sandbox_options_v1 = _sandbox_options_v1_from_registry_surface(
        registry_surface,
        bundle_for_surface,
    )
    research_status_badges_v1 = _research_status_badges_v1_from_bundle(
        registry_surface,
        bundle_for_surface,
    )
    # AGH v1 Patch 6 — surface the most recent research_structured_v1 for
    # this asset/horizon so the Research renderer has bullets to show.
    # Best-effort: if the harness store is not available, we quietly
    # return None and the UI renders its empty state.
    research_structured_v1 = _latest_research_structured_v1_for_asset(
        repo_root=repo_root,
        asset_id=aid,
        horizon=hz,
    )

    result = {
        "ok": True,
        "detail_contract": "SPRINT4_MESSAGE_INFORMATION_RESEARCH_V0",
        "lang": lg,
        "horizon": hz,
        "horizon_label": sp.get("horizon_label"),
        "active_model_family": fam,
        "as_of_utc": sp.get("as_of_utc"),
        "mock_price_tick": sp.get("mock_price_tick"),
        "asset_id": aid,
        "message_snapshot_id": snap_id,
        "spectrum": {
            "spectrum_position": row.get("spectrum_position"),
            "spectrum_band": row.get("spectrum_band"),
            "spectrum_quintile": row.get("spectrum_quintile"),
            "rank_index": row.get("rank_index"),
            "rank_total": row.get("rank_total"),
            "rank_movement": row.get("rank_movement"),
            "valuation_tension": row.get("valuation_tension"),
            "rationale_summary": row.get("rationale_summary"),
            "what_changed": row.get("what_changed"),
        },
        "message": msg,
        "information": info,
        "research": research,
        "replay_lineage_join_v1": rj,
        "registry_surface_v1": sp.get("registry_surface_v1"),
        "sandbox_options_v1": sandbox_options_v1,
        "research_status_badges_v1": research_status_badges_v1,
        "research_structured_v1": research_structured_v1,
    }
    _emit_perf_log(
        fn="today_spectrum.build_today_object_detail_payload",
        ms=(perf_counter() - t0) * 1000.0,
        extra={"asset_id": aid, "horizon": hz, "ok": True},
    )
    return result
