"""AGH v1 Patch 3 — Today surface exposes recent_governed_applies_for_horizon.

The bridge writes ``bundle.recent_governed_applies`` (global FIFO capped at 20)
on every successful ``registry_entry_artifact_promotion`` apply. Today reads
that list, filters it by the current horizon, sorts by ``applied_at_utc``
descending, and exposes at most 5 entries under
``recent_governed_applies_for_horizon`` so the product surface can render
"a governed apply landed" badges without spinning up a new worker.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from phase47_runtime.today_spectrum import build_today_spectrum_payload


def _repo() -> Path:
    return Path(__file__).resolve().parents[2]


def _clone_bundle_with_applies(
    src_bundle_path: Path,
    tmp_path: Path,
    *,
    applies: list[dict],
) -> Path:
    dst = tmp_path / "data" / "mvp" / "metis_brain_bundle_v0.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_bundle_path, dst)
    bundle = json.loads(dst.read_text(encoding="utf-8"))
    bundle["recent_governed_applies"] = list(applies)
    dst.write_text(json.dumps(bundle), encoding="utf-8")
    return dst


def _make_event(
    *,
    horizon: str,
    applied_at_utc: str,
    proposal_id: str = "pkt_prop_v0",
    decision_id: str = "pkt_dec_v0",
    applied_id: str = "pkt_applied_v0",
    outcome: str = "carry_over_fixture_fallback",
    needs_db_rebuild: bool = True,
) -> dict:
    return {
        "target": "registry_entry_artifact_promotion",
        "horizon": horizon,
        "registry_entry_id": f"reg_{horizon}_demo_v0",
        "proposal_packet_id": proposal_id,
        "decision_packet_id": decision_id,
        "applied_packet_id": applied_id,
        "from_active_artifact_id": f"art_{horizon}_demo_v0",
        "to_active_artifact_id": f"art_{horizon}_challenger_momentum_v0",
        "applied_at_utc": applied_at_utc,
        "spectrum_refresh_outcome": outcome,
        "spectrum_refresh_needs_db_rebuild": needs_db_rebuild,
    }


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("METIS_BRAIN_BUNDLE", raising=False)
    monkeypatch.setenv("METIS_TODAY_SOURCE", "registry")


def test_today_registry_surface_exposes_recent_governed_applies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = _repo() / "data" / "mvp" / "metis_brain_bundle_v0.json"
    if not src.is_file():
        pytest.skip("metis_brain_bundle_v0.json missing")

    applies = [
        _make_event(
            horizon="short",
            applied_at_utc="2026-04-18T00:00:00+00:00",
            proposal_id="pkt_prop_short_1",
            applied_id="pkt_applied_short_1",
            outcome="recomputed",
            needs_db_rebuild=False,
        ),
        _make_event(
            horizon="short",
            applied_at_utc="2026-04-19T12:00:00+00:00",
            proposal_id="pkt_prop_short_2",
            applied_id="pkt_applied_short_2",
            outcome="carry_over_fixture_fallback",
            needs_db_rebuild=True,
        ),
        _make_event(
            horizon="medium",
            applied_at_utc="2026-04-19T13:00:00+00:00",
            proposal_id="pkt_prop_medium_1",
            applied_id="pkt_applied_medium_1",
        ),
    ]
    _clone_bundle_with_applies(src, tmp_path, applies=applies)

    out = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    assert out.get("ok") is True

    recents = out.get("recent_governed_applies_for_horizon")
    assert isinstance(recents, list)
    assert len(recents) == 2  # filtered by horizon=short
    # Newest first, so pkt_prop_short_2 must be at position 0.
    assert recents[0]["proposal_packet_id"] == "pkt_prop_short_2"
    assert recents[0]["applied_packet_id"] == "pkt_applied_short_2"
    assert recents[0]["spectrum_refresh_outcome"] == "carry_over_fixture_fallback"
    assert recents[0]["spectrum_refresh_needs_db_rebuild"] is True
    assert recents[1]["proposal_packet_id"] == "pkt_prop_short_1"
    assert recents[1]["spectrum_refresh_needs_db_rebuild"] is False
    # No cross-horizon leakage.
    assert all(e["horizon"] == "short" for e in recents)


def test_today_registry_caps_recent_governed_applies_at_five(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = _repo() / "data" / "mvp" / "metis_brain_bundle_v0.json"
    if not src.is_file():
        pytest.skip("metis_brain_bundle_v0.json missing")

    applies = [
        _make_event(
            horizon="short",
            applied_at_utc=f"2026-04-1{i}T00:00:00+00:00",
            proposal_id=f"pkt_prop_short_{i}",
        )
        for i in range(9)
    ]
    _clone_bundle_with_applies(src, tmp_path, applies=applies)

    out = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    assert out.get("ok") is True

    recents = out.get("recent_governed_applies_for_horizon") or []
    assert len(recents) == 5  # per-horizon cap = 5
    # Newest five: indices 8, 7, 6, 5, 4
    assert [e["proposal_packet_id"] for e in recents] == [
        "pkt_prop_short_8",
        "pkt_prop_short_7",
        "pkt_prop_short_6",
        "pkt_prop_short_5",
        "pkt_prop_short_4",
    ]


def test_today_registry_missing_recent_applies_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = _repo() / "data" / "mvp" / "metis_brain_bundle_v0.json"
    if not src.is_file():
        pytest.skip("metis_brain_bundle_v0.json missing")

    dst = tmp_path / "data" / "mvp" / "metis_brain_bundle_v0.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

    out = build_today_spectrum_payload(repo_root=tmp_path, horizon="short", lang="ko")
    assert out.get("ok") is True
    # Field must be present as an empty list (not missing) so the UI can
    # stably render the "no governed apply yet" placeholder.
    assert out.get("recent_governed_applies_for_horizon") == []
