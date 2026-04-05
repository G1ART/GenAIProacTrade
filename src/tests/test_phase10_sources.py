"""Phase 10: source registry contracts, provenance snapshot, adapter seams."""

from __future__ import annotations

import pytest

from main import build_parser
from sources.contracts import AdapterProbeResult, validate_probe_result
from sources.estimates_adapter import EstimatesAdapter
from sources.price_quality_adapter import PriceQualityAdapter
from sources.provenance import build_overlay_awareness_snapshot, tag_field_provenance
from sources.registry import REGISTRY_SEED_ROWS
from sources.reporting import OVERLAY_ROI_RANKED, build_overlay_gap_report
from sources.transcripts_adapter import TranscriptsAdapter


def test_overlay_roi_ranked_covers_required_overlays() -> None:
    keys = {x["overlay_key"] for x in OVERLAY_ROI_RANKED}
    assert "earnings_call_transcripts" in keys
    assert "analyst_estimates" in keys
    assert "higher_quality_price_or_intraday" in keys


def test_registry_seed_mixed_classes() -> None:
    classes = {r["source_class"] for r in REGISTRY_SEED_ROWS}
    assert "public" in classes
    assert "premium" in classes
    assert "private_internal" in classes
    assert "partner_only" in classes
    assert len(REGISTRY_SEED_ROWS) >= 5


def test_provenance_snapshot_none_client() -> None:
    snap = build_overlay_awareness_snapshot(None)
    assert snap["overlay_available"] is False
    assert "earnings_call_transcripts" in snap["overlay_not_available_yet"]


def test_tag_field_provenance() -> None:
    t = tag_field_provenance(origin="public_truth_spine", source_id="sec_edgar_xbrl_public")
    assert t["origin_lane"] == "public_truth_spine"


def test_transcripts_adapter_probe() -> None:
    p = TranscriptsAdapter().probe()
    validate_probe_result(p)
    assert p.availability == "not_available_yet"
    assert TranscriptsAdapter().fetch_normalized() == []


def test_estimates_and_price_adapters() -> None:
    e = EstimatesAdapter().probe()
    validate_probe_result(e)
    q = PriceQualityAdapter().probe()
    validate_probe_result(q)
    assert e.availability == "not_available_yet"


def test_validate_probe_bad() -> None:
    p = AdapterProbeResult(
        adapter_name="x",
        availability="not_available_yet",
        normalization_schema_version="v0",
    )
    p.availability = "bogus"  # type: ignore[assignment]
    with pytest.raises(ValueError):
        validate_probe_result(p)


def test_build_overlay_gap_report_empty_db(monkeypatch) -> None:
    class Fake:
        pass

    def fake_fetch_all(_c):
        return []

    import sources.reporting as rep

    monkeypatch.setattr(rep.dbrec, "fetch_source_overlay_availability_all", fake_fetch_all)
    gap = build_overlay_gap_report(Fake())
    assert gap["report_type"] == "overlay_gap_v1"
    assert len(gap["roi_ranked_overlays"]) == len(OVERLAY_ROI_RANKED)


def test_phase10_cli_registered() -> None:
    p = build_parser()
    sub = next(a for a in p._actions if getattr(a, "dest", None) == "command")
    names = set(sub.choices.keys())
    for c in (
        "seed-source-registry",
        "report-source-registry",
        "report-overlay-gap",
        "smoke-source-adapters",
        "export-source-roi-matrix",
    ):
        assert c in names
