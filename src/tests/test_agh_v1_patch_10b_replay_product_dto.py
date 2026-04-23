"""Patch 10B — Product Shell ``/api/product/replay`` DTO composer tests."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

from phase47_runtime.product_shell.view_models_replay import (  # type: ignore
    compose_replay_product_dto,
)
from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore


def _stub_bundle(provenance: dict[str, dict[str, object]] | None = None):
    provenance = provenance or {hz: {"source": "real_derived"} for hz in HORIZON_KEYS}
    reg_entries = []
    artifacts = []
    for hz in HORIZON_KEYS:
        reg_entries.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"art_stub_{hz}",
            registry_entry_id=f"reg_stub_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
        artifacts.append(SimpleNamespace(
            artifact_id=f"art_stub_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
    return SimpleNamespace(
        artifacts=artifacts,
        registry_entries=reg_entries,
        horizon_provenance=provenance,
        metadata={"graduation_tier": "production",
                  "built_at_utc": "2026-04-23T07:30:00Z"},
        as_of_utc="2026-04-23T08:00:00Z",
    )


def _spectrum_by_hz():
    rows = [
        {"asset_id": "AAPL", "spectrum_position": 0.6,  "rank_index": 1,
         "rank_movement": "up",   "rationale_summary": "모멘텀 강세",
         "what_changed": "상승 지속"},
        {"asset_id": "MSFT", "spectrum_position": -0.4, "rank_index": 2,
         "rank_movement": "down", "rationale_summary": "조정 국면",
         "what_changed": "하락 전환"},
    ]
    return {hz: {"ok": True, "rows": rows} for hz in HORIZON_KEYS}


def _lineage_sample():
    """A synthetic governance-lineage chain with a 45-day gap."""
    return {
        "ok": True,
        "registry_entry_id": "reg_stub_short",
        "horizon": "short",
        "chain": [
            {
                "proposal": {
                    "packet_id": "pkt_prop_2",
                    "created_at_utc": "2026-03-01T10:00:00Z",
                    "payload": {
                        "change_reason_human": "시장 변화로 인해 가중치를 조정 제안",
                    },
                },
                "decision": {
                    "packet_id": "pkt_dec_2",
                    "created_at_utc": "2026-03-01T12:00:00Z",
                    "payload": {
                        "change_reason_human": "운영자가 승인",
                        "outcome": "adopted",
                    },
                },
                "applied": {
                    "packet_id": "pkt_app_2",
                    "created_at_utc": "2026-03-02T09:00:00Z",
                    "payload": {
                        "outcome": "applied",
                        "change_reason_human": "라이브 상태에 반영 완료",
                    },
                },
                "spectrum_refresh": {
                    "packet_id": "pkt_ref_2",
                    "created_at_utc": "2026-03-02T10:00:00Z",
                    "payload": {
                        "change_reason_human": "스펙트럼이 갱신되었습니다",
                    },
                },
                "validation_promotion_evaluation": None,
            },
            {
                "proposal": {
                    "packet_id": "pkt_prop_1",
                    "created_at_utc": "2026-01-10T10:00:00Z",
                    "payload": {
                        "change_reason_human": "초기 가설 제안",
                    },
                },
                "decision": None,
                "applied": None,
                "spectrum_refresh": None,
                "validation_promotion_evaluation": None,
            },
        ],
        "sandbox_followups": [],
        "summary": {
            "total_proposals": 2,
            "total_applied":   1,
            "total_spectrum_refreshed": 1,
            "total_sandbox_requests": 0,
        },
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestTimelineComposition:
    def test_contract_and_shape(self):
        dto = compose_replay_product_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            lineage=_lineage_sample(),
            asset_id="AAPL",
            horizon_key="short",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["contract"] == "PRODUCT_REPLAY_V1"
        assert dto["ok"] is True
        assert dto["focus"]["asset_id"] == "AAPL"
        assert dto["focus"]["horizon_key"] == "short"
        assert dto["focus"]["row_matched"] is True
        assert len(dto["scenarios"]) == 3
        scenario_kinds = [s["kind"] for s in dto["scenarios"]]
        assert scenario_kinds == ["baseline", "weakened_evidence", "stressed"]
        tl_kinds = {e["kind"] for e in dto["timeline"]}
        # proposal/decision/applied/spectrum_refresh are all present,
        # plus a gap annotation from the >30-day span.
        assert {"proposal", "decision", "applied", "spectrum_refresh", "gap"} <= tl_kinds

    def test_gap_annotation_emitted(self):
        dto = compose_replay_product_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            lineage=_lineage_sample(),
            asset_id="AAPL",
            horizon_key="short",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        gaps = [e for e in dto["timeline"] if e.get("kind") == "gap"]
        assert len(gaps) == 1
        assert gaps[0]["days"] >= 30
        assert gaps[0]["tag"] == "gap"

    def test_checkpoints_start_and_end(self):
        dto = compose_replay_product_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            lineage=_lineage_sample(),
            asset_id="AAPL",
            horizon_key="short",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        positions = {c["position"] for c in dto["checkpoints"]}
        assert positions == {"start", "end"}

    def test_scenario_stances_change_across_cards(self):
        dto = compose_replay_product_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            lineage=_lineage_sample(),
            asset_id="AAPL",
            horizon_key="short",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        scenarios = dto["scenarios"]
        # AAPL baseline pos 0.6 is long; weakened reduces toward neutral;
        # stressed flips to short bias. Positions must be strictly moving
        # from baseline toward / past neutral.
        baseline = [s for s in scenarios if s["kind"] == "baseline"][0]["position"]
        weakened = [s for s in scenarios if s["kind"] == "weakened_evidence"][0]["position"]
        stressed = [s for s in scenarios if s["kind"] == "stressed"][0]["position"]
        assert baseline == 0.6
        assert 0 <= weakened < baseline
        assert stressed < 0

    def test_empty_lineage_yields_empty_state_and_still_composes_scenarios(self):
        dto = compose_replay_product_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            lineage=None,
            asset_id="AAPL",
            horizon_key="short",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["empty_state"] is not None
        assert dto["empty_state"]["kind"] == "no_lineage"
        # Scenarios still composed from spectrum.
        assert len(dto["scenarios"]) == 3

    def test_no_engineering_tokens(self):
        dto = compose_replay_product_dto(
            bundle=_stub_bundle({
                "short":       {"source": "real_derived"},
                "medium":      {"source": "real_derived_with_degraded_challenger"},
                "medium_long": {"source": "template_fallback"},
                "long":        {"source": "insufficient_evidence"},
            }),
            spectrum_by_horizon=_spectrum_by_hz(),
            lineage=_lineage_sample(),
            asset_id="AAPL",
            horizon_key="short",
            lang="en",
            now_utc="2026-04-23T08:00:00Z",
        )
        blob = json.dumps(dto, ensure_ascii=False)
        banned = [
            r"\bart_[A-Za-z0-9_]+\b",
            r"\breg_[A-Za-z0-9_]+\b",
            r"\bfactor_",
            r"\bpkt_[A-Za-z0-9_]+\b",
            r"\breal_derived\b",
            r"\btemplate_fallback\b",
            r"\binsufficient_evidence\b",
            r"\bhorizon_provenance\b",
            r"\breplay_lineage_pointer\b",
        ]
        for pat in banned:
            m = re.search(pat, blob)
            assert m is None, f"leaked {pat}: {m!r}"

    def test_row_not_matched_falls_back_to_representative(self):
        dto = compose_replay_product_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            lineage=_lineage_sample(),
            asset_id="GOOGL",
            horizon_key="short",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["focus"]["row_matched"] is False
        # Representative row in sample has |pos|=0.6 (AAPL).
        baseline = [s for s in dto["scenarios"] if s["kind"] == "baseline"][0]
        assert abs(baseline["position"]) == 0.6


# ---------------------------------------------------------------------------
# Integration — dispatch through the routes layer
# ---------------------------------------------------------------------------


class TestReplayRoute:
    def test_route_returns_packet(self, tmp_path):
        from phase47_runtime.routes import dispatch_json
        from phase47_runtime.runtime_state import CockpitRuntimeState

        bpath = tmp_path / "phase46_bundle.json"
        bpath.write_text(
            json.dumps({
                "phase": "phase46_founder_decision_cockpit",
                "generated_utc": "2026-04-23T08:00:00+00:00",
                "founder_read_model": {"asset_id": "x"},
                "cockpit_state": {"cohort_aggregate": {"decision_card": {}}},
            }),
            encoding="utf-8",
        )
        (tmp_path / "a.json").write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
        (tmp_path / "d.json").write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
        st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
        code, obj = dispatch_json(
            st, method="GET",
            path="/api/product/replay?asset=AAPL&horizon=short",
            body=None,
        )
        assert code == 200
        assert obj.get("contract") == "PRODUCT_REPLAY_V1"
        assert "scenarios" in obj
