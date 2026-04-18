"""Pragmatic Brain Absorption v1 — Milestone D.

Persona Candidate Harness v1 lets governed agent personas (Quant Residual
Analyst / Value Reversion Analyst / Non-Quant Regime Tracker) emit
**structured artifact-like candidate packets**. These are NOT live truth —
work-order §8.4 requires an explicit PIT + provenance + validation + runtime
explainability + promotion gate before any active registry entry is touched.

The module is therefore write-to-file / stdout only. It never mutates the
brain bundle, factor_validation_* tables, registry entries, or the overlay
layer. Downstream promotion pipelines (Patch Bundle D+ of the unified Build
Plan) can read these JSON packets later, but the harness itself declines to
publish anything as active brain truth.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


PERSONA_KINDS = (
    "quant_residual_analyst",
    "value_reversion_analyst",
    "non_quant_regime_tracker",
    "growth_durability_analyst",
    "capital_allocation_analyst",
)

PersonaKind = Literal[
    "quant_residual_analyst",
    "value_reversion_analyst",
    "non_quant_regime_tracker",
    "growth_durability_analyst",
    "capital_allocation_analyst",
]


class PersonaEvidenceRefV1(BaseModel):
    kind: str
    pointer: str = Field(min_length=1)
    summary: str = ""

    @field_validator("kind")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = str(v or "").strip()
        if not v:
            raise ValueError("kind required")
        return v


class PersonaCandidatePacketV1(BaseModel):
    """One candidate thesis family emitted by a governed persona.

    The packet explicitly mirrors artifact shape but is never an active
    artifact by itself. ``gate_eligibility`` is a diagnostic field only — it
    lists which promotion-gate checks the persona believes might plausibly
    pass, never a claim that any of them have passed.
    """

    contract: str = "METIS_PERSONA_CANDIDATE_PACKET_V1"
    candidate_id: str = Field(min_length=1)
    persona: PersonaKind
    thesis_family: str = Field(min_length=1)
    targeted_horizon: Literal["short", "medium", "medium_long", "long"]
    targeted_universe: str = Field(min_length=1)
    evidence_refs: list[PersonaEvidenceRefV1] = Field(default_factory=list)
    overlay_recommendation: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    countercase: str = ""
    gate_eligibility: dict[str, bool] = Field(default_factory=dict)
    provenance_summary: str = ""
    promotion_doctrine_note: str = (
        "Candidate only. Not active truth. Must pass PIT + provenance + "
        "validation + runtime explainability + explicit promotion before any "
        "active registry or overlay entry is created."
    )
    created_at_utc: str = ""

    @field_validator("persona")
    @classmethod
    def _persona_in_vocab(cls, v: str) -> str:
        if v not in PERSONA_KINDS:
            raise ValueError(f"persona must be one of {PERSONA_KINDS}")
        return v

    @model_validator(mode="after")
    def _stamp_created_at(self) -> "PersonaCandidatePacketV1":
        if not str(self.created_at_utc or "").strip():
            self.created_at_utc = datetime.now(timezone.utc).isoformat()
        return self


def deterministic_candidate_id(
    *,
    persona: str,
    thesis_family: str,
    targeted_horizon: str,
    targeted_universe: str,
) -> str:
    payload = f"{persona}|{thesis_family}|{targeted_horizon}|{targeted_universe}".encode("utf-8")
    return "pcand_" + hashlib.sha256(payload).hexdigest()[:24]


def build_persona_candidate_packet(
    *,
    persona: str,
    thesis_family: str,
    targeted_horizon: str,
    targeted_universe: str,
    evidence_refs: list[dict[str, str]],
    confidence: float,
    overlay_recommendation: str = "",
    countercase: str = "",
    gate_eligibility: dict[str, bool] | None = None,
    provenance_summary: str = "",
) -> PersonaCandidatePacketV1:
    cid = deterministic_candidate_id(
        persona=persona,
        thesis_family=thesis_family,
        targeted_horizon=targeted_horizon,
        targeted_universe=targeted_universe,
    )
    return PersonaCandidatePacketV1.model_validate(
        {
            "candidate_id": cid,
            "persona": persona,
            "thesis_family": thesis_family,
            "targeted_horizon": targeted_horizon,
            "targeted_universe": targeted_universe,
            "evidence_refs": evidence_refs,
            "overlay_recommendation": overlay_recommendation,
            "confidence": confidence,
            "countercase": countercase,
            "gate_eligibility": dict(gate_eligibility or {}),
            "provenance_summary": provenance_summary,
        }
    )


def write_persona_candidate_report(
    packets: list[PersonaCandidatePacketV1],
    *,
    out_path: Path,
) -> dict[str, Any]:
    report = {
        "contract": "METIS_PERSONA_CANDIDATES_REPORT_V1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "packet_count": len(packets),
        "packets": [p.model_dump() for p in packets],
        "governance_note": (
            "Persona candidates are diagnostic inputs only. They never short-"
            "circuit promotion gates, never write to the active registry, "
            "and never update the brain overlays seed file directly."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
