# Thin-input root cause review (Phase 26)

- UTC: `2026-04-07T21:54:55.444379+00:00`
- Universe: `sp500_current`

## Why thin_input_share can stay 1.0

thin_input_share 은 public_core_cycle_quality_runs 의 quality_class 비율에서 온다. joined recipe 행 품질과는 별개 축이다.

### Cycle-quality drivers (public_core_cycle_quality_runs, thin_input only)

- Counts: `{'thin_insufficient_ge_075': 2}`
- Thin runs in lookback: 2

### Joined substrate row flags (recipe-joined panels)

- Joined rows: 243
- Driver counts: `{'joined_but_market_metadata_flagged': 243}`

## Phase 25 repair effectiveness (zero-delta audit)

### Validation panel repair

- Targets (panel rows): 0
- Likely no-op: `True`
- Current no_validation_panel rows: 191

### Forward backfill

- Targets: 61
- Likely no-op: `False`
- Current missing_excess rows: 61

### State-change engine

- Current no_state_change_join rows: 8
- Note: Phase 25 state 수리는 엔진 재실행만 수행; no_state_change_join 이 PIT 간극(시그널 이전 as_of 부재)이면 동일 메트릭이 유지될 수 있음.

## Quality threshold sensitivity (review-only)

```json
{
  "ok": true,
  "review_only": true,
  "no_automatic_threshold_mutation": true,
  "current_quality_class": "thin_input",
  "current_insufficient_data_fraction": 1.0,
  "scenarios": [
    {
      "label": "relax_thin_insufficient_to_085",
      "hypothetical_quality_class": "thin_input"
    },
    {
      "label": "relax_thin_insufficient_to_090",
      "hypothetical_quality_class": "thin_input"
    },
    {
      "label": "tighten_combo_gating_to_030",
      "hypothetical_quality_class": "thin_input"
    },
    {
      "label": "tighten_combo_insufficient_to_055",
      "hypothetical_quality_class": "thin_input"
    }
  ],
  "all_listed_scenarios_remain_thin_input": true,
  "note": "모든 나열 시나리오에서 여전히 thin_input → 정책 민감도가 낮고 후보 데이터 자체가 얇을 가능성.",
  "source_quality_run_id": "1724e913-f8a0-4a39-bb4f-191d2d2dc2e7"
}
```

## Primary blocker & Phase 27

- **Primary blocker category**: `data_absence`
- **Top exclusion lever**: `no_validation_panel_for_symbol`
- **Phase 27 recommendation**: `targeted_data_backfill_next`
- **Rationale**: 남은 블로커가 데이터/조인에 있고 좁은 백필이 레버리지가 될 수 있음.

## Another broad substrate sprint?

If all Phase 25 paths show `likely_no_op: true` and exclusions are unchanged, **another generic sprint is likely wasteful** until the bounded blocker set (exports) is addressed.

## Boundaries

thin_input_root_cause 는 진단·보내기만 수행; 프로덕션 스코어링 경로를 변경하지 않음.
- **Premium auto-open**: false (public-first default).
