# Public depth series brief (Phase 22)

- **Series**: `eda6a9b1-18f9-4490-8649-db54066bbb7b`
- **Members (total)**: 1
- **Included in plateau (default quarantine)**: 1
- **Current escalation**: `hold_and_repeat_public_repair`
- **Public-depth operator signal**: `repeat_targeted_public_repair`

## Improvement classifications (public-depth members, chronological)

```json
[
  "no_material_progress"
]
```

## Classification counts

```json
{
  "no_material_progress": 1
}
```

## Persisted escalation branch counts (history)

```json
{
  "hold_and_repeat_public_repair": 1
}
```

## Excluded runs (audit)

```json
[]
```

## Latest dominant exclusions (after snapshot)

```json
[
  "no_validation_panel_for_symbol",
  "missing_excess_return_1q",
  "no_state_change_join"
]
```

## Signal rationale

```json
{
  "escalation_recommendation": "hold_and_repeat_public_repair",
  "latest_improvement_classification": "no_material_progress",
  "rule": "default_hold_maps_to_targeted_repair_cycle"
}
```


---

# Public repair escalation brief (Phase 21)

- **Series**: `eda6a9b1-18f9-4490-8649-db54066bbb7b`
- **Program**: `45ec4d1a-fd77-4254-9390-462da04d1d11`
- **Universe**: `sp500_current`
- **Compatibility**: policy `1` (expected `1`), status `active`

## Final recommendation (recomputed, infra-quarantine default)

`hold_and_repeat_public_repair`

## Included runs

```json
{
  "repair_campaign_run_ids_in_order": [
    ""
  ],
  "public_depth_run_ids_in_order": [
    "d7dc52a8-1762-4ad5-859a-4d2f6a91dc47"
  ],
  "member_kinds_in_order": [
    "public_depth"
  ],
  "included_run_count": 1
}
```

## Excluded runs (audit)

```json
[]
```

## Trend deltas vs prior persisted decision

```json
{}
```

## Counterfactual summary

```json
{
  "if_more_iterations": "Collect more completed repair campaigns before premium escalation.",
  "if_substrate_jumps": "Would favor continue_public_depth.",
  "if_premium_share_drops": "Would reduce pressure toward open_targeted_premium_discovery."
}
```

## Premium discovery gate checklist

```json
{
  "recommendation_matches_open_premium": false,
  "rule": "insufficient_iterations",
  "n_iterations_used": 1,
  "included_run_count": 1,
  "joined_delta_first_last": null,
  "thin_latest": 1.0,
  "premium_share_latest": null,
  "infra_quarantine_applied_default": true
}
```

## Latest persisted recommendation (DB row)

`hold_and_repeat_public_repair`

hold_and_repeat_public_repair: insufficient_iterations
