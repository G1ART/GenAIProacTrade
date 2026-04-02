# GenAIProacTrade — Phase 0–4 (SEC + XBRL + 회계 팩터 + 시장 검증 패널)

미국 SEC **공시 메타데이터**·**XBRL fact**·**분기 스냅샷**·**회계 팩터**에 이어, Phase 4에서 **시장 가격·선행 수익률·무위험 이자율**을 **provider 추상화**로 적재하고 **`factor_market_validation_panels`** 까지 조인하는 Python 워커입니다.

**Phase 4에서도 포함하지 않는 것**: 팩터 **랭킹·알파 점수**, 포트폴리오·롱숏 바스켓, **백테스트 리포트**, 상태변화 엔진, **OpenAI/AI 하네스**, 알림·Slack·email, Railway·**스케줄러/cron**·**UI**, “공식 S&P 편입 후보” 포장. (GDELT/FINRA 등 확장 API는 무위험 FRED 최소 수준만.)

## Phase 4 목표 (market validation layer)

- **Provider 추상화**: `src/market/providers/base.py`의 `MarketDataProvider`. 기본 구현 `yahoo_chart`(일봉 JSON + 위키 S&P 표, urllib) 및 테스트용 `stub`(`MARKET_DATA_PROVIDER=stub`).
- **유니버스**: `sp500_current`(구성종목, `membership_status=constituent`)와 **`sp500_proxy_candidates_v1`**(시드 `config/sp500_proxy_candidates_v1.json` 기반 **비공식 프록시 후보**, 공식 위원회 후보 아님).
- **가격 계층**: `raw_market_prices_daily`(원문) → `silver_market_prices_daily`(정규화, **조정종가 우선**, `daily_return`).
- **무위험**: `risk_free_rates_daily` — 기본 소스 **FRED DTB3** graph CSV (`src/market/risk_free_fred.py`): URL에 **cosd/coed**로 요청 구간을 한정해 CSV 부하·**504** 가능성을 줄이고, **httpx** + **5xx/429 재시도**, `source_name=fred_dtb3_graph_csv`. 여전히 504면 FRED 측 게이트웨이 이슈일 수 있으니 잠시 후 `ingest-risk-free`를 다시 실행하면 됩니다.
- **선행 수익률**: `forward_returns_daily_horizons`, `horizon_type` = `next_month`(약 21거래일) / `next_quarter`(약 63거래일). **raw**와 **excess** 모두 저장.
- **검증 패널**: `factor_market_validation_panels` — 팩터 패널 + 시그널일 + 선행수익률 + (있으면) 메타. **research/backtest 아님.**

### Phase 4: raw vs excess 정의

- **raw_forward_return**: `silver` 기준 가격(조정종가 우선)으로, 시그널일 이후 첫 거래일 종가 → 각 지평 종가까지의 총수익률.
- **excess_forward_return**: 동일 구간 거래일 수 `n`에 대해, 해당 기간 일별 무위험 **연율화(%) 평균**으로 `period_rf ≈ (1+r_avg/100)^(n/252)−1` 를 두고 `(1+raw)/(1+period_rf)−1` (단순화, `return_basis_json`에 메타).

### Phase 4: 시그널일·no-lookahead (보수적)

- `signal_available_date` = `issuer_quarter_snapshots`의 **`accepted_at`이 있으면 그 UTC 날짜의 다음 날부터 첫 평일**, 없으면 **`filed_at`** 동일. **접수 당일 종가는 사용하지 않음.** 캘린더는 MVP로 **주말만 제외**(NYSE 휴장일 전체 반영 아님 — `schema_notes` 동일).
- 가격·무위험·선행수익률·검증 패널 빌드는 `ingest_runs`에 각각 `universe_refresh`, `universe_candidate_build`, `market_prices_ingest`, `market_metadata_refresh`, `risk_free_ingest`, `forward_return_build`, `factor_market_validation_build` 로 남김.

