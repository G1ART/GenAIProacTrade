# GenAIProacTrade — Phase 0–1 (SEC truth spine)

미국 SEC 공시 메타데이터를 **issuer / filing identity / raw / silver** 로 분리해 Supabase에 쌓는 Python 워커입니다. Phase 1에서 워치리스트 배치 ingest·`ingest_runs` 감사·idempotency를 강화했습니다. 팩터·AI·가격 데이터는 포함하지 않습니다.

## Phase 1 목표

- **Issuer 중심** 운영: `issuer_master`에 CIK canonical, 티커는 관측값.
- **Filing identity** 독립: `filing_index`로 공시 존재 여부를 raw와 별도 조회.
- **감사**: `ingest_runs`로 배치 실행별 성공/실패·메타 보존.
- **워치리스트** 소규모 다종목 ingest (순차·rate-limit 친화).
- **Arelle**: `src/sec/validation/arelle_check.py` 스켈레톤만 (미설치 시 skip).

## 데이터 계층

| 계층 | 테이블 | 설명 |
|------|--------|------|
| Issuer identity | `issuer_master` | CIK 유니크, 티커·회사명·SIC·거래소 등 |
| Filing identity | `filing_index` | `(cik, accession_no)` 유니크 |
| Raw truth | `raw_sec_filings` | 원문 JSON, **불변** |
| Normalized | `silver_sec_filings` | 정규화 요약, `revision_no` |
| Audit | `ingest_runs` | run_type, status, 성공/실패 건수 |

상세 idempotency 정책은 [`src/db/schema_notes.md`](src/db/schema_notes.md) 참고.

## Idempotency 정책 (한 줄 요약)

- **raw**: 동일 `(cik, accession_no)` 이미 있으면 insert 안 함 (덮어쓰기 없음).
- **filing_index**: 동일 키면 메타·`last_seen_at` 갱신.
- **silver**: Phase 1은 `revision_no=1`만; 이미 있으면 insert 안 함.
- **issuer**: CIK 기준 upsert, `first_seen_at` 유지.

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

### 스모크

```bash
python3 src/main.py smoke-sec
python3 src/main.py smoke-db
```

- `smoke-sec`: SEC에 접속 (네트워크 필요).
- `smoke-db`: Supabase `issuer_master`에 대한 단순 select.

## 로컬에서 실제 워치리스트 ingest 1회 + DB 확인 (복붙 절차)

**전제**: Supabase SQL Editor에서 Phase 0 → Phase 1 마이그레이션을 이미 실행했고, 루트에 `.env`에 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `EDGAR_IDENTITY`가 채워져 있어야 합니다.

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

같은 명령을 다시 실행해도 **멱등** 정책상 raw/silver가 무한히 늘지 않고, issuer·filing_index는 upsert·갱신 위주입니다. 상세는 [`src/db/schema_notes.md`](src/db/schema_notes.md) 참고.

## 워치리스트 파일 형식

`config/watchlist.json` 예:

```json
{
  "tickers": ["NVDA", "MSFT", "AAPL"],
  "filings_per_issuer": 1
}
```

## Optional Arelle 검증 경로

- 모듈: `src/sec/validation/arelle_check.py`
- Arelle 미설치 시 `validate_filing_identity` 등은 `status: skipped` 반환.
- Phase 2+에서 실제 XBRL 교차검증을 붙일 때 사용.

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
  sec/
    ingest_pipeline.py
    ingest_company_sample.py
    watchlist_ingest.py
    validation/arelle_check.py
  models/
  tests/
```

## 운영 문서

제품 스펙 → Cursor Agent Protocol → Plan Mode Roadmap → Phase Work Order 순으로 상위 문서를 우선합니다.
