# Phase 36 패치 보고 — Substrate freeze + metadata reconciliation + residual join

## 목적

Phase 35 이후 **신규 joined 23행의 `missing_market_metadata` 플래그**·**잔여 `no_state_change_join`**을 좁게 분류·수리하고, **`substrate_freeze_recommendation`**(셋 중 하나)과 **연구 엔진 handoff brief**를 남긴다. 광역 filing·forward·GIS·임계 완화·스코어 변경은 비목표.

## 모듈·CLI

| 구역 | 내용 |
|------|------|
| `phase36.joined_metadata_reconciliation` | `report/export-joined-metadata-flag-reconciliation-targets`, `run-joined-metadata-reconciliation-repair`(**2패스**), `run-joined-metadata-reconciliation-repair-two-pass`(별칭) |
| `phase36.residual_state_change_join` | `report/export-residual-state-change-join-gaps`, `run-residual-state-change-join-repair` |
| `phase36.residual_pit_deferral` | `join_key_mismatch` 등 잔여 SC를 PIT/연구 defer 요약으로만 집계(광역 SC 없음) |
| `phase36.substrate_freeze_readiness` | `report-substrate-freeze-readiness` |
| `phase36.research_handoff_brief` | `export-research-engine-handoff-brief` |
| `phase36.orchestrator` | `run-phase36-substrate-freeze-and-research-handoff`, **`run-phase36-1-complete-narrow-integrity-round`** |
| `phase36.review` | Phase 36 / **Phase 36.1** 클로즈아웃 MD·JSON |
| `main.py` | 위 서브커맨드 + `write-phase36-1-complete-narrow-integrity-round-review` |

## 산출물

- `docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_review.md`
- `docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_bundle.json`
- **Phase 36.1 (narrow integrity)**: `docs/operator_closeout/phase36_1_complete_narrow_integrity_round_review.md`, `docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json`

## 재현

### Phase 36 (초차 오케스트레이션)

```bash
export PYTHONPATH=src
python3 src/main.py run-phase36-substrate-freeze-and-research-handoff \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase35-bundle-in docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json \
  --bundle-out docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_bundle.json \
  --out-md docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_review.md
```

### Phase 36.1 — 2패스 메타 + PIT defer + freeze 재평가

```bash
export PYTHONPATH=src
python3 src/main.py run-phase36-1-complete-narrow-integrity-round \
  --universe sp500_current \
  --panel-limit 8000 \
  --phase35-bundle-in docs/operator_closeout/phase35_join_displacement_and_maturity_bundle.json \
  --bundle-out docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json \
  --out-md docs/operator_closeout/phase36_1_complete_narrow_integrity_round_review.md
```

메타 수리만 단독으로 돌릴 때는 `run-joined-metadata-reconciliation-repair-two-pass`(또는 `run-joined-metadata-reconciliation-repair`)를 사용한다. **동일 호출**이 `report_before` → 수화 → `report_mid` → stale 대상 validation rebuild → `report_after` 순서를 수행한다.

## 테스트

`pytest src/tests/test_phase36_substrate_freeze.py -q`

## 실측 (sp500_current)

### Phase 36.1 — 권위 클로즈아웃 (2026-04-10, ~06:50 UTC)

- **증거**: `docs/phase36_evidence.md`, `docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json`, review UTC `2026-04-10T06:50:18.520557+00:00`.
- **기판 델타**: `joined_recipe_substrate_row_count` **266→266**, **`joined_market_metadata_flagged_count` 23→0**, `no_state_change_join` **8→8**.
- **2패스 메타**: `report_before`·`report_mid`에서 **`stale_metadata_flag_after_join` 23**; **`hydration.skipped: true`**; **`validation_rebuild`** **`completed`**, **`rows_upserted` 23**, **`failures` 0**; **`metadata_flags_cleared_now_count` 23**, **`metadata_flags_still_present_count` 0**.
- **잔여 SC**: 8행 전부 **`state_change_built_but_join_key_mismatch`** — `residual_pit_deferral`·handoff `pit_lab_no_state_change_deferral`만, 광역 SC 없음.
- **GIS / maturity**: 샘플 unmapped **13**, `maturity_deferred_symbol_count` **7** (번들 `closeout_summary`·`gis_deterministic_inspect` 정합).
- **Freeze**: **`freeze_public_core_and_shift_to_research_engine`**.
- **Phase 37**: **`execute_research_engine_backlog_sprint`**.

### Phase 36 초차 — 역사적 (2026-04-10, ~04:33 UTC)

- **번들**: `docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_bundle.json` (review UTC `2026-04-10T04:33:00.479414+00:00`).
- **한계**: 메타 수화 **23/23** 성공 후에도 **사전 분류가 전부 `true_missing`**이어서 **동일 런에서 `validation_rebuild` 스킵** → 헤드라인 **`joined_market_metadata_flagged` 23 유지** → freeze **`one_more_narrow_integrity_round_then_freeze`**.

### 구현 메모 (간극 → 해소)

- **이전**: 단일 패스에서 수화 후 `stale` 재분류가 `report_after`에만 반영되어 **같은 런에서 validation rebuild가 스킵**될 수 있음.
- **현재**: `run_joined_metadata_reconciliation_repair` / `_two_pass`가 **한 번의 진입점**에서 **mid 리포트 후 stale 행만 재빌드**하고 **report_after**까지 수행. `run-phase36-1-complete-narrow-integrity-round`는 이 2패스 메타를 오케스트레이션에 포함하고, **`state_change_built_but_join_key_mismatch` 8행은 광역 SC 없이** `residual_pit_deferral`로 번들·handoff에 명시한다.
