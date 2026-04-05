# DB 스키마 메모 (Phase 0–7)

## 데이터 계층 역할

| 테이블 | 역할 |
|--------|------|
| `issuer_master` | **Issuer identity**. CIK가 canonical key. 티커·이름·SIC 등은 최근 관측값으로 갱신. |
| `filing_index` | **Filing identity**. “이 accession 공시가 존재한다”는 구조적 인덱스. raw와 독립 조회. |
| `raw_sec_filings` | **공시 메타 원문**. `payload_json`에 edgartools 기준 스냅샷. **업데이트 없음.** |
| `silver_sec_filings` | **공시 메타 정규화**. `normalized_summary_json`. revision으로 이력 확장. |
| `raw_xbrl_facts` | **XBRL fact 원형**. 행 단위 fact, `dedupe_key`로 동일 fact 재삽입 방지. **UPDATE 없음.** |
| `silver_xbrl_facts` | **XBRL fact 정규화**. `canonical_concept` + `fact_period_key` + `revision_no`. |
| `issuer_quarter_snapshots` | **분기 스냅샷**. 공시(accession) + `fiscal_year`/`fiscal_period` 단위 숫자 요약. |
| `issuer_quarter_factor_panels` | **회계 팩터 truth layer**. 스냅샷에서 결정적으로 계산된 팩터 + `coverage_json` / `quality_flags_json`. 가격 결합 전 단계. |
| `ingest_runs` | **수집 실행 감사**. run_type으로 메타 / facts / 스냅샷 / **factor panel** / **시장·검증** 구분. |
| `universe_memberships` | **유니버스**. `sp500_current`(위키/프로바이더 파싱) vs `sp500_proxy_candidates_v1`(시드·비공식 프록시 후보). `(universe_name, symbol, as_of_date)` 유니크. |
| `market_symbol_registry` | **거래 심볼 ↔ CIK**. 대문자 `symbol` 유니크. 위키 CIK vs `issuer_master` 불일치 시 감사 run `quality_flags`에 기록. |
| `raw_market_prices_daily` | **시세 원문**. `(symbol, trade_date, source_name)` 유니크. |
| `silver_market_prices_daily` | **정규화 일봉**. `(symbol, trade_date)` 유니크, upsert. `daily_return`은 전일 대비(조정종가 우선). |
| `market_metadata_latest` | **메타 스냅샷**(MVP). `(symbol, source_name)` 유니크 upsert. Yahoo chart-only 프로바이더는 빈 적재 가능. |
| `risk_free_rates_daily` | **무위험 연율(%)**. FRED DTB3 graph CSV 등. `(rate_date, source_name)` 유니크. |
| `forward_returns_daily_horizons` | **선행 수익률**. `(symbol, signal_date, horizon_type)` 유니크 upsert. `horizon_type`: `next_month` \| `next_quarter`. |
| `factor_market_validation_panels` | **팩터–시장 검증 조인**. `(cik, accession_no, factor_version)` 유니크 upsert. 랭킹·백테스트 없음. |
| `factor_validation_runs` | Phase 5 검증 **실행** 메타. `run_type` 기본 `factor_validation_research`. `ingest_runs`와 별도. |
| `factor_validation_summaries` | 팩터×지평×유니버스×`return_basis(raw\|excess)` 기술 요약(상관·평균 등). 전략 아님. |
| `factor_quantile_results` | 분위별 기술 통계. `(run_id, factor_name, horizon_type, universe_name, quantile_index, return_basis)` 유니크. |
| `factor_coverage_reports` | 슬라이스 내 팩터 값 가용성. `(run_id, factor_name, universe_name)` 유니크. |
| `state_change_runs` | Phase 6 **state change 실행** 메타. `run_type` 예: `state_change_engine_v1`. |
| `issuer_state_change_components` | 발행일·신호 long-form 구성요소(level/velocity/…). `(run_id, cik, as_of_date, signal_name)` 유니크. |
| `issuer_state_change_scores` | 발행일 단위 투명 합성 점수. `(run_id, cik, as_of_date)` 유니크. |
| `state_change_candidates` | 조사 후보(실행 신호 아님). `(run_id, cik, as_of_date, candidate_rank)` 유니크. |
| `ai_harness_candidate_inputs` | Phase 7 **AI Harness 입력 계약** JSON. `(candidate_id, contract_version)` 유니크 upsert. 진실 테이블 비변경. |
| `investigation_memos` | 조사 메모 오버레이. `(candidate_id, memo_version)` 유니크. `input_payload_hash`(재실행/idempotency용). thesis+challenge+synthesis+referee 메타. |
| `investigation_memo_claims` | Phase 7.1 **주장 단위** 추적: `claim_id`, `claim_role`(thesis\|challenge\|synthesis\|referee\|evidence), `statement`, `support_summary`, `counter_evidence_summary`, `trace_refs`, `needs_verification`, `verdict`(pending\|…), `candidate_id`. `(memo_id, claim_id)` 유니크. |
| `operator_review_queue` | 운영자 리뷰 큐. `candidate_id` 유니크. `status_reason`, `reviewed_at`. 상태: pending\|reviewed\|needs_followup\|blocked_insufficient_data. |
| `hypothesis_registry` | **스텁** — 미래 연구 가설; 스코어링 미연동. |
| `promotion_gate_events` | **스텁** — 미래 승격 게이트; 자동 승격 없음. |
| `backfill_orchestration_runs` | **유니버스 백필** 상위 실행 메타. `mode`·`universe_name`·`summary_json`(retry_tickers 등). |
| `backfill_stage_events` | 백필 **스테이지별** 행 수·에러·`notes_json`. `ingest_runs` 와 별도 감사. |

