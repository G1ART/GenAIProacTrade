"""Bounded Non-Quant Cash-Out v1 — BNCO-2 / BNCO-3 cash-out surface tests.

Verifies that Today surfaces compact ``brain_overlay_summary`` in a bounded
form (short locale labels, controlled vocabulary, no buy/sell/guarantee copy),
and that Research surfaces ``overlay_explanations`` with every string sourced
from the seed (no LLM free-text).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from metis_brain.brain_overlays_v1 import OVERLAY_TYPES
from metis_brain.bundle import BrainBundleV0
from phase47_runtime.phase47e_user_locale import t
from phase47_runtime.today_spectrum import (
    _registry_surface_v1_from_bundle_entry,
    build_today_object_detail_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[2]

# Wording that MUST NOT leak into any overlay cash-out surface. Matches are
# case-insensitive; the check below stringifies everything and lowercases.
_FORBIDDEN_COPY_TOKENS = (
    "buy",
    "sell",
    "guaranteed",
    "will definitely",
    "recommend",
)


def _load_current_bundle() -> dict:
    p = REPO_ROOT / "data" / "mvp" / "metis_brain_bundle_from_db_v0.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _load_overlay_seed() -> dict:
    p = REPO_ROOT / "data" / "mvp" / "brain_overlays_seed_v1.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _bundle_with_transcript_overlays() -> BrainBundleV0:
    raw = _load_current_bundle()
    seed = _load_overlay_seed()
    # Only the two transcript overlays; the policy overlay remains illustrative.
    raw["brain_overlays"] = [
        ov
        for ov in seed["overlays"]
        if ov["overlay_id"]
        in {
            "ovr_short_transcript_guidance_tone_v1",
            "ovr_medium_transcript_regime_shift_v1",
        }
    ]
    return BrainBundleV0.model_validate(raw)


def _assert_no_forbidden_copy(payload) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for token in _FORBIDDEN_COPY_TOKENS:
        assert token not in serialized, f"forbidden copy token {token!r} leaked"


# ---------------------------------------------------------------------------
# BNCO-2 — Today compact summary
# ---------------------------------------------------------------------------


def test_today_registry_surface_emits_compact_overlay_summary() -> None:
    bundle = _bundle_with_transcript_overlays()
    # Pick the short horizon registry entry that binds to art_short_demo_v0.
    ent = next(
        e
        for e in bundle.registry_entries
        if e.active_artifact_id == "art_short_demo_v0"
    )
    surface = _registry_surface_v1_from_bundle_entry(bundle, ent)
    summary = surface["brain_overlay_summary"]
    assert summary["contract"] == "TODAY_BRAIN_OVERLAY_SUMMARY_V1"
    assert summary["total"] == 1
    assert summary["count_by_type"] == {"confidence_adjustment": 1}
    label = summary["labels"][0]
    assert label["overlay_id"] == "ovr_short_transcript_guidance_tone_v1"
    # Short labels must match the fixed locale dictionary (no free text).
    assert label["short_label_ko"] == t("ko", "overlay.short.confidence_adjustment")
    assert label["short_label_en"] == t("en", "overlay.short.confidence_adjustment")
    assert label["expected_direction_hint"] == "position_weakens"
    # Card-sized: no what_it_changes body on Today.
    assert "what_it_changes" not in label
    _assert_no_forbidden_copy(summary)


def test_today_overlay_summary_controlled_vocabulary_only() -> None:
    bundle = _bundle_with_transcript_overlays()
    for ent in bundle.registry_entries:
        surface = _registry_surface_v1_from_bundle_entry(bundle, ent)
        for label in surface["brain_overlay_summary"]["labels"]:
            assert label["overlay_type"] in OVERLAY_TYPES


def test_today_overlay_summary_empty_when_no_overlays() -> None:
    raw = _load_current_bundle()
    raw.pop("brain_overlays", None)
    bundle = BrainBundleV0.model_validate(raw)
    ent = bundle.registry_entries[0]
    surface = _registry_surface_v1_from_bundle_entry(bundle, ent)
    summary = surface["brain_overlay_summary"]
    assert summary["total"] == 0
    assert summary["labels"] == []
    assert summary["count_by_type"] == {}


# ---------------------------------------------------------------------------
# BNCO-3 — Research overlay_explanations
# ---------------------------------------------------------------------------


def _write_temp_bundle_with_transcript_overlays(tmp_path: Path) -> Path:
    raw = _load_current_bundle()
    seed = _load_overlay_seed()
    raw["brain_overlays"] = [
        ov
        for ov in seed["overlays"]
        if ov["overlay_id"]
        in {
            "ovr_short_transcript_guidance_tone_v1",
            "ovr_medium_transcript_regime_shift_v1",
        }
    ]
    p = tmp_path / "bundle.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return p


def test_research_surface_emits_bounded_overlay_explanations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle_path = _write_temp_bundle_with_transcript_overlays(tmp_path)
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(bundle_path))
    monkeypatch.setenv("METIS_TODAY_SOURCE", "registry")
    # Pick an asset in the short-horizon rows.
    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    short_rows = raw["spectrum_rows_by_horizon"]["short"]
    assert short_rows, "bundle short rows must exist for this test"
    asset_id = str(short_rows[0]["asset_id"])
    payload = build_today_object_detail_payload(
        repo_root=REPO_ROOT, asset_id=asset_id, horizon="short", lang="ko"
    )
    assert payload["ok"], payload
    research = payload["research"]
    explanations = research.get("overlay_explanations")
    assert isinstance(explanations, list)
    assert len(explanations) == 1, explanations
    e = explanations[0]
    assert e["overlay_id"] == "ovr_short_transcript_guidance_tone_v1"
    assert e["overlay_type"] == "confidence_adjustment"
    assert e["fact_vs_interpretation"] == "interpretation"
    assert e["expected_direction_hint"] == "position_weakens"
    assert e["what_it_changes"]
    assert e["source_artifact_ref_summary"]
    assert e["recheck_rule"]
    assert e["counter_interpretation_present"] is True
    assert e["pit_window"]["starts_at"] and e["pit_window"]["ends_at"]
    _assert_no_forbidden_copy(explanations)
    # Fact-vs-interpretation MUST always be "interpretation" for overlays.
    for exp in explanations:
        assert exp["fact_vs_interpretation"] == "interpretation"


# ---------------------------------------------------------------------------
# BNCO-4 — Replay directional aging lineage
# ---------------------------------------------------------------------------


def test_inject_overlay_aging_lineage_into_decision_event(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from phase47_runtime.traceability_replay import (
        _compute_overlay_aging_lineage,
        _inject_lineage_into_timeline_events,
        micro_brief_for_event,
    )

    overlay = {
        "overlay_id": "ovr_test_weakens",
        "overlay_type": "confidence_adjustment",
        "expected_direction_hint": "position_weakens",
    }

    events = [
        {
            "event_id": "evt_decision_1",
            "event_type": "decision_event",
            "asset_id": "AAA",
            "timestamp_utc": "2026-04-17T12:00:00Z",
            "title": "dec",
            "message_summary": "m",
            "evidence_summary": "e",
            "known_then": "k",
            "stance_at_time": "explore",
            "founder_note": "n",
            # Pre-existing decision-level lineage.
            "brain_overlay_ids_at_decision": ["ovr_test_weakens"],
            "persona_candidate_ids_at_decision": [],
            # Snapshot id for aging lookup.
            "message_snapshot_id": "msg_snap_aaa_2026-04-01",
        }
    ]
    # Seed a snapshot with a known spectrum_position.
    repo_root = tmp_path
    snapshots_path = repo_root / "data" / "mvp"
    snapshots_path.mkdir(parents=True)
    (snapshots_path / "message_snapshots_v0.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "snapshots": {
                    "msg_snap_aaa_2026-04-01": {
                        "asset_id": "AAA",
                        "spectrum": {"spectrum_position": 0.60},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    join = {
        "contract": "REPLAY_LINEAGE_JOIN_V1",
        "asset_id": "AAA",
        "horizon": "short",
        "brain_overlay_ids": ["ovr_test_weakens"],
        "current_spectrum_position": 0.30,
    }
    aging_ctx = {"bound_overlays": [overlay], "repo_root": repo_root}
    _inject_lineage_into_timeline_events(events, join, None, aging_ctx)

    evt = events[0]
    assert evt["current_spectrum_position"] == pytest.approx(0.30)
    assert evt["snapshot_spectrum_position"] == pytest.approx(0.60)
    aging = evt["overlay_aging_lineage"]
    assert len(aging) == 1
    assert aging[0]["overlay_id"] == "ovr_test_weakens"
    # Current (0.30) < snapshot (0.60) by > 0.05 with position_weakens hint
    # → aged_in_line.
    assert aging[0]["aging_label"] == "aged_in_line"

    mb = micro_brief_for_event(events, "evt_decision_1")
    assert mb is not None
    assert mb["overlay_aging_lineage"][0]["aging_label"] == "aged_in_line"
    assert mb["snapshot_spectrum_position"] == pytest.approx(0.60)
    assert mb["current_spectrum_position"] == pytest.approx(0.30)

    # Pure compute sanity check.
    lineage = _compute_overlay_aging_lineage(
        overlays=[overlay],
        snapshot_spectrum_position=0.60,
        current_spectrum_position=0.30,
    )
    assert lineage[0]["aging_label"] == "aged_in_line"


def test_inject_overlay_aging_neutral_when_snapshot_missing(
    tmp_path: Path,
) -> None:
    from phase47_runtime.traceability_replay import _inject_lineage_into_timeline_events

    overlay = {
        "overlay_id": "ovr_unknown_snapshot",
        "overlay_type": "regime_shift",
        "expected_direction_hint": "position_weakens",
    }
    events = [
        {
            "event_id": "evt_decision_2",
            "event_type": "decision_event",
            "asset_id": "BBB",
            "timestamp_utc": "2026-04-17T12:00:00Z",
            "message_snapshot_id": "msg_not_in_store",
            "brain_overlay_ids_at_decision": ["ovr_unknown_snapshot"],
            "persona_candidate_ids_at_decision": [],
        }
    ]
    # Empty snapshot store.
    (tmp_path / "data" / "mvp").mkdir(parents=True)
    (tmp_path / "data" / "mvp" / "message_snapshots_v0.json").write_text(
        json.dumps({"schema_version": 1, "snapshots": {}}),
        encoding="utf-8",
    )
    join = {
        "asset_id": "BBB",
        "brain_overlay_ids": ["ovr_unknown_snapshot"],
        "current_spectrum_position": 0.5,
    }
    _inject_lineage_into_timeline_events(
        events,
        join,
        None,
        {"bound_overlays": [overlay], "repo_root": tmp_path},
    )
    evt = events[0]
    assert evt["overlay_aging_lineage"][0]["aging_label"] == "neutral"


def test_inject_no_aging_when_no_overlays_bound(tmp_path: Path) -> None:
    from phase47_runtime.traceability_replay import _inject_lineage_into_timeline_events

    events = [
        {
            "event_id": "evt_decision_3",
            "event_type": "decision_event",
            "asset_id": "CCC",
            "timestamp_utc": "2026-04-17T12:00:00Z",
        }
    ]
    _inject_lineage_into_timeline_events(
        events, {"asset_id": "CCC", "brain_overlay_ids": []}, None, None
    )
    assert "overlay_aging_lineage" not in events[0]


def test_research_overlay_explanations_match_seed_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every string emitted MUST come from the seed overlay record — no synthesis."""
    bundle_path = _write_temp_bundle_with_transcript_overlays(tmp_path)
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(bundle_path))
    monkeypatch.setenv("METIS_TODAY_SOURCE", "registry")
    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    short_rows = raw["spectrum_rows_by_horizon"]["short"]
    asset_id = str(short_rows[0]["asset_id"])
    payload = build_today_object_detail_payload(
        repo_root=REPO_ROOT, asset_id=asset_id, horizon="short", lang="ko"
    )
    assert payload["ok"]
    seed = _load_overlay_seed()
    seed_by_id = {ov["overlay_id"]: ov for ov in seed["overlays"]}
    for exp in payload["research"]["overlay_explanations"]:
        src = seed_by_id[exp["overlay_id"]]
        assert exp["what_it_changes"] == src.get("what_it_changes", "")
        # Either source_artifact_refs_summary OR first ref summary fallback.
        refs = src.get("source_artifact_refs") or []
        first = refs[0] if refs else {}
        allowed_sources = {
            src.get("source_artifact_refs_summary", ""),
            first.get("summary", ""),
        }
        assert exp["source_artifact_ref_summary"] in allowed_sources
        assert exp["recheck_rule"] == src.get("expiry_or_recheck_rule", "")
        assert exp["expected_direction_hint"] == src.get(
            "expected_direction_hint", ""
        )
