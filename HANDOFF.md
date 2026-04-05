# HANDOFF — Phase 9 (가시성 · 실패 추적 · 연구 레지스트리 · Phase 8 실DB 마감)

## HEAD / 마이그레이션

- 패치 후 `git rev-parse HEAD` 로 SHA 기록.
- **Phase 9 마이그레이션**: `20250412100000_phase9_observability_research_registry.sql` (`20250411100000_phase8` 이후).
- 원격 Supabase에 미적용이면 `operational_runs` 부재(`PGRST205`)로 Phase 9 스모크·로깅 INSERT 전부 실패 — **먼저 SQL 적용**.

## Phase 9에서 닫힌 것

1. **운영 실행 감사**: `operational_runs` + `operational_failures` — `run_type`, `component`, `status`(success / warning / failed / **empty_valid**), 행 수, `trace_json`, 실패 시 `failure_category`(configuration_error, db_migration_missing, source_data_missing, empty_but_valid, heuristic_low_confidence, execution_error, other).
2. **코드 연동**: `OperationalRunSession` — `run-state-change`, `generate-investigation-memos`, `build-outlier-casebook`, `build-daily-signal-snapshot` 가 종료 시 DB에 실행 메타를 남김. `tokens_used` 는 스키마에 두고 **미사용 시 null**.
3. **연구 레지스트리**: `hypothesis_registry` 컬럼 강화 + `promotion_gate_events`에 `hypothesis_id`, `event_type`, `decision_summary`, `rationale`, `actor`. **프로덕션 스코어링은 레지스트리를 읽지 않음** (`research_registry.promotion_rules.assert_no_auto_promotion_wiring` 테스트).
4. **CLI**: `smoke-phase9-observability`, `report-run-health`, `report-failures`, `report-research-registry`, `seed-phase9-research-samples`.
5. **모듈**: `src/observability/` (`run_logger`, `reporting`), `src/research_registry/` (`registry`, `promotion_rules`, `reporting`), `src/db/records.py` 헬퍼.
6. **메시지 진실성**: `message_contract.MESSAGE_LAYER_TRUTH_GUARDS` (포트폴리오/실행·과장 성과·결손·휴리스틱 표기).
7. **문서**: `docs/phase9_evidence.md`, `docs/phase9_samples/`, `src/db/schema_notes.md`, README Phase 9 절.
8. **테스트**: `src/tests/test_phase9_observability.py`.

## Phase 8 실DB 증거 (현재 환경)

- **백엔드·CLI는 Phase 8과 동일**하며, 케이스북/스캐너 실행 시 이제 `operational_runs`에도 흔적이 남음.
- **이 저장소가 연결한 원격 DB**에는 2026-04-05 기준 Phase 9 테이블이 없어 `smoke-phase9-observability`가 `PGRST205`로 실패함. 따라서 **실제 `casebook_run_id` / `scanner_run_id` / 샘플 entry ID 를 이 패치만으로 채우지는 못함** — 마이그레이션 적용 후 `docs/phase9_evidence.md` 절차대로 채울 것.

## 운영 명령 (요약)

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py smoke-phase9-observability
python3 src/main.py seed-phase9-research-samples
python3 src/main.py build-outlier-casebook --universe sp500_current --candidate-limit 600
python3 src/main.py build-daily-signal-snapshot --universe sp500_current
python3 src/main.py report-daily-watchlist
python3 src/main.py export-casebook-samples --state-change-run-id <RUN_UUID> --limit 20 --out-dir docs/phase9_samples/latest
python3 src/main.py report-run-health --limit 50
python3 src/main.py report-failures --limit 50
python3 src/main.py report-research-registry --limit 50
```

## 가시성이 동작하는 방식

- 각 주요 CLI는 `OperationalRunSession`으로 `operational_runs` 행을 열고, 정상/경고/의도적 0출력(`empty_valid`)/실패를 구분해 마감한다.
- 하드 예외는 컨텍스트 종료 시 `failed` + `operational_failures` 행.
- `finish_*` 누락 시 `no_finish_called` 로 실패 처리(버그 탐지).

## 연구 레지스트리 / 승격 경계

- 항목은 `hypothesis_registry`에만 존재; 상태는 `proposed` … `promoted_to_candidate_logic` 등 DB CHECK와 일치.
- 승격/거부는 `promotion_gate_events`에 감사 로그; **자동으로 팩터 패널·state_change 로직에 주입되지 않음**.
- 거버넌스 문장 요약: `research_registry.promotion_rules.describe_production_boundary()`.

## 의도적 비범위 (Phase 9)

- 코크핏/UI, 알림 대량 발송, 매매·포트폴리오·실행, 벤치마크 마케팅, 레지스트리→프로덕션 자동 승격, 광범위 유료 데이터 연동.

## 다음 권장 단계

- 원격 DB에 Phase 9 마이그레이션 적용 후 Phase 8 CLI 재실행 → `docs/phase9_evidence.md`에 실 ID 기록.
- (선택) `operational_run_events` 같은 세부 이벤트 스트림 확장.

---

## Phase 8 (요약, 코드 유지)

- 케이스북/스캐너/메시지 계약: `README.md` Phase 8 절, `docs/phase8_evidence.md`.

## Phase 7 / 7.1 / Phase 6 이전

- README 및 이전 HANDOFF 요약과 동일.
