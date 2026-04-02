# DB 스키마 메모 (Phase 0–4)

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
