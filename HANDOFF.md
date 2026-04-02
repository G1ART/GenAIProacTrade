# HANDOFF — Phase 6 + Universe Backfill

## Universe Backfill 오케스트레이션 (신규)

- **마이그레이션** `20250408100000_backfill_orchestration.sql`: `backfill_orchestration_runs`, `backfill_stage_events`, RPC `backfill_coverage_counts()`
- **모듈** `src/backfill/`: `universe_resolver`, `backfill_runner`, `join_diagnostics`, `coverage_report`, `status_report`, `cli_report`, `normalize`, `pilot_tickers`
- **설정** `config/backfill_pilot_tickers_v1.json` — pilot 30종(유니버스와 교집합)
- **CLI**: `smoke-backfill`, `backfill-universe`, `report-backfill-status`
- **SEC/facts 리팩터**: `run_sec_ingest_for_tickers`, `run_facts_extract_for_tickers`, `run_quarter_snapshot_build_tickers`
- **records**: `fetch_factor_panels_all` 페이지네이션(대량 forward/validation 빌드), backfill CRUD·RPC 래퍼
- **pytest** `src/tests/test_backfill_orchestration.py`
- **문서**: README `## Full Universe Backfill` 복붙 (1)–(14), `schema_notes` 마이그레이션 8

**하지 않는 것**: 수동 SQL/CSV로 데이터 채우기, 웹 매크로, 가짜 placeholder row, 백테스트·전략·AI harness.

**재시도**: `summary_json.retry_tickers_all` + `--retry-failed-only --from-orchestration-run-id <UUID>`

---

## Phase 6 완료 범위 (state change)

- **마이그레이션** `20250407100000_phase6_state_change_engine.sql`: `state_change_runs`, `issuer_state_change_components`, `issuer_state_change_scores`, `state_change_candidates`
- **모듈** `src/state_change/`: `signal_registry`, `universe_scope`, `loaders`, `transforms`, `components`, `scoring`, `candidates`, `runner`, `reports`, `cli_report`, `__init__.py`
- **DB** `src/db/records.py`: issuer/패널/스냅샷 조회, state change run insert/finalize, 배치 insert, smoke, 최근 run·점수·후보·run 단건·후보 class 집계
- **CLI**: `run-state-change`, `report-state-change-summary`, `smoke-state-change`
- **문서**: `README.md`(Phase 6 목적·Phase 5 차이·복붙 1–10·CLI), `src/db/schema_notes.md`
- **pytest**: `src/tests/test_state_change_phase6.py` — 결정성·누수 방지(state_change 패키지가 validation 패널 테이블 미조회)·lag·null 처리·방향 매핑·후보 정렬·요약 포맷·CLI `-h`

## State change의 정의 (이번 Phase)

- **입력**: 분기 팩터 패널·스냅샷·유니버스·(선택) 무위험 이자율로 **동시점 단면 z** 및 **lag 기반 velocity/acceleration/persistence** 등을 계산해 issuer–`as_of_date` 단위로 적재.
- **출력**: 구성요소 long-form, 투명 가중 합성 점수, **조사 후보** 분류(`investigate_now` 등). **트레이드 추천·알파·포트폴리오 아님.**

## 새 테이블 4종

| 테이블 | 역할 |
|--------|------|
| `state_change_runs` | 실행 메타(`run_type`, 유니버스, 기간, `config_version`, `input_snapshot_json`, 상태) |
| `issuer_state_change_components` | 신호별 level/velocity/acceleration/persistence·nullable contamination/regime |
| `issuer_state_change_scores` | 일자별 합성 `state_change_score_v1`, 방향, 신뢰 구간, 게이트, `normalized_weight_sum` |
| `state_change_candidates` | 순위·분류·사유 JSON·우선순위(휴먼 리뷰용) |

## 새 CLI 3종

- `smoke-state-change` — 테이블 도달
- `run-state-change` — `--universe`, `--as-of-date`, `--start-date`, `--end-date`, `--limit`, `--dry-run`, `--include-nullable-overlays`, `--output-json`
- `report-state-change-summary` — `--run-id` 또는 `--universe`(최근 completed), `--output-json`

## 아직 하지 않는 것 (Phase 6 범위 밖)

- AI 하네스·메시지 레이어, 알림, UI, 포트폴리오, 백테스트 확장, execution signal
- `factor_market_validation_panels`의 **forward/excess return·horizon outcome** 을 state change **feature**로 사용 (금지; 코드상 `src/state_change/*` 에서 해당 테이블 조회 없음)

## 대표 수동 액션

1. Phase 6 SQL 적용 후 `smoke-state-change`
2. `run-state-change --limit` 소규모 → `report-state-change-summary`
3. SQL로 `run_id`별 row count·상위 후보 확인(README 복붙)

## 다음 Phase (AI harness / message layer) 진입 조건 제안

- [ ] Phase 6 마이그레이션 적용·`smoke-state-change` 성공
- [ ] 최소 1회 `run-state-change` completed·`state_change_candidates` 샘플 확인
- [ ] 조사 워크플로에 맞는 후보 필터·우선순위를 사람이 검토해 피드백 반영 여부 결정
- [ ] `.env`·service role 미커밋 유지

## 이번 패치에서 추가·수정한 주요 파일

- `supabase/migrations/20250407100000_phase6_state_change_engine.sql`
- `src/state_change/**`
- `src/db/records.py`, `src/main.py`
- `src/tests/test_state_change_phase6.py`
- `README.md`, `HANDOFF.md`, `src/db/schema_notes.md`

## 알려진 리스크

- 유니버스에 팩터 패널이 거의 없으면 관측 0·빈 run.
- contamination v1은 결정적 proxy 없이 null·메타만(regime은 무위험 맥락 최소 태깅).
- 동일 `(cik, as_of_date)` 패널 중복 시 **최대 분기 인덱스** 한 행만 유지.
