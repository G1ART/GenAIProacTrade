"""Transcripts adapter seam — Phase 11 FMP binding when credentials present (no live HTTP in probe)."""

from __future__ import annotations

import os

from sources.contracts import AdapterProbeResult, AdapterRightsMetadata


class TranscriptsAdapter:
    """FMP PoC path documented; live verification uses probe-transcripts-provider CLI."""

    name = "transcripts_adapter_v1"
    linked_source_id = "fmp_earning_call_transcripts_poc"

    def probe(self) -> AdapterProbeResult:
        key = os.getenv("FMP_API_KEY", "").strip()
        if not key:
            return AdapterProbeResult(
                adapter_name=self.name,
                availability="not_available_yet",
                normalization_schema_version="normalized_transcripts_phase11_fmp_v1",
                point_in_time_fields=[
                    "event_date",
                    "published_at",
                    "available_at",
                    "ingested_at",
                    "revision_id",
                ],
                revision_semantics="content_hash_short_sha256_prefix_on_vendor_segments",
                failure_behavior="empty_result",
                rights=AdapterRightsMetadata(
                    source_id=self.linked_source_id,
                    source_class="premium",
                    license_scope_summary="FMP_subscription_terms_apply",
                    credential_status="not_available_yet",
                ),
                sample_normalized_keys=[
                    "ticker",
                    "fiscal_period",
                    "transcript_text",
                    "source_rights_class",
                    "provenance_json",
                    "normalization_status",
                ],
            )
        return AdapterProbeResult(
            adapter_name=self.name,
            availability="partial",
            normalization_schema_version="normalized_transcripts_phase11_fmp_v1",
            point_in_time_fields=[
                "event_date",
                "published_at",
                "available_at",
                "ingested_at",
                "revision_id",
            ],
            revision_semantics="content_hash_short_sha256_prefix_on_vendor_segments",
            failure_behavior="empty_result",
            rights=AdapterRightsMetadata(
                source_id=self.linked_source_id,
                source_class="premium",
                license_scope_summary="FMP_subscription_terms_apply",
                credential_status="configured_env_present_unverified_until_cli_probe",
            ),
            sample_normalized_keys=[
                "ticker",
                "fiscal_period",
                "transcript_text",
                "source_rights_class",
                "provenance_json",
                "normalization_status",
            ],
        )

    def fetch_normalized(self, **_kwargs: object) -> list[object]:
        """DB-backed fetch is CLI/ingest path; adapter stays thin."""
        return []
