"""Sprint 6 — bounded Custom Research Sandbox v1 (deterministic, no LLM).

Hypothesis text is echoed and cross-cut against the frozen Today spectrum seed
and Phase 46 bundle read-model. PIT mode `pit_stub` is an honest placeholder for
future point-in-time replay wiring.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from phase47_runtime.phase47e_user_locale import normalize_lang, t
from phase47_runtime.today_spectrum import (
    _ALLOWED,
    _HORIZON_ORDER,
    build_today_object_detail_payload,
    build_today_spectrum_payload,
)

CONTRACT = "SANDBOX_V1"
_MAX_HYP = 1800
_MAX_ASSET = 64


def _run_id(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def run_sandbox_v1(
    *,
    bundle: dict[str, Any],
    repo_root: Path,
    body: dict[str, Any],
    lang: str | None = None,
) -> dict[str, Any]:
    lg = normalize_lang(lang)
    hyp = str(body.get("hypothesis") or body.get("question") or "").strip()
    if not hyp:
        return {"ok": False, "error": "hypothesis_required", "contract": CONTRACT}
    if len(hyp) > _MAX_HYP:
        hyp = hyp[: _MAX_HYP - 1] + "…"

    sid_snap = str(body.get("message_snapshot_id") or "").strip()
    snap_row: dict[str, Any] | None = None
    if sid_snap:
        from metis_brain.message_snapshots_store import get_message_snapshot

        raw = get_message_snapshot(repo_root, sid_snap)
        if not raw:
            return {
                "ok": False,
                "error": "message_snapshot_not_found",
                "message_snapshot_id": sid_snap,
                "contract": CONTRACT,
            }
        snap_row = raw

    aid = str(body.get("asset_id") or "").strip()[:_MAX_ASSET]
    if not aid and snap_row:
        aid = str(snap_row.get("asset_id") or "").strip()[:_MAX_ASSET]

    raw_hz = body.get("horizon")
    hz_src = raw_hz if raw_hz is not None else ((snap_row or {}).get("horizon") or "short")
    hz = str(hz_src or "short").strip().lower().replace("-", "_")
    if hz not in _ALLOWED:
        return {"ok": False, "error": "invalid_horizon", "allowed": sorted(_ALLOWED), "contract": CONTRACT}

    pit_mode = str(body.get("pit_mode") or body.get("mode") or "snapshot").strip().lower()
    if pit_mode not in ("snapshot", "pit_stub"):
        pit_mode = "snapshot"
    mt = str(body.get("mock_price_tick") or "0").strip()
    if mt not in ("0", "1"):
        mt = "0"

    gen_utc = str(bundle.get("phase46_generated_utc") or "")
    rid = _run_id([hyp, aid, hz, pit_mode, mt, gen_utc])

    bullets: list[str] = []
    hyp_snip = hyp if len(hyp) <= 420 else hyp[:419] + "…"
    bullets.append(f"{t(lg, 'sandbox.bullet_hypothesis_prefix')} {hyp_snip}")
    if snap_row:
        msg0 = snap_row.get("message") if isinstance(snap_row.get("message"), dict) else {}
        hl0 = str(msg0.get("headline") or "").strip()
        if hl0:
            sn = sid_snap if len(sid_snap) <= 24 else sid_snap[:20] + "…"
            bullets.append(f"[message_snapshot {sn}] {hl0[:320]}{'…' if len(hl0) > 320 else ''}")

    horizon_scan: list[dict[str, Any]] = []

    if aid:
        obj = build_today_object_detail_payload(
            repo_root=repo_root,
            asset_id=aid,
            horizon=hz,
            lang=lg,
            mock_price_tick=mt,
        )
        if obj.get("ok"):
            sp = obj.get("spectrum") or {}
            msg = obj.get("message") or {}
            hz_lbl = str(obj.get("horizon_label") or hz)
            band = str(sp.get("spectrum_band") or "—")
            bullets.append(t(lg, "sandbox.bullet_selected_lens").format(hz_label=hz_lbl, band=band))
            hl = str(msg.get("headline") or "").strip()
            if hl:
                hl = hl[:280] + ("…" if len(hl) > 280 else "")
                bullets.append(f"{t(lg, 'sandbox.bullet_headline_prefix')} {hl}")
            for h2 in _HORIZON_ORDER:
                sp2 = build_today_spectrum_payload(repo_root=repo_root, horizon=h2, lang=lg, mock_price_tick=mt)
                if not sp2.get("ok"):
                    continue
                row = None
                for r in sp2.get("rows") or []:
                    if isinstance(r, dict) and str(r.get("asset_id") or "") == aid:
                        row = r
                        break
                if not row:
                    continue
                m2 = row.get("message") or {}
                hline = str(m2.get("headline") or "").strip()[:200]
                horizon_scan.append(
                    {
                        "horizon": h2,
                        "horizon_label": str(sp2.get("horizon_label") or h2),
                        "spectrum_band": row.get("spectrum_band"),
                        "spectrum_position": row.get("spectrum_position"),
                        "headline": hline,
                    }
                )
        else:
            bullets.append(t(lg, "sandbox.bullet_asset_not_on_board").format(asset_id=aid))
            for h2 in _HORIZON_ORDER:
                sp2 = build_today_spectrum_payload(repo_root=repo_root, horizon=h2, lang=lg, mock_price_tick=mt)
                if not sp2.get("ok"):
                    continue
                for r in sp2.get("rows") or []:
                    if isinstance(r, dict) and str(r.get("asset_id") or "") == aid:
                        m2 = r.get("message") or {}
                        horizon_scan.append(
                            {
                                "horizon": h2,
                                "horizon_label": str(sp2.get("horizon_label") or h2),
                                "spectrum_band": r.get("spectrum_band"),
                                "spectrum_position": r.get("spectrum_position"),
                                "headline": str(m2.get("headline") or "").strip()[:200],
                            }
                        )
                        break
    else:
        bullets.append(t(lg, "sandbox.bullet_cohort_scope"))
        cohort = (bundle.get("cockpit_state") or {}).get("cohort_aggregate") or {}
        dc = cohort.get("decision_card") or {}
        title = str(dc.get("title") or "").strip()
        body_dc = str(dc.get("body") or "").strip()
        if title:
            snip = (title + (" — " + body_dc[:160] if body_dc else ""))[:320]
            bullets.append(f"{t(lg, 'sandbox.bullet_decision_card_prefix')} {snip}")
        pitch = bundle.get("representative_pitch") or {}
        top = str(pitch.get("top_level_pitch") or "").strip()
        if top:
            bullets.append(f"{t(lg, 'sandbox.bullet_pitch_prefix')} {top[:300]}{'…' if len(top) > 300 else ''}")

    pit_note: str | None = None
    if pit_mode == "pit_stub":
        pit_note = t(lg, "sandbox.pit_stub_note")

    next_actions = [
        {"label": t(lg, "sandbox.action_open_today_detail"), "panel": "today_detail", "requires_asset": True},
        {"label": t(lg, "sandbox.action_open_replay"), "panel": "replay"},
        {"label": t(lg, "sandbox.action_open_ask_ai"), "panel": "ask_ai"},
    ]

    return {
        "ok": True,
        "contract": CONTRACT,
        "run_id": rid,
        "lang": lg,
        "inputs_echo": {
            "hypothesis": hyp,
            "asset_id": aid or None,
            "horizon": hz,
            "pit_mode": pit_mode,
            "mock_price_tick": mt,
            "message_snapshot_id": sid_snap or None,
        },
        "result": {
            "summary_bullets": bullets,
            "horizon_scan": horizon_scan or None,
            "pit_note": pit_note,
            "disclaimer": t(lg, "sandbox.disclaimer"),
        },
        "next_actions": next_actions,
    }
