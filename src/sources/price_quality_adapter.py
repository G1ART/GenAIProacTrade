"""Higher-quality price / intraday adapter seam — stub until vendor exists."""

from __future__ import annotations

from sources.contracts import AdapterProbeResult, AdapterRightsMetadata


class PriceQualityAdapter:
    name = "price_quality_adapter_v1"
    linked_source_id = "higher_quality_price_intraday_vendor_tbd"

    def probe(self) -> AdapterProbeResult:
        return AdapterProbeResult(
            adapter_name=self.name,
            availability="not_available_yet",
            normalization_schema_version="normalized_price_bar_v0",
            point_in_time_fields=["bar_start_utc", "vendor_bar_id"],
            revision_semantics="vendor_may_correct_intraday_bar",
            failure_behavior="degrade_gracefully",
            rights=AdapterRightsMetadata(
                source_id=self.linked_source_id,
                source_class="proprietary",
                license_scope_summary="license_required_not_held",
            ),
            sample_normalized_keys=[
                "symbol",
                "interval",
                "bar_start_utc",
                "ohlc",
                "rights",
            ],
        )

    def fetch_normalized(self, **_kwargs: object) -> list[object]:
        return []
