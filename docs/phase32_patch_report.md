# Phase 32 패치 보고 — Forward-return unlock (Phase 31 touched) + narrow snapshot cleanup

## 목적

Phase 31에서 **검증 패널까지 연 CIK**가 **`missing_excess_return_1q`** 에서 막히는 병목을 **상한**으로 완화하고, **`silver_present_snapshot_materialization_missing`**·GIS류 **`raw_present_no_silver_facts`**·Phase 31 **deferred raw facts** 만 좁게 다룬다. 메타·임계·15/16·프리미엄·프로덕션 스코어 비목표.

## 수정 요약

| # | 영역 | 내용 |
|---|------|------|
| 1 | `phase31.raw_facts_repair` | `deferred_external_source_gap_all` (최대 120행) — Phase 32 재시도 입력. |
| 2 | `phase32.phase31_bundle_io` | Phase 31 번들에서 하류 검증 비스킵 CIK·raw 복구 CIK 순으로 터치 집합. |
| 3 | `phase32.forward_return_phase31` | 터치∩`missing_excess` 큐 갭 리포트·export; `no_forward_row_next_quarter` 후보에 한해 `run_forward_returns_build_from_rows` → `forward_returns_daily_horizons`. |
| 4 | `phase32.silver_snapshot_cleanup` | `silver_present_snapshot_materialization_missing` 타깃·수리; GIS 1건 위임(`run_gis_like_silver_materialization_seam_repair`). |
| 5 | `phase32.raw_deferred_retry` | `facts_extract_exception` 만 백오프 재시도; 복구/외부 지속/스키마 분류. |
| 6 | `phase32.metrics` | `collect_phase32_substrate_snapshot` — `missing_excess_return_1q` 명시. |
| 7 | `phase32.orchestrator` / `review` / `phase33_recommend` | 전후 스냅샷·`stage_transitions`·번들/리뷰 MD·Phase 33 권고. |
| 8 | `main.py` | `report/export-forward-return-gap-targets-after-phase31`, `run-forward-return-backfill-for-phase31-touched`, silver·raw·`run-phase32-forward-unlock-and-snapshot-cleanup`, `write-phase32-…-review`. |
| 9 | `src/tests/test_phase32_forward_unlock_and_snapshot_cleanup.py` | 선별·백필·silver·GIS·raw·리뷰 writer. |

## 산출물

- `docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_review.md`
- `docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json`

## 재현 예시

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

번들만으로 MD 재생성:

```bash
PYTHONPATH=src python3 src/main.py write-phase32-forward-unlock-and-snapshot-cleanup-review \
  --bundle-in docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json \
  --out-md docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_review.md
```

## 실측 한 줄 (2026-04-08)

스냅샷 물질화 10건 클리어·검증 갭 −10·forward 심볼 23건 해소·raw 재시도 7건 복구; 헤드라인 `missing_excess_return_1q`는 91→101(패널 행 증가 효과). 자세한 수치는 `docs/phase32_evidence.md`.