## Phase 3 목표

- **팩터 truth layer**: `issuer_quarter_snapshots` → `issuer_quarter_factor_panels` (가격 데이터 전 단계).
- **정의 고정**: `src/factors/definitions.py` 레지스트리 v1 (자동 팩터 생성기 없음).
- **공식 고정**: `src/factors/formulas.py` — README·`schema_notes`·코드 일치.
- **Prior 분기**: `src/factors/prior_period.py` — 동일 CIK·회계 분기 체인만 (거래일 정렬 없음).
- **설명 가능한 null**: `coverage_json` / `quality_flags_json`에 누락 필드·분모 0·prior 없음 등 기록.
- **감사**: `ingest_runs.run_type` = `sec_factor_panel_build`.

## Phase 3 팩터 공식 (v1)

| 팩터 | 공식 |
|------|------|
| `accruals` | `(net_income - operating_cash_flow) / average_total_assets` |
| `gross_profitability` | `gross_profit / average_total_assets` |
| `asset_growth` | `(total_assets_t - total_assets_t-1) / total_assets_t-1` (직전 **회계** 분기) |
| `capex_intensity` | `capex / average_total_assets` (**고정**. revenue 분모 미사용) |
| `rnd_intensity` | `research_and_development / revenue` (revenue 없으면 null, 대체 분모 없음) |
| `financial_strength_score` (컬럼) | `financial_strength_score_v1`: 이진 합산. 구성요소: `NI>0`, `OCF>0`, `OCF>=NI`, `gross_profitability>0`, `total_liabilities/total_assets` prior 대비 개선. 사용 가능한 항목만 `max_score_available`에 포함 (Piotroski 전체 아님). |

**average_total_assets** = `(total_assets_current + total_assets_prior) / 2`. prior 스냅샷 또는 prior `total_assets` 없으면 null.

## Prior period matching 정책

- `fiscal_period`를 대문자로 정규화한 뒤 **`Q1`–`Q4`, `FY`만** 직전 분기 링크를 지원한다 (`Q1` → 전년 `Q4`, …, `FY` → 전년 `FY`).
- `UNSPECIFIED` / `UNKNOWN` 등은 fiscal prior 없음 → prior 의존 팩터는 null + 플래그.
- 동일 `(fiscal_year, fiscal_period)`에 accession이 여러 개면 **`filed_at` 최신**을 대표 스냅샷으로 쓴다.

## Phase 2 목표

- **XBRL facts**: EdgarTools로 10-Q/10-K 등에서 fact 추출 → raw 보존 → silver 정규화(`canonical_concept`).
- **분기 스냅샷**: `issuer_quarter_snapshots`에 revenue / net_income / total_assets 등 **사실값만** 집계 (팩터 계산 없음).
- **매핑 v1**: `src/sec/facts/concept_map.py` — 대형 기술주에 흔한 us-gaap 태그 위주; 미매핑은 silver에 안 올라가고 `snapshot_json.missing_canonicals`에 기록.
- **감사**: `ingest_runs.run_type`으로 메타 ingest / facts 추출 / 스냅샷 빌드 구분.
- **Arelle**: 검증 **보조 경로**만 (`validate_xbrl_fact_presence` 등). 미설치 시 graceful skip.

## Phase 1 요약 (유지)

- Issuer·filing identity, 워치리스트 메타 ingest, 공시 raw/silver 멱등.

## 데이터 계층

