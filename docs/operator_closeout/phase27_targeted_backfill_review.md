# Phase 27 targeted backfill review

- 생성 시각(UTC): `2026-04-07T22:35:03.662513+00:00`
- 유니버스: `sp500_current`

## 1) 검증 미스 중 레지스트리·별칭 이슈

레지스트리 버킷 카운트(미해결 검증 패널 심볼 기준):

- `issuer_master_missing_for_resolved_cik`: 188
- `factor_panel_missing_for_resolved_cik`: 3

## 2) 조인 행이 메타데이터에만 막힌 규모

- joined recipe 행 수: `243`
- `joined_but_market_metadata` 후보(플래그된 조인 행): `243`

### 메타데이터 갭 버킷

- `missing_market_metadata_latest`: 243

## 3) Forward 미해결 — 성숙 전 vs 오늘 수리 가능

- raw 미해결(`no_forward_row_next_quarter`): `61`
- **true_repairable_forward_gap_count**: `1`
- not_yet_matured_for_1q_horizon: `60`
- 달력 프록시(고정): `95` 일

## 4) State-change PIT — 역사 백필 vs 정렬

- PIT 미해결 행: `8`
- historical_backfill_might_help_count: `0`

### PIT 세분 버킷

- `no_pre_signal_state_change_asof`: 8

## 5) 핵심 지표(현재 스냅샷)

- thin_input_share: `1`
- no_validation_panel_for_symbol: `191`
- missing_excess_return_1q: `61`
- no_state_change_join: `8`

_수리 전후 델타는 운영자가 `run-validation-registry-repair` / `run-market-metadata-hydration-repair` 등 실행 후 동일 명령으로 재집계해 채운다._

## 6) Phase 28 권고(정확히 하나)

- **`continue_targeted_backfill`**
- 근거: 레지스트리·메타·forward·PIT 중 타깃 백필 후보가 남음.

### Rerun 게이트(참고)

- recommend_rerun_phase15: `None`
- recommend_rerun_phase16: `None`

## 경계

프로덕션 스코어링 경로는 변경하지 않음; Phase 27은 공개·연구 파이프라인 진단·좁은 수리만.

프리미엄 디스커버리 자동 오픈 없음; 본 패치는 premium 경계를 건드리지 않음.

