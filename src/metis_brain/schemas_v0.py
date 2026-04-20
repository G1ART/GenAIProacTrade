"""Pydantic models for Metis Brain v0 (Product Spec §6.1–6.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelArtifactPacketV0(BaseModel):
    artifact_id: str
    created_at: str
    created_by: str
    horizon: str
    universe: str
    sector_scope: str
    thesis_family: str
    feature_set: str
    feature_transforms: str
    weighting_rule: str
    score_formula: str
    banding_rule: str
    ranking_direction: str
    invalidation_conditions: str
    expected_holding_horizon: str
    confidence_rule: str
    evidence_requirements: str
    validation_pointer: str
    replay_eligibility: str
    notes_for_message_layer: str
    # Optional founder-facing alias layer. Internal ``artifact_id`` stays stable
    # for schema/join semantics; ``display_*`` fields carry the canonical
    # non-demo name surfaced to Today/Research/Replay.
    display_id: str = ""
    display_family_name_ko: str = ""
    display_family_name_en: str = ""


class PromotionGateRecordV0(BaseModel):
    artifact_id: str
    evaluation_run_id: str
    pit_pass: bool
    coverage_pass: bool
    monotonicity_pass: bool
    regime_notes: str
    sector_override_notes: str
    challenger_or_active: str
    approved_by_rule: str
    approved_at: str
    supersedes_registry_entry: str = ""
    reasons: str
    expiry_or_recheck_rule: str


class ActiveHorizonRegistryEntryV0(BaseModel):
    registry_entry_id: str
    horizon: str
    active_model_family_name: str
    active_artifact_id: str
    challenger_artifact_ids: list[str] = Field(default_factory=list)
    universe: str
    sector_scope: str
    effective_from: str
    effective_to: str
    scoring_endpoint_contract: str
    message_contract_version: str
    replay_lineage_pointer: str
    status: str
    # Optional founder-facing alias layer — see ``ModelArtifactPacketV0``.
    display_id: str = ""
    display_family_name_ko: str = ""
    display_family_name_en: str = ""
    # AGH v1 Patch 5 — research factor bindings. Optional list of
    # ``{"factor_name": str, "return_basis": str}`` entries that tell the
    # ``governance_scan`` cadence which completed ``factor_validation`` runs
    # it may consider as upstream evidence for this registry entry. Empty
    # list (default) means "not yet bound" and the scan honestly skips this
    # entry instead of inventing a factor/basis mapping.
    research_factor_bindings_v1: list[dict[str, str]] = Field(default_factory=list)
