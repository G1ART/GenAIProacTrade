"""Slice A — template bundle + factor_validation gate specs → merged bundle + integrity (single pipeline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from metis_brain.bundle_promotion_merge_v0 import (
    merge_promotion_gate_into_bundle_dict,
    sync_artifact_validation_pointer_for_factor_run,
    validate_merged_bundle_dict,
    write_bundle_json,
)

GateFetchFn = Callable[[Any, dict[str, Any]], dict[str, Any]]

REQUIRED_GATE_KEYS = frozenset(
    {"factor_name", "universe_name", "horizon_type", "return_basis", "artifact_id"}
)


def load_build_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config root must be object")
    return raw


def normalize_gate_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    gates = config.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("config.gates must be a non-empty list")
    out: list[dict[str, Any]] = []
    for i, g in enumerate(gates):
        if not isinstance(g, dict):
            raise ValueError(f"gates[{i}] must be object")
        missing = REQUIRED_GATE_KEYS - set(g.keys())
        if missing:
            raise ValueError(f"gates[{i}] missing keys: {sorted(missing)}")
        out.append({k: str(g[k]).strip() for k in REQUIRED_GATE_KEYS})
    return out


def resolve_repo_path(repo_root: Path, p: str) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path.resolve()
    return (repo_root / path).resolve()


def build_bundle_from_validation_gates(
    *,
    template_bundle: dict[str, Any],
    gate_specs: list[dict[str, Any]],
    fetch_gate: GateFetchFn,
    client: Any,
    sync_artifact_validation_pointer: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Apply each DB gate export onto ``template_bundle`` (copy). Returns (merged, report).

    ``merged`` is None if any export fails or final integrity fails. ``report`` always has
    ``steps`` (per gate), ``integrity_ok``, ``errors`` (bundle-level), ``aborted_reason`` optional.
    """
    merged: dict[str, Any] = json.loads(json.dumps(template_bundle, default=str))
    steps: list[dict[str, Any]] = []

    for spec in gate_specs:
        ex = fetch_gate(client, spec)
        steps.append({"spec": spec, "export_ok": bool(ex.get("ok")), "export": ex})
        if not ex.get("ok"):
            return None, {
                "integrity_ok": False,
                "errors": [f"gate_export_failed:{ex.get('error')}"],
                "steps": steps,
                "aborted_reason": "export_failed",
            }
        gate = ex.get("promotion_gate")
        if not isinstance(gate, dict):
            return None, {
                "integrity_ok": False,
                "errors": ["promotion_gate_missing_in_export"],
                "steps": steps,
                "aborted_reason": "invalid_export",
            }
        try:
            merged = merge_promotion_gate_into_bundle_dict(merged, gate)
            if sync_artifact_validation_pointer:
                merged = sync_artifact_validation_pointer_for_factor_run(
                    merged,
                    artifact_id=str(gate.get("artifact_id") or ""),
                    evaluation_run_id=str(gate.get("evaluation_run_id") or ""),
                )
        except ValueError as e:
            return None, {
                "integrity_ok": False,
                "errors": [f"merge_failed:{e}"],
                "steps": steps,
                "aborted_reason": "merge_failed",
            }

    integrity_ok, errs = validate_merged_bundle_dict(merged)
    report: dict[str, Any] = {
        "integrity_ok": integrity_ok,
        "errors": errs,
        "steps": steps,
    }
    if not integrity_ok:
        report["aborted_reason"] = "integrity_failed"
        return None, report
    report["aborted_reason"] = None
    return merged, report


def write_output_bundle(path: Path, bundle_dict: dict[str, Any]) -> None:
    write_bundle_json(path, bundle_dict)
