# Substrate closure review (Phase 25)

- 생성 시각(UTC): `2026-04-07T21:09:38.945626+00:00`
- 유니버스: `sp500_current`
- 프로그램 ID(게이트): `45ec4d1a-fd77-4254-9390-462da04d1d11`

## Thin-input & joined substrate

| 지표 | 이전 | 이후 |
|------|------|------|
| thin_input_share | 1 | 1 |
| joined_recipe_substrate_row_count | 243 | 243 |

## Coverage (issuer-level counts)

| 지표 | 이전 | 이후 |
|------|------|------|
| n_issuer_with_validation_panel_symbol | 312 | 312 |
| n_issuer_with_next_quarter_excess | 251 | 251 |
| n_issuer_with_state_change_cik | 312 | 312 |

## Dominant exclusions (before)

- `no_validation_panel_for_symbol`: 191
- `missing_excess_return_1q`: 61
- `no_state_change_join`: 8

## Dominant exclusions (after)

- `no_validation_panel_for_symbol`: 191
- `missing_excess_return_1q`: 61
- `no_state_change_join`: 8

## Phase 24-style trio (row counts)

| 제외 사유 | 이전 | 이후 | Δ |
|-----------|------|------|---|
| no_validation_panel_for_symbol | 191 | 191 | +0 |
| missing_excess_return_1q | 61 | 61 | +0 |
| no_state_change_join | 8 | 8 | +0 |

## Rerun gates (Phase 15 / 16)

### Before

- recommend_rerun_phase15: `False`
- recommend_rerun_phase16: `False`

### After

- recommend_rerun_phase15: `False`
- recommend_rerun_phase16: `False`

### Blockers (after, if still false)

- Phase 15: joined 또는 thin_input_share 조건 미충족 (joined=243, thin=1.0, thresholds={'joined_phase15': 120, 'joined_phase16': 144, 'thin_share_max_phase15': 0.55, 'thin_share_max_phase16': 0.45}).
- Phase 16: joined 또는 thin_input_share 조건 미충족(Phase 15보다 엄격).

## Tradeoffs & silent degradation

수리로 한 지표가 개선되고 다른 제외 건수가 늘면 별도 repair JSON의 `tradeoffs.silent_degradation` 필드를 확인한다.

## Production scoring boundary

프로덕션 스코어링 경로는 변경하지 않음; 기판 수리는 연구/공개 파이프라인에만 적용.

## Premium review

프리미엄 자동 오픈 없음; 프리미엄 디스커버리/리뷰는 운영자 명시 승인 전까지 차단 유지.

## Phase 26 권고

joined/thin 게이트가 아직 열리지 않았다면 **공개 기판 수리 스프린트를 한 사이클 더** 진행한다.