## ingest_runs `run_type`

| run_type | 설명 |
|----------|------|
| `sec_watchlist_metadata_ingest` | 워치리스트 기준 공시 메타 ingest |
| `sec_facts_extract` | XBRL facts 추출·적재 |
| `sec_quarter_snapshot_build` | `silver_xbrl_facts` → `issuer_quarter_snapshots` |
| `sec_factor_panel_build` | `issuer_quarter_snapshots` → `issuer_quarter_factor_panels` |
| `universe_refresh` | S&P 500 current 등 → `universe_memberships` |
| `universe_candidate_build` | `sp500_proxy_candidates_v1` 시드 기반 후보 적재 |
| `market_prices_ingest` | 프로바이더 → raw/silver 일봉 |
| `market_metadata_refresh` | 메타(프로바이더가 제공 시) → `market_metadata_latest` |
| `risk_free_ingest` | FRED 등 → `risk_free_rates_daily` |
| `forward_return_build` | 스냅샷 시그널일 + silver + 무위험 → `forward_returns_daily_horizons` |
| `factor_market_validation_build` | 팩터 패널 + 선행수익률 + 메타 → `factor_market_validation_panels` |

`factor_validation_runs.run_type` 기본값은 **`factor_validation_research`** (별도 테이블; `ingest_runs` 아님).

## 시그널일·선행수익률 (Phase 4, no-lookahead)

- **시그널 가용일 `signal_available_date`**: `issuer_quarter_snapshots.accepted_at`의 **UTC 캘린더일** 다음 **첫 평일**(주말만 제외; **미국 공휴일 미반영**—README 동일). `accepted_at` 없으면 `filed_at` 동일 규칙. **당일 종가 사용 안 함**(인트라데이 없음).
- **raw 선행 수익률**: `silver_market_prices_daily`에서 시그널일 **이상** 첫 거래일 종가(조정종가 우선) 대비, 각각 **21거래일·63거래일** 앞으로의 종가 비율 − 1 (`next_month` / `next_quarter` 근사).
- **excess 선행 수익률**: 구간 거래일 수 `n`과 해당 기간 **일별 무위험 연율(%) 평균** `r_avg`로 `period_rf = (1+r_avg/100)^(n/252)−1` 근사 후 `(1+raw)/(1+period_rf)−1`. 세부는 README.

## Idempotency 정책 (요약)

### Raw duplicate policy (`raw_sec_filings`)

- 유니크: `(cik, accession_no)`.
- 동일 키가 이미 있으면 **insert 하지 않음** (immutable).

### Filing identity uniqueness policy (`filing_index`)

- 유니크: `(cik, accession_no)`.
- 재실행 시 **upsert**: `last_seen_at` / `updated_at` 및 일부 메타 갱신.

### Silver filing revision policy (`silver_sec_filings`)

- 유니크: `(cik, accession_no, revision_no)`.
- Phase 1–2 기본: `revision_no = 1`만 사용. 동일 키면 insert 생략.

### Raw XBRL facts (`raw_xbrl_facts`)

- 유니크: `(cik, accession_no, dedupe_key)`.
- 동일 키면 insert 생략 (불변).

### Silver XBRL facts (`silver_xbrl_facts`)

- 유니크: `(cik, accession_no, canonical_concept, revision_no, fact_period_key)`.
- 동일 키면 insert 생략.

