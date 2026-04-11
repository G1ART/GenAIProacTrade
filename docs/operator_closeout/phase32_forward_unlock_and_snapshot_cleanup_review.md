# Phase 32 — Forward-return unlock (Phase 31 touched) + snapshot cleanup

_Generated (UTC): `2026-04-08T20:59:45.039217+00:00`_

## 운영 감사 요약 (post-run)

- **`missing_excess_return_1q` 91→101**은 “악화”와 동일시하기 어렵다. 이번 런에서 **검증 미보유 심볼 161→151**, **분기 스냅·팩터 갭 158→148**, **`silver_present_snapshot_materialization_missing` 10→0**으로 **상류·검증 기판이 넓어졌고**, 그 결과 excess 공백이 있는 **패널 행 수**가 더 잡힐 수 있다.
- **Forward**: Phase 31 터치 30 CIK에 대해 **`repaired_to_forward_present` 23**; 잔여 9건은 샘플 기준 **`insufficient_price_history`**(최근 시그널일 대비 은 가격 창).
- **Joined 243 유지**: `no_state_change_join` 등 다른 제외가 그대로면 recipe 조인 헤드라인은 안 올라간다.
- **Raw 재시도**: 7건 복구, 3건은 API 500/HTML 응답류 **지속 외부 실패** — 스키마 이슈 아님.
- 상세 표·재현·다음 판단: `docs/phase32_evidence.md`.

## 핵심 지표 (Before → After)

| 지표 | Before | After |
| --- | --- | --- |
| joined_recipe_substrate_row_count | `243` | `243` |
| thin_input_share | `1` | `1` |
| missing_excess_return_1q | `91` | `101` |
| missing_validation_symbol_count | `161` | `151` |
| missing_quarter_snapshot_for_cik | `158` | `148` |
| factor_panel_missing_for_resolved_cik | `158` | `148` |

## 분기 스냅샷 분류 (Before → After)

- `no_filing_index_for_cik`: `147` → `147`
- `raw_present_no_silver_facts`: `1` → `1`
- `silver_present_snapshot_materialization_missing`: `10` → `0`

## 단계 전이 (워크오더 E — 이름 혼동 금지)

- phase31_validation_unblocked_cik_count (번들 근거): `30`
- **forward_return_unlocked_now_count**: `23`
- **quarter_snapshot_materialized_now_count**: `10`
- factor_materialized_now_count (스냅샷 수리 후 cascade): `10`
- validation_panel_refreshed_count (동일 cascade): `10`
- downstream_cascade_cik_runs_after_snapshot_repair: `10`
- gis_seam_actions_count: `1`
- raw_facts_recovered_on_retry_count: `7`

## B. Forward 백필 (Phase 31 터치 상한)

- repaired_to_forward_present: `23`
- deferred_market_data_gap (error 샘플 기준): `9`
- blocked_registry_or_time_window_issue: `0`
- panels_built: `30`

## C. Silver→스냅샷 물질화 누락 수리

- snapshot_materialized_now_count: `10`

## D. GIS-like raw→silver

- actions: `1`

## Deferred raw facts 재시도

- recovered_on_retry: `7`
- persistent_external_failure: `3`
- persistent_schema_or_mapping_issue: `0`

## Phase 33 recommendation

- `continue_bounded_forward_return_and_price_coverage`
- forward/조인 기판이 움직였거나 excess 갭이 줄었음 — 동일 상한으로 forward·가격 창 백필 반복.
