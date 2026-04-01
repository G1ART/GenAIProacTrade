# HANDOFF — Phase 1 완료 시점

## 현재 완료 범위

- `issuer_master`, `filing_index`, `ingest_runs` 테이블 및 마이그레이션
- 파이프라인: issuer upsert → filing_index upsert → raw(불변) → silver(rev1 idempotent)
- `config/watchlist.json` + `watchlist_config.py` 기반 `ingest-watchlist`
- CLI: `ingest-single`, `ingest-watchlist`, `smoke-sec`, `smoke-db`
- Arelle 스켈레톤 (`src/sec/validation/arelle_check.py`, 미설치 시 skip)
- pytest 확장 (issuer/filing_index/ingest_run/watchlist/pipeline/워치리스트 JSON)
- README·schema_notes·`.env.example`(플레이스홀더만) 갱신

## 이번 패치에서 생성·수정한 주요 파일

- `supabase/migrations/20250402120000_phase1_issuer_filing_ingest_runs.sql`
- `config/watchlist.json`
- `src/watchlist_config.py`, `src/sec/ingest_pipeline.py`, `src/sec/watchlist_ingest.py`
- `src/sec/validation/arelle_check.py`, `src/sec/validation/__init__.py`
- `src/db/records.py` (대폭 확장), `src/db/schema_notes.md`
- `src/sec/ingest_company_sample.py`, `src/main.py`
- `src/tests/test_phase1_*.py`, `test_watchlist_ingest.py`, `test_ingest_pipeline_flow.py`, `test_watchlist_config.py` 및 `test_smoke_ingest.py` 수정
- `README.md`, `HANDOFF.md`, `.env.example`

## 아직 남은 리스크

- SEC rate limit·재시도·백오프는 여전히 최소 수준 (sleep만).
- SIC/거래소는 edgartools `Company`에 따라 누락될 수 있음 (nullable).
- **보안**: 예전에 `.env.example`에 실제 키가 들어갔던 적이 있다면 **Supabase service role 키 회전**을 권장합니다.

## Phase 2 진입 전 확인사항 (제안)

- [ ] Phase 1 마이그레이션까지 Supabase에 적용됨
- [ ] `ingest-single`·`ingest-watchlist`가 대표님 환경에서 실제 SEC+DB로 한 번씩 성공
- [ ] Table Editor에서 `issuer_master` / `filing_index` / `ingest_runs` 행 확인
- [ ] 동일 `ingest-watchlist` 재실행 시 raw 중복 없음·filing_index·issuer 갱신만 되는지 확인
- [ ] Git에 `.env` 및 service role 미커밋

## 대표님이 직접 해야 하는 작업

1. Supabase에 **Phase 1** 마이그레이션 SQL 실행 (Phase 0 다음 순서).
2. `.env` 유지 (`.env.example`은 플레이스홀더만 유지).
3. 아래 명령으로 로컬 검증.

## 실행 확인 결과 (에이전트 환경)

- `pytest`: **23 passed** (네트워크 미사용; `test_watchlist_config`는 저장소 내 JSON 사용)
