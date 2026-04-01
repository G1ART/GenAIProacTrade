# GenAIProacTrade — Phase 0

미국 SEC 공시 메타데이터를 **원본(raw)** 과 **정규화(silver)** 로 나누어 Supabase에 쌓는 Python 워커의 최소 뼈대입니다. Phase 0는 완성 제품이 아니라 이후 Phase(issuer master, 팩터 엔진, AI harness)를 올릴 **source-of-truth spine** 입니다.

## 현재 구현 범위

- 환경변수 로딩 및 필수 키 검증 (`src/config.py`)
- Supabase service-role 클라이언트 (`src/db/client.py`)
- `raw_sec_filings` / `silver_sec_filings` 테이블용 SQL 마이그레이션 (`supabase/migrations/`)
- edgartools로 티커 1개의 **최근 공시 1건** 메타데이터 수집 및 DB 적재 (`src/sec/ingest_company_sample.py`)
- 최소 정규화 규칙 (`src/sec/normalize.py`)
- pytest: config / normalize / ingest(mock) / Supabase payload 형태 검증 (`src/tests/`)

## 아직 구현하지 않은 것

- 팩터 계산, 백테스트, state-change 엔진, AI 에이전트
- Railway 배포, 알림, UI
- 대량 백필·스케줄 잡
- issuer master / 다중 소스 ingest

## 사전 요구사항

- Python **3.9+** (3.9에서도 동작하도록 타입 힌트 구성)
- [Supabase](https://supabase.com) 프로젝트 (URL + **service_role** 키)
- SEC [EDGAR](https://www.sec.gov/os/accessing-edgar-data) 정책에 맞는 `EDGAR_IDENTITY` (이름 또는 이메일)

## 로컬 설정

```bash
cd /path/to/GenAIProacTrade
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env 를 편집해 실제 SUPABASE_* , EDGAR_IDENTITY 를 채움 (비밀값은 Git에 올리지 말 것)
```

edgartools 데이터·HTTP 캐시는 프로젝트 루트의 `.edgar_cache` 아래로 맞춰 둡니다 (`~/.edgar` 의존 완화).

### 문제 해결: `hishel` / `FileStorage` / 티커 조회 실패

`module 'hishel' has no attribute 'FileStorage'` 또는 `Both data sources are unavailable` 가 나오면, **hishel 1.x** 가 깔린 경우가 많습니다. `requirements.txt` 에서 `hishel<1` 을 고정했으므로 아래로 맞춰 설치하세요.

```bash
python3 -m pip install -r requirements.txt
```

## Supabase 마이그레이션 적용 순서

1. Supabase 대시보드 → **SQL Editor**
2. `supabase/migrations/20250401000000_phase0_raw_silver_sec_filings.sql` 파일 내용을 붙여 넣고 실행

또는 Supabase CLI를 쓰는 경우:

```bash
supabase db push
```

(로컬에 CLI와 프로젝트 연결이 이미 구성되어 있어야 합니다.)

## 샘플 ingest 실행

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
PYTHONPATH=src python3 src/main.py --ticker AAPL
```

다른 티커:

```bash
PYTHONPATH=src python3 src/main.py --ticker MSFT
```

성공 시 JSON으로 `raw_inserted` / `silver_inserted` 등 요약이 출력됩니다. 동일 `accession`은 raw/silver 각각 idempotency 규칙에 따라 재실행 시 insert를 건너뛸 수 있습니다.

## 테스트 실행

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
pytest
```

외부 네트워크 없이 동작하는 단위/모킹 테스트만 포함합니다. SEC·Supabase에 실제로 붙는 검증은 위 **샘플 ingest** 명령으로 수동 확인합니다.

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `SUPABASE_URL` | 예 | 프로젝트 URL |
| `SUPABASE_SERVICE_ROLE_KEY` | 예 | 서버(워커)용 service role 키 |
| `EDGAR_IDENTITY` | 예 | SEC 요청 시 식별 문자열 |
| `OPENAI_API_KEY` | 아니오 | 이후 Phase용 (Phase 0 미사용) |
| `SENTRY_DSN` | 아니오 | 예약 |
| `EDGAR_LOCAL_DATA_DIR` | 아니오 | 캐시 경로 (미설정 시 `.edgar_cache`) |

## 프로젝트 구조 (요약)

```
GenAIProacTrade/
  README.md
  HANDOFF.md
  .env.example
  requirements.txt
  pytest.ini
  supabase/migrations/
  src/
    main.py
    config.py
    logging_utils.py
    db/
    sec/
    models/
    tests/
```

## 운영 문서

상위 기준: 제품 스펙 → Cursor Agent Protocol → Plan Mode Roadmap → Phase 0 Work Order. 구현 판단이 어긋나면 상위 문서를 우선합니다.
