"""Tests for promotion_gate merge into metis_brain_bundle."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from metis_brain.bundle_promotion_merge_v0 import (
    extract_promotion_gate_dict,
    merge_promotion_gate_into_bundle_dict,
    validate_merged_bundle_dict,
)


def _repo_bundle_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "data" / "mvp" / "metis_brain_bundle_v0.json"


def test_extract_promotion_gate_wrapper_and_bare() -> None:
    p = _repo_bundle_path()
    raw = json.loads(p.read_text(encoding="utf-8"))
    full = raw["promotion_gates"][0]
    wrapped = {"ok": True, "promotion_gate": full}
    assert extract_promotion_gate_dict(wrapped) == full
    assert extract_promotion_gate_dict(full) == full


def test_extract_promotion_gate_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="expected keys"):
        extract_promotion_gate_dict({"ok": True})


def test_merge_replaces_same_artifact_id() -> None:
    p = _repo_bundle_path()
    bundle = json.loads(p.read_text(encoding="utf-8"))
    g0 = dict(bundle["promotion_gates"][0])
    g1 = {**g0, "evaluation_run_id": "eval_replaced_v1", "reasons": "merged_test:v0"}
    merged = merge_promotion_gate_into_bundle_dict(bundle, g1)
    aids = [x["artifact_id"] for x in merged["promotion_gates"]]
    assert aids.count("art_short_demo_v0") == 1
    row = next(x for x in merged["promotion_gates"] if x["artifact_id"] == "art_short_demo_v0")
    assert row["evaluation_run_id"] == "eval_replaced_v1"


def test_merge_failing_gate_breaks_integrity() -> None:
    p = _repo_bundle_path()
    bundle = json.loads(p.read_text(encoding="utf-8"))
    g = dict(bundle["promotion_gates"][0])
    g["pit_pass"] = False
    g["coverage_pass"] = False
    g["monotonicity_pass"] = False
    g["approved_by_rule"] = ""
    merged = merge_promotion_gate_into_bundle_dict(bundle, g)
    ok, errs = validate_merged_bundle_dict(merged)
    assert ok is False
    assert any("no passing promotion gate" in e for e in errs)


def test_merge_roundtrip_write_tmp(tmp_path: Path) -> None:
    p = _repo_bundle_path()
    dest = tmp_path / "bundle.json"
    shutil.copy(p, dest)
    bundle = json.loads(dest.read_text(encoding="utf-8"))
    g = dict(bundle["promotion_gates"][0])
    g["evaluation_run_id"] = "eval_roundtrip_tmp"
    merged = merge_promotion_gate_into_bundle_dict(bundle, g)
    ok, errs = validate_merged_bundle_dict(merged)
    assert ok is True, errs
    dest.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    again = json.loads(dest.read_text(encoding="utf-8"))
    ok2, errs2 = validate_merged_bundle_dict(again)
    assert ok2 is True, errs2
