# Validation decision brief

- **Program**: Delayed recognition vs fast reflection of state-change signals (Q horizon)
- **Locked question**: Why do apparently similar deterministic state-change signals get reflected quickly for some issuers, while others experience delayed recognition, weak reflection, or misaligned market response over the next quarter?
- **Campaign run**: `f9106163-da85-416e-950b-c32d7be8911e`

## Recommendation

`public_data_depth_first`

public_data_depth_first: thin_or_degraded_failure_dominance_or_program_qc (validated=3, eligible=3)

## Survival distribution (campaign members)

- survives: 0
- weak_survival: 3
- demote_to_sandbox: 0
- archive_failed: 0

## Hypotheses included

- `8ffeefc1-625b-454c-a3bb-08e74937bcb7` → `weak_survival` (run `af5011c4-5933-4471-af74-806faa82f386`)
- `eaba687b-53b7-43cf-a2db-8f295ee30e7f` → `weak_survival` (run `c38e5c1c-0e2d-42db-8ea6-6daf415eea8e`)
- `aad2f805-18a8-42ce-9b11-00f8e3bab948` → `weak_survival` (run `ed1568ab-4a82-477a-b4b7-e718a2c02f4b`)

## Top failure rationales (fragility / survival)

- fragile_across_windows: 3

## Top premium-overlay hints (from failure cases)

- deeper_public_backfill_or_targeted_premium_later: 3

## What would change the call

- **snapshot**: {'n_validated': 3, 'weak_survival': 3, 'dominant_program_qc': 'thin_input'}
- **if_thin_input_resolved**: Re-run public-core cycle to lift quality_class; then repeat campaign.
- **if_eligible_below_threshold**: Re-run campaign after more hypotheses reach referee.
- **if_more_strong_usable_and_contradictions**: Could move toward targeted_premium_seam_first if contradictory_public_signal failure share rises in strong/usable substrate.
