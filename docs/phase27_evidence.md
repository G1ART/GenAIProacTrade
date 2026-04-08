# Phase 27 evidence closeout (실행 기록)

- **Phase 27.5 hotfix 후** `write-phase27-targeted-backfill-review` / `run-targeted-backfill-repair-and-review`를 다시 실행해 `n_issuer_resolved_cik`·rerun bool·`registry_gap_rollup`·`wiring_warnings`를 확인할 것.
- **실행 시각(UTC)**: 2026-04-07 — 리뷰 MD 생성 타임스탬프 `2026-04-07T22:35:03.662513+00:00` (`phase27_targeted_backfill_review.md` 상단) — **핫픽스 전 계측은 참고용**
- **유니버스**: `sp500_current`

## 생성·갱신 산출물

| 산출물 | 경로 |
|--------|------|
| 타깃 백필 리뷰 MD | `docs/operator_closeout/phase27_targeted_backfill_review.md` |
| 증거 번들 JSON | `docs/operator_closeout/phase27_targeted_backfill_bundle.json` |

선택 재현 산출물(동일 Phase 27 CLI로 경로만 맞추면 됨):

| 산출물 | 명령 |
|--------|------|
| 레지스트리 갭 심볼 | `export-validation-registry-gap-symbols --out …` |
| 메타데이터 갭 행 | `export-market-metadata-gap-rows --out …` |
| Forward 성숙도 버킷 | `export-forward-gap-maturity-buckets --out …` |
| PIT 갭 행 | `export-state-change-pit-gap-rows --out …` |

## 실행에 사용한 명령 (재현)

**Review-only (집계·MD·번들만):**

```bash
cd /path/to/GenAIProacTrade
PYTHONPATH=src python3 src/main.py write-phase27-targeted-backfill-review \
  --universe sp500_current --panel-limit 8000 --program-id latest \
  --out docs/operator_closeout/phase27_targeted_backfill_review.md \
  --bundle-out docs/operator_closeout/phase27_targeted_backfill_bundle.json
```

**수리 후 리뷰(한 번에, Phase 27.5 권장):**

```bash
PYTHONPATH=src python3 src/main.py run-targeted-backfill-repair-and-review \
  --universe sp500_current --panel-limit 8000 --program-id latest \
  --out docs/operator_closeout/phase27_targeted_backfill_review.md \
  --bundle-out docs/operator_closeout/phase27_targeted_backfill_bundle.json
# 선택: --repair-forward
```

수리만 단계별로 할 때:

```bash
PYTHONPATH=src python3 src/main.py run-validation-registry-repair --universe sp500_current
PYTHONPATH=src python3 src/main.py run-market-metadata-hydration-repair --universe sp500_current
# 이후 write-phase27-targeted-backfill-review 재실행
```

## 스냅샷 요약 (해당 실행 기준, 리뷰 MD와 번들이 진실)

- **joined recipe 행 수**: 243; **메타 플래그 조인 행**: 243 — 갭 버킷 `missing_market_metadata_latest`: 243
- **검증 미적재 레지스트리 버킷(상위)**: `issuer_master_missing_for_resolved_cik` 188, `factor_panel_missing_for_resolved_cik` 3
- **Forward raw 미해결(`no_forward_row_next_quarter`)**: 61 — **true_repairable_forward_gap_count**: 1, **not_yet_matured**: 60 (달력 프록시 95일)
- **Phase 28 권고**: 번들 `phase28.phase28_recommendation` 필드(리뷰 §6과 동일)

수치 갱신 후에는 위 MD·JSON을 다시 생성해 본 파일과 `HANDOFF.md`를 맞춘다.

## 패치 보고(코드 스코프)

- `docs/phase27_patch_report.md`
- **27.5 hotfix 이후** 실측·판정은 `docs/phase27_5_hotfix_evidence.md`를 우선한다.
