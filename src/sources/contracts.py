"""Adapter contracts: normalized targets, PIT fields, availability (no live vendor calls)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Availability = Literal["not_available_yet", "partial", "available"]
SourceClass = Literal[
    "public", "premium", "proprietary", "private_internal", "partner_only"
]
FailureBehavior = Literal["empty_result", "raise_on_strict", "degrade_gracefully"]


@dataclass
class AdapterRightsMetadata:
    """Propagated alongside normalized rows; never omit on premium paths."""

    source_id: str
    source_class: str
    license_scope_summary: str
    credential_status: str = "not_available_yet"


@dataclass
class AdapterProbeResult:
    """Seam health without fabricating vendor payloads."""

    adapter_name: str
    availability: Availability
    normalization_schema_version: str
    point_in_time_fields: list[str] = field(default_factory=list)
    revision_semantics: str = "vendor_tbd_until_integrated"
    failure_behavior: FailureBehavior = "empty_result"
    rights: AdapterRightsMetadata | None = None
    sample_normalized_keys: list[str] = field(default_factory=list)


@dataclass
class NormalizedTranscriptChunk:
    """Target shape for future transcripts adapter (documentation / validation)."""

    issuer_id: str | None
    cik: str
    event_time_utc: str
    text_excerpt: str
    source_revision: str | None
    rights: AdapterRightsMetadata


@dataclass
class NormalizedEstimateRow:
    """Target shape for future estimates adapter."""

    cik: str
    fiscal_period: str
    metric_name: str
    consensus_value: float | None
    as_of_vendor_time: str
    rights: AdapterRightsMetadata


@dataclass
class NormalizedPriceBar:
    """Target shape for higher-quality price / intraday adapter."""

    symbol: str
    interval: str
    bar_start_utc: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    vendor_bar_id: str | None
    rights: AdapterRightsMetadata


def validate_probe_result(obj: AdapterProbeResult) -> None:
    if obj.availability not in ("not_available_yet", "partial", "available"):
        raise ValueError("invalid availability")
    if obj.failure_behavior not in ("empty_result", "raise_on_strict", "degrade_gracefully"):
        raise ValueError("invalid failure_behavior")
