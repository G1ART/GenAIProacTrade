"""Stage 4 — counterfactual templates + deterministic preview (Build Plan §7.2–7.3, Product Spec §5.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase47_runtime.message_layer_v1 import spectrum_quintile_from_position
from phase47_runtime.phase47e_user_locale import normalize_lang, t
from phase47_runtime.today_spectrum import _normalize_mock_price_tick, build_today_spectrum_payload

# Four working templates (acceptance: ≥4). Numeric deltas are illustrative only — not live prices.
CF_TEMPLATES_V1: tuple[dict[str, Any], ...] = (
    {
        "template_id": "cf_watch_only_branch",
        "position_delta": 0.0,
        "axis": "spectrum_position",
        "label_key": "replay.cf.label_watch_only",
        "summary_key": "replay.cf.sum_watch_only",
        "narrative_key": "replay.cf.narr_watch_only",
    },
    {
        "template_id": "cf_evidence_softens",
        "position_delta": -0.1,
        "axis": "spectrum_position",
        "label_key": "replay.cf.label_evidence_softens",
        "summary_key": "replay.cf.sum_evidence_softens",
        "narrative_key": "replay.cf.narr_evidence_softens",
    },
    {
        "template_id": "cf_horizon_stretches",
        "position_delta": 0.12,
        "axis": "spectrum_position",
        "label_key": "replay.cf.label_horizon_stretch",
        "summary_key": "replay.cf.sum_horizon_stretch",
        "narrative_key": "replay.cf.narr_horizon_stretch",
    },
    {
        "template_id": "cf_allocation_smaller",
        "position_delta": -0.06,
        "axis": "spectrum_position",
        "label_key": "replay.cf.label_allocation_smaller",
        "summary_key": "replay.cf.sum_allocation_smaller",
        "narrative_key": "replay.cf.narr_allocation_smaller",
    },
)


def counterfactual_templates_v1_payload(lang: str | None) -> dict[str, Any]:
    lg = normalize_lang(lang)
    items: list[dict[str, Any]] = []
    for tpl in CF_TEMPLATES_V1:
        items.append(
            {
                "template_id": tpl["template_id"],
                "label": t(lg, str(tpl["label_key"])),
                "summary": t(lg, str(tpl["summary_key"])),
                "axis": tpl.get("axis", "spectrum_position"),
                "position_delta": tpl["position_delta"],
            }
        )
    return {"ok": True, "contract": "COUNTERFACTUAL_TEMPLATES_V1", "templates": items}


def counterfactual_preview_v1(
    *,
    repo_root: Path,
    template_id: str,
    asset_id: str,
    horizon: str | None,
    lang: str | None,
    mock_price_tick: str | None,
) -> dict[str, Any]:
    lg = normalize_lang(lang)
    tid = (template_id or "").strip()
    meta = next((x for x in CF_TEMPLATES_V1 if x["template_id"] == tid), None)
    if not meta:
        return {
            "ok": False,
            "error": "unknown_template_id",
            "allowed": [x["template_id"] for x in CF_TEMPLATES_V1],
        }
    aid = (asset_id or "").strip()
    if not aid:
        return {"ok": False, "error": "asset_id_required"}
    hz = (horizon or "short").strip().lower().replace("-", "_")
    mt = _normalize_mock_price_tick(mock_price_tick)
    sp = build_today_spectrum_payload(repo_root=repo_root, horizon=hz, lang=lg, mock_price_tick=mt)
    if not sp.get("ok"):
        return sp
    row: dict[str, Any] | None = None
    for r in sp.get("rows") or []:
        if isinstance(r, dict) and str(r.get("asset_id") or "").strip() == aid:
            row = r
            break
    if not row:
        return {"ok": False, "error": "object_not_on_spectrum", "asset_id": aid, "horizon": hz}
    pos = float(row.get("spectrum_position") or 0.5)
    delta = float(meta.get("position_delta") or 0.0)
    hyp = max(0.0, min(1.0, pos + delta))
    msg = row.get("message") if isinstance(row.get("message"), dict) else {}
    head = str(msg.get("headline") or "")[:160]
    return {
        "ok": True,
        "contract": "COUNTERFACTUAL_PREVIEW_V1",
        "template_id": tid,
        "asset_id": aid,
        "horizon": hz,
        "lang": lg,
        "baseline": {
            "spectrum_position": round(pos, 4),
            "spectrum_quintile": row.get("spectrum_quintile"),
            "headline_snippet": head,
            "active_model_family": sp.get("active_model_family"),
            "replay_lineage_pointer": str(row.get("replay_lineage_pointer") or ""),
            "message_snapshot_id": str(row.get("message_snapshot_id") or ""),
        },
        "stressed": {
            "spectrum_position_hypothetical": round(hyp, 4),
            "spectrum_quintile_hypothetical": spectrum_quintile_from_position(hyp),
            "narrative": t(lg, str(meta["narrative_key"])),
            "disclaimer": t(lg, "replay.cf.disclaimer"),
        },
    }