| 계층 | 테이블 | 설명 |
|------|--------|------|
| Issuer identity | `issuer_master` | CIK 유니크, 티커는 관측값 |
| Filing identity | `filing_index` | `(cik, accession_no)` 유니크 |
| Raw filing meta | `raw_sec_filings` | 공시 메타 JSON, **불변** |
| Silver filing meta | `silver_sec_filings` | 정규화 요약, `revision_no` |
| Raw XBRL facts | `raw_xbrl_facts` | fact 원형, `(cik, accession, dedupe_key)` 유니크 |
| Silver XBRL facts | `silver_xbrl_facts` | canonical + `fact_period_key` + `revision_no` |
| Quarter snapshot | `issuer_quarter_snapshots` | `(cik, fiscal_year, fiscal_period, accession_no)` 유니크 |
| Factor panel | `issuer_quarter_factor_panels` | 스냅샷 기반 회계 팩터, `(cik, fy, fp, accession, factor_version)` 유니크 |
| Universe | `universe_memberships` | `sp500_current` / `sp500_proxy_candidates_v1` 등 |
| Symbol registry | `market_symbol_registry` | 심볼·CIK·거래소 메타 |
| Raw/Silver market | `raw_market_prices_daily`, `silver_market_prices_daily` | 시세 원문·정규화 |
| Market meta | `market_metadata_latest` | 시총·거래량 등(프로바이더가 줄 때만) |
| Risk-free | `risk_free_rates_daily` | 일별 연율화 무위험(%) |
| Forward returns | `forward_returns_daily_horizons` | 시그널일 기준 선행 raw/excess |
| Validation panel | `factor_market_validation_panels` | 팩터+시장 조인(검증용) |
| Audit | `ingest_runs` | 메타 / facts / 스냅샷 / factor_panel / **시장·검증** 등 |

상세 idempotency·run_type은 [`src/db/schema_notes.md`](src/db/schema_notes.md) 참고.

## Idempotency 정책 (한 줄 요약)

- **raw_sec_filings**: 동일 `(cik, accession_no)` 이미 있으면 insert 안 함.
- **filing_index**: 동일 키 upsert.
- **silver_sec_filings**: `(cik, accession, revision_no)` 동일하면 insert 안 함.
- **raw_xbrl_facts**: 동일 `dedupe_key`면 insert 안 함 (불변).
- **silver_xbrl_facts**: `(cik, accession, canonical, revision_no, fact_period_key)` 동일하면 insert 안 함.
- **issuer_quarter_snapshots**: 스냅샷 키 동일 시 upsert(갱신).
- **issuer_quarter_factor_panels**: 동일 `(cik, fiscal_year, fiscal_period, accession_no, factor_version)` 이면 **insert 생략** (행 UPDATE 없음, 멱등).
- **issuer_master**: CIK upsert.

## Coverage / quality flags (Phase 3)

- **`coverage_json`**: 팩터별 `formula_used`, `missing_fields`, `prior_snapshot_found`, 평균자산 세부 등.
- **`quality_flags_json`**: `flags` 전역 목록 + `by_factor` (예: `no_prior_snapshot`, `partial_inputs`, `zero_denominator`).
- **`factor_json`**: 팩터별 값·`financial_strength_score_v1`의 `components`·`max_score_available` 등 해석 메타.

## 사전 요구사항

- Python **3.9+**
- Supabase 프로젝트 + **service_role** 키
- `EDGAR_IDENTITY` (SEC 정책)

## 로컬 설정

