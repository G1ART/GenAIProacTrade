# Phase 9 증거 번들 (운영 가시성 + 연구 레지스트리 + Phase 8 실DB 마감)

## 문서 권위 (워크오더 0절)

저장소 루트의 `.docx` 대신 다음 Markdown 등가본을 사용함: `docs/spec/tech500_factor_ai_architecture_blueprint_ko_v2.md`, `docs/spec/tech500_cursor_agent_protocol_ko.md`, `docs/spec/tech500_plan_mode_roadmap_ko.md`, `docs/spec/tech500_phase0_cursor_workorder_ko.md`.

## 마이그레이션

- **파일**: `supabase/migrations/20250412100000_phase9_observability_research_registry.sql`
- **내용**: `operational_runs`, `operational_failures`; `hypothesis_registry` / `promotion_gate_events` 강화.

원격 Supabase에 이 파일이 **적용되기 전**에는 `smoke-phase9-observability` 및 `operational_runs` 기반 CLI가 실패한다.

## 실DB 스모크 (이 환경에서의 결과)

**실행 시각(로컬)**: 2026-04-05

- 명령: `export PYTHONPATH=src && python3 src/main.py smoke-phase9-observability`
- **결과**: 실패 — PostgREST `PGRST205` — `public.operational_runs` 가 스키마 캐시에 없음 (마이그레이션 미적용).
- **의존성 블로커**: 원격 DB에 Phase 9 SQL 미적용.

따라서 아래 ID·카운트는 **플레이스홀더가 아니라 비어 있음** — 마이그레이션 적용 후 동일 절차로 채울 것.

### 마이그레이션 적용 후 필수 절차 (재현)

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py smoke-phase9-observability
python3 src/main.py seed-phase9-research-samples
python3 src/main.py build-outlier-casebook --universe sp500_current --candidate-limit 600
python3 src/main.py build-daily-signal-snapshot --universe sp500_current
python3 src/main.py report-daily-watchlist
python3 src/main.py export-casebook-samples --state-change-run-id <STATE_CHANGE_RUN_UUID> --limit 20 --out-dir docs/phase9_samples/latest
python3 src/main.py report-run-health --limit 50
python3 src/main.py report-failures --limit 50
python3 src/main.py report-research-registry --limit 50
```

기록할 항목:

| 항목 | 값 (마이그레이션 후 기입) |
|------|---------------------------|
| `casebook_run_id` | |
| `scanner_run_id` | |
| 샘플 `outlier_casebook_entries.id` | |
| 샘플 `daily_watchlist_entries` 식별자 | |
| casebook 행 수 / 워치리스트 행 수 | |
| `operational_runs.id` 샘플 (≥3 컴포넌트) | |

샘플 JSON 덤프는 `docs/phase9_samples/` (README 참고).

## 연구 레지스트리 샘플 (시드 CLI)

- `seed-phase9-research-samples`: 제목 기준 idempotent.
  - 한 건: `sandbox_only` + 게이트 이벤트.
  - 한 건: `rejected` + `rejection_reason` + 거부 게이트 이벤트.
- 프로덕션 스코어링(`state_change.runner`)은 레지스트리를 **import/조회하지 않음** — 테스트 `assert_no_auto_promotion_wiring`.

## 메시지 계층 진실성

- `src/message_contract/__init__.py` 의 `MESSAGE_LAYER_TRUTH_GUARDS` — 포트폴리오/실행 금지, 휴리스틱 표기, 결손 가시성.
