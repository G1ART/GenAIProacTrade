# Phase 11 증거 번들 — FMP earnings call transcript PoC

## 선택 벤더

- **Financial Modeling Prep (FMP)** — 단일 바인딩. 엔드포인트 패밀리: `api/v3/earning_call_transcript/{symbol}`.
- **환경**: `FMP_API_KEY`, 선택 `TRANSCRIPTS_PROVIDER=fmp` (기본 `fmp`).

## 재현 커맨드 (로컬)

```bash
cd /path/to/GenAIProacTrade
source .venv/bin/activate
export PYTHONPATH=src
python3 src/main.py probe-transcripts-provider
python3 src/main.py ingest-transcripts-sample --symbol AAPL --year 2020 --quarter 3
python3 src/main.py report-transcripts-overlay-status
python3 src/main.py export-transcript-normalization-sample --ticker AAPL
python3 -m pytest tests/test_phase11_transcripts.py -q
```

- **자격 없음**: `probe-transcripts-provider`는 `truthful_blocked`, `operational_runs`에 `configuration_error`로 남을 수 있음(구현: `finish_failed`).
- **자격 있음**: `source_overlay_availability.availability`가 `partial` 또는 `available`로 갱신될 수 있음; `source_overlay_runs`, `transcript_ingest_runs`, `operational_runs`에 흔적.

## `partial` vs `available` (트랜스크립트 오버레이)

- **available**: HTTP 200 + 세그먼트에 실질 텍스트 + 정규화 `normalization_status=ok`.
- **partial**: API 경로는 동작하나(또는 정규화는 됐으나) 빈 리스트/빈 세그먼트/형식 한계 등으로 **완전 본문 확보는 아님**.

## 다운스트림

- **일일 워치리스트** (`run_daily_scanner_build`): `transcript_enrichment_json` + 정규화 행이 메시지 준비 상태일 때만 `message_why_matters`에 **한 문장** 컨텍스트(본문 전체 비주입). 스코어·랭킹 **불변**.

## DB 샘플 쿼리 (SQL Editor)

```sql
select id, run_type, component, status, started_at
from operational_runs
where run_type = 'transcript_overlay'
order by started_at desc
limit 5;

select * from source_overlay_availability where overlay_key = 'earnings_call_transcripts';

select id, provider_code, operation, probe_status, status, created_at
from transcript_ingest_runs
order by created_at desc
limit 5;

select id, ticker, fiscal_period, normalization_status,
       length(transcript_text) as text_len, ingested_at
from normalized_transcripts
order by ingested_at desc
limit 5;
```

## 의도적 미구현

- 제2 트랜스크립트 벤더, 대규모 배치 ingest UI, NLP 요약 전면 개편, 스코어 가중.
