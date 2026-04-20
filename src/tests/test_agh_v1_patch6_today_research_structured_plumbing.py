"""AGH v1 Patch 6 — B2 plumbing: Today surface exposes the most recent
``research_structured_v1`` for the asset+horizon so the client-side
Research renderer has bullets + ``locale_coverage`` to show.

We exercise the private helper ``_latest_research_structured_v1_for_asset``
and verify:

  * empty ``asset_id`` returns ``None``;
  * unavailable harness store returns ``None`` (best-effort, never raises);
  * a latest-wins sort picks the most recently created matching packet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from phase47_runtime import today_spectrum
from phase47_runtime.today_spectrum import _latest_research_structured_v1_for_asset


class _FakeStore:
    def __init__(self, packets: list[dict[str, Any]]) -> None:
        self._packets = list(packets)

    def list_packets(self, *, packet_type: str, limit: int = 200):
        return [p for p in self._packets if p.get("packet_type") == packet_type][:limit]


def _mk_user_query_packet(
    *,
    packet_id: str,
    asset_id: str,
    created_at_utc: str,
    summary_ko: list[str],
    summary_en: list[str],
    locale_coverage: str = "dual",
    routed_kind: str = "deeper_rationale",
) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "packet_type": "UserQueryActionPacketV1",
        "created_at_utc": created_at_utc,
        "target_scope": {"asset_id": asset_id, "horizon": "short"},
        "payload": {
            "routed_kind": routed_kind,
            "llm_response": {
                "cited_packet_ids": ["Pkt:src_1", "Pkt:src_2"],
                "research_structured_v1": {
                    "summary_bullets_ko": summary_ko,
                    "summary_bullets_en": summary_en,
                    "residual_uncertainty_bullets": [],
                    "what_to_watch_bullets": [],
                    "evidence_cited": ["Pkt:src_1"],
                    "proposed_sandbox_request": None,
                    "locale_coverage": locale_coverage,
                },
            },
        },
    }


def test_returns_none_for_empty_asset_id(tmp_path: Path) -> None:
    got = _latest_research_structured_v1_for_asset(
        repo_root=tmp_path, asset_id="", horizon="short"
    )
    assert got is None


def test_returns_none_when_store_builder_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(**_kw):
        raise RuntimeError("store unavailable")

    # Patch the ``build_store`` symbol in the deferred import path. The
    # helper imports from ``agentic_harness.runtime`` lazily.
    import agentic_harness.runtime as rt

    monkeypatch.setattr(rt, "build_store", _boom)
    got = _latest_research_structured_v1_for_asset(
        repo_root=tmp_path, asset_id="DEMO_AAA", horizon="short"
    )
    assert got is None


def test_picks_latest_matching_asset_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _FakeStore(
        packets=[
            _mk_user_query_packet(
                packet_id="pkt_older",
                asset_id="DEMO_AAA",
                created_at_utc="2026-04-10T12:00:00Z",
                summary_ko=["older"],
                summary_en=["older"],
            ),
            _mk_user_query_packet(
                packet_id="pkt_newer",
                asset_id="DEMO_AAA",
                created_at_utc="2026-04-17T09:00:00Z",
                summary_ko=["신규"],
                summary_en=["newer"],
            ),
            _mk_user_query_packet(
                packet_id="pkt_other_asset",
                asset_id="DEMO_BBB",
                created_at_utc="2026-04-17T23:59:59Z",
                summary_ko=["other"],
                summary_en=["other"],
            ),
        ]
    )

    import agentic_harness.runtime as rt

    monkeypatch.setattr(rt, "build_store", lambda **_kw: store)

    got = _latest_research_structured_v1_for_asset(
        repo_root=tmp_path, asset_id="DEMO_AAA", horizon="short"
    )
    assert got is not None
    assert got["summary_bullets_ko"] == ["신규"]
    assert got["summary_bullets_en"] == ["newer"]
    assert got["locale_coverage"] == "dual"
    assert got["_source_packet_id"] == "pkt_newer"
    assert got["_routed_kind"] == "deeper_rationale"
    assert got["_horizon_hint"] == "short"


def test_skips_packets_with_malformed_llm_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    malformed = {
        "packet_id": "pkt_bad",
        "packet_type": "UserQueryActionPacketV1",
        "created_at_utc": "2026-04-17T12:00:00Z",
        "target_scope": {"asset_id": "DEMO_AAA"},
        "payload": {"llm_response": "this-is-a-string-not-a-dict"},
    }
    good = _mk_user_query_packet(
        packet_id="pkt_good",
        asset_id="DEMO_AAA",
        created_at_utc="2026-04-17T10:00:00Z",
        summary_ko=["ok"],
        summary_en=["ok"],
    )
    store = _FakeStore(packets=[malformed, good])

    import agentic_harness.runtime as rt

    monkeypatch.setattr(rt, "build_store", lambda **_kw: store)

    got = _latest_research_structured_v1_for_asset(
        repo_root=tmp_path, asset_id="DEMO_AAA", horizon="short"
    )
    assert got is not None
    assert got["_source_packet_id"] == "pkt_good"
