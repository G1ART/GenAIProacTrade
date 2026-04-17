"""Sprint 7 — Reality Replay: decision memory + horizon strip (deterministic, no price engine)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase46.decision_trace_ledger import list_decisions

from phase47_runtime.phase47e_user_locale import normalize_lang, t
from phase47_runtime.sandbox_runs_ledger import list_sandbox_runs
from phase47_runtime.today_spectrum import _HORIZON_ORDER, build_today_spectrum_payload

CONTRACT = "REPLAY_AGING_BRIEF_V1"
JOIN_CONTRACT = "REPLAY_LINEAGE_JOIN_V1"


def build_replay_aging_brief(
    *,
    repo_root: Path,
    decision_ledger_path: Path,
    sandbox_ledger_path: Path,
    asset_id: str,
    lang: str | None = None,
) -> dict[str, Any]:
    aid = (asset_id or "").strip()
    if not aid:
        return {"ok": False, "error": "asset_id_required", "contract": CONTRACT}
    lg = normalize_lang(lang)

    decs = [d for d in list_decisions(decision_ledger_path) if str(d.get("asset_id") or "").strip() == aid]
    dec_tail = list(reversed(decs[-8:]))
    slim_dec: list[dict[str, Any]] = []
    for d in dec_tail:
        note = str(d.get("founder_note") or "")
        slim_dec.append(
            {
                "timestamp": d.get("timestamp"),
                "decision_type": d.get("decision_type"),
                "snippet": note[:200] + ("…" if len(note) > 200 else ""),
            }
        )

    runs_all = list_sandbox_runs(sandbox_ledger_path, limit=120)
    sb_match = [r for r in runs_all if str((r.get("inputs_echo") or {}).get("asset_id") or "").strip() == aid][:8]
    slim_sb: list[dict[str, Any]] = []
    for r in sb_match:
        hyp = str((r.get("inputs_echo") or {}).get("hypothesis") or "")
        slim_sb.append(
            {
                "saved_at": r.get("saved_at"),
                "run_id": r.get("run_id"),
                "hypothesis_snip": hyp[:160] + ("…" if len(hyp) > 160 else ""),
            }
        )

    strip: list[dict[str, Any]] = []
    for h in _HORIZON_ORDER:
        sp = build_today_spectrum_payload(repo_root=repo_root, horizon=h, lang=lg, mock_price_tick="0")
        if not sp.get("ok"):
            continue
        row = None
        for rr in sp.get("rows") or []:
            if isinstance(rr, dict) and str(rr.get("asset_id") or "") == aid:
                row = rr
                break
        if not row:
            continue
        msg = row.get("message") or {}
        hl = str(msg.get("headline") or "").strip()
        strip.append(
            {
                "horizon": h,
                "horizon_label": sp.get("horizon_label"),
                "spectrum_band": row.get("spectrum_band"),
                "spectrum_quintile": row.get("spectrum_quintile"),
                "spectrum_position": row.get("spectrum_position"),
                "rank_index": row.get("rank_index"),
                "rank_movement": row.get("rank_movement"),
                "headline": hl[:180] + ("…" if len(hl) > 180 else ""),
                "replay_lineage_pointer": str(row.get("replay_lineage_pointer") or ""),
                "message_snapshot_id": str(row.get("message_snapshot_id") or ""),
                "registry_entry_id": str(sp.get("registry_entry_id") or ""),
            }
        )

    lines: list[str] = []
    if slim_dec:
        lines.append(t(lg, "replay_aging.line_decisions").format(n=len(slim_dec)))
    else:
        lines.append(t(lg, "replay_aging.no_decisions"))
    if slim_sb:
        lines.append(t(lg, "replay_aging.line_sandbox").format(n=len(slim_sb)))
    else:
        lines.append(t(lg, "replay_aging.no_sandbox"))
    if strip:
        lines.append(t(lg, "replay_aging.line_horizons").format(n=len(strip)))
    else:
        lines.append(t(lg, "replay_aging.not_on_seed"))
    framing = " ".join(lines)

    return {
        "ok": True,
        "contract": CONTRACT,
        "replay_lineage_join_contract": JOIN_CONTRACT,
        "lang": lg,
        "asset_id": aid,
        "decisions_tail": slim_dec,
        "sandbox_runs_tail": slim_sb,
        "horizon_spectrum_strip": strip,
        "framing_note": framing,
        "disclaimer": t(lg, "replay_aging.disclaimer"),
    }
