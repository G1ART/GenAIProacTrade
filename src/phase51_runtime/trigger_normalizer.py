"""Map external raw events to governed trigger types (strict, deterministic)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from phase50_runtime.control_plane import DEFAULT_ALLOWED

GOVERNED_TRIGGER_TYPES = frozenset(DEFAULT_ALLOWED)

# raw_event_type -> normalized_trigger_type
RAW_TO_NORMALIZED: dict[str, str] = {
    "named_source_registration": "named_source_signal",
    "external_named_source": "named_source_signal",
    "operator_research_signal": "operator_research_signal",
    "external_operator_research": "operator_research_signal",
    "manual_watchlist": "manual_watchlist",
    "watchlist_submit": "manual_watchlist",
    "closeout_reopen_candidate": "closeout_reopen_candidate",
    "external_reopen_signal": "closeout_reopen_candidate",
    "changed_artifact_bundle": "changed_artifact_bundle",
}


def stable_payload_fingerprint(payload: dict[str, Any]) -> str:
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:24]


def compute_dedupe_key(
    *,
    source_type: str,
    source_id: str,
    raw_event_type: str,
    payload: dict[str, Any],
) -> str:
    fp = stable_payload_fingerprint(payload)
    return f"ext:{source_type}:{source_id}:{raw_event_type}:{fp}"


def normalize_raw_event(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Return {
      ok: bool,
      normalized_trigger_type?: str,
      normalized_payload?: dict,
      reason?: str (rejection),
    }
    """
    raw_type = str(raw.get("raw_event_type") or "").strip()
    if not raw_type:
        return {"ok": False, "reason": "missing_raw_event_type"}
    if raw_type not in RAW_TO_NORMALIZED:
        return {"ok": False, "reason": f"unknown_raw_event_type:{raw_type}"}
    nt = RAW_TO_NORMALIZED[raw_type]
    if nt not in GOVERNED_TRIGGER_TYPES:
        return {"ok": False, "reason": f"mapped_type_not_in_governed_universe:{nt}"}
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "payload_must_be_object"}
    asset_scope = raw.get("asset_scope")
    if not isinstance(asset_scope, dict) or not str(asset_scope.get("asset_id") or "").strip():
        return {"ok": False, "reason": "asset_scope_requires_asset_id"}
    # Light shape checks per type
    if nt == "named_source_signal":
        note = str(payload.get("note") or payload.get("source_note") or "")
        if not note.strip():
            return {"ok": False, "reason": "named_source_requires_note"}
        norm = {"note": note[:2000], "source_name": str(payload.get("source_name") or "")[:500]}
    elif nt == "manual_watchlist":
        norm = {
            "asset_id": str(asset_scope.get("asset_id")),
            "note": str(payload.get("note") or "external_watchlist")[:2000],
            "suggested_job_type": str(payload.get("suggested_job_type") or "debate.execute"),
        }
    elif nt == "operator_research_signal":
        norm = {
            "summary": str(payload.get("summary") or payload.get("note") or "")[:2000],
            "artifact_ref": str(payload.get("artifact_ref") or "")[:500],
        }
    elif nt == "closeout_reopen_candidate":
        norm = {"rationale": str(payload.get("rationale") or payload.get("note") or "")[:2000]}
    elif nt == "changed_artifact_bundle":
        norm = {"hint": str(payload.get("hint") or "external_bundle_signal")[:500]}
    else:
        norm = dict(payload)
    return {"ok": True, "normalized_trigger_type": nt, "normalized_payload": norm}
