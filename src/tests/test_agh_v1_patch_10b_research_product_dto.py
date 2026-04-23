"""Patch 10B — Product Shell ``/api/product/research`` DTO composer tests."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from phase47_runtime.product_shell.view_models_research import (  # type: ignore
    compose_research_deepdive_dto,
    compose_research_landing_dto,
)
from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore


def _stub_bundle(provenance: dict[str, dict[str, object]]):
    reg_entries = []
    artifacts = []
    for hz in HORIZON_KEYS:
        reg_entries.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"art_stub_{hz}",
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


def _spectrum_rows():
    return [
        {"asset_id": "AAPL", "spectrum_position": 0.72, "rank_index": 1,
         "rank_movement": "up", "rationale_summary": "모멘텀 강세 지속",
         "what_changed": "지난 갱신 대비 순위 상승"},
        {"asset_id": "MSFT", "spectrum_position": 0.42, "rank_index": 2,
         "rank_movement": "steady", "rationale_summary": "유틸리티 방어성",
         "what_changed": "큰 변화 없음"},
        {"asset_id": "NVDA", "spectrum_position": -0.35, "rank_index": 3,
         "rank_movement": "down", "rationale_summary": "숨고르기 국면",
         "what_changed": "모멘텀 둔화"},
        {"asset_id": "TSLA", "spectrum_position": -0.8, "rank_index": 4,
         "rank_movement": "down", "rationale_summary": "역풍 지속",
         "what_changed": "추세 반전"},
    ]


def _spectrum_by_hz():
    return {hz: {"ok": True, "rows": _spectrum_rows()} for hz in HORIZON_KEYS}


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------


class TestLanding:
    def test_contract_and_shape(self):
        bundle = _stub_bundle({hz: {"source": "real_derived"} for hz in HORIZON_KEYS})
        dto = compose_research_landing_dto(
            bundle=bundle,
            spectrum_by_horizon=_spectrum_by_hz(),
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["contract"] == "PRODUCT_RESEARCH_LANDING_V1"
        assert dto["presentation"] == "landing"
        assert dto["lang"] == "ko"
        assert len(dto["columns"]) == 4
        for col in dto["columns"]:
            assert col["horizon_key"] in HORIZON_KEYS
            assert 1 <= len(col["tiles"]) <= 3

    def test_tiles_sorted_by_magnitude(self):
        bundle = _stub_bundle({hz: {"source": "real_derived"} for hz in HORIZON_KEYS})
        dto = compose_research_landing_dto(
            bundle=bundle,
            spectrum_by_horizon=_spectrum_by_hz(),
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
            top_n_per_horizon=3,
        )
        col0 = dto["columns"][0]
        tickers = [t["ticker"] for t in col0["tiles"]]
        # TSLA has |pos|=0.8 (highest), AAPL=0.72, MSFT=0.42
        assert tickers[0] == "TSLA"
        assert tickers[1] == "AAPL"
        assert tickers[2] == "MSFT"

    def test_degraded_empty_state_for_preparing(self):
        bundle = _stub_bundle({
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "insufficient_evidence"},
            "long":        {"source": "insufficient_evidence"},
        })
        spectrum = {
            "short":       {"ok": True, "rows": _spectrum_rows()},
            "medium":      {"ok": True, "rows": _spectrum_rows()},
            "medium_long": {"ok": True, "rows": []},
            "long":        {"ok": False, "error": "x"},
        }
        dto = compose_research_landing_dto(
            bundle=bundle, spectrum_by_horizon=spectrum,
            lang="ko", now_utc="2026-04-23T08:00:00Z",
        )
        long_col = [c for c in dto["columns"] if c["horizon_key"] == "long"][0]
        assert long_col["empty_state"] is not None
        assert long_col["empty_state"]["kind"] == "preparing"
        assert long_col["confidence"]["source_key"] == "preparing"

    def test_no_engineering_tokens(self):
        bundle = _stub_bundle({
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived_with_degraded_challenger"},
            "medium_long": {"source": "template_fallback"},
            "long":        {"source": "insufficient_evidence"},
        })
        for lg in ("ko", "en"):
            dto = compose_research_landing_dto(
                bundle=bundle,
                spectrum_by_horizon=_spectrum_by_hz(),
                lang=lg, now_utc="2026-04-23T08:00:00Z",
            )
            blob = json.dumps(dto, ensure_ascii=False)
            for pat in (r"\bart_[A-Za-z0-9_]+\b", r"\breg_", r"\bfactor_",
                        r"\bpkt_", r"\breal_derived\b", r"\bhorizon_provenance\b",
                        r"\btemplate_fallback\b", r"\binsufficient_evidence\b"):
                m = re.search(pat, blob)
                assert m is None, f"lang={lg} leaked {pat}: {m!r}"


# ---------------------------------------------------------------------------
# Deep dive
# ---------------------------------------------------------------------------


class TestDeepDive:
    def test_contract_and_three_rails(self):
        bundle = _stub_bundle({hz: {"source": "real_derived"} for hz in HORIZON_KEYS})
        dto = compose_research_deepdive_dto(
            bundle=bundle,
            spectrum_by_horizon=_spectrum_by_hz(),
            asset_id="AAPL",
            horizon_key="short",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["contract"] == "PRODUCT_RESEARCH_DEEPDIVE_V1"
        assert dto["presentation"] == "deepdive"
        assert dto["ok"] is True
        assert dto["claim"]["ticker"] == "AAPL"
        assert dto["claim"]["horizon_key"] == "short"
        assert dto["claim"]["row_matched"] is True
        assert len(dto["evidence"]) == 5
        kinds = [c["kind"] for c in dto["evidence"]]
        assert kinds == [
            "what_changed",
            "strongest_support",
            "counter_or_companion",
            "missing_or_preparing",
            "peer_context",
        ]
        assert len(dto["actions"]) >= 3
        for a in dto["actions"]:
            # No buy/sell imperative in any action
            assert a["kind"] in ("open_replay", "ask_ai", "back_to_today", "compare_watchlist")

    def test_unknown_horizon_is_guarded(self):
        bundle = _stub_bundle({hz: {"source": "real_derived"} for hz in HORIZON_KEYS})
        dto = compose_research_deepdive_dto(
            bundle=bundle,
            spectrum_by_horizon=_spectrum_by_hz(),
            asset_id="AAPL",
            horizon_key="nope",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto.get("ok") is False
        assert dto.get("error_kind") == "unknown_horizon"

    def test_asset_not_in_rows_falls_back(self):
        bundle = _stub_bundle({hz: {"source": "real_derived"} for hz in HORIZON_KEYS})
        dto = compose_research_deepdive_dto(
            bundle=bundle,
            spectrum_by_horizon=_spectrum_by_hz(),
            asset_id="GOOGL",
            horizon_key="short",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["ok"] is True
        assert dto["claim"]["row_matched"] is False
        # Missing card should explicitly acknowledge the absent asset
        missing = [c for c in dto["evidence"] if c["kind"] == "missing_or_preparing"][0]
        assert missing["body"]

    def test_preparing_horizon_evidence_is_honest(self):
        bundle = _stub_bundle({
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long":        {"source": "insufficient_evidence"},
        })
        dto = compose_research_deepdive_dto(
            bundle=bundle,
            spectrum_by_horizon={
                "short":       {"ok": True, "rows": _spectrum_rows()},
                "medium":      {"ok": True, "rows": _spectrum_rows()},
                "medium_long": {"ok": True, "rows": _spectrum_rows()},
                "long":        {"ok": True, "rows": []},
            },
            asset_id="AAPL",
            horizon_key="long",
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["claim"]["confidence"]["source_key"] == "preparing"
        assert dto["claim"]["grade"]["key"] == "f"

    def test_no_engineering_tokens(self):
        bundle = _stub_bundle({hz: {"source": "real_derived_with_degraded_challenger"}
                               for hz in HORIZON_KEYS})
        for lg in ("ko", "en"):
            dto = compose_research_deepdive_dto(
                bundle=bundle,
                spectrum_by_horizon=_spectrum_by_hz(),
                asset_id="AAPL", horizon_key="short",
                lang=lg, now_utc="2026-04-23T08:00:00Z",
            )
            blob = json.dumps(dto, ensure_ascii=False)
            for pat in (r"\bart_[A-Za-z0-9_]+\b", r"\breg_", r"\bfactor_",
                        r"\bpkt_", r"\breal_derived\b", r"\bhorizon_provenance\b"):
                m = re.search(pat, blob)
                assert m is None, f"lang={lg} leaked {pat}: {m!r}"


# ---------------------------------------------------------------------------
# Integration — dispatch through the routes layer
# ---------------------------------------------------------------------------


class TestResearchRoute:
    def test_landing_route_returns_packet(self, tmp_path):
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
        code, obj = dispatch_json(st, method="GET", path="/api/product/research", body=None)
        assert code == 200
        assert obj.get("ok") is True
        assert obj.get("contract") == "PRODUCT_RESEARCH_LANDING_V1"

    def test_deepdive_route_returns_packet(self, tmp_path):
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
            path="/api/product/research?presentation=deepdive&asset=AAPL&horizon=short",
            body=None,
        )
        assert code == 200
        assert obj.get("contract") == "PRODUCT_RESEARCH_DEEPDIVE_V1"
        assert obj.get("presentation") == "deepdive"
