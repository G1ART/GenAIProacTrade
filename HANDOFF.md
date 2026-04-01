# HANDOFF — Phase 0 완료 시점

## 현재 완료 범위

- Python 워커 스캐폴딩 (`src/`), config / db / sec / models / tests 분리
- 필수 환경변수 검증 및 `.env.example`
- Supabase용 `raw_sec_filings`, `silver_sec_filings` 마이그레이션 SQL
- edgartools 기반 티커 샘플 1건 메타데이터 → raw JSON + silver 요약 적재
- pytest 12건 (config, normalize, ingest mock, payload shape)
- README에 실행·마이그레이션·테스트 방법 정리

## 이번 패치에서 생성·수정한 파일

- 루트: `README.md`, `HANDOFF.md`, `.gitignore`, `.env.example`, `requirements.txt`, `pytest.ini`
- `supabase/migrations/20250401000000_phase0_raw_silver_sec_filings.sql`
- `src/main.py`, `src/config.py`, `src/logging_utils.py`
- `src/db/__init__.py`, `src/db/client.py`, `src/db/records.py`, `src/db/schema_notes.md`
- `src/sec/__init__.py`, `src/sec/normalize.py`, `src/sec/ingest_company_sample.py`
- `src/models/__init__.py`, `src/models/raw_filing.py`, `src/models/silver_filing.py`
- `src/tests/conftest.py`, `src/tests/test_config.py`, `src/tests/test_normalize.py`, `src/tests/test_smoke_ingest.py`

## 아직 남은 리스크

- **실제 Supabase·SEC 연동**은 대표님 환경에서만 검증됨; CI/스테이징 없음
- edgartools·의존성 트리가 무겁고, SEC rate limit·네트워크 실패 시 재시도 정책은 Phase 0 최소 수준
- `silver`의 `form` 컬럼은 canonical 문자열 위주; 원문 form은 raw `payload_json`에 보존
- Python 3.9 + 시스템 LibreSSL 환경에서 urllib3 경고가 나올 수 있음 (동작에는 영향 없을 수 있으나 추후 Python 업그레이드 권장)

## Phase 1 진입 전 확인사항

- [ ] Supabase에 마이그레이션 적용 완료
- [ ] `.env`에 실제 키 설정 후 `PYTHONPATH=src python3 src/main.py --ticker AAPL` 성공
- [ ] Table Editor에서 `raw_sec_filings` / `silver_sec_filings` 행 확인
- [ ] `.env` / service role 키가 Git에 커밋되지 않았는지 확인

## 대표님이 직접 해야 하는 작업

1. `.env.example` → `.env` 복사 후 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `EDGAR_IDENTITY` 입력
2. Supabase SQL 에디터에서 마이그레이션 파일 실행
3. 로컬에서 venv 생성, `pip install -r requirements.txt`, 샘플 ingest 명령 실행
4. (선택) Git 원격 저장소 생성 후 첫 커밋 — **비밀값 제외** 확인

## 실행 확인 결과 (에이전트 환경)

- `pytest`: **12 passed** (외부 API 미호출)
- 실제 Supabase/SEC 라이브 호출은 이 환경에서 대표님 자격증명 없이 수행하지 않음
