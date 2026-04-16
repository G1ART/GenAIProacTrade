"""Metis Brain v0 — artifact / promotion gate / registry bundle (Unified Product Spec §6.1–6.3)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from metis_brain.bundle import (
    brain_bundle_path,
    bundle_ready_for_horizon,
    try_load_brain_bundle_v0,
    validate_active_registry_integrity,
)
from metis_brain.message_object_v1 import (
    MessageObjectV1,
    build_message_object_v1_for_today_row,
    rationale_summary_contract_v1,
)
from metis_brain.message_snapshots_store import message_snapshots_path
from metis_brain.schemas_v0 import ModelArtifactPacketV0
from phase47_runtime.today_spectrum import build_today_spectrum_payload


@pytest.fixture(autouse=True)
def _reset_metis_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("METIS_BRAIN_BUNDLE", raising=False)


def _repo() -> Path:
    return Path(__file__).resolve().parents[2]


def test_repo_bundle_loads() -> None:
    b, errs = try_load_brain_bundle_v0(_repo())
    assert b is not None and errs == []
    assert bundle_ready_for_horizon(b, "short")
    assert any(e.registry_entry_id == "reg_short_demo_v0" for e in b.registry_entries)


def test_missing_active_artifact_fails_integrity() -> None:
    b, errs = try_load_brain_bundle_v0(_repo())
    assert b is not None
    # Corrupt in-memory: drop artifact referenced by short registry
    arts = [a for a in b.artifacts if a.artifact_id != "art_short_demo_v0"]
    broken = b.model_copy(update={"artifacts": arts})
    err = validate_active_registry_integrity(broken)
    assert any("not in artifacts" in x for x in err)


def test_today_registry_only_no_seed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("METIS_TODAY_SOURCE", "registry")
    src = _repo() / "data" / "mvp" / "metis_brain_bundle_v0.json"
    if not src.is_file():
        pytest.skip("metis_brain_bundle_v0.json missing")
    dst = tmp_path / "data" / "mvp" / "metis_brain_bundle_v0.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    out = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    assert out["ok"] is True
    assert out.get("today_input_source") == "active_horizon_model_registry_v0"
    assert out.get("product_stream") == "METIS_BRAIN_REGISTRY_V0"
    assert out.get("registry_entry_id") == "reg_short_demo_v0"
    assert out.get("replay_lineage_pointer")
    rs = out.get("registry_surface_v1") or {}
    assert rs.get("contract") == "TODAY_REGISTRY_SURFACE_V1"
    assert rs.get("registry_entry_id") == "reg_short_demo_v0"
    assert rs.get("active_artifact_id") == "art_short_demo_v0"
    ch = rs.get("challengers_resolved") or []
    assert any(c.get("artifact_id") == "art_short_challenger_momentum_v0" for c in ch)
    row0 = (out.get("rows") or [{}])[0]
    m0 = row0.get("message") or {}
    assert m0.get("linked_registry_entry_id") == "reg_short_demo_v0"
    assert m0.get("linked_artifact_id") == "art_short_demo_v0"
    assert isinstance(m0.get("linked_evidence"), list)
    assert (out.get("rows") or [{}])[0].get("message_snapshot_id", "").startswith("msg_snap:v1:")
    assert (out.get("rows") or [{}])[0].get("replay_lineage_pointer", "").startswith("lineage:")
    snap_path = message_snapshots_path(tmp_path)
    assert snap_path.is_file()
    store = json.loads(snap_path.read_text(encoding="utf-8"))
    sid0 = (out.get("rows") or [{}])[0].get("message_snapshot_id")
    assert sid0 and isinstance(store.get("snapshots"), dict) and sid0 in store["snapshots"]


def test_today_registry_mode_missing_bundle_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("METIS_TODAY_SOURCE", "registry")
    out = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    assert out["ok"] is False
    assert out.get("error") == "brain_bundle_missing"
    assert str(brain_bundle_path(tmp_path)) in str(out.get("hint") or "")


def test_today_auto_falls_back_to_seed_when_bundle_invalid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("METIS_TODAY_SOURCE", "auto")
    (tmp_path / "data" / "mvp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "mvp" / "metis_brain_bundle_v0.json").write_text("{not json", encoding="utf-8")
    src = _repo() / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst = tmp_path / "data" / "mvp" / "today_spectrum_seed_v1.json"
    shutil.copyfile(src, dst)
    out = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    assert out["ok"] is True
    assert out.get("today_input_source") == "today_spectrum_seed_v1"
    assert out.get("brain_bundle_skipped")


def test_artifact_model_requires_all_fields() -> None:
    with pytest.raises(Exception):
        ModelArtifactPacketV0.model_validate({"artifact_id": "x"})


def test_rationale_summary_contract_truncates() -> None:
    long = "x" * 600
    out = rationale_summary_contract_v1(text=long, max_chars=100)
    assert len(out) <= 100
    assert out.endswith("…")


def test_message_object_v1_from_row() -> None:
    row = {
        "asset_id": "DEMO_X",
        "message": {
            "headline": {"ko": "헤드", "en": "Head"},
            "why_now": {"ko": "이유", "en": "Why"},
            "linked_evidence": [{"pointer": "pit:demo:1", "summary": "cov", "kind": "validation"}],
        },
    }
    obj = build_message_object_v1_for_today_row(
        row=row,
        horizon="short",
        lang="ko",
        rationale_summary="요약문장입니다.",
        what_changed_plain="변경",
        confidence_band="medium",
        linked_registry_entry_id="reg_short_demo_v0",
        linked_artifact_id="art_short_demo_v0",
    )
    assert isinstance(obj, MessageObjectV1)
    assert obj.linked_registry_entry_id == "reg_short_demo_v0"
    assert obj.linked_artifact_id == "art_short_demo_v0"
    assert len(obj.linked_evidence) == 1
    assert obj.linked_evidence[0].pointer == "pit:demo:1"


def test_today_row_message_has_contract_fields(tmp_path: Path) -> None:
    src = _repo() / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst = tmp_path / "data" / "mvp" / "today_spectrum_seed_v1.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    out = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    assert out["ok"] is True
    assert out.get("message_object_contract") == "METIS_PRODUCT_SPEC_6_4_V1"
    row_a = next(x for x in out["rows"] if x.get("asset_id") == "DEMO_KR_A")
    msg = row_a.get("message") or {}
    assert msg.get("linked_registry_entry_id") == "seed:unlinked_registry_v0"
    assert msg.get("linked_artifact_id") == "seed:unlinked_artifact_v0"
    assert isinstance(msg.get("linked_evidence"), list) and msg["linked_evidence"]
    assert row_a.get("message_snapshot_id", "").startswith("msg_snap:v1:")
    assert row_a.get("replay_lineage_pointer") == "seed:replay_lineage_v0"
    snap_path = message_snapshots_path(tmp_path)
    assert snap_path.is_file()
    store = json.loads(snap_path.read_text(encoding="utf-8"))
    sid = row_a.get("message_snapshot_id")
    assert sid and isinstance(store.get("snapshots"), dict) and sid in store["snapshots"]
