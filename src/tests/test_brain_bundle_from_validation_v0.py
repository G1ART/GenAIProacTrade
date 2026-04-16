"""Slice A — build bundle from template + gate specs (mocked DB export)."""

from __future__ import annotations

from pathlib import Path

import pytest

from metis_brain.brain_bundle_from_validation_v0 import (
    build_bundle_from_validation_gates,
    load_build_config,
    normalize_gate_specs,
    resolve_repo_path,
)
from metis_brain.bundle_promotion_merge_v0 import load_bundle_json


def _repo() -> Path:
    return Path(__file__).resolve().parents[2]


def _template() -> dict:
    p = _repo() / "data/mvp/metis_brain_bundle_v0.json"
    return load_bundle_json(p)


def test_normalize_gate_specs_minimal() -> None:
    cfg = {
        "gates": [
            {
                "factor_name": "accruals",
                "universe_name": "sp500_current",
                "horizon_type": "next_month",
                "return_basis": "raw",
                "artifact_id": "art_short_demo_v0",
            }
        ]
    }
    specs = normalize_gate_specs(cfg)
    assert len(specs) == 1
    assert specs[0]["artifact_id"] == "art_short_demo_v0"


def test_normalize_gate_specs_missing_key() -> None:
    with pytest.raises(ValueError, match="missing keys"):
        normalize_gate_specs({"gates": [{"factor_name": "x"}]})


def test_load_build_config_example() -> None:
    p = _repo() / "data/mvp/metis_bundle_from_validation_config.example.json"
    if not p.is_file():
        pytest.skip("example config missing")
    c = load_build_config(p)
    assert c.get("gates")


def test_resolve_repo_path_relative() -> None:
    root = _repo()
    assert resolve_repo_path(root, "data/mvp/metis_brain_bundle_v0.json").is_file()


def test_build_bundle_mock_fetch_keeps_integrity() -> None:
    template = _template()
    g0 = dict((template.get("promotion_gates") or [])[0])
    g0["evaluation_run_id"] = "eval_mock_integrity_v0"
    g0["reasons"] = "mock_pipeline_test:v0"

    def fetch_ok(_client: object, _spec: dict[str, str]) -> dict[str, object]:
        return {"ok": True, "promotion_gate": g0}

    merged, report = build_bundle_from_validation_gates(
        template_bundle=template,
        gate_specs=[
            {
                "factor_name": "accruals",
                "universe_name": "sp500_current",
                "horizon_type": "next_month",
                "return_basis": "raw",
                "artifact_id": str(g0["artifact_id"]),
            }
        ],
        fetch_gate=fetch_ok,
        client=None,
        sync_artifact_validation_pointer=False,
    )
    assert merged is not None, report
    assert report.get("integrity_ok") is True
    assert not report.get("errors")


def test_build_bundle_aborts_on_export_fail() -> None:
    template = _template()

    def fetch_bad(_client: object, _spec: dict[str, str]) -> dict[str, object]:
        return {"ok": False, "error": "no_completed_factor_validation_summary"}

    merged, report = build_bundle_from_validation_gates(
        template_bundle=template,
        gate_specs=[
            {
                "factor_name": "accruals",
                "universe_name": "sp500_current",
                "horizon_type": "next_month",
                "return_basis": "raw",
                "artifact_id": "art_short_demo_v0",
            }
        ],
        fetch_gate=fetch_bad,
        client=None,
        sync_artifact_validation_pointer=False,
    )
    assert merged is None
    assert report.get("aborted_reason") == "export_failed"
