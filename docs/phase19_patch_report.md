# Phase 19 패치 보고 — Public Repair Campaign & Revalidation Loop

## 한 줄 요약

공개 수리(Phase 18) 이후 **재검증 게이트**를 통과하면 Phase 16 캠페인을 강제 재실행하고, **전후 생존 분포·캠페인 권고**를 영구 비교 행으로 남긴 뒤 **`continue_public_depth` / `consider_targeted_premium_seam` / `repair_insufficient_repeat_buildout`** 중 하나만 기계적으로 선택한다. 이로써 “진단·수리만 했다”에서 “수리가 연구 결과를 바꿨는지 증명 가능한 아티팩트가 있다”로 넘어간다.

## HEAD / 변경 파일 (워크스페이스 기준)

- **마이그레이션**: `supabase/migrations/20250422100000_phase19_public_repair_campaign.sql`
- **신규 패키지**: `src/public_repair_campaign/` (`constants`, `comparisons`, `decision_policy`, `service`, `__init__`)
- **수정**: `src/db/records.py`, `src/main.py`, `src/research_registry/promotion_rules.py`, `HANDOFF.md`, `README.md`, `src/db/schema_notes.md`
- **신규 테스트**: `src/tests/test_phase19.py` (14개)
- **문서**: `docs/phase19_evidence.md`, 본 파일

정확한 git SHA는 로컬 저장소에서 `git rev-parse HEAD`로 확인한다.

## 신규 CLI

| 커맨드 | 역할 |
|--------|------|
| `smoke-phase19-public-repair-campaign` | Phase 19 테이블 도달 |
| `run-public-repair-campaign` | 전체 루프 실행 |
| `report-public-repair-campaign` | 런·스텝·결정·비교 조회 |
| `compare-repair-revalidation-outcomes` | 저장된 비교 행 조회 |
| `export-public-repair-decision-brief` | JSON + Markdown 브리프 |
| `list-repair-campaigns` | 프로그램별 런 목록 |

## 테스트 카운트

- `src/tests/test_phase19.py`: 14 passed (전체 스위트: 로컬에서 `pytest src/tests` 실행)

## 거버넌스

- `promotion_rules.describe_production_boundary` 및 `assert_no_auto_promotion_wiring`에 Phase 19(`public_repair_campaign`) 비참조를 명시한다.

## 완료 보고서

- 운영 클로징·테스트 결과·체크리스트: [phase19_completion_report.md](./phase19_completion_report.md)