```bash
cd /path/to/GenAIProacTrade
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

`.env`에 실제 키를 넣고 **Git에 커밋하지 마세요.**

### hishel / `FileStorage` 오류

`requirements.txt`의 `hishel>=0.1.3,<1` 을 유지한 뒤 `python3 -m pip install -r requirements.txt` 로 맞춥니다.

## Supabase 마이그레이션 적용 순서

SQL Editor에서 아래를 **순서대로** 실행합니다.

1. `supabase/migrations/20250401000000_phase0_raw_silver_sec_filings.sql`
2. `supabase/migrations/20250402120000_phase1_issuer_filing_ingest_runs.sql`
3. `supabase/migrations/20250403100000_phase2_xbrl_facts_snapshots.sql`
4. `supabase/migrations/20250404100000_phase3_factor_panels.sql`
5. `supabase/migrations/20250405100000_phase4_market_validation.sql`

## CLI (복붙용)

프로젝트 루트에서, 가상환경 활성화 후:

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

### 단일 티커 ingest

```bash
python3 src/main.py ingest-single --ticker NVDA
```

### 워치리스트 배치 ingest

기본 파일: `config/watchlist.json` (`tickers`, `filings_per_issuer`).

```bash
python3 src/main.py ingest-watchlist
```

다른 파일:

```bash
python3 src/main.py ingest-watchlist --watchlist /path/to/watchlist.json
```

환경변수 `WATCHLIST_PATH`로 기본 경로를 바꿀 수 있습니다. 티커 간 대기는 `--sleep` 또는 `INGEST_TICKER_SLEEP_SEC`.

`ingest_runs.run_type`은 **`sec_watchlist_metadata_ingest`** 로 기록됩니다.

### 스모크

```bash
python3 src/main.py smoke-sec
python3 src/main.py smoke-db
```

- `smoke-sec`: SEC에 접속 (네트워크 필요).
- `smoke-db`: Supabase `issuer_master`에 대한 단순 select.
- `smoke-facts`: `raw_xbrl_facts` 테이블 도달 + AAPL 등으로 XBRL fact 로드 프로브 (네트워크).
- `smoke-factors`: `issuer_quarter_factor_panels` 테이블 도달 + accruals 공식 sanity (DB·`.env` 필요, SEC 호출 없음).
- `smoke-market`: Phase 4 시장 테이블 도달 + 스텁 프로바이더 형태 (DB·`.env` 필요, 외부 호출 없음).
- `smoke-validation`: `factor_market_validation_panels` 테이블 도달 (DB·`.env`).

### Phase 4 시장·검증 (복붙 순서 예시)

**전제**: Phase 4 마이그레이션 적용, `.env` 설정, `export PYTHONPATH=src`.

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

**1) 스모크 (네트워크 없음, DB 필요)**

```bash
python3 src/main.py smoke-market
python3 src/main.py smoke-validation
```

**2) S&P 500 유니버스 갱신 (네트워크: 위키 + Yahoo 등)**

```bash
python3 src/main.py refresh-universe --universe sp500_current
```

**3) 프록시 후보 유니버스 (시드; 공식 후보 아님)**

```bash
python3 src/main.py build-candidate-universe
```

`build-candidate-universe` 는 **어디에 가입하는 것이 아니라**, `config/sp500_proxy_candidates_v1.json` 시드에서 **당시 `sp500_current` 에 이미 들어 있는 티커를 뺀 뒤** 남은 심볼만 `universe_memberships` 에 `candidate` 로 넣는다. 시드가 전부 S&P 구성이면 `candidate_count: 0` 이 되고 실패로 끝나니, JSON 심볼을 **지금 인덱스에 없는 티커**로 바꾸면 된다.

**4) 무위험 이자율 (FRED, 네트워크)**

다운로드는 **httpx**(긴 read 타임아웃) + **재시도**(`--fred-retries`, 기본 3). 행이 0이면 **`status: failed`**·exit code 1 (이전에는 completed 로 헷갈릴 수 있었음).

```bash
python3 src/main.py ingest-risk-free --lookback-years 3
```

느리거나 끊기면:

```bash
python3 src/main.py ingest-risk-free --lookback-years 1 --fred-timeout 600 --fred-retries 5
```

**7)·8) 전 보강 (복붙)** — `risk_free_rates_daily` 비어 있음 / `next_quarter` 실패 / 팩터 패널이 한 티커뿐일 때:

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

**액션 A — 무위험 적재(FRED)**

```bash
python3 src/main.py ingest-risk-free --lookback-years 1 --fred-timeout 600 --fred-retries 5
```

Supabase `risk_free_rates_daily` 행 수 확인. 회사 방화벽이 `fred.stlouisfed.org` 를 막으면 다른 네트워크/VPN에서 동일 명령.

**액션 B — 1분기(63거래일) 선행수익에 일봉 부족**

시그널일 이후 거래일이 충분히 쌓이도록 S&P 일봉 lookback 을 키운 뒤 선행·패널 재빌드:

```bash
python3 src/main.py ingest-market-prices --universe sp500_current --lookback-days 400
python3 src/main.py build-forward-returns --limit-panels 500
python3 src/main.py build-validation-panel --limit-panels 500
```

**액션 C — 팩터 패널 종목 수 늘리기 (Phase 3)**

워치리스트에 티커를 넣고 스냅샷·팩터까지 돌린 뒤 7)·8) 재실행:

```bash
python3 src/main.py compute-factors-watchlist
python3 src/main.py build-forward-returns --limit-panels 500
python3 src/main.py build-validation-panel --limit-panels 500
```

**5) 일봉 수집 (심볼 수 많음·시간 소요; 개발 시 `--start`/`--end` 또는 `MARKET_PRICE_LOOKBACK_DAYS`로 구간 축소)**

`sp500_proxy_candidates_v1` 은 **반드시 위 3) `build-candidate-universe` 를 먼저** 돌려 `universe_memberships` 에 행이 있어야 한다. (`refresh-universe` 만으로는 후보 유니버스가 생기지 않는다.)

```bash
python3 src/main.py ingest-market-prices --universe sp500_current --lookback-days 120
python3 src/main.py ingest-market-prices --universe sp500_proxy_candidates_v1 --lookback-days 120
```

**6) (선택) 메타 — Yahoo chart 전용 구현은 보통 빈 결과; 다른 프로바이더 붙이면 채워짐**

```bash
python3 src/main.py refresh-market-metadata --universe sp500_current
```

**7) 선행 수익률 → 검증 패널 (팩터 패널·스냅샷·가격·무위험이 갖춰져 있어야 함)**

```bash
python3 src/main.py build-forward-returns --limit-panels 500
python3 src/main.py build-validation-panel --limit-panels 500
```

**macOS에서 `refresh-universe`가 `SSL: CERTIFICATE_VERIFY_FAILED` 로 실패할 때**: `python3 -m pip install -r requirements.txt` 로 **`certifi`** 를 확보한 뒤 다시 실행한다(코드가 urllib TLS에 `certifi` 번들을 사용). 그래도 실패하면 python.org 설치본의 **Install Certificates.command** 실행을 고려.

**로컬/CI에서 외부 API 끄기**: `export MARKET_DATA_PROVIDER=stub` (유니버스 refresh는 스텁 목록만 적재).

### 회계 팩터 패널 (Phase 3)

`issuer_master`에 티커가 있고 `issuer_quarter_snapshots`에 행이 있어야 합니다.

#### Phase 3 실DB 확인 (액션별 복붙)

**전제**: Phase 3 마이그레이션 적용, 루트 `.env`에 Supabase 키, 해당 티커 CIK로 `issuer_quarter_snapshots`에 행이 있음.

**액션 1 — 프로젝트·가상환경·PYTHONPATH**

```bash
cd /Users/hyunminkim/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

