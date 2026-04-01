# HANDOFF — Phase 3 완료 시점

## 현재 완료 범위

- **`issuer_quarter_factor_panels`** 테이블 + 마이그레이션 `20250404100000_phase3_factor_panels.sql`
- **팩터 레지스트리 v1**: `src/factors/definitions.py`
- **공식 v1**: `src/factors/formulas.py` (accruals, gross_profitability, asset_growth, capex_intensity, rnd_intensity, financial_strength_score_v1)
- **Prior resolver**: `src/factors/prior_period.py` (Q1–Q4, FY 체인만; 동일 기간 다 accession 시 `filed_at` 최신)
- **패널 조립**: `src/factors/compute_panel.py`, **파이프라인·ingest_runs**: `src/factors/panel_build.py` (`sec_factor_panel_build`)
- **DB 접근**: `src/db/records.py` (snapshots 조회, factor panel insert/exists, ticker→cik)
- **CLI**: `compute-factors-single`, `compute-factors-watchlist`, `smoke-factors`, `show-factor-panel`
- **pytest**: **58 passed** (공식·prior·패널 멱등·E2E mock, 네트워크 없음)
- **문서**: `README.md`, `src/db/schema_notes.md`, `.env.example` (`FACTOR_VERSION` 설명)

## 이번 패치에서 생성·수정한 주요 파일

- `supabase/migrations/20250404100000_phase3_factor_panels.sql`
- `src/factors/__init__.py`, `definitions.py`, `formulas.py`, `prior_period.py`, `compute_panel.py`, `panel_build.py`
- `src/db/records.py`, `src/main.py`
- `src/tests/test_prior_period.py`, `test_factor_formulas.py`, `test_factor_panel_build.py`, `test_phase3_e2e_mock.py`
- `README.md`, `HANDOFF.md`, `src/db/schema_notes.md`, `.env.example`

## 아직 남은 리스크

- 스냅샷 `fiscal_period`가 `UNSPECIFIED` 등이면 prior 체인이 끊겨 평균자산·성장률·레버리지 개선 팩터가 null이 되기 쉬움 (의도된 동작; `coverage_json` 확인).
- 스냅샷이 한 분기만 있으면 prior 의존 팩터 대부분 null.
- **보안**: service role 키가 유출된 적 있으면 회전 권장.

## Phase 4 진입 전 확인사항 (제안)

- [ ] Phase 3 마이그레이션 Supabase 적용
- [ ] `compute-factors-single --ticker …` 실환경 성공·`issuer_quarter_factor_panels` 행 확인
- [ ] 동일 명령 재실행 시 기존 행 스킵(멱등)·`ingest_runs`에 `sec_factor_panel_build` 기록
- [ ] `coverage_json` / `quality_flags_json`에 null 이유가 남는지 샘플 검토
- [ ] Git에 `.env` 미커밋

## 대표님이 직접 해야 하는 작업

1. Supabase에 **Phase 3** SQL 실행 (Phase 2 다음).
2. `export PYTHONPATH=src` 후 `python3 src/main.py smoke-factors`
3. 스냅샷이 있는 티커로 `python3 src/main.py compute-factors-single --ticker AAPL`

## 실행 확인 결과 (에이전트 환경)

- `pytest`: **58 passed**
