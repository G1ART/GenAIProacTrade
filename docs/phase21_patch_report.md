# Phase 21 — Iteration governance and selector completion

**Date:** 2026-04-07

## Migration

- Apply `supabase/migrations/20250424100000_phase21_iteration_governance.sql` (governance_audit_json + one open series per program/universe/policy for active/paused).

## Selectors

- `latest`, `latest-success`, `latest-for-program`, `latest-compatible` (needs series context; CLI resolves active series when possible).
- `from-latest-pair`: use `resolve-repair-campaign-pair` CLI or `resolve_repair_campaign_latest_pair`.
- `latest-active-series`: `resolve_iteration_series_id` for advance/override flows.

## Lifecycle CLI

- `pause-public-repair-series`, `resume-public-repair-series`, `close-public-repair-series`

## Tests

- `src/tests/test_phase21_iteration_governance.py`: three escalation branches, infra exclusion, resolver, runner boundary, CLI 등록 — **10 tests**.
- Full suite: `pytest src/tests -q` — **263 passed** (local, 2026-04-07; `edgar` DeprecationWarning 3건).

## Operational verification (2026-04-07)

운영 DB에 Phase 21 마이그레이션 적용 후, 아래가 실제 CLI로 확인됨.

| Step | Evidence |
|------|----------|
| 골든 패스 | `advance-public-repair-series` 실행 완료 (활성 시리즈·캠페인/attach·멤버 append·플래토·브리프) |
| 시리즈 ID 출처 | `public_repair_iteration_series.id` — `advance` JSON/`list-public-repair-series` 등에서 확인한 UUID를 `--series-id`에 사용 |
| `pause-public-repair-series` | `ok: true`, `status: "paused"` (PATCH 200) |
| `resume-public-repair-series` | `ok: true`, `status: "active"` |
| `close-public-repair-series` | `ok: true`, `status: "closed"` |
| 단위 테스트 | `pytest src/tests/test_phase21_iteration_governance.py -q` → 10 passed |
| 전체 테스트 | `pytest src/tests -q` → 263 passed |
| 원격 동기화 | `git push origin main`: `550961a..28026fb` |

**운영 메모:** 예시로 사용된 시리즈 UUID `02119b7d-504e-4ad1-80d2-bb7fe5d94fb1`는 위 라이프사이클 시퀀스 후 **closed** 상태. 이후 동일 프로그램/유니버스/정책 키로 반복하려면 `advance` 등으로 **새 시리즈**가 생성·활성화된다(부분 유니크 인덱스: active/paused 1슬롯).

## Git (this workspace)

- **3d956e9ece1fbd5ecc9722dc16d3acc83c853a7f** (`3d956e9`) — `Phase 21: iteration governance, repair selectors, infra quarantine, advance CLI`.
- **28026fb** — 문서/HANDOFF/patch report 정리; **origin/main**에 반영됨 (2026-04-07). 이후 amend 시 `git rev-parse HEAD`로 갱신.

## Linked Supabase (MCP 참고)

- MCP에 연결된 프로젝트 마이그레이션 목록은 로컬 파일명(`20250424100000_…`)과 다를 수 있음. **이 저장소의 Phase 21 DDL은 `supabase/migrations/20250424100000_phase21_iteration_governance.sql`을 대상 DB에 적용**하면 됨.

## Golden path CLI

- `advance-public-repair-series --program-id latest --universe U --out path/stem`

## Production boundary

- `state_change.runner` must not reference `public_repair_iteration` or `public_repair_campaign` (see tests).
