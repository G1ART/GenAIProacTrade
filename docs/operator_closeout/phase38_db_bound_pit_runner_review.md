# Phase 38 — DB-bound PIT runner (alternate specs)

_Generated (UTC): `2026-04-10T18:26:47.398780+00:00`_
_Bundle generated (UTC): `2026-04-10T18:26:47.398074+00:00`_

## PIT execution

- ok: `True`
- experiment_id: `41dea3b0-02fe-46d8-951d-e2778af01e9f`
- universe: `sp500_current`
- baseline_run_id: `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`
- alternate_run_id: `39208f19-8d0e-4c35-9950-78963bb59a97`

### Executed specs

- `baseline_production_equivalent` — run `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`
- `alternate_prior_completed_run` — run `39208f19-8d0e-4c35-9950-78963bb59a97`
- `lag_calendar_signal_bound` — run `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`

### Summary counts (raw)

- baseline: `{'still_join_key_mismatch': 8}`
- alternate_prior_run: `{'still_join_key_mismatch': 8}`
- lag: `{'still_join_key_mismatch': 8}`

### Standard rollup (four buckets)

- `{'baseline': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}, 'lag_signal_bound': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}, 'alternate_prior_run': {'still_join_key_mismatch': 8, 'reclassified_to_joined': 0, 'reclassified_to_other_exclusion': 0, 'invalid_due_to_leakage_or_non_pit': 0}}`

## Leakage audit

- passed: `True`
- violations: 0

## Adversarial review

- phase38_resolution_status: `deferred_with_evidence_reinforces_baseline_mismatch`
- leakage_audit_passed: `True`
- evidence: DB-bound replay preserves join_key_mismatch for fixture under baseline and lag; alternate did not yield joined outcomes for this fixture.

## Promotion gate v1

- gate_status: `blocked`
- blocking_reasons: `['hypothesis_under_test_not_eligible_for_product_promotion', 'adversarial_challenge_not_cleared']`

## Casebook

- `{'case_id_updated': 'case_pit_no_sc_join_key_mismatch_8', 'fields_added': ['residual_join_bucket', 'phase38_pit_experiment_id', 'phase38_baseline_summary', 'phase38_lag_summary', 'phase38_alternate_summary', 'phase38_leakage_audit_passed', 'better_understood', 'phase38_narrative']}`

## Explanation surface

- `/Users/hyunminkim/GenAIProacTrade/docs/operator_closeout/phase38_explanation_surface.md`

## Phase 39 recommendation

- **`broaden_hypothesis_families_and_harden_explanation_under_persistent_mismatch`**
- Fixture remains join_key_mismatch under executed specs; expand research hypotheses beyond this single seam and strengthen user-facing explanation of persistent PIT boundaries.
