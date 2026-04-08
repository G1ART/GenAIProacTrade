# Phase 28 패치 보고 (Provider metadata & factor panel materialization)

## 목적

프로바이더 메타데이터를 **실제로 채우거나**, 채울 수 없을 때 **명시적 차단·계측**으로 “0행인데 완료” 위장을 막는다. 레지스트리 `factor_panel_missing` 심볼을 **분기 스냅샷·factor·validation** 관점으로 세분하고, 상한이 있는 수리 CLI를 제공한다.

## 수정 요약

| # | 대상 | 내용 |
|---|------|------|
| 1 | `market.providers.yahoo_chart_provider` | `fetch_market_metadata`: 차트 구간(약 75일) 일봉으로 `avg_daily_volume`, `as_of_date`, `exchange` 채움. |
| 2 | `market.price_ingest` | `run_market_metadata_hydration_for_symbols`, `run_market_metadata_refresh`: `provider_rows_returned`, upsert 시도/스킵/재조회 누락 카운터; 프로바이더 0행 시 `status=blocked`, `blocked_reason=provider_returned_zero_metadata_rows`. |
| 3 | `phase28.factor_materialization` | `report_factor_panel_materialization_gaps`, `run_factor_panel_materialization_repair` (CIK 상한). |
| 4 | `phase28.orchestrator` | 메타 수화 수리 + 팩터 물질화 수리 + 전후 기판·메타 플래그·레지스트리 롤업. |
| 5 | `phase28.review` | 번들 → `phase28_provider_metadata_and_factor_panel_review.md`. |
| 6 | `main.py` | `report-factor-panel-materialization-gaps`, `run-factor-panel-materialization-repair`, `run-phase28-provider-metadata-and-panel-repair`, `write-phase28-provider-metadata-review`. |
| 7 | 테스트 | `src/tests/test_phase28_provider_metadata_and_factor_panel.py`. |
| 8 | `HANDOFF.md` | Phase 28 절·CLI·테스트 카운트 갱신. |

## 비목표

거버넌스·프리미엄 자동 오픈·품질 임계 변경·제네릭 전 유니버스 스프린트 전용 로직 추가.

## 관련 문서

- 실측 클로즈아웃: `docs/phase28_evidence.md`
- 운영 리뷰·번들: `docs/operator_closeout/phase28_provider_metadata_and_factor_panel_review.md`, `…_bundle.json`
