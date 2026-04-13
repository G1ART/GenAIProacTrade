"""Deterministic triggers from bundles + decision ledger (no external scan)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase48_runtime.budget_policy import default_budget_policy, trigger_allowed


def _parse_ts(s: str | None) -> str | None:
    if not s:
        return None
    return str(s).strip() or None


def load_manual_triggers(repo_root: Path) -> tuple[list[dict[str, Any]], Path | None]:
    p = repo_root / "data" / "research_runtime" / "manual_triggers_v1.json"
    if not p.is_file():
        return [], None
    raw = json.loads(p.read_text(encoding="utf-8"))
    pending = list(raw.get("pending") or [])
    return pending, p


def evaluate_triggers(
    *,
    repo_root: Path,
    phase46_bundle: dict[str, Any],
    phase45_bundle: dict[str, Any] | None,
    decision_ledger_path: Path,
    registry_metadata: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    policy = policy or default_budget_policy()
    out: list[dict[str, Any]] = []
    rm = phase46_bundle.get("founder_read_model") or {}
    asset_id = str(rm.get("asset_id") or "unknown_cohort")
    p46_gen = _parse_ts(str(phase46_bundle.get("generated_utc") or ""))
    last_p46 = _parse_ts(str(registry_metadata.get("last_phase46_generated_utc") or ""))

    if p46_gen and p46_gen != last_p46 and trigger_allowed(policy, "changed_artifact_bundle"):
        out.append(
            {
                "trigger_type": "changed_artifact_bundle",
                "dedupe_key": f"bundle:{p46_gen}",
                "priority": 10,
                "payload": {"phase46_generated_utc": p46_gen, "prior_utc": last_p46},
                "suggested_job_type": "evidence.refresh",
            }
        )

    last_cycle = _parse_ts(str(registry_metadata.get("last_cycle_utc") or ""))
    decisions: list[dict[str, Any]] = []
    if decision_ledger_path.is_file():
        try:
            ledger = json.loads(decision_ledger_path.read_text(encoding="utf-8"))
            decisions = list(ledger.get("decisions") or [])
        except (json.JSONDecodeError, OSError):
            decisions = []

    for d in decisions:
        ts = _parse_ts(str(d.get("timestamp") or ""))
        if last_cycle and ts and ts <= last_cycle:
            continue
        dt = str(d.get("decision_type") or "")
        if dt in ("watch", "reopen_request") and trigger_allowed(policy, "operator_research_signal"):
            out.append(
                {
                    "trigger_type": "operator_research_signal",
                    "dedupe_key": f"op:{dt}:{d.get('timestamp')}:{d.get('asset_id', asset_id)}",
                    "priority": 20,
                    "payload": {"decision": d},
                    "suggested_job_type": "hypothesis.check",
                }
            )
        if dt == "reopen_request" and trigger_allowed(policy, "closeout_reopen_candidate"):
            out.append(
                {
                    "trigger_type": "closeout_reopen_candidate",
                    "dedupe_key": f"reopen:{d.get('timestamp')}:{d.get('asset_id', asset_id)}",
                    "priority": 25,
                    "payload": {"decision": d},
                    "suggested_job_type": "debate.execute",
                }
            )

    closeout = str(rm.get("closeout_status") or "")
    if (
        phase45_bundle
        and closeout == "closed_pending_new_evidence"
        and rm.get("reopen_requires_named_source")
        and trigger_allowed(policy, "named_source_signal")
    ):
        note = ""
        for d in decisions[-5:]:
            if str(d.get("decision_type") or "") == "reopen_request":
                note = str(d.get("founder_note") or "")
                break
        if "named" in note.lower() or "source" in note.lower():
            out.append(
                {
                    "trigger_type": "named_source_signal",
                    "dedupe_key": f"named_src:{asset_id}:{note[:80]}",
                    "priority": 30,
                    "payload": {"founder_note_excerpt": note[:500]},
                    "suggested_job_type": "debate.execute",
                }
            )

    manual, mpath = load_manual_triggers(repo_root)
    for i, m in enumerate(manual):
        if trigger_allowed(policy, "manual_watchlist"):
            out.append(
                {
                    "trigger_type": "manual_watchlist",
                    "dedupe_key": f"manual:{i}:{m.get('asset_id', asset_id)}:{m.get('note', '')[:40]}",
                    "priority": 15,
                    "payload": dict(m),
                    "suggested_job_type": "evidence.refresh",
                    "manual_file": str(mpath) if mpath else None,
                }
            )

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for t in sorted(out, key=lambda x: -int(x.get("priority") or 0)):
        dk = str(t.get("dedupe_key") or "")
        if dk in seen:
            continue
        seen.add(dk)
        deduped.append(t)
    return deduped


def clear_manual_triggers_file(path: Path) -> None:
    if not path.is_file():
        return
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["pending"] = []
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
