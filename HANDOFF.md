# HANDOFF — Phase 5 완료 시점

## 현재 완료 범위

- **마이그레이션** `20250406100000_phase5_factor_validation_research.sql`: `factor_validation_runs`, `factor_validation_summaries`, `factor_quantile_results`, `factor_coverage_reports`
- **연구 모듈**: `src/research/validation_registry.py`, `universe_slices.py`, `standardize.py`, `metrics.py`, `quantiles.py`, `summaries.py`, `validation_runner.py`, `cli_report.py`
- **DB**: `src/db/records.py` — 검증 패널 심볼 조회, 팩터 패널 맵, 검증 run·자식 insert, smoke-research, `report-factor-summary` 조회
- **CLI**: `run-factor-validation`, `report-factor-summary`, `smoke-research`
- **문서**: `README.md`(Phase 5 목적·슬라이스·미구현·복붙), `src/db/schema_notes.md`
- **pytest**: **81 passed** (기존 + Phase 5, 네트워크 없음 기본)

## Phase 6 진입 제안 기준

- [ ] Supabase에 **Phase 5** SQL 적용 완료
- [ ] `smoke-research` 성공
- [ ] `build-validation-panel` 후 `run-factor-validation`(최소 한 유니버스·한 지평) 성공·`factor_validation_summaries` 샘플 확인
- [ ] `report-factor-summary`로 Spearman·coverage·분위 요약이 사람이 읽을 수 있는지 확인
- [ ] `.env`·service role 미커밋 유지

## 대표님이 직접 해야 하는 작업

1. SQL Editor에서 `20250406100000_phase5_factor_validation_research.sql` 실행 (Phase 4 다음).
2. `export PYTHONPATH=src` 후 `python3 src/main.py smoke-research`.
3. Phase 4 파이프라인으로 `factor_market_validation_panels`를 채운 뒤 `run-factor-validation` 실행.

## 알려진 리스크 / 한계

- **표본**: 워치리스트만 팩터가 있으면 S&P 슬라이스에서 패널 행이 거의 없을 수 있음.
- **OLS / 상관**: 단면 기술통계; 다중비교·구조적 변동 미보정; **robust SE·FM·패널 회귀 미구현**.
- **분위**: 소표본 시 분위 수 자동 축소; 극소 표본은 분위 행 없음.
- **커버리지 누락 이유**: `coverage_json`·`quality_flags` 기반 휴리스틱; 완전 감사 분해는 아님.

## 이번 패치에서 추가·수정한 주요 파일

- `supabase/migrations/20250406100000_phase5_factor_validation_research.sql`
- `src/research/**`
- `src/db/records.py`, `src/main.py`
- `src/tests/test_research_phase5.py`
- `README.md`, `HANDOFF.md`, `src/db/schema_notes.md`
