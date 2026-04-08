# Phase 29 패치 보고 — Validation refresh after metadata + quarter snapshot backfill

## 목적

메타데이터 행이 생긴 뒤에도 **`factor_market_validation_panels`에 `missing_market_metadata`가 남는** 스테일 상태를 **상한 있는 행 기반 재빌드**로 해소한다. 동시에 `missing_quarter_snapshot_for_cik` 다발 구간을 **진단 분류**하고, **silver는 있는데 스냅샷만 없는** 경우에 한해 DB 내 재구성을 시도한다.

## 수정 요약

| # | 대상 | 내용 |
|---|------|------|
| 1 | `db.records` | `pick_best_market_metadata_row`, `fetch_market_metadata_latest_row_deterministic`; `fetch_market_metadata_latest_rows_for_symbols`가 `select("*")` 후 동일 pick 규칙 적용. `fetch_issuer_quarter_factor_panel_one`, `fetch_factor_market_validation_panel_one`. |
| 2 | `market.validation_panel_run` | 메타 조회를 결정적 헬퍼로 통일. |
| 3 | `phase29.stale_validation_metadata` | report / run refresh / export. |
| 4 | `phase29.quarter_snapshot_gaps` | 분류 report·bounded repair·export. |
| 5 | `phase29.orchestrator` | 메타 수화 → stale 갱신 → 스냅샷 수리 → 팩터 물질화. |
| 6 | `phase29.review` | 리뷰 MD + 수용 기준 미달 시 명시 문단. |
| 7 | `phase29.phase30_recommend` | 다음 단일 분기 권고. |
| 8 | `main.py` | Phase 29 CLI (중복 정의 제거). |
| 9 | `src/tests/test_phase29_validation_refresh.py` | 메타 pick·검증 빌드·분류·오케스트레이션 순서. |

## Phase 29.1 — 성능·운영 핫픽스 (동일 시맨틱)

| # | 대상 | 내용 |
|---|------|------|
| A | `db.records.fetch_tickers_for_ciks` | `issuer_master` 를 CIK당 단건이 아니라 청크 `in_` 배치 조회; 키는 `norm_cik`, 티커는 동일 키에 대해 정렬 후 결정적 1개 선택. |
| B | `targeted_backfill.validation_registry` | `canonical_for_cik` 채울 때 위 배치 헬퍼만 사용 (per-CIK `fetch_ticker_for_cik` 루프 제거). |
| C | `phase28.factor_materialization` | 선택 인자 `registry_report` — 전달 시 내부에서 `report_validation_registry_gaps` 재호출 안 함. |
| D | `phase29.quarter_snapshot_gaps` | `registry_report` / `materialization_report` — 동일 스냅에서 팩터 물질화·레지스트리 중복 제거. |
| E | `phase29.orchestrator` | `_snap()` 당 레지스트리 무거운 경로 1회; 수리 단계 사이 진행 로그. |
| F | `phase28.orchestrator` | 최종 `mat_report` 생성 시 이미 계산한 `reg_a` 를 `registry_report` 로 전달 (중복 레지스트리 1회 절감). |
| G | `main.py` | `--bundle-out` / `--out-md` 기록 직후 `phase29_bundle_written` / `phase29_review_written`. |
| H | `src/tests/test_db_fetch_tickers_for_ciks.py` 등 | 배치·오케스트레이션 호출 수·stdout 태그. |

## 비목표

프리미엄 오픈·임계 완화·Phase 15/16 강제·프로덕션 스코어 경로 변경·무제한 전 테이블 검증 리빌드.

## 관련 문서

- `docs/phase29_evidence.md`
- `docs/operator_closeout/phase29_validation_refresh_and_snapshot_backfill_review.md` (실행 후)
