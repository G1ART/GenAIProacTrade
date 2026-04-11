# Phase 36 — Substrate freeze + metadata reconciliation + residual join audit

> **역사적 스냅샷** — Phase 36 **초차** 오케스트레이션(`run-phase36-substrate-freeze-and-research-handoff`) 산출물이다. **권위 클로즈아웃·freeze 판정**은 **`phase36_1_complete_narrow_integrity_round_review.md`** 및 동명 번들(메타 플래그 23→0, `freeze_public_core_and_shift_to_research_engine`)을 따른다.

_Generated (UTC): `2026-04-10T04:33:00.479414+00:00`_

## Closeout summary

- joined_recipe_substrate_row_count: `266`
- joined_market_metadata_flagged_count: `23`
- thin_input_share: `1`
- missing_excess_return_1q: `78`
- missing_validation_symbol_count: `151`
- missing_quarter_snapshot_for_cik: `148`
- factor_panel_missing_for_resolved_cik: `148`
- no_state_change_join: `8`
- metadata_flags_cleared_now_count: `0`
- metadata_flags_still_present_count: `23`
- no_state_change_join_cleared_now_count: `0`
- residual_join_rows_still_blocked_count: `8`
- maturity_deferred_symbol_count: `7`
- GIS outcome: `blocked_unmapped_concepts_remain_in_sample`

## Substrate freeze

- substrate_freeze_recommendation: `one_more_narrow_integrity_round_then_freeze`
- rationale: headline_joined_stable_registry_tail_treated_as_low_roi_deferred; metadata_flags_still_23_or_repairable_residual_sc_0

## Phase 37 recommendation

- `complete_narrow_integrity_round_then_execute_research_handoff`
- Residual metadata or repairable state_change seams remain; finish bounded closure then export handoff.

## 실측 해석 (운영)

### 메타데이터 (Phase 35 신규 23행)

- **사전 분류**: 전부 `true_missing_market_metadata` — `no_market_metadata_row_or_empty_as_of`.
- **수화**: `yahoo_chart`, `rows_upserted` **23**, `rows_missing_after_requery` **0**.
- **검증 패널 재빌드**: 이번 런 **`skipped`** (`rows_upserted` 0) — 재빌드 큐는 **사전 `stale_metadata_flag_after_join` 행**만 포함하는데, 사전에는 stale이 0건이었음.
- **사후 재분류** (`report_after`): 전부 `stale_metadata_flag_after_join` — DB 메타는 채워졌으나 `panel_json`의 `missing_market_metadata` 플래그는 그대로.
- **다음 액션**: 동일 23키에 대해 `run_validation_panel_build_from_rows`(또는 Phase 29 스타일 스테일 플래그 재빌드) **한 패스**, 또는 오케스트레이터에서 수화 후 **재분류 → stale 재빌드** 연쇄.

### 잔여 state_change 조인 (8행)

- 전부 `state_change_built_but_join_key_mismatch` — 시그널일 ≤ PIT로 잡힌 최초 `as_of`보다 이른 케이스(번들에 `first_state_change_as_of_in_run` 참조).
- **`state_change_not_built_for_row` 0건** → `run_state_change` 자동 수리 **스킵** (의도된 정책).
- 심볼: BBY, ADSK, CRM, CRWD, DELL, DUK, NVDA, WMT — PIT 실험·런 경계 문서화용; 광역 SC 재실행 비목표.

### GIS·성숙

- GIS: 개념맵 샘플 **unmapped**로 차단 유지 (대규모 맵 캠페인 비목표).
- 미성숙 NQ **7심볼**: Phase 34/35와 동일하게 캘린더 지연으로 명시적 defer.

## 번들 교차 참조

- `joined_metadata_reconciliation_repair.hydration` / `validation_rebuild`
- `residual_state_change_join_repair` — `skipped` + `report_before.rows`
- `substrate_freeze_readiness.blocker_mix`
- `research_engine_handoff_brief` — 상위 레이어 아젠다 시드
- 상세 표·재현: **`docs/phase36_evidence.md`**
