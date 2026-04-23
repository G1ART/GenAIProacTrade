"""Patch 10C — Ops ↔ Product cross-abstraction parity test.

Scope A3 of the Patch 10C workorder says:

> 동일 focus에 대해 Ops Cockpit의 raw lineage/message 와 Product Shell의
> customer wording 이 같은 사실을 다른 추상화 레벨에서 말하고 있음을
> 검증하는 테스트/증거를 추가한다.

This test builds a realistic governance lineage payload (the same
shape ``api_governance_lineage_for_registry_entry`` returns to the
Ops Cockpit) and feeds it into the Product Shell Replay composer.
It then asserts:

- Every non-gap event in the Product Replay timeline corresponds to
  a packet (proposal / decision / applied / spectrum_refresh /
  validation_promotion_evaluation) in the raw chain, PLUS every
  sandbox followup pair yields exactly two events (request+result) or
  one (request-only pending).
- No raw packet IDs or engineering enums leak into the Product DTO.
- Product-side status labels ("Completed" / "Blocked") cover the same
  outcome semantics as the raw outcome strings.
"""

from __future__ import annotations

from types import SimpleNamespace

from phase47_runtime.product_shell.view_models_replay import compose_replay_product_dto
from phase47_runtime.product_shell.view_models_common import ENG_ID_PATTERNS


NOW = "2026-04-23T00:00:00Z"


def _bundle() -> SimpleNamespace:
    return SimpleNamespace(
        as_of_utc=NOW,
        horizon_provenance={
            "short": {"source": "real_derived"},
            "medium": {"source": "real_derived"},
            "medium_long": {"source": "real_derived"},
            "long": {"source": "real_derived"},
        },
        registry_entries=[
            SimpleNamespace(
                status="active", horizon="short",
                active_artifact_id="art_x", registry_entry_id="reg_x",
                display_family_name_ko="모멘텀", display_family_name_en="Momentum",
            ),
        ],
        artifacts=[
            SimpleNamespace(artifact_id="art_x",
                            display_family_name_ko="모멘텀",
                            display_family_name_en="Momentum"),
        ],
        metadata={"built_at_utc": NOW, "graduation_tier": "production"},
    )


def _spectrum() -> dict:
    return {
        "short": {
            "ok": True,
            "rows": [
                {
                    "asset_id": "AAPL", "spectrum_position": 0.42,
                    "rank_index": 0, "rank_movement": "up",
                    "what_changed": "Momentum picked up.",
                    "rationale_summary": "Short-term flow leaning long.",
                },
            ],
        },
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long":        {"ok": True, "rows": []},
    }


def _synthetic_lineage() -> dict:
    """Shape mirrors ``api_governance_lineage_for_registry_entry`` output."""
    return {
        "ok": True,
        "registry_entry_id": "reg_x",
        "horizon": "short",
        "chain": [
            {
                "proposal": {
                    "proposal_packet_id": "pkt_prop_1",
                    "created_at_utc": "2026-03-01T00:00:00Z",
                    "payload": {
                        "rationale_free_text":
                            "Proposed a momentum refresh after the February beats.",
                    },
                },
                "decision": {
                    "decision_packet_id": "pkt_dec_1",
                    "created_at_utc": "2026-03-02T00:00:00Z",
                    "payload": {
                        "change_reason_human":
                            "Adopted the momentum update after validation promotion.",
                    },
                },
                "applied": {
                    "decision_packet_id": "pkt_dec_1",
                    "created_at_utc": "2026-03-03T00:00:00Z",
                    "payload": {
                        "outcome": "applied",
                        "summary":
                            "Applied the new registry entry to live state.",
                    },
                },
                "spectrum_refresh": {
                    "artifact_id": "art_x",
                    "created_at_utc": "2026-03-04T00:00:00Z",
                    "payload": {
                        "notes": "Spectrum re-scored after the promotion.",
                    },
                },
                "validation_promotion_evaluation": {
                    "created_at_utc": "2026-03-05T00:00:00Z",
                    "payload": {
                        "outcome": "promoted",
                        "summary": "Evaluation passed the promotion bar.",
                    },
                },
            },
            {
                "proposal": {
                    "proposal_packet_id": "pkt_prop_2",
                    "created_at_utc": "2026-04-10T00:00:00Z",
                    "payload": {
                        "rationale_free_text":
                            "Proposed a second refresh to capture post-earnings drift.",
                    },
                },
                "decision": {
                    "decision_packet_id": "pkt_dec_2",
                    "created_at_utc": "2026-04-11T00:00:00Z",
                    "payload": {
                        "change_reason_human":
                            "Second adoption after post-earnings validation.",
                    },
                },
                "applied": {
                    "decision_packet_id": "pkt_dec_2",
                    "created_at_utc": "2026-04-12T00:00:00Z",
                    "payload": {
                        "outcome": "applied",
                        "summary": "Second apply; registry advanced.",
                    },
                },
            },
        ],
        "sandbox_followups": [
            {
                "request": {
                    "sandbox_request_id": "pkt_sbox_req_1",
                    "created_at_utc": "2026-04-13T00:00:00Z",
                    "payload": {
                        "kind": "validation_rerun",
                        "rationale_free_text":
                            "Operator asked for a bounded side-experiment.",
                    },
                },
                "result": {
                    "sandbox_result_id": "pkt_sbox_res_1",
                    "created_at_utc": "2026-04-13T01:00:00Z",
                    "payload": {
                        "outcome": "completed",
                        "summary": "Side-experiment completed without change.",
                    },
                },
            },
            {
                "request": {
                    "sandbox_request_id": "pkt_sbox_req_2",
                    "created_at_utc": "2026-04-14T00:00:00Z",
                    "payload": {
                        "kind": "validation_rerun",
                        "rationale_free_text":
                            "A second bounded ask, this one blocked.",
                    },
                },
                "result": {
                    "sandbox_result_id": "pkt_sbox_res_2",
                    "created_at_utc": "2026-04-14T02:00:00Z",
                    "payload": {
                        "outcome": "blocked_insufficient_inputs",
                        "summary": "Blocked due to missing companion evidence.",
                    },
                },
            },
        ],
        "summary": {
            "total_applied": 2,
            "total_sandbox_requests": 2,
            "total_sandbox_completed": 1,
            "total_sandbox_blocked": 1,
        },
    }