**액션 2 — `issuer_quarter_factor_panels` 테이블 도달 + accruals 공식 sanity (`smoke-factors`, SEC 호출 없음)**

```bash
python3 src/main.py smoke-factors
```

**액션 3 — 단일 티커로 패널 적재 (`compute-factors-single`, DB 쓰기)**

```bash
python3 src/main.py compute-factors-single --ticker AAPL
```

**액션 4 — (선택) 방금 적재된 패널 JSON으로 확인**

```bash
python3 src/main.py show-factor-panel --ticker AAPL --limit 5
```

한 줄로 2→3만 이어서:

```bash
cd /Users/hyunminkim/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src && python3 src/main.py smoke-factors && python3 src/main.py compute-factors-single --ticker AAPL
```

```bash
python3 src/main.py compute-factors-watchlist
python3 src/main.py compute-factors-watchlist --sleep 1.0
```

팩터 공식 버전 (기본 `v1`, 환경변수 `FACTOR_VERSION` 또는 `--factor-version`):

```bash
python3 src/main.py compute-factors-single --ticker AAPL --factor-version v1
```

최근 패널 조회:

```bash
python3 src/main.py show-factor-panel --ticker NVDA --limit 5
```

단일 티커·워치리스트 배치는 `ingest_runs.run_type` = **`sec_factor_panel_build`** 로 남습니다.

