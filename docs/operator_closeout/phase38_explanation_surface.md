# Research explanation — after DB-bound PIT (`hyp_pit_join_key_mismatch_as_of_boundary_v1`)

**Experiment id:** `41dea3b0-02fe-46d8-951d-e2778af01e9f`

## What was actually tested

- **Fixture:** 8 residual `state_change_built_but_join_key_mismatch` rows (Phase 37 fixture, loaded from persisted artifact / code).
- **Database:** `issuer_state_change_scores` for resolved `state_change_runs.id` per spec.

### Specs executed

- **`baseline_production_equivalent`**: Same pick rule as Phase 36 residual audit: bisect_right on as_of grid vs signal date.
- **`alternate_prior_completed_run`**: Second-most-recent completed run for universe (if distinct from baseline); same pick rule — tests whether an older score grid changes join classification.
- **`lag_calendar_signal_bound`**: Baseline run scores; evaluation uses signal + N calendar days as upper bound for as_of (simulates later join decision without using post-signal price data).

## Row-level outcomes (headline)

- **Baseline counts:** `{'still_join_key_mismatch': 8}`
- **Alternate prior run:** `{'still_join_key_mismatch': 8}`
- **Lag signal bound:** `{'still_join_key_mismatch': 8}`

### Standard rollup (baseline / lag; excludes `alternate_spec_not_executed`)

- `{"baseline": {"still_join_key_mismatch": 8, "reclassified_to_joined": 0, "reclassified_to_other_exclusion": 0, "invalid_due_to_leakage_or_non_pit": 0}, "lag_signal_bound": {"still_join_key_mismatch": 8, "reclassified_to_joined": 0, "reclassified_to_other_exclusion": 0, "invalid_due_to_leakage_or_non_pit": 0}, "alternate_prior_run": {"still_join_key_mismatch": 8, "reclassified_to_joined": 0, "reclassified_to_other_exclusion": 0, "invalid_due_to_leakage_or_non_pit": 0}}`

## Leakage audit

- **Passed:** `True`
- **Violations:** 0
- **Rule:** every picked row must satisfy `as_of_date <= signal_bound` for that spec.

## Adversarial review (evidence-backed)

- **Status:** `deferred_with_evidence_reinforces_baseline_mismatch`
- **Leakage audit passed:** `True`
- **Summary:** DB-bound replay preserves join_key_mismatch for fixture under baseline and lag; alternate did not yield joined outcomes for this fixture.

## Promotion gate

- **Gate status:** `blocked`
- **Blocking reasons:** ['hypothesis_under_test_not_eligible_for_product_promotion', 'adversarial_challenge_not_cleared']

## What remains uncertain
- Under baseline production-equivalent pick, **earliest score as_of remains after signal** for some rows — economic interpretation of the filing signal vs score grid lag is still an open research question.

## Why this is not a buy/sell recommendation

- No return forecast, position sizing, or price target appears here.
- **Promotion gate is blocked/deferred**; this document is audit and judgment support only.
