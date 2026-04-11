# Phase 32 evidence (실측 클로즈아웃)

## 실행 개요

- **명령**: `run-phase32-forward-unlock-and-snapshot-cleanup`
- **유니버스**: `sp500_current`
- **Phase 31 입력 번들**: `docs/operator_closeout/phase31_raw_facts_bridge_bundle.json`
- **근거 번들**: `docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json`
- **리뷰 MD 생성 시각(UTC)**: `2026-04-08T20:59:45.039217+00:00` (`phase32_forward_unlock_and_snapshot_cleanup_review.md` 상단)

## 번들 Before / After (기판 스냅샷)

| 항목 | Before | After |
|------|--------|-------|
| `joined_recipe_substrate_row_count` | 243 | 243 |
| `thin_input_share` | 1.0 | 1.0 |
| `missing_excess_return_1q` (exclusion_distribution) | 91 | 101 |
| `no_validation_panel_for_symbol` | 161 | 151 |
| `no_state_change_join` | 8 | 8 |
| `missing_validation_symbol_count` | 161 | 151 |
| `missing_quarter_snapshot_for_cik` | 158 | 148 |
| `factor_panel_missing_for_resolved_cik` | 158 | 148 |

## 분기 스냅샷 분류 (`quarter_snapshot_classification_counts`)

| 분류 | Before | After |
|------|--------|-------|
| `no_filing_index_for_cik` | 147 | 147 |
| `raw_present_no_silver_facts` | 1 | 1 |
| `silver_present_snapshot_materialization_missing` | 10 | 0 |

## Forward 갭 리포트 (Phase 31 터치)

- `phase31_touched_cik_count`: **30**
- 진단: 전원 `no_forward_row_next_quarter` / `build_not_attempted_or_no_forward_row`
- `missing_excess_return_1q_queue_size` (리포트 시점): **91**

## Forward 백필 (`forward_return_backfill_phase31_touched`)

| 항목 | 값 |
|------|-----|
| `panels_built` | 30 |
| `cik_accession_pairs` | 30 |
| `forward_build.success_operations` | 51 |
| `forward_build.failures` | 9 |
| `repaired_to_forward_present` | 23 |
| `deferred_market_data_gap` (error_sample 기준) | 9 |
| `blocked_registry_or_time_window_issue` | 0 |

`error_sample`에 등장한 실패는 주로 **`insufficient_price_history`** (예: MKC, NDSN, MU, MCK, NTAP, NWSA, MDT 등 — 최근 `signal_date` 대비 은 가격 시계열 부족).

## Silver / 스냅샷 수리

- `snapshot_materialized_now_count`: **10**
- 하류 cascade: `factor_materialized_now_count` / `validation_panel_refreshed_count` 각 **10** (번들 `stage_transitions`)

## GIS-like raw→silver

- `gis_seam_actions_count`: **1**
- 분류 `raw_present_no_silver_facts`: **1 → 1** (이번 런만으로는 GIS 분류 클리어 없음)

## Deferred raw facts 재시도 (`raw_facts_deferred_retry`)

| outcome | 건수 |
|---------|------|
| `recovered_on_retry` | 7 |
| `persistent_external_failure` | 3 |
| `persistent_schema_or_mapping_issue` | 0 |
| `rows_attempted` | 10 |

지속 외부 실패 3건은 번들 `per_row` 기준 **Supabase/JSON 500 + Cloudflare HTML** 응답 문자열이 포함됨(스키마·매핑 분류 아님).

## 단계 전이 (`stage_transitions`)

- `validation_unblocked_cik_count_in_phase31` (참조): **30**
- `forward_return_unlocked_now_count`: **23**
- `quarter_snapshot_materialized_now_count`: **10**
- `downstream_cascade_cik_runs_after_snapshot_repair`: **10**
- `factor_materialized_now_count`: **10**
- `validation_panel_refreshed_count`: **10**
- `gis_seam_actions_count`: **1**
- `raw_facts_recovered_on_retry_count`: **7**

## Phase 33 (번들 자동 권고)

- `phase33_recommendation`: `continue_bounded_forward_return_and_price_coverage`
- **주의**: 권고 로직은 `repaired_to_forward_present > 0` 등으로 **트리거**될 수 있어, 헤드라인 `missing_excess_return_1q` 증가와 문구가 어긋날 수 있다. 해석은 본 evidence 표·`HANDOFF` Phase 32.1 감사 요약을 우선한다.

## 재현 명령

```bash
cd /path/to/GenAIProacTrade
export PYTHONPATH=src
python3 src/main.py run-phase32-forward-unlock-and-snapshot-cleanup \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase31-bundle-in docs/operator_closeout/phase31_raw_facts_bridge_bundle.json \
  --bundle-out docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json \
  --out-md docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_review.md
```

## 로컬 테스트

```bash
pytest src/tests/test_phase32_forward_unlock_and_snapshot_cleanup.py -q
```

## 관련 문서

| 파일 | 용도 |
|------|------|
| `docs/phase32_patch_report.md` | 코드·모듈 변경 요약 |
| `HANDOFF.md` (Phase 32) | 운영 핸드오프·한 줄 판단 |
| `docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_review.md` | 표·감사 요약 (생성물) |
