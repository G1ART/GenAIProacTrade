# Public-first empirical review (Phase 24)

- **Generated (UTC)**: `2026-04-07T17:04:00.111369+00:00`

## Branch census (aggregated)

- **Series included**: 1
- **Included runs (sum, quarantine default)**: 2
- **Excluded infra failures (sum)**: 0
- **Dominant persisted escalation branch (raw counts)**: `hold_and_repeat_public_repair`

```json
{
  "hold_and_repeat_public_repair": 2
}
```

## Depth operator signal counts (per series snapshot)

```json
{
  "repeat_targeted_public_repair": 1
}
```

## Improvement classifications (aggregated / deduped)

```json
{
  "no_material_progress": 1
}
```

## Latest rerun readiness (program)

```json
{
  "ok": true,
  "program_id": "45ec4d1a-fd77-4254-9390-462da04d1d11",
  "universe_name": "sp500_current",
  "program_quality_context_hint": "thin_input",
  "substrate_snapshot": {
    "universe_name": "sp500_current",
    "as_of_date": "2026-04-05",
    "n_issuer_universe": 503,
    "state_change_run_id": "d911b273-1c8a-4bbe-b653-2c90b193f0c1",
    "panel_limit_used": 8000,
    "state_change_scores_limit_used": 50000,
    "thin_input_share": 1.0,
    "degraded_share": 0.0,
    "strong_share": 0.0,
    "usable_with_gaps_share": 0.0,
    "n_issuer_resolved_cik": 313,
    "n_issuer_with_factor_panel": 312,
    "n_issuer_with_state_change_cik": 312,
    "validation_panel_row_count": 312,
    "n_issuer_no_validation_panel_row": 191,
    "n_issuer_with_validation_panel_symbol": 312,
    "n_issuer_with_next_quarter_excess": 251,
    "validation_join_row_count": 251,
    "joined_recipe_substrate_row_count": 243,
    "dominant_exclusion_reasons": [
      {
        "reason": "no_validation_panel_for_symbol",
        "count": 191
      },
      {
        "reason": "missing_excess_return_1q",
        "count": 61
      },
      {
        "reason": "no_state_change_join",
        "count": 8
      }
    ]
  },
  "thresholds": {
    "joined_phase15": 120,
    "joined_phase16": 144,
    "thin_share_max_phase15": 0.55,
    "thin_share_max_phase16": 0.45
  },
  "recommend_rerun_phase15": false,
  "recommend_rerun_phase16": false,
  "notes": "Phase 15 권고: joined_recipe_substrate_row_count >= joined_phase15 이고 thin_input_share < thin_share_max_phase15. Phase 16은 joined·thin 바가 더 엄격함."
}
```

## Plateau review conclusion

- **Conclusion**: `mixed_or_insufficient_evidence`
- **Reason**: insufficient_depth_moves_or_mixed_classification_balance
- **Premium live integration**: False

## Exclusions (hygiene)

```json
[
  {
    "series_id": "02119b7d-504e-4ad1-80d2-bb7fe5d94fb1",
    "reason": "series_closed_excluded",
    "hint": "pass include_closed_series to include"
  }
]
```

## Recommended next command

다음 권장: `run-post-patch-closeout --universe sp500_current` 또는 `advance-public-first-cycle --universe sp500_current`.
