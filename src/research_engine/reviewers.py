"""Deterministic bounded review lenses (no LLM required for Phase 14 kernel)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class LensResult:
    lens: str
    decision: str
    strongest_objection: str
    evidence_needed: str
    proceed_to_validation: bool
    detail_json: dict[str, Any]


def review_mechanism(
    *,
    economic_rationale: str,
    mechanism_json: dict[str, Any],
) -> LensResult:
    rationale = (economic_rationale or "").strip()
    if len(rationale) < 80:
        return LensResult(
            lens="mechanism",
            decision="reject",
            strongest_objection="Economic rationale too short to be falsifiable or substantive.",
            evidence_needed="Expand causal story, scope, and what would disprove it.",
            proceed_to_validation=False,
            detail_json={"rationale_len": len(rationale)},
        )
    pm = mechanism_json.get("primary_mechanism")
    if not pm or not str(pm).strip():
        return LensResult(
            lens="mechanism",
            decision="reject",
            strongest_objection="No primary_mechanism in mechanism_json.",
            evidence_needed="Name a testable economic mechanism, not only labels.",
            proceed_to_validation=False,
            detail_json={},
        )
    if len(str(pm)) < 20:
        return LensResult(
            lens="mechanism",
            decision="concern",
            strongest_objection="Mechanism statement is very terse.",
            evidence_needed="Clarify transmission channel to forward returns.",
            proceed_to_validation=True,
            detail_json={},
        )
    return LensResult(
        lens="mechanism",
        decision="pass",
        strongest_objection="",
        evidence_needed="",
        proceed_to_validation=True,
        detail_json={},
    )


def review_pit_data(*, quality_context: dict[str, Any]) -> LensResult:
    qc = str(quality_context.get("quality_class") or "")
    m = quality_context.get("metrics_json") or {}
    ins_frac = float(m.get("insufficient_data_fraction") or 0.0)
    if qc in ("failed", "degraded"):
        return LensResult(
            lens="pit_data",
            decision="reject",
            strongest_objection="Public-core quality context is failed/degraded; not a strong validation substrate.",
            evidence_needed="Re-run cycle on usable_with_gaps or strong quality_class before treating as evidence.",
            proceed_to_validation=False,
            detail_json={"quality_class": qc},
        )
    if qc == "thin_input" or ins_frac >= 0.75:
        return LensResult(
            lens="pit_data",
            decision="concern",
            strongest_objection="Dominant missingness / thin_input substrate; ideas allowed but not strong grounds.",
            evidence_needed="Thicker factor coverage or lower insufficient_data_fraction in quality metrics.",
            proceed_to_validation=True,
            detail_json={"quality_class": qc, "insufficient_data_fraction": ins_frac},
        )
    return LensResult(
        lens="pit_data",
        decision="pass",
        strongest_objection="",
        evidence_needed="",
        proceed_to_validation=True,
        detail_json={"quality_class": qc},
    )


def review_residual(
    *,
    hypothesis_title: str,
    residual_link_count: int,
    dominant_bucket: Optional[str],
) -> LensResult:
    if residual_link_count == 0:
        return LensResult(
            lens="residual",
            decision="concern",
            strongest_objection="No residual_case links; hypothesis not grounded in unresolved queue.",
            evidence_needed="Attach representative residual items the hypothesis claims to explain.",
            proceed_to_validation=True,
            detail_json={},
        )
    if dominant_bucket == "unresolved_residual" and "liquidity" in hypothesis_title.lower():
        return LensResult(
            lens="residual",
            decision="concern",
            strongest_objection="Dominant residuals are class/score tension; liquidity story may miss the failure mode.",
            evidence_needed="Show the mechanism addresses unresolved_residual patterns, not only liquid names.",
            proceed_to_validation=True,
            detail_json={"dominant_bucket": dominant_bucket},
        )
    return LensResult(
        lens="residual",
        decision="pass",
        strongest_objection="",
        evidence_needed="",
        proceed_to_validation=True,
        detail_json={"dominant_bucket": dominant_bucket},
    )


def review_compression(
    *,
    feature_definition_json: dict[str, Any],
    economic_rationale: str,
) -> LensResult:
    rationale_l = (economic_rationale or "").lower()
    fd = " ".join(str(v).lower() for v in feature_definition_json.values())
    if "state_change_score" in fd and "novel" not in rationale_l and "beyond" not in rationale_l:
        return LensResult(
            lens="compression",
            decision="concern",
            strongest_objection="Feature definition leans on existing score without stated incremental claim.",
            evidence_needed="Document what is not already encoded in deterministic state_change_score.",
            proceed_to_validation=True,
            detail_json={},
        )
    return LensResult(
        lens="compression",
        decision="pass",
        strongest_objection="",
        evidence_needed="",
        proceed_to_validation=True,
        detail_json={},
    )


def run_all_lenses_for_round(
    *,
    economic_rationale: str,
    mechanism_json: dict[str, Any],
    feature_definition_json: dict[str, Any],
    quality_context: dict[str, Any],
    residual_link_count: int,
    dominant_bucket: Optional[str],
    hypothesis_title: str,
    include_compression: bool = True,
) -> list[LensResult]:
    out = [
        review_mechanism(
            economic_rationale=economic_rationale, mechanism_json=mechanism_json
        ),
        review_pit_data(quality_context=quality_context),
        review_residual(
            hypothesis_title=hypothesis_title,
            residual_link_count=residual_link_count,
            dominant_bucket=dominant_bucket,
        ),
    ]
    if include_compression:
        out.append(
            review_compression(
                feature_definition_json=feature_definition_json,
                economic_rationale=economic_rationale,
            )
        )
    return out