### XBRL facts 추출 (단일 티커)

최근 **10-Q → 10-K** 순으로 XBRL이 있는 첫 공시를 고른 뒤 fact 적재 + 분기 스냅샷 upsert.

```bash
python3 src/main.py extract-facts-single --ticker NVDA
```

form 우선순만 바꾸려면:

```bash
python3 src/main.py extract-facts-single --ticker AAPL --forms 10-Q
```

### XBRL facts 워치리스트 배치

```bash
python3 src/main.py extract-facts-watchlist
python3 src/main.py extract-facts-watchlist --sleep 1.0
```

### 분기 스냅샷 재계산 (DB silver 기준)

이미 적재된 `silver_xbrl_facts`로 `issuer_quarter_snapshots`만 다시 채웁니다.

```bash
python3 src/main.py build-quarter-snapshots
python3 src/main.py build-quarter-snapshots --ticker NVDA --limit 5
```

- **고유 공시 수집**: 한 accession의 silver 행이 매우 많아서, 예전 구현은 API 첫 페이지만 읽으면 **서로 다른 공시가 1건으로만 잡히는** 경우가 있었다. 지금은 페이지를 넘기며 `--limit`개의 **서로 다른 (cik, accession)** 까지 모은 뒤 스냅샷을 만든다.

## Canonical mapping v1 (지원 범위)

- 모듈: [`src/sec/facts/concept_map.py`](src/sec/facts/concept_map.py)
- 지원 canonical: `revenue`, `net_income`, `operating_cash_flow`, `total_assets`, `total_liabilities`, `cash_and_equivalents`, `research_and_development`, `capex`, `gross_profit`, `shares_outstanding`.
- us-gaap(및 일부 dei) 태그 문자열 **정확 일치** 매핑. extension taxonomy·별칭은 이번 단계에서 광범위 지원하지 않음.
- **한계**: 동일 태그·다른 context/차원이 압축되면 `dedupe_key`로 구분되나, 스냅샷은 DEI fiscal focus에 맞는 행을 우선 선택한다.

## Quarter snapshot 생성 방식

1. `dei:DocumentFiscalYearFocus` / `dei:DocumentFiscalPeriodFocus`로 primary 분기 결정 (없으면 revenue 등에서 fallback).
2. `silver_xbrl_facts` 중 primary에 맞는 duration/instant 행을 canonical별로 하나씩 선택.
3. `snapshot_json`에 `filled_canonicals` / `missing_canonicals` 기록.

## 로컬에서 실제 워치리스트 ingest 1회 + DB 확인 (복붙 절차)

**전제**: Supabase SQL Editor에서 Phase 0 → Phase 1 → Phase 2 → **Phase 3** 마이그레이션을 실행했고, 루트 `.env`에 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `EDGAR_IDENTITY`가 채워져 있어야 합니다.

### 1) 터미널에서 한 번에 (macOS / zsh)

아래에서 첫 줄 `cd`만 본인 프로젝트 경로로 바꿉니다.

```bash
cd /Users/hyunminkim/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
```

### 2) 연결 확인 (순서 권장)

```bash
python3 src/main.py smoke-sec
python3 src/main.py smoke-db
```

- `smoke-sec` 실패: 네트워크·`EDGAR_IDENTITY` 확인.
- `smoke-db` 실패: `.env`의 Supabase URL/키·마이그레이션(테이블 존재) 확인.

### 3) 워치리스트 ingest 1회 (실제 SEC 호출 + DB 적재)

```bash
python3 src/main.py ingest-watchlist
```

