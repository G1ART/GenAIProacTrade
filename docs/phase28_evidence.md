# Phase 28 evidence (실측 클로즈아웃)

## 실행 개요

- **명령**: `run-phase28-provider-metadata-and-panel-repair` (오케스트레이션: 메타 수화 + 팩터 물질화 수리)
- **유니버스**: `sp500_current`
- **리뷰 MD 생성 시각(UTC)**: `2026-04-08T01:34:10.123881+00:00` (`phase28_provider_metadata_and_factor_panel_review.md` 상단)
- **근거 번들**: `docs/operator_closeout/phase28_provider_metadata_and_factor_panel_bundle.json`

## 번들에서 확인한 수치 (Before = After, 본 실행)

| 항목 | 값 | 비고 |
|------|-----|------|
| `joined_recipe_substrate_row_count` | 243 | 전후 동일 |
| `joined_market_metadata_flagged_count` | 243 | 메타 수화 후에도 동일 — `report_market_metadata_gap_drivers`의 조인·as_of·가격 창 등 **다른 버킷**이 플래그를 유지할 수 있음 |
| `thin_input_share` | 1.0 | 전후 동일 |
| `no_validation_panel_for_symbol` | 191 | 제외 분포 전후 동일 |
| `registry_blocker_symbol_total` | 191 | 전후 동일 |
| 레지스트리 `per_bucket.factor_panel_missing_for_resolved_cik` | 189 | + norm mismatch 2 = 191 미해결 검증 심볼과 정합 |
| 메타 수화 `hydration.status` | `completed` | 차단 아님 |
| `provider_rows_returned` / `rows_upserted` | 243 / 243 | Yahoo chart |
| `rows_missing_after_requery` | 0 | `avg_daily_volume` 재조회 기준 누락 없음 |
| `factor_panel_repairs_attempted` | 0 | 아래 물질화 분해 참고 |
| `validation_panel_repairs_attempted` | 0 | 동일 |

## 팩터 물질화 분해 (최종 스냅샷)

| 버킷 | 건수 | 해석 |
|------|------|------|
| `missing_quarter_snapshot_for_cik` | 189 | 레지스트리상 factor 누락으로 분류된 심볼 대부분이 **분기 스냅샷 부재**로 세분됨 → 이번 실행에서 `run_factor_panels_for_cik` 타깃 없음 |
| `snapshot_present_but_factor_panel_missing` | 0 | — |
| `factor_panel_exists_but_validation_panel_missing` | 0 | — |
| `validation_panel_build_omission_for_existing_factor_panel` | 0 | — |

## 재현 명령

```bash
cd /path/to/GenAIProacTrade
PYTHONPATH=src python3 src/main.py run-phase28-provider-metadata-and-panel-repair \
  --universe sp500_current \
  --panel-limit 8000 \
  --out-md docs/operator_closeout/phase28_provider_metadata_and_factor_panel_review.md \
  --bundle-out docs/operator_closeout/phase28_provider_metadata_and_factor_panel_bundle.json
```

번들만으로 MD 재생성:

```bash
PYTHONPATH=src python3 src/main.py write-phase28-provider-metadata-review \
  --bundle-in docs/operator_closeout/phase28_provider_metadata_and_factor_panel_bundle.json \
  --out docs/operator_closeout/phase28_provider_metadata_and_factor_panel_review.md
```

## 로컬 테스트

```bash
pytest src/tests/test_phase28_provider_metadata_and_factor_panel.py -q
```

## 다음 판단 (증거 기준)

- Yahoo 메타 수화는 **243심볼 모두 행 반환·upsert·재조회 통과**로 계측 목적 달성.
- **검증 패널·thin_input** 델타는 이번 런에서 없음; 상류는 **분기 스냅샷 부재(189)** 가 지배적 분해.
- 스냅샷·XBRL/쿼터 파이프라인 또는 Phase 27 레지스트리 수리와의 **교차 확인**이 다음 브랜치에서 유효.

---

## 리뷰·에스컬레이션용 신규 문건 목록 (이번 Phase에서 새로 쓰거나 갱신해 두면 좋은 것)

아래는 **코드 리뷰·운영 리뷰·감사**에 넘길 때 묶음으로 쓰기 좋은 경로다.

| # | 경로 | 용도 |
|---|------|------|
| 1 | `docs/phase28_patch_report.md` | 변경 범위·비목표 (본 문서의 형제) |
| 2 | `docs/phase28_evidence.md` | 실측 명령·수치·재현 (본 문서) |
| 3 | `docs/operator_closeout/phase28_provider_metadata_and_factor_panel_review.md` | 운영자 1페이지 요약 |
| 4 | `docs/operator_closeout/phase28_provider_metadata_and_factor_panel_bundle.json` | 전체 JSON 스냅샷(전후·수화·물질화) |
| 5 | `HANDOFF.md` (Phase 28 절) | 다음 담당자 온보딩 |
| 6 | `src/phase28/*.py` | 구현 본문 (factor_materialization, orchestrator, review) |
| 7 | `src/market/price_ingest.py` (메타 수화 구간) | 차단·카운터 시맨틱 |
| 8 | `src/market/providers/yahoo_chart_provider.py` (`fetch_market_metadata`) | 프로바이더 계약 |
| 9 | `src/tests/test_phase28_provider_metadata_and_factor_panel.py` | 회귀·차단 경로 |

**선택(맥락 공유용)**: `docs/phase27_patch_report.md`, `docs/phase27_5_hotfix_patch_report.md` — 레지스트리·CIK 핫픽스와 Phase 28 분해가 같은 미해결 집합(191)을 다루므로 같이 붙이면 원인 추적이 쉽다.
