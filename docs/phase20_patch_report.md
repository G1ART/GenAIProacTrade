# Phase 20 패치 보고 — Repair Iteration Manager & Escalation Gate

## 한 줄 요약

반복 Phase 19 런을 **시리즈·트렌드 스냅샷**으로 영구화하고, 결정적 플래토·에스컬레이션 정책으로 **공개 심화 / 반복 수리 / 프리미엄 발견 궤도** 중 하나만 고른다. 동시에 **`latest` 선택자**로 운영자 UUID 체인을 줄였다.

## 변경 요약

- **마이그레이션**: `supabase/migrations/20250423100000_phase20_repair_iteration.sql`
- **신규**: `src/public_repair_iteration/` (`constants`, `resolver`, `escalation_policy`, `service`, `__init__`)
- **수정**: `src/db/records.py`, `src/main.py`, `src/research_registry/promotion_rules.py`, `HANDOFF.md`, `README.md`, `src/db/schema_notes.md`
- **테스트**: `src/tests/test_phase20.py` (11개)
- **문서**: `docs/phase20_evidence.md`, `docs/phase20_completion_report.md`(운영 클로징·검증 표), 본 파일

## 신규 CLI

| 커맨드 | 역할 |
|--------|------|
| `smoke-phase20-repair-iteration` | 테이블 스모크 |
| `run-public-repair-iteration` | Phase 19 1회 + 멤버·에스컬레이션 적재 |
| `report-public-repair-iteration-history` | 시리즈/멤버/결정 이력 |
| `report-public-repair-plateau` | 활성 시리즈 기준 재계산(비삽입) |
| `export-public-repair-escalation-brief` | JSON+MD |
| `list-public-repair-series` | 시리즈 목록 |
| `report-latest-repair-state` | 최근 런+시리즈 요약 |
| `report-premium-discovery-readiness` | `open_targeted_premium_discovery` 여부 |

## Phase 19 CLI 보강

- `run-public-repair-campaign`: `--program-id latest` (+ `--universe`)
- `report-public-repair-campaign` / `compare-*` / `export-public-repair-decision-brief`: `--repair-campaign-id latest` 시 `--program-id` 필요; export는 완료 런 우선.

## 테스트

- `test_phase20`: 11 passed; 전체 `src/tests`: 253 passed (로컬 기준).

## 거버넌스

- `promotion_rules` 및 `state_change.runner` 비참조에 `public_repair_iteration` 포함.
