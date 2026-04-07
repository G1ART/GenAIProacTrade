# Public repair campaign decision brief

- **Run**: `72314715-df43-4405-8c85-d7e9b76d9964`
- **Program**: `45ec4d1a-fd77-4254-9390-462da04d1d11`
- **Universe**: `sp500_current`

## Final decision

`repair_insufficient_repeat_buildout`

## Reruns

- reran_phase15: False
- reran_phase16: False

## Survival (before → after)

- before: `{'weak_survival': 3}`
- after: `{'weak_survival': 3}`

## Campaign recommendation

- before: `public_data_depth_first`
- after: `None`

## Interpretation

```json
{
  "survival_compare": {
    "after": {
      "survives": 0,
      "weak_survival": 3,
      "archive_failed": 0,
      "demote_to_sandbox": 0
    },
    "before": {
      "survives": 0,
      "weak_survival": 3,
      "archive_failed": 0,
      "demote_to_sandbox": 0
    },
    "deltas": {
      "survives": 0,
      "weak_survival": 0,
      "archive_failed": 0,
      "demote_to_sandbox": 0
    },
    "outcome_improved_heuristic": false
  },
  "recommendation_after": null,
  "recommendation_before": "public_data_depth_first",
  "recommendation_changed": true,
  "after_campaign_failure_totals": {
    "premium_share": 0.0,
    "total_failure_cases": 0,
    "premium_signal_cases": 0,
    "n_contradictory_failure_cases": 0
  }
}
```
