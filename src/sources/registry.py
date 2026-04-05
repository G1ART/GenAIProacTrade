"""Idempotent seed rows for data_source_registry (CLI + migration alignment)."""

from __future__ import annotations

from typing import Any

from db import records as dbrec

# Mirrors migration seed; safe to upsert from CLI after partial deploy.
REGISTRY_SEED_ROWS: list[dict[str, Any]] = [
    {
        "source_id": "sec_edgar_xbrl_public",
        "provider_name": "SEC",
        "source_name": "EDGAR filings + XBRL (public)",
        "source_class": "public",
        "asset_domain": "equities",
        "data_family": "filings",
        "point_in_time_safety": "accession_filed_at_and_accepted_at_rules",
        "license_or_rights_scope": "US_public_filings_redistribution_subject_to_SEC_terms",
        "cost_tier": "free_public",
        "activation_status": "active",
        "notes_json": {"role": "deterministic_truth_spine_core"},
        "provenance_policy_json": {"downstream_label": "public_truth_spine"},
    },
    {
        "source_id": "fred_dtb3_public",
        "provider_name": "FRED",
        "source_name": "Risk-free daily (DTB3 graph CSV)",
        "source_class": "public",
        "asset_domain": "equities",
        "data_family": "alt",
        "point_in_time_safety": "rate_date_calendar",
        "license_or_rights_scope": "FRED_terms_apply",
        "cost_tier": "free_public",
        "activation_status": "active",
        "notes_json": {"role": "regime_input_public"},
        "provenance_policy_json": {"downstream_label": "public_truth_spine"},
    },
    {
        "source_id": "market_prices_yahoo_silver_eod",
        "provider_name": "Yahoo_chart",
        "source_name": "Silver EOD prices (ingested)",
        "source_class": "public",
        "asset_domain": "equities",
        "data_family": "prices",
        "point_in_time_safety": "trade_date_eod_only",
        "license_or_rights_scope": "provider_terms_apply_non_professional_chart",
        "cost_tier": "free_public",
        "activation_status": "active",
        "notes_json": {
            "role": "market_join_public",
            "quality_note": "chart_provider_not_bloomberg_class",
        },
        "provenance_policy_json": {
            "downstream_label": "public_truth_spine",
            "quality_tier": "standard_eod",
        },
    },
    {
        "source_id": "earnings_call_transcripts_vendor_tbd",
        "provider_name": "TBD_VENDOR",
        "source_name": "Earnings call transcripts (premium target)",
        "source_class": "premium",
        "asset_domain": "equities",
        "data_family": "transcripts",
        "point_in_time_safety": "vendor_event_timestamp_and_revision_policy_tbd",
        "license_or_rights_scope": "license_required_not_held",
        "cost_tier": "paid_tier_unknown",
        "activation_status": "planned",
        "notes_json": {"why_it_matters": "narrative_drift_vs_filings"},
        "provenance_policy_json": {
            "downstream_label": "premium_overlay",
            "credentials": "not_available_yet",
        },
    },
    {
        "source_id": "analyst_estimates_vendor_tbd",
        "provider_name": "TBD_VENDOR",
        "source_name": "Analyst consensus estimates (premium target)",
        "source_class": "premium",
        "asset_domain": "equities",
        "data_family": "estimates",
        "point_in_time_safety": "fiscal_period_alignment_and_revision_semantics_tbd",
        "license_or_rights_scope": "license_required_not_held",
        "cost_tier": "paid_tier_unknown",
        "activation_status": "planned",
        "notes_json": {"why_it_matters": "expectations_gap_vs_realized_fundamentals"},
        "provenance_policy_json": {
            "downstream_label": "premium_overlay",
            "credentials": "not_available_yet",
        },
    },
    {
        "source_id": "higher_quality_price_intraday_vendor_tbd",
        "provider_name": "TBD_VENDOR",
        "source_name": "Higher-quality price or intraday feed (premium target)",
        "source_class": "proprietary",
        "asset_domain": "equities",
        "data_family": "prices",
        "point_in_time_safety": "vendor_pit_rules_tbd",
        "license_or_rights_scope": "license_required_not_held",
        "cost_tier": "paid_tier_unknown",
        "activation_status": "planned",
        "notes_json": {"why_it_matters": "microstructure_and_open_close_quality"},
        "provenance_policy_json": {
            "downstream_label": "premium_overlay",
            "credentials": "not_available_yet",
        },
    },
    {
        "source_id": "operator_internal_research_notes",
        "provider_name": "INTERNAL",
        "source_name": "Operator private research notes (not a market feed)",
        "source_class": "private_internal",
        "asset_domain": "equities",
        "data_family": "internal",
        "point_in_time_safety": "operator_authored_timestamps",
        "license_or_rights_scope": "internal_use_only",
        "cost_tier": "internal",
        "activation_status": "inactive",
        "notes_json": {
            "placeholder": True,
            "must_not_mix_with_public_spine_rows": True,
        },
        "provenance_policy_json": {"downstream_label": "private_internal"},
    },
    {
        "source_id": "partner_syndicated_feed_placeholder",
        "provider_name": "PARTNER_TBD",
        "source_name": "Partner-only syndicated feed (placeholder)",
        "source_class": "partner_only",
        "asset_domain": "multi",
        "data_family": "news",
        "point_in_time_safety": "partner_contract_tbd",
        "license_or_rights_scope": "partner_agreement_required",
        "cost_tier": "unknown",
        "activation_status": "inactive",
        "notes_json": {"placeholder": True},
        "provenance_policy_json": {"downstream_label": "partner_only"},
    },
]


def seed_registry_from_constants(client: Any) -> dict[str, Any]:
    """Upsert core registry rows; does not replace SQL migration seed."""
    n = 0
    for row in REGISTRY_SEED_ROWS:
        dbrec.upsert_data_source_registry_row(client, row)
        n += 1
    return {"upserted_source_ids": [r["source_id"] for r in REGISTRY_SEED_ROWS], "count": n}
