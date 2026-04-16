"""Merge operator-exported promotion_gate rows into metis_brain_bundle JSON (P0 sprint)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from metis_brain.bundle import (
    BrainBundleV0,
    validate_active_registry_integrity,
)
from metis_brain.schemas_v0 import PromotionGateRecordV0


def extract_promotion_gate_dict(export_or_gate: dict[str, Any]) -> dict[str, Any]:
    """Accept full export JSON from export-metis-gates-from-factor-validation or a bare gate object."""
    if not isinstance(export_or_gate, dict):
        raise ValueError("input must be a JSON object")
    if "promotion_gate" in export_or_gate and isinstance(export_or_gate["promotion_gate"], dict):
        return dict(export_or_gate["promotion_gate"])
    if "artifact_id" in export_or_gate and "evaluation_run_id" in export_or_gate:
        return dict(export_or_gate)
    raise ValueError("expected keys promotion_gate or a bare promotion gate with artifact_id")


def merge_promotion_gate_into_bundle_dict(
    bundle_dict: dict[str, Any],
    gate_dict: dict[str, Any],
) -> dict[str, Any]:
    """Replace any existing gate(s) with the same artifact_id, then append this gate."""
    PromotionGateRecordV0.model_validate(gate_dict)
    out = json.loads(json.dumps(bundle_dict, default=str))
    gates = list(out.get("promotion_gates") or [])
    aid = str(gate_dict.get("artifact_id") or "").strip()
    if not aid:
        raise ValueError("gate.artifact_id required")
    gates = [g for g in gates if str((g or {}).get("artifact_id") or "") != aid]
    gates.append(dict(gate_dict))
    out["promotion_gates"] = gates
    return out


def validate_merged_bundle_dict(bundle_dict: dict[str, Any]) -> tuple[bool, list[str]]:
    """Schema + active-registry integrity (same rules as Today consumption)."""
    try:
        bundle = BrainBundleV0.model_validate(bundle_dict)
    except ValidationError as e:
        return False, [f"bundle_schema:{e}"]
    errs = validate_active_registry_integrity(bundle)
    return (len(errs) == 0), errs


def load_bundle_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("bundle root must be object")
    return raw


def write_bundle_json(path: Path, bundle_dict: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle_dict, indent=2, ensure_ascii=False), encoding="utf-8")
