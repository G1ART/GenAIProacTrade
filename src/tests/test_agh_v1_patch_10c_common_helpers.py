"""Unit tests for Patch 10C shared-coherence helpers.

These tests pin the invariants that the four Product Shell composers
(Today / Research / Replay / Ask AI) will rely on in
:mod:`phase47_runtime.product_shell.view_models_common`:

- :func:`compute_coherence_signature` is deterministic and
  language-independent.
- :func:`build_shared_focus_block` returns identical
  grade/stance/confidence/evidence_summary for the same focus — even
  when one surface hands the ``(asset_id, horizon_key)`` tuple and
  another hands the same tuple in a different language.
- :data:`SHARED_WORDING` has KO/EN parity for every listed bucket.
- :func:`strip_engineering_ids` never eats the coherence fingerprint
  (12-hex lowercase) nor the ``COHERENCE_V1`` contract label.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from phase47_runtime.product_shell.view_models_common import (
    SHARED_WORDING,
    SHARED_WORDING_KINDS,
    SOURCE_KEY_TO_WORDING_KIND,
    build_shared_focus_block,
    compute_coherence_signature,
    evidence_lineage_summary,
    shared_wording,
    strip_engineering_ids,
)


def _synthetic_bundle(source: str = "real_derived") -> SimpleNamespace:
    return SimpleNamespace(
        as_of_utc="2026-04-23T00:00:00Z",
        horizon_provenance={
            "short":       {"source": source},
            "medium":      {"source": source},
            "medium_long": {"source": source},
            "long":        {"source": source},
        },
        registry_entries=[
            SimpleNamespace(
                status="active",
                horizon="short",
                active_artifact_id="art_x",
                registry_entry_id="reg_x",
                display_family_name_ko="모멘텀",
                display_family_name_en="Momentum",
            ),
        ],
        artifacts=[
            SimpleNamespace(
                artifact_id="art_x",
                display_family_name_ko="모멘텀",
                display_family_name_en="Momentum",
            ),
        ],
        metadata={"built_at_utc": "2026-04-23T00:00:00Z",
                  "graduation_tier": "production"},
    )


def _spectrum_with_aapl(position: float = 0.42) -> dict[str, dict]:
    return {
        "short": {
            "ok": True,
            "rows": [
                {
                    "asset_id": "AAPL",
                    "spectrum_position": position,
                    "rank_index": 0,
                    "rank_movement": "up",
                    "what_changed": "Momentum picked up after earnings beat.",
                    "rationale_summary": "Short-term flow and breadth both leaning long.",
                },
                {
                    "asset_id": "MSFT",
                    "spectrum_position": position - 0.1,
                    "rank_index": 1,
                    "rank_movement": "flat",
                    "what_changed": "",
                    "rationale_summary": "Steady setup; no material change.",
                },
            ],
        },
        "medium":      {"ok": True, "rows": []},
        "medium_long": {"ok": True, "rows": []},
        "long":        {"ok": True, "rows": []},
    }


def test_compute_coherence_signature_is_deterministic():
    kw = dict(
        asset_id="AAPL",
        horizon_key="short",
        position=0.42,
        grade_key="a",
        stance_key="long",
        source_key="live",
        what_changed="Momentum picked up after earnings beat.",
        rationale_summary="Short-term flow and breadth both leaning long.",
    )
    a = compute_coherence_signature(**kw)
    b = compute_coherence_signature(**kw)
    assert a == b
    assert len(a["fingerprint"]) == 12
    assert a["contract_version"] == "COHERENCE_V1"
    # Small float jitter below the 2-decimal quantization step must
    # not alter the signature.
    jitter = dict(kw)
    jitter["position"] = 0.4201  # -> quantizes to 0.42
    assert compute_coherence_signature(**jitter)["fingerprint"] == a["fingerprint"]


def test_compute_coherence_signature_changes_when_evidence_changes():
    base = compute_coherence_signature(
        asset_id="AAPL", horizon_key="short", position=0.42,
        grade_key="a", stance_key="long", source_key="live",
        what_changed="A", rationale_summary="B",
    )
    flipped = compute_coherence_signature(
        asset_id="AAPL", horizon_key="short", position=0.42,
        grade_key="a", stance_key="long", source_key="live",
        what_changed="A*",  # silent rationale edit detected
        rationale_summary="B",
    )
    assert base["fingerprint"] != flipped["fingerprint"]


def test_build_shared_focus_block_language_independent_signature():
    bundle = _synthetic_bundle()
    spectrum = _spectrum_with_aapl(0.42)
    ko = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    en = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang="en",
    )
    # Signature is language-agnostic.
    assert ko["coherence_signature"] == en["coherence_signature"]
    # Grade + confidence source_key also match across languages.
    assert ko["grade"]["key"] == en["grade"]["key"]
    assert ko["stance"]["key"] == en["stance"]["key"]
    assert ko["confidence"]["source_key"] == en["confidence"]["source_key"]
    # Row matched, evidence summary filled from spectrum row text.
    assert ko["row_matched"] is True
    assert ko["evidence_summary"]["what_changed"].startswith("Momentum")


def test_build_shared_focus_block_falls_back_to_representative_row():
    bundle = _synthetic_bundle()
    spectrum = _spectrum_with_aapl(0.42)
    # Request an asset not on the horizon; falls back to best rep.
    block = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="TSLA", horizon_key="short", lang="ko",
    )
    assert block["row_matched"] is False
    # Fingerprint pinned to the representative's position, not zero.
    assert block["position"] != 0.0


def test_build_shared_focus_block_preparing_source_uses_shared_wording():
    bundle = _synthetic_bundle(source="insufficient_evidence")
    spectrum = {"short": {"ok": True, "rows": []},
                "medium": {"ok": True, "rows": []},
                "medium_long": {"ok": True, "rows": []},
                "long": {"ok": True, "rows": []}}
    block = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang="ko",
    )
    body = block["evidence_summary"]["body"]
    assert body == shared_wording("preparing", lang="ko")["body"]
    summary = evidence_lineage_summary(block)
    assert summary["source_key"] == "preparing"


def test_shared_wording_parity():
    for kind in SHARED_WORDING_KINDS:
        ko = SHARED_WORDING["ko"][kind]
        en = SHARED_WORDING["en"][kind]
        assert set(ko.keys()) == set(en.keys()) == {"title", "body", "chip"}
        assert ko["title"] and en["title"]
        assert ko["chip"] and en["chip"]


def test_source_key_to_wording_kind_is_total():
    for src_key in ("live", "live_with_caveat", "sample", "preparing"):
        assert src_key in SOURCE_KEY_TO_WORDING_KIND
        kind = SOURCE_KEY_TO_WORDING_KIND[src_key]
        assert kind in SHARED_WORDING_KINDS


def test_coherence_fingerprint_survives_strip_scrubber():
    bundle = _synthetic_bundle()
    spectrum = _spectrum_with_aapl(0.42)
    block = build_shared_focus_block(
        bundle=bundle, spectrum_by_horizon=spectrum,
        asset_id="AAPL", horizon_key="short", lang="en",
    )
    scrubbed = strip_engineering_ids(block)
    fp = scrubbed["coherence_signature"]["fingerprint"]
    assert len(fp) == 12
    assert fp.isalnum()
    assert "[redacted]" not in fp
    assert scrubbed["coherence_signature"]["contract_version"] == "COHERENCE_V1"


def test_shared_wording_unknown_kind_falls_back_safely():
    block = shared_wording("nonexistent_bucket", lang="ko")
    # Falls back to limited_evidence so UI never renders an empty string.
    assert block["title"] == SHARED_WORDING["ko"]["limited_evidence"]["title"]
