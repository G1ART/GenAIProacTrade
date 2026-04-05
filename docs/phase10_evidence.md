# Phase 10 증거 (소스 레지스트리 · 프리미엄 오버레이 seam · 권리/계보)

## 권위 문서

루트 `.docx` 미수록 시: `docs/spec/tech500_factor_ai_architecture_blueprint_ko_v2.md`, `tech500_cursor_agent_protocol_ko.md`, `tech500_plan_mode_roadmap_ko.md`, `tech500_phase0_cursor_workorder_ko.md`.

## 마이그레이션

- `supabase/migrations/20250413100000_phase10_source_registry_overlays.sql`
- `outlier_casebook_entries.overlay_awareness_json`, `daily_watchlist_entries.overlay_awareness_json` 추가.

## 필수 CLI (재현)

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py smoke-source-adapters
python3 src/main.py export-source-roi-matrix
python3 src/main.py seed-source-registry
python3 src/main.py report-source-registry
python3 src/main.py report-overlay-gap
```

## A) 소스 레지스트리 샘플 `source_id` (시드 8건, 클래스 혼합)

| source_id | source_class | 비고 |
|-----------|--------------|------|
| `sec_edgar_xbrl_public` | public | 결정적 스파인 코어 |
| `fred_dtb3_public` | public | 무위험 레짐 입력 |
| `market_prices_yahoo_silver_eod` | public | EOD 조인(품질 한계 명시) |
| `earnings_call_transcripts_vendor_tbd` | premium | 자격 없음 |
| `analyst_estimates_vendor_tbd` | premium | 자격 없음 |
| `higher_quality_price_intraday_vendor_tbd` | proprietary | 자격 없음 |
| `operator_internal_research_notes` | private_internal | 플레이스홀더 |
| `partner_syndicated_feed_placeholder` | partner_only | 플레이스홀더 |

## B) ROI 행렬

- 코드 내장: `src/sources/reporting.py` 의 `OVERLAY_ROI_RANKED` 또는 `export-source-roi-matrix`.
- 순위: transcripts → estimates → higher_quality_price_or_intraday → options(선택).

## C) 어댑터 seam

- `src/sources/transcripts_adapter.py`, `estimates_adapter.py`, `price_quality_adapter.py` — `probe()`만으로 `not_available_yet`, 정규화 필드·권리 메타 문서화.
- 계약 타입: `src/sources/contracts.py`.

## D) 다운스트림 overlay 인지

- 케이스북·워치리스트 행에 `overlay_awareness_json` 스냅샷(`truth_spine_provenance`, `overlay_not_available_yet`, `overlay_used_sources` 등).
- 메시지 계약: `PREMIUM_OVERLAY_SEAMS_DEFAULT` (`src/message_contract/__init__.py`).

## 진실성

- 벤더 자격이 없으면 **가짜 데이터 없음**; `fetch_normalized`는 빈 리스트.
- 공개 스파인 테이블에 프리미엄 행을 **자동 병합하지 않음** (워크오더·`truth_spine_rule`).
