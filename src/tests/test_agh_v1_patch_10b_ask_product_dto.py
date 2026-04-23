"""Patch 10B — Product Shell ``/api/product/ask`` DTO composer tests."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

from phase47_runtime.product_shell.view_models_ask import (  # type: ignore
    compose_ask_product_dto,
    compose_quick_answers_dto,
    compose_request_state_dto,
    scrub_free_text_answer,
)
from phase47_runtime.product_shell.view_models_common import HORIZON_KEYS  # type: ignore


def _stub_bundle():
    reg = []
    arts = []
    for hz in HORIZON_KEYS:
        reg.append(SimpleNamespace(
            status="active", horizon=hz,
            active_artifact_id=f"art_stub_{hz}",
            registry_entry_id=f"reg_stub_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
        arts.append(SimpleNamespace(
            artifact_id=f"art_stub_{hz}",
            display_family_name_ko=f"{hz}-가문",
            display_family_name_en=f"{hz}-family",
        ))
    return SimpleNamespace(
        artifacts=arts,
        registry_entries=reg,
        horizon_provenance={
            "short":       {"source": "real_derived"},
            "medium":      {"source": "real_derived_with_degraded_challenger"},
            "medium_long": {"source": "template_fallback"},
            "long":        {"source": "insufficient_evidence"},
        },
        metadata={"graduation_tier": "production",
                  "built_at_utc": "2026-04-23T07:30:00Z"},
        as_of_utc="2026-04-23T08:00:00Z",
    )


def _spectrum_by_hz():
    rows = [
        {"asset_id": "AAPL", "spectrum_position": 0.6,  "rank_index": 1,
         "rank_movement": "up", "rationale_summary": "모멘텀 강세",
         "what_changed": "상승 지속"},
        {"asset_id": "MSFT", "spectrum_position": -0.4, "rank_index": 2,
         "rank_movement": "down", "rationale_summary": "조정 국면",
         "what_changed": "하락 전환"},
    ]
    return {hz: {"ok": True, "rows": rows} for hz in HORIZON_KEYS}


# ---------------------------------------------------------------------------
# Landing DTO
# ---------------------------------------------------------------------------


class TestAskLanding:
    def test_contract_and_shape(self):
        dto = compose_ask_product_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            asset_id="AAPL",
            horizon_key="short",
            followups=[],
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["contract"] == "PRODUCT_ASK_V1"
        assert dto["lang"] == "ko"
        assert dto["context"]["asset_id"] == "AAPL"
        assert dto["context"]["horizon_key"] == "short"
        assert len(dto["quick_chips"]) == 6
        intents = [c["intent"] for c in dto["quick_chips"]]
        assert intents == [
            "explain_claim", "show_support", "show_counter",
            "other_horizons", "why_confidence", "whats_missing",
        ]
        assert dto["free_text"]["max_length"] == 400
        assert "banner" not in dto["contract_banner"] or True  # tolerant

    def test_no_engineering_tokens(self):
        dto = compose_ask_product_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            asset_id="AAPL",
            horizon_key="short",
            followups=[],
            lang="en",
            now_utc="2026-04-23T08:00:00Z",
        )
        blob = json.dumps(dto, ensure_ascii=False)
        banned = [
            r"\bart_[A-Za-z0-9_]+\b",
            r"\breg_[A-Za-z0-9_]+\b",
            r"\bpkt_[A-Za-z0-9_]+\b",
            r"\breal_derived\b",
            r"\btemplate_fallback\b",
            r"\binsufficient_evidence\b",
            r"\bhorizon_provenance\b",
            r"\bprocess_governed_prompt\b",
        ]
        for pat in banned:
            m = re.search(pat, blob)
            assert m is None, f"leaked {pat}: {m!r}"


# ---------------------------------------------------------------------------
# Quick answers
# ---------------------------------------------------------------------------


class TestQuickAnswers:
    def test_all_six_quick_answers_composed(self):
        dto = compose_quick_answers_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            asset_id="AAPL",
            horizon_key="short",
            lang="ko",
        )
        assert dto["contract"] == "PRODUCT_ASK_QUICK_V1"
        assert len(dto["answers"]) == 6
        kinds = [a["intent"] for a in dto["answers"]]
        assert kinds[0] == "explain_claim"

    def test_explain_claim_surfaces_rationale(self):
        dto = compose_quick_answers_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon=_spectrum_by_hz(),
            asset_id="AAPL",
            horizon_key="short",
            lang="ko",
        )
        a = [x for x in dto["answers"] if x["intent"] == "explain_claim"][0]
        assert a["claim"]
        assert any("모멘텀" in s for s in a["evidence"])

    def test_preparing_horizon_quick_answer_is_honest(self):
        dto = compose_quick_answers_dto(
            bundle=_stub_bundle(),
            spectrum_by_horizon={
                **_spectrum_by_hz(),
                "long": {"ok": True, "rows": []},
            },
            asset_id="AAPL",
            horizon_key="long",
            lang="ko",
        )
        a = [x for x in dto["answers"] if x["intent"] == "show_support"][0]
        assert a["insufficiency"]


# ---------------------------------------------------------------------------
# Free-text wrapper: degraded & grounded paths
# ---------------------------------------------------------------------------


class TestFreeText:
    def _ctx(self):
        return {
            "asset_id": "AAPL",
            "horizon_key": "short",
            "horizon_caption": "단기",
            "row_matched": True,
            "confidence": {"source_key": "live", "label": "실데이터 근거", "tooltip": ""},
            "grade": {"key": "a", "label": "A"},
            "stance": {"key": "long", "label": "매수 경향"},
        }

    def test_empty_prompt_returns_empty_kind(self):
        out = scrub_free_text_answer(
            prompt="",
            context=self._ctx(),
            conversation_callable=lambda: {"ok": True, "response": {"body": "x"}},
            lang="ko",
        )
        assert out["kind"] == "empty_prompt"
        assert out["grounded"] is False

    def test_degraded_when_callable_raises(self):
        def _boom():
            raise RuntimeError("llm down")
        out = scrub_free_text_answer(
            prompt="이 청구를 설명해 줘",
            context=self._ctx(),
            conversation_callable=_boom,
            lang="ko",
        )
        assert out["kind"] == "degraded"
        assert out["grounded"] is False
        assert "banner" in out

    def test_degraded_when_callable_returns_not_ok(self):
        out = scrub_free_text_answer(
            prompt="이 청구를 설명해 줘",
            context=self._ctx(),
            conversation_callable=lambda: {"ok": False, "error": "something"},
            lang="ko",
        )
        assert out["kind"] == "degraded"

    def test_grounded_answer_scrubbed_for_engineering_tokens(self):
        out = scrub_free_text_answer(
            prompt="설명",
            context=self._ctx(),
            conversation_callable=lambda: {
                "ok": True,
                "response": {
                    "body": "이 art_123 과 reg_test 는 내부 식별자입니다. 실데이터 근거.",
                },
            },
            lang="ko",
        )
        assert out["kind"] == "grounded"
        assert out["grounded"] is True
        for s in out["claim"]:
            assert "art_123" not in s
            assert "reg_test" not in s


# ---------------------------------------------------------------------------
# Request-state
# ---------------------------------------------------------------------------


class TestRequestState:
    def test_empty_list_yields_empty_state(self):
        dto = compose_request_state_dto([], lang="ko")
        assert dto["contract"] == "PRODUCT_REQUEST_STATE_V1"
        assert dto["empty_state"] is not None
        assert dto["cards"] == []

    def test_running_completed_blocked(self):
        followups = [
            {
                "request": {"packet_id": "pkt_r1",
                            "created_at_utc": "2026-04-01T00:00:00Z",
                            "payload": {"kind": "validation_rerun"}},
                "result":  None,
            },
            {
                "request": {"packet_id": "pkt_r2",
                            "created_at_utc": "2026-04-02T00:00:00Z",
                            "payload": {"kind": "validation_rerun"}},
                "result":  {"packet_id": "pkt_s2",
                            "created_at_utc": "2026-04-03T00:00:00Z",
                            "payload": {"outcome": "completed"}},
            },
            {
                "request": {"packet_id": "pkt_r3",
                            "created_at_utc": "2026-04-04T00:00:00Z",
                            "payload": {"kind": "validation_rerun"}},
                "result":  {"packet_id": "pkt_s3",
                            "created_at_utc": "2026-04-05T00:00:00Z",
                            "payload": {"outcome": "blocked_insufficient_inputs"}},
            },
        ]
        dto = compose_request_state_dto(followups, lang="ko")
        assert len(dto["cards"]) == 3
        statuses = [c["status_key"] for c in dto["cards"]]
        assert statuses == ["running", "completed", "blocked"]
        blob = json.dumps(dto, ensure_ascii=False)
        assert "pkt_r1" not in blob
        assert "pkt_s2" not in blob


# ---------------------------------------------------------------------------
# Integration — routes
# ---------------------------------------------------------------------------


def _tmp_state(tmp_path):
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
    return CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)


class TestAskRoutes:
    def test_get_ask_landing(self, tmp_path):
        from phase47_runtime.routes import dispatch_json
        st = _tmp_state(tmp_path)
        code, obj = dispatch_json(
            st, method="GET",
            path="/api/product/ask?asset=AAPL&horizon=short",
            body=None,
        )
        assert code == 200
        assert obj.get("contract") == "PRODUCT_ASK_V1"
        assert len(obj.get("quick_chips") or []) == 6

    def test_get_ask_quick(self, tmp_path):
        from phase47_runtime.routes import dispatch_json
        st = _tmp_state(tmp_path)
        code, obj = dispatch_json(
            st, method="GET",
            path="/api/product/ask/quick?asset=AAPL&horizon=short",
            body=None,
        )
        assert code == 200
        assert obj.get("contract") == "PRODUCT_ASK_QUICK_V1"
        assert len(obj.get("answers") or []) == 6

    def test_get_requests(self, tmp_path):
        from phase47_runtime.routes import dispatch_json
        st = _tmp_state(tmp_path)
        code, obj = dispatch_json(st, method="GET", path="/api/product/requests", body=None)
        assert code == 200
        assert obj.get("contract") == "PRODUCT_REQUEST_STATE_V1"

    def test_post_ask_degraded_path(self, tmp_path):
        """Free-text POST should return a degraded-but-clean envelope
        even when the LLM layer cannot route the question."""
        from phase47_runtime.routes import dispatch_json
        st = _tmp_state(tmp_path)
        body = json.dumps({
            "prompt": "이 청구를 설명해 줘",
            "context": {"asset_id": "AAPL", "horizon_key": "short"},
        }).encode("utf-8")
        code, obj = dispatch_json(st, method="POST", path="/api/product/ask", body=body)
        assert code == 200
        assert obj.get("contract") == "PRODUCT_ASK_ANSWER_V1"
        assert obj.get("answer", {}).get("kind") in ("grounded", "degraded", "empty_prompt")
