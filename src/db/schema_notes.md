# DB 스키마 메모 (Phase 0–16)

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
| `hypothesis_registry` | Phase 9 **연구 레지스트리**: `title`, `research_item_status`, `source_scope`, `intended_use`, `leakage_review_status`, `promotion_decision`, `rejection_reason`, `linked_artifacts`. 프로덕션 스코어링이 자동 조회하지 않음(거버넌스 전용). |
| `promotion_gate_events` | 승격/거부 감사: `hypothesis_id`, `event_type`, `decision_summary`, `rationale`, `actor`, `metadata_json`. |
| `operational_runs` | Phase 9 **운영 실행** 감사: `run_type`, `component`, `status`(running\|success\|warning\|failed\|empty_valid), 행 수, `tokens_used`(null 가능), `trace_json`. |
| `operational_failures` | 실행별 **쿼리 가능** 실패/경고 분류: `failure_category`(configuration_error, db_migration_missing, source_data_missing, empty_but_valid, heuristic_low_confidence, execution_error, other). |
| `outlier_casebook_runs` | Phase 8 배치 메타; `detection_logic_version`, `policy_json`. |
| `outlier_casebook_entries` | 이상치 사례 메모리: discrepancy·expected/observed·uncertainty·message 필드·`is_heuristic`·Phase 10 `overlay_awareness_json`(오버레이 유무 명시). Phase 13: `residual_triage_bucket`, `premium_overlay_suggestion`(감사용 트리이지·선택 프리미엄 힌트). |
| `public_core_cycle_quality_runs` | Phase 13 **공개 코어 사이클 품질** 스냅샷: `quality_class`, `metrics_json`, `gap_reasons_ranked`, `overlay_status_json`, `residual_triage_json`, `unresolved_residual_items`. |
| `research_programs` | Phase 14 연구 프로그램; `linked_quality_context_json`; `premium_overlays_allowed` 기본 false. |
| `research_hypotheses` | Phase 14 구조화 가설(경제 근거·메커니즘·특성 JSON); 상태 `proposed`…`candidate_recipe`. |
| `research_reviews` | 렌즈별 `pass`/`concern`/`reject`; 라운드 1–2. |
| `research_referee_decisions` | `kill`/`sandbox`/`candidate_recipe`; `disagreement_json`. |
| `research_residual_links` | 가설↔잔차 버킷·미해결·프리미엄 힌트(정보). |
| `recipe_validation_runs` | Phase 15 검증 랩 실행(베이스라인·코호트·창·품질 필터 JSON; state_change·품질 run 링크). Phase 16: `join_policy_version`(예: `cik_asof_v1`)로 캠페인 재사용 호환 판정. |
| `recipe_validation_results` | 코호트/베이스라인별 결정적 지표(예: 분위 스프레드). |
| `recipe_validation_comparisons` | 후보 vs 명시 베이스라인 델타·해석 JSON. |
| `recipe_survival_decisions` | `survives` \| `weak_survival` \| `demote_to_sandbox` \| `archive_failed`. |
| `recipe_failure_cases` | 실패 맥락·잔차 링크·프리미엄 힌트(연구용). |
| `validation_campaign_runs` | Phase 16 프로그램 단위 캠페인: `policy_version`, `run_mode`, 집계 JSON, `recommendation`, `rationale_json`. |
| `validation_campaign_members` | 캠페인에 포함된 가설별 `validation_run_id`, 생존·베이스라인·취약성·프리미엄 힌트 요약 JSON. |
| `validation_campaign_decisions` | 권고 1건·근거 텍스트·임계값·반증 시 다음 행동 JSON. |
| `public_depth_runs` | Phase 17 공개 기판 확장 오케스트레이션: `universe_name`, `policy_version`, `status`, `expansion_summary_json`. |
| `public_depth_coverage_reports` | 유니버스별 커버리지 스냅샷: `snapshot_label`(before/after/standalone), `metrics_json`, `exclusion_distribution_json`; `public_depth_run_id` nullable. |
| `public_depth_uplift_reports` | before/after 커버리지 리포트 FK와 `uplift_metrics_json`. |
| `scanner_runs` | 일일 스캐너 실행; `policy_json`(top_n, floor 등). |
| `daily_signal_snapshots` | 스캐너 run당 1행 집계 `stats_json`. |
| `daily_watchlist_entries` | 저잡음 우선순위 워치리스트; thesis/challenge/uncertainty + message 필드·Phase 10 `overlay_awareness_json`·Phase 11 `transcript_enrichment_json`(선택 메시지 보강; 스코어 비사용). |
| `data_source_registry` | Phase 10 **소스 카탈로그**: `source_class`(public\|premium\|…), `data_family`, PIT·라이선스·`provenance_policy_json`. 진실 스파인 오염 금지. |
| `source_access_profiles` | 소스별 접근 프로필(`access_mechanism`, 자격 필요 여부). |
| `source_entitlements` | 권한/스코프 라벨(`active\|pending\|none` 등). |
| `source_coverage_profiles` | 커버리지 메타 `coverage_json`. |
| `source_rights_notes` | 권리·주의 문구(감사/파트너 대화용). |
| `source_overlay_availability` | 프리미엄 오버레이 키별 `not_available_yet`\|partial\|available. |
| `source_overlay_runs` | (선택) 오버레이 스모크/감사 run 메타. |
| `source_overlay_gap_reports` | `report-overlay-gap --persist` 저장용 ROI/갭 JSON. |
| `transcript_ingest_runs` | Phase 11 FMP PoC: 프로브/ingest 감사(`provider_code`, `operation`, `probe_status`, `detail_json`). |
| `raw_transcript_payloads_fmp` | FMP `earning_call_transcript` 원문 JSON(`symbol`,`fiscal_year`,`fiscal_quarter` 유니크). |
| `raw_transcript_payloads_fmp_history` | Phase 11.1: upsert 전 **이전 raw** 스냅샷(불변 감사). |
| `normalized_transcripts` | PIT 메타 포함 정규화 본문(`provider_name`,`ticker`,`fiscal_period` 유니크); 결정적 스파인과 분리. |
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
11. `20250411100000_phase8_casebook_scanner.sql` — 아웃라이어 케이스북 + 일일 스캐너/워치리스트

## Phase 8 저잡음 워치리스트 정책 (요약)

- 기본: `top_n=15`, `min_priority_score=20`, `max_candidate_rank=60`, 후보 클래스 `investigate_now` \| `investigate_watch` \| `recheck_later` 만 게이트 통과 후 우선순위 점수 내림차순.
- 임계 미달 시 **빈 워치리스트 허용** (스팸 금지).

## Phase 7 / 7.1 재실행 정책 (요약)

- **`ai_harness_candidate_inputs`**: `(candidate_id, contract_version)` 유니크 **upsert**. PostgREST `on_conflict="candidate_id,contract_version"` (쉼표 구분, 공백 없음).
- **`generate-investigation-memos`**: 최신 메모의 `input_payload_hash`·`generation_mode`가 현재 입력과 같으면 **동일 `memo_version`/`id`로 `investigation_memos` 업데이트**, 기존 `investigation_memo_claims`는 해당 `memo_id` **삭제 후 재삽입**. 해시가 다르면 `memo_version = max+1` **INSERT** (감사 이력).
- **`operator_review_queue`**: `candidate_id` 기준 **upsert**; 운영자 확정 상태(`reviewed` 등)는 재생성 시 **유지**하도록 애플리케이션에서 `status`를 덮어쓰지 않음(구현: `resolve_queue_status_on_memo_regen`).
