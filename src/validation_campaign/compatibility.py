from __future__ import annotations

from typing import Any

from validation_campaign.constants import (
    COHORT_CONFIG_VERSION,
    COHORT_DIMENSIONS,
    JOIN_POLICY_CANONICAL,
    WINDOW_STABILITY_METRIC,
    canonical_baseline_config,
)


def is_recipe_validation_run_compatible(
    run: dict[str, Any],
    *,
    program_quality_class: str,
) -> bool:
    """
    Deterministic reuse: same hypothesis is implied by caller; configs must match
    current canonical Phase 15 logic (join policy, baselines, cohort slice version).
    """
    if str(run.get("status") or "") != "completed":
        return False

    jp = run.get("join_policy_version")
    if jp != JOIN_POLICY_CANONICAL:
        return False

    qf = run.get("quality_filter_json") or {}
    if isinstance(qf, dict):
        qf_jp = qf.get("join_policy_version")
        if qf_jp is not None and qf_jp != JOIN_POLICY_CANONICAL:
            return False

    if run.get("baseline_config_json") != canonical_baseline_config():
        return False

    cc = run.get("cohort_config_json") or {}
    if not isinstance(cc, dict):
        return False
    cv = cc.get("config_version")
    if cv not in (None, COHORT_CONFIG_VERSION):
        return False
    if tuple(cc.get("dimensions") or []) != COHORT_DIMENSIONS:
        return False
    if str(cc.get("program_quality_class") or "") != str(program_quality_class):
        return False

    wc = run.get("window_config_json") or {}
    if not isinstance(wc, dict):
        return False
    if wc.get("stability_metric") != WINDOW_STABILITY_METRIC:
        return False

    return True
