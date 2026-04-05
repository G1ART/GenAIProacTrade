"""Analyst estimates adapter seam — stub until vendor credentials exist."""

from __future__ import annotations

from sources.contracts import AdapterProbeResult, AdapterRightsMetadata


class EstimatesAdapter:
    name = "estimates_adapter_v1"
    linked_source_id = "analyst_estimates_vendor_tbd"

    def probe(self) -> AdapterProbeResult:
        return AdapterProbeResult(
            adapter_name=self.name,
            availability="not_available_yet",
            normalization_schema_version="normalized_estimate_row_v0",
            point_in_time_fields=["as_of_vendor_time", "fiscal_period"],
            revision_semantics="vendor_revision_chain_tbd",
            failure_behavior="empty_result",
            rights=AdapterRightsMetadata(
                source_id=self.linked_source_id,
                source_class="premium",
                license_scope_summary="license_required_not_held",
            ),
            sample_normalized_keys=[
                "cik",
                "fiscal_period",
                "metric_name",
                "consensus_value",
                "rights",
            ],
        )

    def fetch_normalized(self, **_kwargs: object) -> list[object]:
        return []