def _count_expected_events(lineage: dict) -> int:
    count = 0
    for step in lineage["chain"]:
        for key in ("proposal", "decision", "applied",
                    "spectrum_refresh", "validation_promotion_evaluation"):
            if isinstance(step.get(key), dict):
                count += 1
    for pair in lineage["sandbox_followups"]:
        if isinstance(pair.get("request"), dict):
            count += 1
        if isinstance(pair.get("result"), dict):
            count += 1
    return count


def test_ops_product_parity_event_count():
    lineage = _synthetic_lineage()
    dto = compose_replay_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lineage=lineage, asset_id="AAPL", horizon_key="short",
        lang="ko", now_utc=NOW,
    )
    expected = _count_expected_events(lineage)
    actual = dto["summary_counts"]["total_events"]
    assert actual == expected, (
        f"Product replay event count {actual} does not match raw chain {expected}"
    )


def test_ops_product_parity_sandbox_counts():
    lineage = _synthetic_lineage()
    dto = compose_replay_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lineage=lineage, asset_id="AAPL", horizon_key="short",
        lang="en", now_utc=NOW,
    )
    assert dto["summary_counts"]["total_applied"] == lineage["summary"]["total_applied"]
    assert dto["summary_counts"]["total_sandbox_requests"] == lineage["summary"]["total_sandbox_requests"]


def test_ops_product_parity_no_raw_id_leak():
    lineage = _synthetic_lineage()
    dto = compose_replay_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lineage=lineage, asset_id="AAPL", horizon_key="short",
        lang="ko", now_utc=NOW,
    )
    import json as _json
    serialized = _json.dumps(dto, ensure_ascii=False)
    for pat in ENG_ID_PATTERNS:
        assert not pat.search(serialized), f"engineering pattern leak: {pat.pattern}"
    # Specific raw packet ids must be absent.
    for raw in ("pkt_prop_1", "pkt_dec_1", "pkt_sbox_req_1", "pkt_sbox_res_1",
                "pkt_prop_2", "pkt_dec_2", "pkt_sbox_req_2", "pkt_sbox_res_2"):
        assert raw not in serialized, f"raw packet id leaked: {raw}"


def test_ops_product_parity_outcome_labels_are_humanized():
    lineage = _synthetic_lineage()
    dto_en = compose_replay_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lineage=lineage, asset_id="AAPL", horizon_key="short",
        lang="en", now_utc=NOW,
    )
    dto_ko = compose_replay_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lineage=lineage, asset_id="AAPL", horizon_key="short",
        lang="ko", now_utc=NOW,
    )
    titles_en = {ev["title"] for ev in dto_en["timeline"] if ev["kind"] != "gap"}
    titles_ko = {ev["title"] for ev in dto_ko["timeline"] if ev["kind"] != "gap"}
    # Humanized titles should appear in the customer language; raw
    # enum names like ``blocked_insufficient_inputs`` or
    # ``validation_promotion_evaluation`` must not.
    assert "blocked_insufficient_inputs" not in "|".join(titles_en)
    assert "validation_promotion_evaluation" not in "|".join(titles_en)
    assert "Sandbox blocked" in titles_en
    assert "Sandbox completed" in titles_en
    # KO surface uses Korean labels.
    assert any("보류" in t for t in titles_ko)
    assert any("완료" in t for t in titles_ko)


def test_ops_product_parity_gap_annotation_matches_real_gap():
    lineage = _synthetic_lineage()
    dto = compose_replay_product_dto(
        bundle=_bundle(), spectrum_by_horizon=_spectrum(),
        lineage=lineage, asset_id="AAPL", horizon_key="short",
        lang="en", now_utc=NOW,
    )
    gaps = [ev for ev in dto["timeline"] if ev["kind"] == "gap"]
    # The chain jumps from 2026-03-05 to 2026-04-10 (>=30 days apart),
    # so a single gap annotation should appear.
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap["days"] >= 30
    assert "no material updates" in gap["body"].lower() or "not " in gap["body"].lower()
