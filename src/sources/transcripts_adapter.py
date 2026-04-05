"""Transcripts adapter seam — stub until vendor credentials exist."""

from __future__ import annotations

from sources.contracts import AdapterProbeResult, AdapterRightsMetadata


class TranscriptsAdapter:
    """Provider interface placeholder; returns explicit not_available_yet."""

    name = "transcripts_adapter_v1"
    linked_source_id = "earnings_call_transcripts_vendor_tbd"

    def probe(self) -> AdapterProbeResult:
        return AdapterProbeResult(
            adapter_name=self.name,
            availability="not_available_yet",
            normalization_schema_version="normalized_transcript_chunk_v0",
            point_in_time_fields=["event_time_utc", "source_revision"],
            revision_semantics="vendor_supersedes_prior_revision",
            failure_behavior="empty_result",
            rights=AdapterRightsMetadata(
                source_id=self.linked_source_id,
                source_class="premium",
                license_scope_summary="license_required_not_held",
            ),
            sample_normalized_keys=[
                "cik",
                "event_time_utc",
                "text_excerpt",
                "rights",
            ],
        )

    def fetch_normalized(self, **_kwargs: object) -> list[object]:
        """No credentials → empty list (honest)."""
        return []