### Issuer quarter snapshots (`issuer_quarter_snapshots`)

- 유니크: `(cik, fiscal_year, fiscal_period, accession_no)`.
- 재실행 시 **upsert**.

### Issuer quarter factor panels (`issuer_quarter_factor_panels`)

- 유니크: `(cik, fiscal_year, fiscal_period, accession_no, factor_version)`.
- 동일 키면 **insert 생략** (행 UPDATE 없음, 멱등). 공식 변경 시 `factor_version`을 올려 새 행으로 적재.

### Issuer master

- 유니크: `cik`. 재실행 시 upsert.

### Market raw/silver / risk-free / forward / validation (Phase 4)

- `raw_market_prices_daily`: `(symbol, trade_date, source_name)` upsert.
- `silver_market_prices_daily`: `(symbol, trade_date)` upsert (재실행 안전).
- `risk_free_rates_daily`: `(rate_date, source_name)` upsert.
- `forward_returns_daily_horizons`: `(symbol, signal_date, horizon_type)` upsert.
- `factor_market_validation_panels`: `(cik, accession_no, factor_version)` upsert.
- `universe_memberships`: 보통 **새 `as_of_date` 배치 insert** (같은 as_of 재실행 시 유니크 충돌 가능—운영 시 같은 날 재실행 주의).
- **Phase 5** `factor_validation_runs`: 매 실행 **새 행 insert**; 자식 요약·분위·커버리지는 해당 `run_id`에 insert. 재실행 시 이전 run 보존(감사 비교용).
- **Phase 6** `state_change_runs`: 매 실행 **새 행 insert**; components/scores/candidates는 해당 `run_id`에 insert. 동일 입력 재현은 동일 코드·동일 DB 스냅샷 전제.
- **Backfill** `backfill_orchestration_runs` / `backfill_stage_events`: 오케스트레이션마다 **새 parent run** + 스테이지별 자식 행 insert.

## Factor panel JSON

- **`factor_json`**: 팩터별 값·`financial_strength_score_v1`의 `components`·`max_score_available` 등.
- **`coverage_json`**: 팩터별 `formula_used`, `missing_fields`, `prior_snapshot_found`, 평균자산 세부.
- **`quality_flags_json`**: 전역 `flags` + `by_factor` (`no_prior_snapshot`, `partial_inputs`, `zero_denominator` 등).

## Arelle (validation assist path)

- `src/sec/validation/arelle_check.py`는 **교차검증 보조** 용도이며, 미설치 시 `status: skipped`.

## RLS

Service role 키는 RLS를 우회한다. 로컬 워커는 service role 전제.

## 마이그레이션

`supabase/migrations/` 에서 **시간순**으로 적용한다.

1. `20250401000000_phase0_raw_silver_sec_filings.sql`
2. `20250402120000_phase1_issuer_filing_ingest_runs.sql`
3. `20250403100000_phase2_xbrl_facts_snapshots.sql`
4. `20250404100000_phase3_factor_panels.sql`
5. `20250405100000_phase4_market_validation.sql`
6. `20250406100000_phase5_factor_validation_research.sql`
7. `20250407100000_phase6_state_change_engine.sql`
8. `20250408100000_backfill_orchestration.sql` — `backfill_*` 테이블 + `backfill_coverage_counts()` RPC
9. `20250409100000_phase7_ai_harness_minimum.sql` — harness 입력·메모·리뷰 큐·R&D 스텁
10. `20250410100000_phase71_harness_hardening.sql` — 클레임 스키마 확장, `input_payload_hash`, 큐 감사 컬럼, 인덱스

## Phase 7 / 7.1 재실행 정책 (요약)

- **`ai_harness_candidate_inputs`**: `(candidate_id, contract_version)` 유니크 **upsert**. PostgREST `on_conflict="candidate_id,contract_version"` (쉼표 구분, 공백 없음).
- **`generate-investigation-memos`**: 최신 메모의 `input_payload_hash`·`generation_mode`가 현재 입력과 같으면 **동일 `memo_version`/`id`로 `investigation_memos` 업데이트**, 기존 `investigation_memo_claims`는 해당 `memo_id` **삭제 후 재삽입**. 해시가 다르면 `memo_version = max+1` **INSERT** (감사 이력).
- **`operator_review_queue`**: `candidate_id` 기준 **upsert**; 운영자 확정 상태(`reviewed` 등)는 재생성 시 **유지**하도록 애플리케이션에서 `status`를 덮어쓰지 않음(구현: `resolve_queue_status_on_memo_regen`).
