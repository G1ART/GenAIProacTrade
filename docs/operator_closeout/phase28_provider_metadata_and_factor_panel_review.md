# Phase 28 — Provider metadata & factor panel materialization

_Generated (UTC): `2026-04-08T01:34:10.123881+00:00`_

## 요약

- **메타데이터 수화**: `run_market_metadata_hydration_repair` 경로(Phase 27)를 오케스트레이션에 포함.
- **팩터·검증 패널**: 스냅샷 대비 factor 패널 누락 → `run_factor_panels_for_cik`, factor 대비 validation 누락 → `run_validation_panel_build_from_rows` (CIK당 상한).

## Before → After (기판·레지스트리)

| 항목 | Before | After |
| --- | --- | --- |
| joined_recipe_substrate_row_count | `243` | `243` |
| joined_market_metadata_flagged_count | `243` | `243` |
| thin_input_share | `1` | `1` |
| missing_validation_symbol_count | `191` | `191` |
| registry_blocker_symbol_total | `191` | `191` |

## 메타데이터 수화 (마지막 실행)

- status: `completed`
- provider: `yahoo_chart`
- provider_rows_returned: `243`
- rows_upserted: `243`
- rows_already_current: `0`
- rows_missing_after_requery: `0`
- blocked_reason: ``

## 팩터 물질화 수리

- factor_panel_repairs_attempted: `0`
- validation_panel_repairs_attempted: `0`

### materialization_bucket_counts (최종 스냅샷)

- `factor_panel_exists_but_validation_panel_missing`: `0`
- `missing_quarter_snapshot_for_cik`: `189`
- `snapshot_present_but_factor_panel_missing`: `0`
- `validation_panel_build_omission_for_existing_factor_panel`: `0`

## 프로바이더 메타 no-op 방지

`MARKET_DATA_PROVIDER=stub` 등으로 `provider_rows_returned=0`이면 수화는 **`blocked`** + `blocked_reason=provider_returned_zero_metadata_rows` 로 종료한다(완료 위장 금지).
Yahoo chart 프로바이더는 차트 구간으로 `avg_daily_volume`·`as_of_date` 등을 채운다.

