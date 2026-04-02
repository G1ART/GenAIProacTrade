# HANDOFF — Phase 4 완료 시점

## 현재 완료 범위

- **마이그레이션** `20250405100000_phase4_market_validation.sql`: `universe_memberships`, `market_symbol_registry`, `raw_market_prices_daily`, `silver_market_prices_daily`, `market_metadata_latest`, `risk_free_rates_daily`, `forward_returns_daily_horizons`, `factor_market_validation_panels`
- **Provider 추상화**: `src/market/providers/base.py`, `stub_provider.py`, `yahoo_chart_provider.py`, `src/market/provider_factory.py` (`MARKET_DATA_PROVIDER`)
- **파이프라인**: `universe_refresh.py`, `candidate_universe_build.py`, `price_ingest.py`, `risk_free_ingest.py`, `forward_returns_run.py`, `validation_panel_run.py`, `signal_date.py`, `forward_math.py`, `risk_free_fred.py`
- **DB**: `src/db/records.py` Phase 4 CRUD/upsert/smoke
- **CLI**: `refresh-universe`, `build-candidate-universe`, `ingest-market-prices`, `refresh-market-metadata`, `ingest-risk-free`, `build-forward-returns`, `build-validation-panel`, `smoke-market`, `smoke-validation`
- **시드**: `config/sp500_proxy_candidates_v1.json` (**비공식 프록시 후보**, 공식 S&P 후보 아님)
- **문서**: `README.md`, `src/db/schema_notes.md`, `.env.example`
- **pytest**: **69 passed** (기존 + Phase 4, 네트워크 없음 기본)

## Phase 5 진입 제안 기준

- [ ] Supabase에 **Phase 4** SQL 적용 완료
- [ ] `refresh-universe`로 `sp500_current` 행 확인 + `build-candidate-universe`로 `sp500_proxy_candidates_v1` 확인
- [ ] `ingest-risk-free` + `ingest-market-prices`(적절한 lookback) 후 `silver_market_prices_daily`에 주요 심볼 데이터 확인
- [ ] `build-forward-returns` / `build-validation-panel` 성공·`factor_market_validation_panels` 샘플 행 확인
- [ ] `signal_available_date`·raw/excess 정의가 샘플 종목에서 설명 가능한지 검토
- [ ] `.env`·service role 미커밋

## 대표님이 직접 해야 하는 작업

1. Supabase SQL Editor에서 `20250405100000_phase4_market_validation.sql` 실행 (Phase 3 다음).
2. `export PYTHONPATH=src` 후 `python3 src/main.py smoke-market` / `smoke-validation`.
3. 네트워크 허용 환경에서 `refresh-universe` → `ingest-risk-free` → `ingest-market-prices`(구간 조절) → `build-forward-returns` → `build-validation-panel` 순으로 실데이터 검증.

## 알려진 리스크 / 한계

- **거래일 캘린더**: 주말만 제외, NYSE 공휴일 미반영 → 시그널·지평 종가가 실제 휴장과 어긋날 수 있음.
- **Yahoo/위키**: 비공식·변경 가능; 위키 HTML 파서는 표 구조 변경 시 깨질 수 있음.
- **무위험 근사**: 구간 평균 연율화 + `(n/252)` 지수 근사; 재무·리스크 모델 수준의 정밀도 아님.
- **메타**: chart-only 프로바이더는 `market_metadata_latest`가 비어 있을 수 있음(의도된 MVP).
- **유니버스 동일 as_of 재실행**: `universe_memberships` 유니크로 insert 충돌 가능.

## 이번 패치에서 추가·수정한 주요 파일

- `supabase/migrations/20250405100000_phase4_market_validation.sql`
- `src/market/**`, `config/sp500_proxy_candidates_v1.json`
- `src/db/records.py`, `src/main.py`
- `src/tests/test_market_phase4.py`
- `README.md`, `HANDOFF.md`, `src/db/schema_notes.md`, `.env.example`
