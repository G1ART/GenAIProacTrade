"""Patch 10A — Product Shell ``/api/product/today`` DTO composer tests.

Scope:

- ``_spectrum_position_to_grade`` / ``_spectrum_position_to_stance``
  / ``_horizon_provenance_to_confidence`` contract coverage.
- ``strip_engineering_ids`` recursive regex scrub + DTO-level
  invariant (no engineering token may survive composition).
- ``compose_today_product_dto`` shape and honest-degraded mapping.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from phase47_runtime.product_shell.view_models import (  # type: ignore
    _horizon_provenance_to_confidence,
    _spectrum_position_to_grade,
    _spectrum_position_to_stance,
    compose_today_product_dto,
    strip_engineering_ids,
)


def _stub_bundle(
    *,
    provenance: dict[str, dict[str, object]],
    metadata: dict[str, object] | None = None,
):
    """Lightweight stand-in for ``BrainBundleV0`` — the composer only calls
    a narrow attribute/method surface (``.artifacts``, ``.registry_entries``,
    ``.horizon_provenance``, ``.metadata``, ``.as_of_utc``)."""
    reg_entries = []
    for hz in ("short", "medium", "medium_long", "long"):
        reg_entries.append(SimpleNamespace(
            status="active",
            horizon=hz,
            active_artifact_id=f"art_stub_{hz}",
            display_family_name_ko=f"{hz}-family-ko",
            display_family_name_en=f"{hz}-family-en",
        ))
    artifacts = [
        SimpleNamespace(
            artifact_id=f"art_stub_{hz}",
            display_family_name_ko=f"{hz}-family-ko",
            display_family_name_en=f"{hz}-family-en",
        )
        for hz in ("short", "medium", "medium_long", "long")
    ]
    return SimpleNamespace(
        artifacts=artifacts,
        registry_entries=reg_entries,
        horizon_provenance=provenance,
        metadata=metadata or {},
        as_of_utc="2026-04-23T08:00:00Z",
    )


def _stub_spectrum(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"ok": True, "rows": rows}


# ---------------------------------------------------------------------------
# Grade / stance / confidence atomic mappers
# ---------------------------------------------------------------------------


class TestGradeMapper:
    def test_extreme_long_with_live_is_a_plus(self):
        assert _spectrum_position_to_grade(0.9, source_key="live")["key"] == "a_plus"

    def test_strong_long_with_live_is_a(self):
        assert _spectrum_position_to_grade(0.6, source_key="live")["key"] == "a"

    def test_moderate_long_with_live_is_b(self):
        assert _spectrum_position_to_grade(0.3, source_key="live")["key"] == "b"

    def test_neutral_with_live_is_c(self):
        assert _spectrum_position_to_grade(0.05, source_key="live")["key"] == "c"

    def test_sample_always_d_regardless_of_magnitude(self):
        assert _spectrum_position_to_grade(0.9, source_key="sample")["key"] == "d"
        assert _spectrum_position_to_grade(0.01, source_key="sample")["key"] == "d"

    def test_preparing_always_f_regardless_of_magnitude(self):
        assert _spectrum_position_to_grade(0.9, source_key="preparing")["key"] == "f"
        assert _spectrum_position_to_grade(None, source_key="preparing")["key"] == "f"

    def test_negative_positions_mirror_positive_magnitude(self):
        assert _spectrum_position_to_grade(-0.9, source_key="live")["key"] == "a_plus"
        assert _spectrum_position_to_grade(-0.6, source_key="live")["key"] == "a"
        assert _spectrum_position_to_grade(-0.3, source_key="live")["key"] == "b"


class TestStanceMapper:
    def test_strong_long(self):
        assert _spectrum_position_to_stance(0.8, lang="ko")["key"] == "strong_long"

    def test_long(self):
        assert _spectrum_position_to_stance(0.3, lang="ko")["key"] == "long"

    def test_neutral(self):
        assert _spectrum_position_to_stance(0.0, lang="ko")["key"] == "neutral"
        assert _spectrum_position_to_stance(0.15, lang="ko")["key"] == "neutral"
        assert _spectrum_position_to_stance(-0.15, lang="ko")["key"] == "neutral"

    def test_short(self):
        assert _spectrum_position_to_stance(-0.3, lang="ko")["key"] == "short"

    def test_strong_short(self):
        assert _spectrum_position_to_stance(-0.8, lang="ko")["key"] == "strong_short"

    def test_ko_en_labels_present(self):
        ko = _spectrum_position_to_stance(0.3, lang="ko")
        en = _spectrum_position_to_stance(0.3, lang="en")
        assert ko["label"] and ko["label"] != en["label"]
        assert "long" in en["label"].lower() or "bias" in en["label"].lower()


class TestConfidenceMapper:
    def test_real_derived_maps_to_live(self):
        c = _horizon_provenance_to_confidence({"source": "real_derived"}, lang="ko")
        assert c["source_key"] == "live"
        assert "실데이터" in c["label"]

    def test_degraded_challenger_maps_to_live_with_caveat(self):
        c = _horizon_provenance_to_confidence(
            {"source": "real_derived_with_degraded_challenger"}, lang="ko"
        )
        assert c["source_key"] == "live_with_caveat"

    def test_template_fallback_maps_to_sample(self):
        c = _horizon_provenance_to_confidence({"source": "template_fallback"}, lang="ko")
        assert c["source_key"] == "sample"
        assert "샘플" in c["label"]

    def test_insufficient_evidence_maps_to_preparing(self):
        c = _horizon_provenance_to_confidence(
            {"source": "insufficient_evidence"}, lang="ko"
        )
        assert c["source_key"] == "preparing"
        assert "준비 중" in c["label"]

    def test_none_falls_back_to_preparing(self):
        c = _horizon_provenance_to_confidence(None, lang="ko")
        assert c["source_key"] == "preparing"

    def test_raw_engineering_enum_never_in_label(self):
        for src in ("real_derived", "template_fallback", "insufficient_evidence",
                    "real_derived_with_degraded_challenger"):
            c = _horizon_provenance_to_confidence({"source": src}, lang="ko")
            assert src not in c["label"]
            assert src not in c["tooltip"]


# ---------------------------------------------------------------------------
# strip_engineering_ids
# ---------------------------------------------------------------------------


class TestEngineeringScrubber:
    def test_strips_artifact_id(self):
        assert strip_engineering_ids("hello art_abc123 world") == "hello [redacted] world"

    def test_strips_registry_entry_id(self):
        assert "reg_" not in strip_engineering_ids("reg_xyz here")

    def test_strips_factor_slug(self):
        assert "factor_" not in strip_engineering_ids("factor_momentum_1")

    def test_strips_packet_id(self):
        assert "pkt_" not in strip_engineering_ids("proposal pkt_abc123 ok")

    def test_strips_demo_pit_pointer(self):
        assert "pit:demo:" not in strip_engineering_ids("pit:demo:v1:short")

    def test_strips_raw_provenance_enums(self):
        for src in ("real_derived", "real_derived_with_degraded_challenger",
                    "template_fallback", "insufficient_evidence", "horizon_provenance"):
            assert src not in strip_engineering_ids(f"leaking {src} here")

    def test_strips_versioned_slugs(self):
        assert "message_v1" not in strip_engineering_ids("schema message_v1 contract")
        assert "factor_validation_gate_export_v0" not in strip_engineering_ids(
            "factor_validation_gate_export_v0"
        )

    def test_recursive_dict_and_list(self):
        inp = {
            "a": "art_one",
            "b": ["reg_two", {"c": "factor_three"}],
            "d": ("insufficient_evidence", "ok"),
        }
        out = strip_engineering_ids(inp)
        assert out["a"] == "[redacted]"
        assert out["b"][0] == "[redacted]"
        assert out["b"][1]["c"] == "[redacted]"
        assert out["d"][0] == "[redacted]"
        assert out["d"][1] == "ok"

    def test_non_string_values_preserved(self):
        inp = {"x": 1, "y": 2.5, "z": None, "w": True, "list": [1, 2]}
        assert strip_engineering_ids(inp) == inp


# ---------------------------------------------------------------------------
# Full compose_today_product_dto
# ---------------------------------------------------------------------------


class TestComposeToday:
    def _all_live_bundle(self):
        return _stub_bundle(
            provenance={hz: {"source": "real_derived"} for hz in
                        ("short", "medium", "medium_long", "long")},
            metadata={"graduation_tier": "production",
                      "built_at_utc": "2026-04-23T07:30:00Z",
                      "source_run_ids": ["run_a"]},
        )

    def _mixed_bundle(self):
        return _stub_bundle(
            provenance={
                "short":       {"source": "real_derived"},
                "medium":      {"source": "real_derived_with_degraded_challenger"},
                "medium_long": {"source": "template_fallback"},
                "long":        {"source": "insufficient_evidence"},
            },
            metadata={"graduation_tier": "production",
                      "built_at_utc": "2026-04-23T07:30:00Z"},
        )

    def _rows(self, top_position: float = 0.7):
        return [
            {"asset_id": "AAPL", "spectrum_position": top_position,
             "rank_index": 1, "rank_movement": "up",
             "rationale_summary": "강한 모멘텀이 지지됨",
             "what_changed": "지난 주 대비 상승"},
            {"asset_id": "MSFT", "spectrum_position": -0.3,
             "rank_index": 2, "rank_movement": "down",
             "rationale_summary": "방어적 흐름",
             "what_changed": "상대적 하락"},
        ]

    def test_dto_contract_and_shape(self):
        bundle = self._all_live_bundle()
        dto = compose_today_product_dto(
            bundle=bundle,
            spectrum_by_horizon={hz: _stub_spectrum(self._rows()) for hz in
                                 ("short", "medium", "medium_long", "long")},
            lang="ko",
            watchlist_tickers=["AAPL", "NVDA"],
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["contract"] == "PRODUCT_TODAY_V1"
        assert dto["lang"] == "ko"
        assert len(dto["hero_cards"]) == 4
        assert dto["trust_strip"]["tier_kind"] == "production"
        assert dto["watchlist_strip"]["tickers"][0]["ticker"] == "AAPL"
        assert dto["watchlist_strip"]["tickers"][1]["has_data"] is False
        assert all(k in dto for k in ("today_at_a_glance", "selected_movers",
                                      "stubs", "advanced_disclosure"))

    def test_hero_card_grade_and_stance_are_separate(self):
        bundle = self._all_live_bundle()
        dto = compose_today_product_dto(
            bundle=bundle,
            spectrum_by_horizon={hz: _stub_spectrum(self._rows(top_position=0.85))
                                 for hz in ("short", "medium", "medium_long", "long")},
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        hc0 = dto["hero_cards"][0]
        assert hc0["grade"]["key"] == "a_plus"
        assert hc0["stance"]["key"] == "strong_long"
        assert hc0["grade"]["key"] != hc0["stance"]["key"]

    def test_mixed_bundle_yields_degraded_trust_strip(self):
        bundle = self._mixed_bundle()
        dto = compose_today_product_dto(
            bundle=bundle,
            spectrum_by_horizon={hz: _stub_spectrum(self._rows()) for hz in
                                 ("short", "medium", "medium_long", "long")},
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["trust_strip"]["tier_kind"] == "degraded"
        # Preparing horizon maps to F grade regardless of incoming rows.
        long_card = [h for h in dto["hero_cards"] if h["horizon_key"] == "long"][0]
        assert long_card["grade"]["key"] == "f"
        assert long_card["confidence"]["source_key"] == "preparing"
        # Sample horizon maps to D.
        ml_card = [h for h in dto["hero_cards"] if h["horizon_key"] == "medium_long"][0]
        assert ml_card["grade"]["key"] == "d"
        assert ml_card["confidence"]["source_key"] == "sample"

    def test_no_bundle_yields_sample_trust_strip_and_all_preparing(self):
        dto = compose_today_product_dto(
            bundle=None,
            spectrum_by_horizon={hz: _stub_spectrum([]) for hz in
                                 ("short", "medium", "medium_long", "long")},
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto["trust_strip"]["tier_kind"] == "sample"
        for hc in dto["hero_cards"]:
            assert hc["confidence"]["source_key"] == "preparing"
            assert hc["grade"]["key"] == "f"

    def test_dto_contains_no_engineering_tokens(self):
        """The output of compose must be free of all scanner-banned tokens."""
        import json
        import re
        bundle = self._mixed_bundle()
        dto = compose_today_product_dto(
            bundle=bundle,
            spectrum_by_horizon={hz: _stub_spectrum(self._rows()) for hz in
                                 ("short", "medium", "medium_long", "long")},
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        blob = json.dumps(dto, ensure_ascii=False)
        banned = [
            r"\bart_[A-Za-z0-9_]+\b",
            r"\breg_[A-Za-z0-9_]+\b",
            r"\bfactor_[A-Za-z0-9_]+\b",
            r"\bpkt_[A-Za-z0-9_]+\b",
            r"\bpit:demo:",
            r"\bhorizon_provenance\b",
            r"\breal_derived\b",
            r"\binsufficient_evidence\b",
            r"\btemplate_fallback\b",
        ]
        for pat in banned:
            m = re.search(pat, blob)
            assert m is None, f"DTO leaked engineering token: {pat!r} → {m!r}"

    def test_selected_movers_capped_and_sorted(self):
        bundle = self._all_live_bundle()
        rows = [
            {"asset_id": f"T{i}", "spectrum_position": 0.7 - i * 0.05,
             "rank_index": i + 1, "rank_movement": "up",
             "rationale_summary": "", "what_changed": ""}
            for i in range(10)
        ]
        dto = compose_today_product_dto(
            bundle=bundle,
            spectrum_by_horizon={hz: _stub_spectrum(rows) for hz in
                                 ("short", "medium", "medium_long", "long")},
            lang="ko",
            now_utc="2026-04-23T08:00:00Z",
        )
        movers = dto["selected_movers"]
        assert 1 <= len(movers) <= 3
        tickers = [m["ticker"] for m in movers]
        assert len(tickers) == len(set(tickers))  # unique

    def test_lang_en_round_trip(self):
        bundle = self._all_live_bundle()
        dto_en = compose_today_product_dto(
            bundle=bundle,
            spectrum_by_horizon={hz: _stub_spectrum(self._rows()) for hz in
                                 ("short", "medium", "medium_long", "long")},
            lang="en",
            now_utc="2026-04-23T08:00:00Z",
        )
        assert dto_en["lang"] == "en"
        hc0 = dto_en["hero_cards"][0]
        assert hc0["cta_primary"]["label"] == "Open evidence"
        assert dto_en["trust_strip"]["tier_kind"] == "production"


# ---------------------------------------------------------------------------
# Integration — dispatch through the routes layer
# ---------------------------------------------------------------------------


class TestProductTodayRoute:
    def test_route_returns_product_today_packet(self, tmp_path):
        import json as _json
        from phase47_runtime.routes import dispatch_json
        from phase47_runtime.runtime_state import CockpitRuntimeState

        bpath = tmp_path / "phase46_bundle.json"
        bpath.write_text(
            _json.dumps({
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
        code, obj = dispatch_json(st, method="GET", path="/api/product/today", body=None)
        assert code == 200
        assert obj.get("ok") is True
        assert obj.get("contract") == "PRODUCT_TODAY_V1"
        assert len(obj.get("hero_cards", [])) == 4
        # Hard rule: no engineering IDs survive in the packet body.
        blob = _json.dumps(obj, ensure_ascii=False)
        assert "horizon_provenance" not in blob
        assert "real_derived" not in blob
        assert "template_fallback" not in blob
