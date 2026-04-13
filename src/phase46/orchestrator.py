"""Assemble Phase 46 founder cockpit bundle."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase46.alert_ledger import alert_ledger_schema
from phase46.alert_ledger import default_ledger_path as default_alert_path
from phase46.alert_ledger import load_alert_ledger
from phase46.cockpit_state import build_cockpit_state
from phase46.decision_trace_ledger import decision_trace_ledger_schema
from phase46.decision_trace_ledger import default_ledger_path as default_decision_path
from phase46.decision_trace_ledger import load_decision_ledger
from phase46.drilldown import render_drilldown
from phase46.phase47_recommend import recommend_phase47
from phase46.read_model import build_founder_read_model
from phase46.representative_agent import build_representative_pitch
from phase46.ui_contract import build_ui_surface_contract


def _read_json(path: str) -> dict[str, Any]:
    import json

    return dict(json.loads(Path(path).read_text(encoding="utf-8")))


def run_phase46_founder_decision_cockpit(
    *,
    phase45_bundle_in: str,
    phase44_bundle_in: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    p45 = _read_json(phase45_bundle_in)
    p44 = _read_json(phase44_bundle_in)
    p45_path = str(Path(phase45_bundle_in).resolve())
    p44_path = str(Path(phase44_bundle_in).resolve())

    founder_read_model = build_founder_read_model(
        phase45_bundle=p45,
        phase44_bundle=p44,
        input_phase45_bundle_path=p45_path,
        input_phase44_bundle_path=p44_path,
    )
    cockpit_state = build_cockpit_state(
        founder_read_model=founder_read_model,
        phase45_bundle=p45,
        phase44_bundle=p44,
    )
    representative_pitch = build_representative_pitch(
        founder_read_model=founder_read_model,
        cockpit_state=cockpit_state,
        phase45_bundle=p45,
    )

    drilldown_examples: dict[str, Any] = {}
    for layer in ("decision", "message", "information", "research", "provenance", "closeout"):
        drilldown_examples[layer] = render_drilldown(
            layer,
            founder_read_model=founder_read_model,
            representative_pitch=representative_pitch,
            cockpit_state=cockpit_state,
            phase45_bundle=p45,
            phase44_bundle=p44,
        )

    root = repo_root or Path(__file__).resolve().parents[2]
    ap = default_alert_path(root)
    dp = default_decision_path(root)

    gen = datetime.now(timezone.utc).isoformat()

    return {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": gen,
        "input_phase45_bundle_path": p45_path,
        "input_phase44_bundle_path": p44_path,
        "founder_read_model": founder_read_model,
        "cockpit_state": cockpit_state,
        "representative_pitch": representative_pitch,
        "drilldown_examples": drilldown_examples,
        "alert_ledger_schema": alert_ledger_schema(),
        "decision_trace_ledger_schema": decision_trace_ledger_schema(),
        "alert_ledger_snapshot": load_alert_ledger(ap),
        "decision_trace_ledger_snapshot": load_decision_ledger(dp),
        "alert_ledger_path": str(ap.resolve()),
        "decision_trace_ledger_path": str(dp.resolve()),
        "ui_surface_contract": build_ui_surface_contract(),
        "phase47": recommend_phase47(),
    }
