"""Agentic harness v1 packet contracts.

All inter-agent and agent->rail communication rides on these typed packets.
Free-form LLM chatter is confined to scratchpads inside Layer 5's bounded
orchestrator. A packet that does not validate is never written to the store.

Hard rules (work-order METIS_Agentic_Operating_Harness_v1 sec 3.3, 10):
    * ``provenance_refs`` must have at least one ref. Agents cannot emit
      orphan packets.
    * ``status`` vocabulary is fixed.
    * ``forbidden_copy_tokens`` are rejected at the base-class level so no
      packet payload can smuggle buy/sell/recommendation language onto a
      downstream surface.
    * ``target_layer`` vocabulary is fixed to the five layers in section 4
      of the work-order.

Controlled vocabulary in sub-classes reuses the existing
``brain_overlays_v1.OVERLAY_TYPES`` and ``persona_candidates_v1.SIGNAL_TYPES``
so that the harness and the brain share one truth for overlay / signal kinds.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from metis_brain.brain_overlays_v1 import EXPECTED_DIRECTION_HINTS, OVERLAY_TYPES
from metis_brain.persona_candidates_v1 import (
    PersonaCandidatePacketV1,
    SIGNAL_TYPES,
)


PACKET_SCHEMA_VERSION = 1

TARGET_LAYERS = (
    "layer1_ingest",
    "layer2_library",
    "layer3_research",
    "layer4_governance",
    "layer5_surface",
)

TargetLayer = Literal[
    "layer1_ingest",
    "layer2_library",
    "layer3_research",
    "layer4_governance",
    "layer5_surface",
]

PACKET_STATUS_VALUES = (
    "proposed",
    "enqueued",
    "running",
    "done",
    "blocked",
    "escalated",
    "expired",
    # AGH v1 Patch 2 (Promotion Bridge Closure) - RegistryUpdateProposalV1
    # transitions into one of these terminal states after an operator decision
    # is recorded and the registry_patch_executor has or has not applied it.
    "applied",
    "rejected",
    "deferred",
)

PacketStatus = Literal[
    "proposed",
    "enqueued",
    "running",
    "done",
    "blocked",
    "escalated",
    "expired",
    "applied",
    "rejected",
    "deferred",
]

PACKET_TYPES = (
    "IngestAlertPacketV1",
    "SourceArtifactPacketV1",
    "EventTriggerPacketV1",
    "LibraryIntegrityPacketV1",
    "CoverageGapPacketV1",
    "ResearchCandidatePacketV1",
    "OverlayProposalPacketV1",
    "EvaluationPacketV1",
    "PromotionGatePacketV1",
    "RegistryUpdateProposalV1",
    "ReplayLearningPacketV1",
    "UserQueryActionPacketV1",
    # AGH v1 Patch 2: operator-gated promotion bridge closure.
    "RegistryDecisionPacketV1",
    "RegistryPatchAppliedPacketV1",
    # AGH v1 Patch 3: artifact promotion bridge closure (per-horizon spectrum
    # refresh audit recorded alongside the registry_entry active/challenger
    # swap performed by registry_patch_executor).
    "SpectrumRefreshRecordV1",
)


# Forbidden copy tokens - any packet field that stringifies to something
# containing these substrings (case-insensitive, word-aware) is rejected.
# Shares vocabulary with the Bounded Non-Quant Cash-Out guardrails so drift
# cannot slip in via a new packet path.
_FORBIDDEN_COPY_PATTERNS = [
    re.compile(r"\bbuy\b", re.IGNORECASE),
    re.compile(r"\bsell\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\b", re.IGNORECASE),
    re.compile(r"\brecommend(?:s|ed|ing)?\b", re.IGNORECASE),
    re.compile(r"will\s+definitely", re.IGNORECASE),
    re.compile(r"반드시\s*오른"),
    re.compile(r"반드시\s*내린"),
    re.compile(r"무조건\s*(?:오른|내린)"),
]


def _scan_forbidden_tokens(value: Any) -> list[str]:
    """Return list of forbidden substrings found in any string leaf of ``value``."""

    hits: list[str] = []
    stack: list[Any] = [value]
    while stack:
        cur = stack.pop()
        if isinstance(cur, str):
            for pat in _FORBIDDEN_COPY_PATTERNS:
                m = pat.search(cur)
                if m is not None:
                    hits.append(m.group(0))
        elif isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple, set)):
            stack.extend(cur)
    return hits


def deterministic_packet_id(
    *, packet_type: str, created_by_agent: str, target_scope: dict[str, Any], salt: str = ""
) -> str:
    scope_key = "|".join(
        f"{k}={target_scope[k]}" for k in sorted(target_scope or {})
    )
    payload = f"{packet_type}|{created_by_agent}|{scope_key}|{salt}".encode("utf-8")
    return "pkt_" + hashlib.sha256(payload).hexdigest()[:22]


class AgenticPacketBaseV1(BaseModel):
    """Every agentic-harness packet inherits from this base contract."""

    contract: str = "METIS_AGENTIC_HARNESS_PACKET_V1"
    packet_schema_version: int = PACKET_SCHEMA_VERSION

    packet_id: str = Field(min_length=1)
    packet_type: str = Field(min_length=1)
    target_layer: TargetLayer
    created_by_agent: str = Field(min_length=1)
    created_at_utc: str = ""
    target_scope: dict[str, Any] = Field(default_factory=dict)
    provenance_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    blocking_reasons: list[str] = Field(default_factory=list)
    expiry_or_recheck_rule: str = ""
    status: PacketStatus = "proposed"
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("packet_type")
    @classmethod
    def _packet_type_in_vocab(cls, v: str) -> str:
        if v not in PACKET_TYPES:
            raise ValueError(f"packet_type must be one of {PACKET_TYPES}, got {v!r}")
        return v

    @field_validator("target_layer")
    @classmethod
    def _target_layer_in_vocab(cls, v: str) -> str:
        if v not in TARGET_LAYERS:
            raise ValueError(f"target_layer must be one of {TARGET_LAYERS}, got {v!r}")
        return v

    @field_validator("provenance_refs")
    @classmethod
    def _provenance_refs_non_empty(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("provenance_refs must be a list of strings")
        out: list[str] = []
        for item in v:
            s = str(item or "").strip()
            if s:
                out.append(s)
        if not out:
            raise ValueError("provenance_refs must contain at least one non-empty ref")
        return out

    @field_validator("blocking_reasons")
    @classmethod
    def _blocking_reasons_are_strings(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("blocking_reasons must be a list of strings")
        return [str(x).strip() for x in v if str(x or "").strip()]

    @field_validator("expiry_or_recheck_rule")
    @classmethod
    def _expiry_is_string(cls, v: Any) -> str:
        return str(v or "").strip()

    @field_validator("target_scope")
    @classmethod
    def _target_scope_is_mapping(cls, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("target_scope must be a dict")
        return dict(v)

    @field_validator("payload")
    @classmethod
    def _payload_is_mapping(cls, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        return dict(v)

    @model_validator(mode="after")
    def _stamp_and_scan(self) -> "AgenticPacketBaseV1":
        if not str(self.created_at_utc or "").strip():
            self.created_at_utc = datetime.now(timezone.utc).isoformat()
        hits = _scan_forbidden_tokens(
            [self.target_scope, self.payload, self.blocking_reasons, self.expiry_or_recheck_rule]
        )
        if hits:
            raise ValueError(
                "agentic packet contains forbidden copy tokens: " + ", ".join(sorted(set(hits)))
            )
        return self


# -----------------------------------------------------------------------------
# Layer 1 - Proactive Data Collection Layer
# -----------------------------------------------------------------------------


INGEST_TRIGGER_KINDS = (
    "earnings_transcript_stale",
    "earnings_transcript_new_filing_hint",
    "price_dislocation",
    "manual_operator",
)


class IngestAlertPacketV1(AgenticPacketBaseV1):
    packet_type: str = "IngestAlertPacketV1"
    target_layer: TargetLayer = "layer1_ingest"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("source_family", "trigger_kind", "asset_ids"):
            if k not in v:
                raise ValueError(f"IngestAlertPacketV1.payload requires '{k}'")
        if v["trigger_kind"] not in INGEST_TRIGGER_KINDS:
            raise ValueError(
                f"IngestAlertPacketV1 trigger_kind must be one of {INGEST_TRIGGER_KINDS}"
            )
        if not isinstance(v["asset_ids"], list) or not v["asset_ids"]:
            raise ValueError("IngestAlertPacketV1 asset_ids must be a non-empty list")
        return dict(v)


class EventTriggerPacketV1(AgenticPacketBaseV1):
    packet_type: str = "EventTriggerPacketV1"
    target_layer: TargetLayer = "layer1_ingest"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("trigger_kind", "asset_id", "expected_freshness_hours"):
            if k not in v:
                raise ValueError(f"EventTriggerPacketV1.payload requires '{k}'")
        if v["trigger_kind"] not in INGEST_TRIGGER_KINDS:
            raise ValueError(
                f"EventTriggerPacketV1 trigger_kind must be one of {INGEST_TRIGGER_KINDS}"
            )
        return dict(v)


class SourceArtifactPacketV1(AgenticPacketBaseV1):
    packet_type: str = "SourceArtifactPacketV1"
    target_layer: TargetLayer = "layer1_ingest"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("source_family", "artifact_kind", "fetch_outcome"):
            if k not in v:
                raise ValueError(f"SourceArtifactPacketV1.payload requires '{k}'")
        if v["fetch_outcome"] not in ("ok", "empty", "error", "skipped"):
            raise ValueError(
                "SourceArtifactPacketV1.payload.fetch_outcome must be one of "
                "('ok','empty','error','skipped')"
            )
        return dict(v)


# -----------------------------------------------------------------------------
# Layer 2 - Data Quality Verification / Library Management
# -----------------------------------------------------------------------------


INTEGRITY_SEVERITIES = ("low", "medium", "high")
INTEGRITY_CHECK_NAMES = (
    "pit_violation",
    "stale_data",
    "schema_drift",
    "missing_coverage",
    "duplicate_artifact",
)


class LibraryIntegrityPacketV1(AgenticPacketBaseV1):
    packet_type: str = "LibraryIntegrityPacketV1"
    target_layer: TargetLayer = "layer2_library"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("check_name", "severity", "offending_refs", "summary"):
            if k not in v:
                raise ValueError(f"LibraryIntegrityPacketV1.payload requires '{k}'")
        if v["check_name"] not in INTEGRITY_CHECK_NAMES:
            raise ValueError(
                f"LibraryIntegrityPacketV1 check_name must be one of {INTEGRITY_CHECK_NAMES}"
            )
        if v["severity"] not in INTEGRITY_SEVERITIES:
            raise ValueError(
                f"LibraryIntegrityPacketV1 severity must be one of {INTEGRITY_SEVERITIES}"
            )
        if not isinstance(v["offending_refs"], list):
            raise ValueError("offending_refs must be a list")
        return dict(v)


class CoverageGapPacketV1(AgenticPacketBaseV1):
    packet_type: str = "CoverageGapPacketV1"
    target_layer: TargetLayer = "layer2_library"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("cohort_name", "missing_asset_ids", "dimension"):
            if k not in v:
                raise ValueError(f"CoverageGapPacketV1.payload requires '{k}'")
        if not isinstance(v["missing_asset_ids"], list):
            raise ValueError("missing_asset_ids must be a list")
        return dict(v)


# -----------------------------------------------------------------------------
# Layer 3 - Research Engine
# -----------------------------------------------------------------------------


class ResearchCandidatePacketV1(AgenticPacketBaseV1):
    packet_type: str = "ResearchCandidatePacketV1"
    target_layer: TargetLayer = "layer3_research"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        pc = v.get("persona_candidate_packet")
        if not isinstance(pc, dict):
            raise ValueError(
                "ResearchCandidatePacketV1.payload.persona_candidate_packet must be a dict "
                "(PersonaCandidatePacketV1 shape)"
            )
        # Validate the embedded persona packet with its own schema.
        PersonaCandidatePacketV1.model_validate(pc)
        sig = str(v.get("signal_type", "") or "")
        if sig not in SIGNAL_TYPES:
            raise ValueError(
                f"ResearchCandidatePacketV1.payload.signal_type must be one of {SIGNAL_TYPES}"
            )
        iov = str(v.get("intended_overlay_type", "") or "")
        if iov and iov not in OVERLAY_TYPES:
            raise ValueError(
                "ResearchCandidatePacketV1.payload.intended_overlay_type must be empty or in "
                f"{OVERLAY_TYPES}"
            )
        return dict(v)


class OverlayProposalPacketV1(AgenticPacketBaseV1):
    packet_type: str = "OverlayProposalPacketV1"
    target_layer: TargetLayer = "layer3_research"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("overlay_type", "expected_direction_hint", "why_it_matters"):
            if k not in v:
                raise ValueError(f"OverlayProposalPacketV1.payload requires '{k}'")
        if v["overlay_type"] not in OVERLAY_TYPES:
            raise ValueError(
                f"OverlayProposalPacketV1 overlay_type must be one of {OVERLAY_TYPES}"
            )
        if v["expected_direction_hint"] not in EXPECTED_DIRECTION_HINTS:
            raise ValueError(
                "OverlayProposalPacketV1 expected_direction_hint must be one of "
                f"{EXPECTED_DIRECTION_HINTS}"
            )
        return dict(v)


# -----------------------------------------------------------------------------
# Layer 4 - Model Quality / Governance
# -----------------------------------------------------------------------------


HORIZON_STATE_VALUES = (
    "real_derived",
    "real_derived_with_degraded_challenger",
    "template_fallback",
    "insufficient_evidence",
)

GATE_OUTCOMES = ("pass", "fail", "deferred")

# AGH v1 Patch 3: controlled vocabulary for the ``payload.target`` field of
# ``RegistryUpdateProposalV1`` and ``RegistryPatchAppliedPacketV1``. Patch 2
# only supported ``horizon_provenance``; Patch 3 adds
# ``registry_entry_artifact_promotion`` so the governed apply path can swap
# ``registry_entries[*].active_artifact_id`` / ``challenger_artifact_ids``.
REGISTRY_PROPOSAL_TARGETS = (
    "horizon_provenance",
    "registry_entry_artifact_promotion",
)

# AGH v1 Patch 3: bundle-allowed brain bundle horizon buckets. Mirrors
# ``metis_brain.bundle._HORIZON_BUCKETS`` normalization keys; kept duplicated
# here to avoid a circular import (packets <- metis_brain.bundle <- packets).
REGISTRY_BUNDLE_HORIZONS = ("short", "medium", "medium_long", "long")


class EvaluationPacketV1(AgenticPacketBaseV1):
    packet_type: str = "EvaluationPacketV1"
    target_layer: TargetLayer = "layer4_governance"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("evaluation_kind", "target_ref", "metrics"):
            if k not in v:
                raise ValueError(f"EvaluationPacketV1.payload requires '{k}'")
        if not isinstance(v["metrics"], dict):
            raise ValueError("EvaluationPacketV1.payload.metrics must be a dict")
        return dict(v)


class PromotionGatePacketV1(AgenticPacketBaseV1):
    packet_type: str = "PromotionGatePacketV1"
    target_layer: TargetLayer = "layer4_governance"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("candidate_ref", "gate_steps", "overall_outcome"):
            if k not in v:
                raise ValueError(f"PromotionGatePacketV1.payload requires '{k}'")
        if v["overall_outcome"] not in GATE_OUTCOMES:
            raise ValueError(
                f"PromotionGatePacketV1 overall_outcome must be one of {GATE_OUTCOMES}"
            )
        if not isinstance(v["gate_steps"], list):
            raise ValueError("PromotionGatePacketV1 gate_steps must be a list")
        return dict(v)


class RegistryUpdateProposalV1(AgenticPacketBaseV1):
    packet_type: str = "RegistryUpdateProposalV1"
    target_layer: TargetLayer = "layer4_governance"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        if "target" not in v:
            raise ValueError("RegistryUpdateProposalV1.payload requires 'target'")
        target = v["target"]
        if target not in REGISTRY_PROPOSAL_TARGETS:
            raise ValueError(
                f"RegistryUpdateProposalV1 target must be one of "
                f"{REGISTRY_PROPOSAL_TARGETS}"
            )
        if target == "horizon_provenance":
            for k in ("from_state", "to_state", "evidence_refs"):
                if k not in v:
                    raise ValueError(
                        f"RegistryUpdateProposalV1.payload requires '{k}'"
                    )
            for s in (v["from_state"], v["to_state"]):
                if s not in HORIZON_STATE_VALUES:
                    raise ValueError(
                        f"horizon_provenance state must be one of {HORIZON_STATE_VALUES}"
                    )
        elif target == "registry_entry_artifact_promotion":
            # Patch 3: controlled vocabulary for artifact-level promotion.
            # No free-form mutation payload; explicit before/after pointer
            # fields the executor can verify against the current bundle.
            required_keys = (
                "registry_entry_id",
                "horizon",
                "from_active_artifact_id",
                "to_active_artifact_id",
                "from_challenger_artifact_ids",
                "to_challenger_artifact_ids",
                "evidence_refs",
            )
            for k in required_keys:
                if k not in v:
                    raise ValueError(
                        f"RegistryUpdateProposalV1(registry_entry_artifact_promotion)"
                        f".payload requires '{k}'"
                    )
            if not str(v["registry_entry_id"]).strip():
                raise ValueError("registry_entry_id must be non-empty")
            if v["horizon"] not in REGISTRY_BUNDLE_HORIZONS:
                raise ValueError(
                    f"horizon must be one of {REGISTRY_BUNDLE_HORIZONS}"
                )
            if not str(v["from_active_artifact_id"]).strip():
                raise ValueError("from_active_artifact_id must be non-empty")
            if not str(v["to_active_artifact_id"]).strip():
                raise ValueError("to_active_artifact_id must be non-empty")
            if v["from_active_artifact_id"] == v["to_active_artifact_id"]:
                raise ValueError(
                    "from_active_artifact_id and to_active_artifact_id must differ"
                )
            for k in ("from_challenger_artifact_ids", "to_challenger_artifact_ids"):
                val = v[k]
                if not isinstance(val, list):
                    raise ValueError(f"{k} must be a list")
                if len(set(val)) != len(val):
                    raise ValueError(f"{k} entries must be unique")
                for entry in val:
                    if not isinstance(entry, str) or not entry.strip():
                        raise ValueError(
                            f"{k} entries must be non-empty strings"
                        )
        if not isinstance(v["evidence_refs"], list) or not v["evidence_refs"]:
            raise ValueError("evidence_refs must be a non-empty list")
        # Proposal-only invariant: never include a raw registry row here.
        if "active_registry_mutation" in v:
            raise ValueError(
                "RegistryUpdateProposalV1 must not carry raw active_registry_mutation; "
                "registry writes stay outside the agentic harness (governed CLI only)."
            )
        return dict(v)


# -----------------------------------------------------------------------------
# AGH v1 Patch 2 (Promotion Bridge Closure) - operator-gated decision + apply.
#
# Flow:
#   1. Layer 4 emits ``RegistryUpdateProposalV1`` (target=horizon_provenance).
#   2. Operator issues a decision via ``harness-decide``; this records a
#      ``RegistryDecisionPacketV1`` with action ``approve|reject|defer``.
#   3. On ``approve`` the registry_patch_executor worker loads the brain
#      bundle, verifies ``from_state`` matches the current
#      ``horizon_provenance[horizon].source``, and either performs a governed
#      atomic write (outcome=applied) or records a conflict_skip
#      ``RegistryPatchAppliedPacketV1``.
#
# Both packets are strictly audit artifacts: they never carry raw registry
# mutations of the ``active_registry_mutation`` shape (same invariant as
# ``RegistryUpdateProposalV1``).
# -----------------------------------------------------------------------------


REGISTRY_DECISION_ACTIONS = ("approve", "reject", "defer")

REGISTRY_PATCH_OUTCOMES = ("applied", "conflict_skip")


class RegistryDecisionPacketV1(AgenticPacketBaseV1):
    packet_type: str = "RegistryDecisionPacketV1"
    target_layer: TargetLayer = "layer4_governance"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in (
            "action",
            "actor",
            "reason",
            "decision_at_utc",
            "cited_proposal_packet_id",
        ):
            if k not in v:
                raise ValueError(f"RegistryDecisionPacketV1.payload requires '{k}'")
        if v["action"] not in REGISTRY_DECISION_ACTIONS:
            raise ValueError(
                "RegistryDecisionPacketV1 action must be one of "
                f"{REGISTRY_DECISION_ACTIONS}"
            )
        if not str(v["cited_proposal_packet_id"]).strip():
            raise ValueError("cited_proposal_packet_id must be non-empty")
        if not str(v["actor"]).strip():
            raise ValueError("actor must be non-empty")
        # Patch 2 invariant: a decision packet is an audit record only; it
        # must not smuggle a raw registry mutation.
        if "active_registry_mutation" in v:
            raise ValueError(
                "RegistryDecisionPacketV1 must not carry raw active_registry_mutation; "
                "registry writes stay in the registry_patch_executor worker."
            )
        return dict(v)


class RegistryPatchAppliedPacketV1(AgenticPacketBaseV1):
    packet_type: str = "RegistryPatchAppliedPacketV1"
    target_layer: TargetLayer = "layer4_governance"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in (
            "outcome",
            "target",
            "horizon",
            "cited_proposal_packet_id",
            "cited_decision_packet_id",
            "applied_at_utc",
            "before_snapshot",
            "after_snapshot",
        ):
            if k not in v:
                raise ValueError(f"RegistryPatchAppliedPacketV1.payload requires '{k}'")
        if v["outcome"] not in REGISTRY_PATCH_OUTCOMES:
            raise ValueError(
                "RegistryPatchAppliedPacketV1 outcome must be one of "
                f"{REGISTRY_PATCH_OUTCOMES}"
            )
        target = v["target"]
        if target not in REGISTRY_PROPOSAL_TARGETS:
            raise ValueError(
                f"RegistryPatchAppliedPacketV1 target must be one of "
                f"{REGISTRY_PROPOSAL_TARGETS}"
            )
        if target == "horizon_provenance":
            for k in ("from_state", "to_state"):
                if k not in v:
                    raise ValueError(
                        f"RegistryPatchAppliedPacketV1(horizon_provenance)"
                        f".payload requires '{k}'"
                    )
            for s in (v["from_state"], v["to_state"]):
                if s not in HORIZON_STATE_VALUES:
                    raise ValueError(
                        f"horizon_provenance state must be one of {HORIZON_STATE_VALUES}"
                    )
        elif target == "registry_entry_artifact_promotion":
            if "registry_entry_id" not in v or not str(
                v["registry_entry_id"]
            ).strip():
                raise ValueError(
                    "RegistryPatchAppliedPacketV1(registry_entry_artifact_promotion)"
                    ".payload requires non-empty 'registry_entry_id'"
                )
            if v["horizon"] not in REGISTRY_BUNDLE_HORIZONS:
                raise ValueError(
                    f"horizon must be one of {REGISTRY_BUNDLE_HORIZONS}"
                )
        if not str(v["cited_proposal_packet_id"]).strip():
            raise ValueError("cited_proposal_packet_id must be non-empty")
        if not str(v["cited_decision_packet_id"]).strip():
            raise ValueError("cited_decision_packet_id must be non-empty")
        if not isinstance(v["before_snapshot"], dict):
            raise ValueError("before_snapshot must be a dict")
        # after_snapshot may be an empty dict when outcome=conflict_skip.
        if not isinstance(v["after_snapshot"], dict):
            raise ValueError("after_snapshot must be a dict")
        # Same invariant as RegistryUpdateProposalV1: audit packet, not a
        # vehicle for raw registry mutation.
        if "active_registry_mutation" in v:
            raise ValueError(
                "RegistryPatchAppliedPacketV1 must not carry raw active_registry_mutation; "
                "the applied diff lives in before_snapshot / after_snapshot only."
            )
        return dict(v)


# -----------------------------------------------------------------------------
# AGH v1 Patch 3 (Artifact Promotion Bridge Closure) - per-horizon spectrum
# refresh audit. Emitted by ``registry_patch_executor`` after an
# ``registry_entry_artifact_promotion`` apply so Today/L5/Replay can cite the
# exact refresh outcome (full recompute vs. carry-over) alongside the
# RegistryPatchAppliedPacketV1.
# -----------------------------------------------------------------------------


SPECTRUM_REFRESH_OUTCOMES = (
    "recomputed",
    "carry_over_fixture_fallback",
    "carry_over_db_unavailable",
)

SPECTRUM_REFRESH_MODES = (
    "full_recompute_from_validation",
    "fixture_fallback",
)


class SpectrumRefreshRecordV1(AgenticPacketBaseV1):
    packet_type: str = "SpectrumRefreshRecordV1"
    target_layer: TargetLayer = "layer4_governance"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in (
            "outcome",
            "refresh_mode",
            "needs_db_rebuild",
            "cited_applied_packet_id",
            "cited_proposal_packet_id",
            "cited_decision_packet_id",
            "horizon",
            "registry_entry_id",
            "before_row_count",
            "after_row_count",
            "refreshed_at_utc",
            "bundle_path",
        ):
            if k not in v:
                raise ValueError(f"SpectrumRefreshRecordV1.payload requires '{k}'")
        if v["outcome"] not in SPECTRUM_REFRESH_OUTCOMES:
            raise ValueError(
                f"SpectrumRefreshRecordV1 outcome must be one of "
                f"{SPECTRUM_REFRESH_OUTCOMES}"
            )
        if v["refresh_mode"] not in SPECTRUM_REFRESH_MODES:
            raise ValueError(
                f"SpectrumRefreshRecordV1 refresh_mode must be one of "
                f"{SPECTRUM_REFRESH_MODES}"
            )
        if not isinstance(v["needs_db_rebuild"], bool):
            raise ValueError("needs_db_rebuild must be a bool")
        if v["horizon"] not in REGISTRY_BUNDLE_HORIZONS:
            raise ValueError(
                f"horizon must be one of {REGISTRY_BUNDLE_HORIZONS}"
            )
        for k in (
            "cited_applied_packet_id",
            "cited_proposal_packet_id",
            "cited_decision_packet_id",
            "registry_entry_id",
            "bundle_path",
        ):
            if not str(v[k]).strip():
                raise ValueError(f"{k} must be non-empty")
        for k in ("before_row_count", "after_row_count"):
            if not isinstance(v[k], int) or v[k] < 0:
                raise ValueError(f"{k} must be a non-negative int")
        # Optional sample fields, capped at 10 each if present.
        for k in ("before_row_asset_ids_sample", "after_row_asset_ids_sample"):
            if k in v:
                if not isinstance(v[k], list):
                    raise ValueError(f"{k} must be a list")
                if len(v[k]) > 10:
                    raise ValueError(f"{k} must have at most 10 entries")
        if "blocking_reasons" in v and not isinstance(v["blocking_reasons"], list):
            raise ValueError("blocking_reasons must be a list")
        if "active_registry_mutation" in v:
            raise ValueError(
                "SpectrumRefreshRecordV1 must not carry raw active_registry_mutation; "
                "row replacement lives inline inside the bundle atomic write."
            )
        return dict(v)


# -----------------------------------------------------------------------------
# Replay & User Surface
# -----------------------------------------------------------------------------


AGING_LABELS = ("aged_in_line", "aged_against", "neutral")


class ReplayLearningPacketV1(AgenticPacketBaseV1):
    packet_type: str = "ReplayLearningPacketV1"
    target_layer: TargetLayer = "layer4_governance"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in ("asset_id", "decision_event_id", "overlay_aging_lineage"):
            if k not in v:
                raise ValueError(f"ReplayLearningPacketV1.payload requires '{k}'")
        if not isinstance(v["overlay_aging_lineage"], list):
            raise ValueError("overlay_aging_lineage must be a list")
        for entry in v["overlay_aging_lineage"]:
            if not isinstance(entry, dict) or entry.get("aging_label") not in AGING_LABELS:
                raise ValueError(
                    f"overlay_aging_lineage entries must include aging_label in {AGING_LABELS}"
                )
        return dict(v)


USER_QUESTION_KINDS = ("why_changed", "system_status", "research_pending")


class UserQueryActionPacketV1(AgenticPacketBaseV1):
    packet_type: str = "UserQueryActionPacketV1"
    target_layer: TargetLayer = "layer5_surface"

    @field_validator("payload")
    @classmethod
    def _required_payload_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("payload must be a dict")
        for k in (
            "question",
            "routed_kind",
            "state_bundle_refs",
            "llm_response",
            "guardrail_passed",
        ):
            if k not in v:
                raise ValueError(f"UserQueryActionPacketV1.payload requires '{k}'")
        if v["routed_kind"] not in USER_QUESTION_KINDS:
            raise ValueError(
                f"UserQueryActionPacketV1 routed_kind must be one of {USER_QUESTION_KINDS}"
            )
        if not isinstance(v["state_bundle_refs"], list) or not v["state_bundle_refs"]:
            raise ValueError("state_bundle_refs must be a non-empty list")
        if not isinstance(v["llm_response"], dict):
            raise ValueError("llm_response must be a dict")
        return dict(v)


PACKET_TYPE_TO_CLASS: dict[str, type[AgenticPacketBaseV1]] = {
    "IngestAlertPacketV1": IngestAlertPacketV1,
    "EventTriggerPacketV1": EventTriggerPacketV1,
    "SourceArtifactPacketV1": SourceArtifactPacketV1,
    "LibraryIntegrityPacketV1": LibraryIntegrityPacketV1,
    "CoverageGapPacketV1": CoverageGapPacketV1,
    "ResearchCandidatePacketV1": ResearchCandidatePacketV1,
    "OverlayProposalPacketV1": OverlayProposalPacketV1,
    "EvaluationPacketV1": EvaluationPacketV1,
    "PromotionGatePacketV1": PromotionGatePacketV1,
    "RegistryUpdateProposalV1": RegistryUpdateProposalV1,
    "ReplayLearningPacketV1": ReplayLearningPacketV1,
    "UserQueryActionPacketV1": UserQueryActionPacketV1,
    "RegistryDecisionPacketV1": RegistryDecisionPacketV1,
    "RegistryPatchAppliedPacketV1": RegistryPatchAppliedPacketV1,
    "SpectrumRefreshRecordV1": SpectrumRefreshRecordV1,
}


def validate_packet(row: dict[str, Any]) -> AgenticPacketBaseV1:
    """Type-dispatch a raw dict into the matching Pydantic packet class."""

    pt = str(row.get("packet_type") or "")
    klass = PACKET_TYPE_TO_CLASS.get(pt)
    if klass is None:
        raise ValueError(f"unknown packet_type {pt!r}")
    return klass.model_validate(row)
