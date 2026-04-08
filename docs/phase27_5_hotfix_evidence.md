# Phase 27.5 hotfix evidence (실측 클로즈아웃)

## 실행 개요

- **명령**: `write-phase27-targeted-backfill-review` (review-only 스냅샷)
- **실행 시각(UTC)**: `2026-04-07T23:33:55.986291+00:00` (리뷰 MD 상단)
- **유니버스**: `sp500_current`
- **프로그램 ID**: `45ec4d1a-fd77-4254-9390-462da04d1d11` (번들 `program_id`)

## 핫픽스 검증 포인트 (이번 번들 기준)

| 검증 항목 | 결과 | 비고 |
|-----------|------|------|
| `n_issuer_resolved_cik` 정상화 | **313** / 유니버스 503 | 핫픽스 전 `fetch_cik_map` 버그 시 ~5 수준 붕괴 가능성과 대비 **계측 정상** |
| `n_issuer_with_factor_panel` | **312** | CIK 맵과 정합 |
| `n_issuer_with_state_change_cik` | **312** | CIK 맵과 정합 |
| `rerun_readiness.recommend_rerun_phase15` | **false** (bool) | `None` 아님 — wiring 정상 |
| `rerun_readiness.recommend_rerun_phase16` | **false** (bool) | 동일 |
| `wiring_warnings` | **[]** | 침묵 실패 없음 |
| `registry_gap_rollup.registry_blocker_symbol_total` | **191** | issuer/factor/norm 등 전 버킷 반영 |
| `registry_repair_automation_eligible_count` | **2** | norm mismatch 등 |
| `registry_upstream_or_pipeline_deferred_count` | **189** | issuer 188 + factor 1 |
| `phase28.phase28_recommendation` | **`continue_targeted_backfill`** | 집계 기반 타깃 백필 지속 |

## 리뷰 MD와 일치하는 스냅샷

- `joined_recipe_substrate_row_count`: 243  
- `no_validation_panel_for_symbol`: 191  
- `missing_excess_return_1q`: 61 (`true_repairable_forward_gap_count`: 1, not_yet_matured: 60)  
- `no_state_change_join`: 8 (PIT: `no_pre_signal_state_change_asof` 8)  
- 메타데이터 플래그 조인 행: 243 (`missing_market_metadata_latest`: 243)  
- 레지스트리 버킷: `issuer_master_missing_for_resolved_cik` 188, `symbol_normalization_mismatch` 2, `factor_panel_missing_for_resolved_cik` 1  

## 산출물 경로

| 파일 | 역할 |
|------|------|
| `docs/operator_closeout/phase27_targeted_backfill_review.md` | 사람이 읽는 한 페이지 |
| `docs/operator_closeout/phase27_targeted_backfill_bundle.json` | 전체 번들(JSON) |

## 재현 명령

```bash
cd /path/to/GenAIProacTrade
PYTHONPATH=src python3 src/main.py write-phase27-targeted-backfill-review \
  --universe sp500_current --panel-limit 8000 --program-id latest \
  --out docs/operator_closeout/phase27_targeted_backfill_review.md \
  --bundle-out docs/operator_closeout/phase27_targeted_backfill_bundle.json
```

수리 실행까지 포함한 클로즈아웃:

```bash
PYTHONPATH=src python3 src/main.py run-targeted-backfill-repair-and-review \
  --universe sp500_current --panel-limit 8000 --program-id latest \
  --out docs/operator_closeout/phase27_targeted_backfill_review.md \
  --bundle-out docs/operator_closeout/phase27_targeted_backfill_bundle.json
```

## 로컬 테스트

```bash
pytest src/tests/test_phase27_targeted_backfill.py -q
pytest src/tests/test_phase27_5_hotfix.py -q
```

## Phase 28 판단

- 본 증거 기준: 계측은 신뢰 가능하고, 블로커가 남아 **`continue_targeted_backfill`** 가 타당.  
- Rerun 15/16은 **아직 열리지 않음** (joined는 임계를 넘으나 `thin_input_share=1.0`으로 게이트 미충족).  
- 추가 **corrective patch**는 당장 필수는 아님 — 다음은 **타깃 수리 실행·재집계**로 델타 확인.