티커 사이에 더 쉬고 싶으면 (초 단위):

```bash
python3 src/main.py ingest-watchlist --sleep 1.0
```

종료 시 터미널에 JSON 요약이 출력됩니다. `ingest_runs`에 이번 run이 남고, 티커별로 issuer / filing_index / raw / silver가 쌓입니다.

### 4) Supabase에서 행 확인

**방법 A — Table Editor**: Dashboard → **Table Editor** → `ingest_runs`, `issuer_master`, `filing_index`, `raw_sec_filings`, `silver_sec_filings` 순으로 열어 최근 행 확인.

**방법 B — SQL Editor**에서 아래를 붙여넣어 실행:

```sql
-- 최근 ingest run
select id, run_type, status, target_count, success_count, failure_count, started_at, completed_at
from ingest_runs
order by started_at desc
limit 5;

-- 건수 요약
select (select count(*) from issuer_master) as issuer_master_rows,
       (select count(*) from filing_index) as filing_index_rows,
       (select count(*) from raw_sec_filings) as raw_rows,
       (select count(*) from silver_sec_filings) as silver_rows;
```

Phase 2·3 테이블 건수 확인 예:

```sql
select (select count(*) from raw_xbrl_facts) as raw_xbrl,
       (select count(*) from silver_xbrl_facts) as silver_xbrl,
       (select count(*) from issuer_quarter_snapshots) as quarter_snapshots,
       (select count(*) from issuer_quarter_factor_panels) as factor_panels;
```

같은 명령을 다시 실행해도 **멱등** 정책상 raw/silver가 무한히 늘지 않고, issuer·filing_index는 upsert·갱신 위주입니다. 상세는 [`src/db/schema_notes.md`](src/db/schema_notes.md) 참고.

## 워치리스트 파일 형식

`config/watchlist.json` 예:

```json
{
  "tickers": ["NVDA", "MSFT", "AAPL"],
  "filings_per_issuer": 1
}
```

## Optional Arelle 검증 경로 (validation assist)

- 모듈: [`src/sec/validation/arelle_check.py`](src/sec/validation/arelle_check.py)
- 미설치 시 `validate_filing_identity`, `validate_xbrl_fact_presence`, `compare_statement_concept_presence` 등은 `status: skipped`.
- 설치되어 있어도 Phase 2는 **전체 인스턴스 대조·문장 단위 parity까지는 구현하지 않음** (`arelle_assist_pending` 등).

## 테스트

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
pytest
```

외부 네트워크 없이 mock 위주입니다.

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `SUPABASE_URL` | 예 | 프로젝트 URL |
| `SUPABASE_SERVICE_ROLE_KEY` | 예 | service role |
| `EDGAR_IDENTITY` | 예 | SEC 식별 |
| `WATCHLIST_PATH` | 아니오 | 워치리스트 JSON 경로 |
| `INGEST_TICKER_SLEEP_SEC` | 아니오 | 배치 티커 간 sleep (초) |
| `FACTOR_VERSION` | 아니오 | 팩터 패널 공식 버전 (기본 `v1`) |
| `OPENAI_API_KEY` | 아니오 | 예약 |
| `SENTRY_DSN` | 아니오 | 예약 |

## 프로젝트 구조 (요약)

```
config/watchlist.json
supabase/migrations/
src/
  main.py              # CLI 서브커맨드
  config.py
  watchlist_config.py
  db/
  factors/            # definitions, formulas, prior_period, panel_build
  sec/
    facts/              # concept_map, extract, normalize, pipeline
    ingest_pipeline.py
    ingest_company_sample.py
    watchlist_ingest.py
    facts_watchlist.py
    snapshot_build_run.py
    validation/arelle_check.py
  models/
  tests/
```

## 운영 문서

제품 스펙 → Cursor Agent Protocol → Plan Mode Roadmap → Phase Work Order 순으로 상위 문서를 우선합니다.
