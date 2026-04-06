# Phase 17 패치 리포트 — Public Substrate Depth Expansion

## Git

- **구현 직전 로컬 `main` tip (참고)**: `e822e9c265b2e1f3c83d2db15d01b26f0dbbd985`
- **커밋 후 HEAD**: `46c84e5` (Phase 17 본체: `f273b88` — `feat(phase17): public substrate depth coverage, expansion, uplift evidence`)

## 변경 파일

- `supabase/migrations/20250420100000_phase17_public_depth.sql` — `public_depth_runs`, `public_depth_coverage_reports`, `public_depth_uplift_reports`
- `src/public_depth/` — `constants`, `diagnostics`, `uplift`, `expansion`, `readiness`, `__init__`
- `src/db/records.py` — Phase 17 CRUD, `fetch_public_core_cycle_quality_runs_for_universe`
- `src/main.py` — smoke + 5개 필수 CLI + `export-public-depth-brief`
- `src/research_registry/promotion_rules.py` — `public_depth` 비침투 문구·가드
- `src/tests/test_phase17.py`
- `docs/phase17_evidence.md`, `HANDOFF.md`, `README.md`, `src/db/schema_notes.md`, 본 파일

## 마이그레이션

- `20250420100000_phase17_public_depth.sql`

## 신규 CLI

- `smoke-phase17-public-depth`
- `run-public-depth-expansion`
- `report-public-depth-coverage` (`--persist` 선택)
- `report-quality-uplift` (`--persist` 선택)
- `report-research-readiness`
- `export-public-depth-brief`

## 테스트

- 전체 `pytest`: **219 passed** (본 패치 기준).

## 한 줄 요약

이제 운영자는 유니버스별로 **레시피 검증용 PIT 조인 행 수·품질 쉐어·제외 사유**를 스냅샷으로 저장하고, **선택적 공개 파이프라인 빌드 전후**의 델타를 DB에 남긴 뒤, 프로그램 단위로 **Phase 15/16 재실행이 의미 있는지**를 `report-research-readiness`로 1차 판단할 수 있다. 제품 스코어 경로는 여전히 이 레이어를 읽지 않는다.
