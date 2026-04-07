# Public repair escalation brief (Phase 21)

- **Series**: `02119b7d-504e-4ad1-80d2-bb7fe5d94fb1`
- **Program**: `45ec4d1a-fd77-4254-9390-462da04d1d11`
- **Universe**: `sp500_current`
- **Compatibility**: policy `1` (expected `1`), status `active`

## Final recommendation (recomputed, infra-quarantine default)

`hold_and_repeat_public_repair`

## Included runs

```json
{
  "repair_campaign_run_ids_in_order": [
    "7ae92cef-d138-407c-a1cc-534f3bff07a0",
    "035a3ca4-0734-4c36-88b8-48437ddcd342"
  ],
  "included_run_count": 2
}
```

## Excluded runs (audit)

```json
[]
```

## Trend deltas vs prior persisted decision

```json
{
  "included_run_count_delta": null,
  "n_iterations_delta": 1.0
}
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
  "rule": "mixed_or_inconclusive",
  "n_iterations_used": 2,
  "included_run_count": 2,
  "joined_delta_first_last": 0,
  "thin_latest": 1.0,
  "premium_share_latest": 0.0,
  "infra_quarantine_applied_default": true
}
```

## Latest persisted recommendation (DB row)

`hold_and_repeat_public_repair`

hold_and_repeat_public_repair: mixed_or_inconclusive
