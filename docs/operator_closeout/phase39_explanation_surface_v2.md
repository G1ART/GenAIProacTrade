# Research explanation (Phase 39 v2)

_This document supports human judgment. It is **not** a buy, sell, or hold recommendation and does not constitute investment advice._

## What Phase 38 showed (ground truth)

- PIT loop ok: `True`
- Leakage audit passed: `True`
- Fixture rows: `True` still `join_key_mismatch` under baseline, alternate prior run, and lag signal bound.
- Adversarial (lineage): `deferred_with_evidence_reinforces_baseline_mismatch`
- Experiment id: `41dea3b0-02fe-46d8-951d-e2778af01e9f`

## Competing hypotheses (same 8-row fixture)

### `hyp_pit_join_key_mismatch_as_of_boundary_v1`
- **Status**: `challenged`
- **Thesis**: For a subset of joined recipe rows, state_change scores exist but the earliest as_of in the referenced run is after the signal_available_date; joins fail under current PIT keys while economic content may still be coherent under alternate as-of or lag conventions.
- **Latest transition**: under_test → challenged (Phase 39: Phase 38 PIT kept join_key_mismatch for 8 rows under baseline, alternate, lag; leakage passed; single-family t)

### `hyp_score_publication_cadence_run_grid_lag_v1`
- **Status**: `draft`
- **Thesis**: Issuer economics may be knowable on the signal calendar, but the score run as_of grid reflects a coarser publication or batch cadence; mismatch is timing of score availability, not thesis failure.

### `hyp_signal_availability_filing_boundary_v1`
- **Status**: `draft`
- **Thesis**: The pipeline signal_available_date may align to an internal recipe date while filers public availability differs; strict bisect_right against score as_of then correctly excludes under production rules.

### `hyp_issuer_sector_reporting_cadence_v1`
- **Status**: `draft`
- **Thesis**: Certain sectors cluster fiscal period ends and restatement windows; the eight symbols may share patterns where score as-of grids systematically trail economically relevant signal timing.

### `hyp_governance_safe_alternate_join_policy_v1`
- **Status**: `draft`
- **Thesis**: Production uses one pick rule; research may define additional rules that remain PIT-safe and documented; some mismatches are policy choice, not data error.

## Tested vs not tested

| Hypothesis | Tested in Phase 38 PIT? | Notes |
|------------|-------------------------|-------|
| `hyp_pit_join_key_mismatch_as_of_boundary_v1` | Yes (baseline / alternate run / lag) | Outcome unchanged for all 8 rows. |
| `hyp_score_publication_cadence_run_grid_lag_v1` | No | Planned specs in family contract only. |
| `hyp_signal_availability_filing_boundary_v1` | No | Planned specs in family contract only. |
| `hyp_issuer_sector_reporting_cadence_v1` | No | Planned stratified replay only. |
| `hyp_governance_safe_alternate_join_policy_v1` | Partially (lag is governance-style bound) | Still mismatch; further governed policies not yet encoded. |

## Unresolved

- Why the eight rows remain `join_key_mismatch` under executed specs is **documented** but **not** economically resolved.
- Multiple mechanisms (cadence, filing semantics, sector cadence, policy) remain **draft** families.
- Multi-stance adversarial reviews are **deferred**; promotion remains gated.

## PIT runner family contract (summary)

- Fixture class: `join_key_mismatch_8`
- Shared leakage rule reused: `True`
- Families defined: `5`

## Promotion gate (lifecycle-aware)
- **Gate status**: `deferred`
- **Primary block category**: `deferred_pending_more_hypothesis_coverage`
- **Lifecycle snapshot**: `{'hyp_pit_join_key_mismatch_as_of_boundary_v1': 'challenged', 'hyp_score_publication_cadence_run_grid_lag_v1': 'draft', 'hyp_signal_availability_filing_boundary_v1': 'draft', 'hyp_issuer_sector_reporting_cadence_v1': 'draft', 'hyp_governance_safe_alternate_join_policy_v1': 'draft'}`

## Phase 40 (recommended next)

- **`implement_pit_family_spec_bindings_and_rerun_db_runner_under_shared_leakage_audit`**
- Phase 39 defined four draft hypothesis families and a PIT runner contract; Phase 40 should implement at least one planned spec key per family (bounded to the same fixture), execute row-level comparisons under the shared schema, then refresh lifecycle and gate.
