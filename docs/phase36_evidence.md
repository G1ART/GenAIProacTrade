# Phase 36 evidence (measured closeout)

## 한줄 해석 (권위: Phase 36.1)

`run-phase36-1-complete-narrow-integrity-round` (`sp500_current`)에서 **2패스 메타 정합**이 완료되었다. Phase 35 신규 joined **23**행은 **report_before·report_mid**에서 모두 **`stale_metadata_flag_after_join`**(패널 `panel_json` 스테일 플래그)였다. **`hydration`은 `skipped: true`**로 기록되어, 이번 런의 결정적 액션은 **수화가 아니라 검증 패널 재빌드**였다. **`validation_rebuild_target_count_after_hydration` 23**에 대해 재빌드가 **`completed`**, **`rows_upserted` 23**, **`failures` 0**. 헤드라인 **`joined_market_metadata_flagged_count`는 23 → 0** (`bundle.before` / `bundle.after`).

잔여 **`no_state_change_join` 8**은 변동 없이 전부 **`state_change_built_but_join_key_mismatch`** — **`residual_pit_deferral`**·handoff brief의 **`pit_lab_no_state_change_deferral`**에만 고정, 광역 `run_state_change` 없음.

**Freeze**: **`freeze_public_core_and_shift_to_research_engine`**. **Phase 37**: **`execute_research_engine_backlog_sprint`**.

## Run (Phase 36.1 — 권위)

- Command: `run-phase36-1-complete-narrow-integrity-round`
- Universe: `sp500_current`
- Phase 35 bundle in: `docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json`
- Output bundle: `docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json`
- Review MD generated (UTC): `2026-04-10T06:50:18.520557+00:00`
- Handoff brief generated (UTC): `2026-04-10T06:50:18.515921+00:00` (`research_engine_handoff_brief.generated_utc`)

## Headline substrate (before → after, Phase 36.1 스냅샷)

| Field | Before | After |
|-------|--------|-------|
| joined_recipe_substrate_row_count | 266 | 266 |
| joined_market_metadata_flagged_count | 23 | 0 |
| thin_input_share | 1.0 | 1.0 |
| missing_excess_return_1q | 78 | 78 |
| no_state_change_join | 8 | 8 |
| missing_validation_symbol_count | 151 | 151 |
| missing_quarter_snapshot_for_cik | 148 | 148 |
| factor_panel_missing_for_resolved_cik | 148 | 148 |

## Two-pass metadata reconciliation (번들 `joined_metadata_reconciliation_two_pass`)

| 단계 | 요약 |
|------|------|
| `report_before` | `stale_metadata_flag_after_join` **23** |
| `hydration` | **`skipped: true`** |
| `report_mid` | `stale_metadata_flag_after_join` **23** |
| 재빌드 대상 | **`validation_rebuild_target_count_after_hydration` 23** |
| `validation_rebuild` | `status` **completed**, **`rows_upserted` 23**, **`failures` 0** |
| `report_after` (타깃 집합) | `metadata_flagged_in_target_set_count` **0**; 버킷 **`other_join_metadata_seam` 23** |
| 집계 | **`metadata_flags_cleared_now_count` 23**, **`metadata_flags_still_present_count` 0**, **`targets_flagged_before` 23** |

`closeout_summary`의 버킷 스냅: **before/mid** `stale_metadata_flag_after_join` 23 → **after** `other_join_metadata_seam` 23 (헤드라인 플래그 카운트는 0).

## Residual `no_state_change_join` (8행, PIT defer)

- `state_change_run_id`: `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`
- `state_change_scores_loaded`: 353
- **버킷**: `state_change_built_but_join_key_mismatch` **8**
- **정책**: `no_broad_state_change_rerun` (`residual_pit_deferral.policy`)

| symbol | signal_available_date | first_state_change_as_of_in_run |
|--------|------------------------|--------------------------------|
| BBY | 2025-12-08 | 2026-09-28 |
| ADSK | 2025-11-27 | 2026-09-28 |
| CRM | 2025-12-04 | 2026-09-28 |
| CRWD | 2025-12-03 | 2026-09-28 |
| DELL | 2025-12-10 | 2026-09-28 |
| DUK | 2025-11-10 | 2026-03-28 |
| NVDA | 2025-11-20 | 2026-09-28 |
| WMT | 2025-12-04 | 2026-09-28 |

## GIS (narrow)

- outcome: `blocked_unmapped_concepts_remain_in_sample`
- `unmapped_count`: 13 (샘플 concept)

## Maturity

- `maturity_deferred_symbol_count`: 7

## Substrate freeze + Phase 37 (Phase 36.1 재평가)

- `substrate_freeze_recommendation`: **`freeze_public_core_and_shift_to_research_engine`**
- `rationale` (번들): `headline_joined_stable_registry_tail_treated_as_low_roi_deferred; residual_no_sc_rows_8_non_repairable_buckets_only_defer_pit_lab; shift_primary_build_energy_to_research_engine_and_user_facing_layer`
- `phase37_recommendation`: **`execute_research_engine_backlog_sprint`**

---

## Historical — Phase 36 초차 (동일 일자, 시퀀싱 갭 이전)

아래는 **`run-phase36-substrate-freeze-and-research-handoff`** 단일 패스 한계가 드러난 **초차** 실측이다. 메타 수화는 성공했으나 **같은 런에서 stale 전용 재빌드가 스킵**되어 헤드라인 플래그 **23이 유지**되었고, freeze 권고는 **`one_more_narrow_integrity_round_then_freeze`**였다. 이 갭은 **Phase 36.1 2패스**로 해소되었다.

- Output bundle: `docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_bundle.json`
- Review MD generated (UTC): `2026-04-10T04:33:00.479414+00:00`

### 초차 — Phase 35 신규 joined 23 (요약)

- 사전 `reconciliation_bucket_counts`: **`true_missing_market_metadata` 23**
- 수화: Yahoo chart **`rows_upserted` 23**, `rows_missing_after_requery` 0
- **`validation_rebuild`**: **skipped** (사전에 stale 큐 없음)
- 사후: **`stale_metadata_flag_after_join` 23**, **`metadata_flags_cleared_now_count` 0**

## Reproduce (Phase 36.1)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase36-1-complete-narrow-integrity-round \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase35-bundle-in docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json \
  --bundle-out docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json \
  --out-md docs/operator_closeout/phase36_1_complete_narrow_integrity_round_review.md
```

## Reproduce (Phase 36 초차, 역사적)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase36-substrate-freeze-and-research-handoff \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase35-bundle-in docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json \
  --bundle-out docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_bundle.json \
  --out-md docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_review.md
```

## Related

- docs/phase36_patch_report.md
- HANDOFF.md (상단 요약, Phase 36·37 절)
- docs/phase35_evidence.md
- docs/operator_closeout/phase36_1_complete_narrow_integrity_round_review.md
- docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_review.md (초차)

## Tests

```bash
pytest src/tests/test_phase36_substrate_freeze.py -q
```
