"""Canonical PIT certification propagation for factor_validation_summaries.

The live factor_validation pipeline keys signal_date off filing ``accepted_at``
and reads forward returns strictly *after* that signal (see
``factor_market_validation_panels`` construction). That discipline is what
``pit_certified`` in ``factor_validation_summaries.summary_json`` attests to.

Two entry points:

* Going-forward runs — :func:`src.research.validation_runner.run_factor_validation_research`
  writes ``pit_certified=true`` and ``pit_rule=accepted_at_signal_date_pit_rule_v0``
  directly into ``summary_json`` when it inserts each summary row.
* Past runs — operator bridge: :func:`certify_factor_validation_pit_for_runs`
  walks the Supabase ``factor_validation_summaries`` rows for a universe /
  horizon and merges the same rule into ``summary_json`` without changing any
  numeric fields.

Both paths leave the same canonical source of truth the gate adapter consumes
(``factor_validation_gate_adapter_v0.py``).
"""

from __future__ import annotations

import json
from typing import Any

PIT_RULE_ID_V0 = "accepted_at_signal_date_pit_rule_v0"
PIT_RULE_NOTE_V0 = (
    "factor_market_validation_panels are keyed on filing accepted_at "
    "signal_date; forward returns are read strictly after signal_date. "
    "No same-day peek; no future revisions leak into this summary."
)


def _parse_summary_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            o = json.loads(raw)
            return dict(o) if isinstance(o, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def apply_pit_rule_to_summary_json(
    summary_json: Any,
    *,
    rule_id: str = PIT_RULE_ID_V0,
    rule_note: str = PIT_RULE_NOTE_V0,
    force: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Return ``(merged_summary_json, changed)``.

    ``changed=False`` when the existing row already carries the same certified
    state under the same rule (and ``force`` is false), so callers can skip a
    no-op update.
    """
    current = _parse_summary_json(summary_json)
    already = (
        bool(current.get("pit_certified"))
        and str(current.get("pit_rule") or "").strip() == rule_id
    )
    if already and not force:
        return current, False
    merged = dict(current)
    merged["pit_certified"] = True
    merged["pit_rule"] = rule_id
    merged["pit_rule_note"] = rule_note
    return merged, True


def certify_factor_validation_pit_for_runs(
    client: Any,
    *,
    universe_name: str,
    horizon_type: str,
    factor_name: str | None = None,
    rule_id: str = PIT_RULE_ID_V0,
    rule_note: str = PIT_RULE_NOTE_V0,
    force: bool = False,
) -> dict[str, Any]:
    """Walk completed ``factor_validation_summaries`` for the slice and merge PIT rule.

    Returns a report dict:
        {
          "ok": True,
          "universe_name": ...,
          "horizon_type": ...,
          "factor_name": ... | None,
          "runs_inspected": int,
          "summaries_inspected": int,
          "summaries_updated": int,
          "summaries_already_certified": int,
          "pit_rule": rule_id,
          "updated_ids": [...],
        }
    """
    runs_resp = (
        client.table("factor_validation_runs")
        .select("id,status,completed_at,universe_name,horizon_type")
        .eq("universe_name", universe_name)
        .eq("horizon_type", horizon_type)
        .eq("status", "completed")
        .order("completed_at", desc=True)
        .execute()
    )
    run_rows = list(runs_resp.data or [])
    run_ids = [str(r["id"]) for r in run_rows if r.get("id")]

    inspected = 0
    updated = 0
    already_ok = 0
    updated_ids: list[str] = []

    if not run_ids:
        return {
            "ok": True,
            "universe_name": universe_name,
            "horizon_type": horizon_type,
            "factor_name": factor_name,
            "runs_inspected": 0,
            "summaries_inspected": 0,
            "summaries_updated": 0,
            "summaries_already_certified": 0,
            "pit_rule": rule_id,
            "updated_ids": [],
            "note": "no_completed_factor_validation_runs_for_slice",
        }

    chunk = 200
    for i in range(0, len(run_ids), chunk):
        batch = run_ids[i : i + chunk]
        q = (
            client.table("factor_validation_summaries")
            .select("id,run_id,factor_name,return_basis,summary_json")
            .in_("run_id", batch)
        )
        if factor_name:
            q = q.eq("factor_name", factor_name)
        resp = q.execute()
        rows = list(resp.data or [])
        for row in rows:
            inspected += 1
            sj = row.get("summary_json")
            merged, changed = apply_pit_rule_to_summary_json(
                sj, rule_id=rule_id, rule_note=rule_note, force=force
            )
            if not changed:
                already_ok += 1
                continue
            client.table("factor_validation_summaries").update(
                {"summary_json": merged}
            ).eq("id", row["id"]).execute()
            updated += 1
            updated_ids.append(str(row["id"]))

    return {
        "ok": True,
        "universe_name": universe_name,
        "horizon_type": horizon_type,
        "factor_name": factor_name,
        "runs_inspected": len(run_ids),
        "summaries_inspected": inspected,
        "summaries_updated": updated,
        "summaries_already_certified": already_ok,
        "pit_rule": rule_id,
        "updated_ids": updated_ids,
    }
