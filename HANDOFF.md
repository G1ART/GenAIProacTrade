# HANDOFF — Phase 6–7 + Universe Backfill

## Phase 7 완료 범위 (AI Harness Minimum)

- **마이그레이션** `20250409100000_phase7_ai_harness_minimum.sql`: `ai_harness_candidate_inputs`, `investigation_memos`, `investigation_memo_claims`, `operator_review_queue`, 스텁 `hypothesis_registry`, `promotion_gate_events`.
- **입력 계약** `ai_harness_input_v1`: `harness/input_materializer.py` — candidate + score + components + issuer + factor panel + validation panel join + filing handles + Phase 5 요약(연구 맥락만, 피처 아님).
- **메모 스키마** `investigation_memo_v1`: `memo_builder/pipeline.py` — deterministic_signal_summary, thesis, **mandatory** strongest_counter_argument(대체해석·데이터 부족·오염/레짐·무의미 가능성·반증 조건), synthesis(이견 보존), uncertainty_labels, evidence_blocks, limitations, source_trace, referee_result.
- **역할** `roles/deterministic_agents.py`: ThesisAgent / ChallengeAgent / SynthesisAgent (현재 **결정적 스켈레톤**; LLM 연결은 이후 옵션).
- **RefereeGate** `referee/gate.py`: 매매·포트폴리오·과장 수익 문구 차단; 반론·uncertainty·합성 이견 검사.
- **배치** `harness/run_batch.py`: 메모 생성 → claims 적재 → `operator_review_queue` upsert (`pending`).
- **DB** `src/db/records.py`: harness CRUD, `fetch_latest_factor_validation_run_id`.
- **CLI**: `smoke-harness`, `build-ai-harness-inputs`, `generate-investigation-memos`, `report-review-queue`.
- **문서**: `README.md` Phase 7 절, `docs/founder-surface-contract.md`, `docs/phase7_future_seams.md`, `src/db/schema_notes.md` (Phase 7 테이블).
- **pytest**: `src/tests/test_harness_phase7.py`.

### Founder north-star (문서·구조에 반영된 것)

- **대립적이되 협력적인 하네스**: thesis vs challenge를 합성에서 평탄화하지 않음.
- **내부 R&D / discovery 레인**: `hypothesis_registry`·`research_lab/`·`phase7_future_seams.md`로 **프로덕션 스코어링과 분리**.
- **장기 벤치마 포부**: 시뮬레이션 엔진은 **구현 안 함**; 평가 규율은 “설명 ≠ 예측력”으로 문서화.
- **지평·레짐별 툴킷**: `routing_policy_doc.py` + `phase7_future_seams.md`에 훅만.
- **크로스 도메인**: 어댑터 철학은 문서만; 본 패치에서 ingestion 확장 없음.

### 운영 명령 (end-to-end)

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py smoke-harness
python3 src/main.py build-ai-harness-inputs --universe sp500_current --limit 200
python3 src/main.py generate-investigation-memos --universe sp500_current --limit 200
python3 src/main.py report-review-queue --limit 50
```

`--run-id <UUID>` 로 특정 `state_change_runs` 지정 가능.

### Phase 7에서 의도적으로 안 한 것

- LLM 프로바이더 연동, UI, 알림, 실거래, 포트폴리오, 백테스트 실적, 자동 승격, 연구 샌드박스 실구현, walk-forward 엔진, 도메인 어댑터 코드.

### 남은 리스크

- 메모 본문이 **템플릿 기반**이라 운영 품질은 후속 LLM·편집 레이어에서 강화 필요.
- Supabase **upsert** API가 환경에 따라 `on_conflict` 문자열 요구가 다를 수 있음 — 실패 시 마이그레이션/클라이언트 버전 확인.
- `factor_market_validation_panels`의 forward 컬럼 **존재 여부**는 입력의 `coverage_flags`에만 반영; 피처로 사용하지 않음.

### 다음 권장 단계

- 운영자 피드백 후 Referee 규칙·메모 톤 조정.
- (선택) OpenAI 등으로 Challenge/Thesis **문장만** 보강하되 수치는 입력에서만 인용.
- 리뷰 큐 상태 전환을 위한 소규모 CLI 또는 내부 도구.

---

## Universe Backfill 오케스트레이션

- **마이그레이션** `20250408100000_backfill_orchestration.sql`: `backfill_orchestration_runs`, `backfill_stage_events`, RPC `backfill_coverage_counts()`
- **모듈** `src/backfill/`: `universe_resolver`, `backfill_runner`, `join_diagnostics`, `coverage_report`, `status_report`, `cli_report`, `normalize`, `pilot_tickers`, **`staged_cohort`**, **`checkpoint_report`**, **`sparse_diagnostics`**
- **Staged coverage expansion**: `backfill-universe --coverage-stage stage_a|stage_b|full --issuer-target N` — `sp500_current` 티커 **오름차순** 고정 코호트(무작위 없음), 부족 시 `combined_largecap_research_v1` 보강. SEC/스냅/팩터 한도는 full과 동일(`--mode full` 권장). 완료 시 `coverage_checkpoint` JSON·`--write-coverage-checkpoint PATH`. `report-backfill-status --include-coverage-checkpoint`, `--include-sparse-diagnostics`, `--write-sparse-diagnostics PATH`.
- **설정** `config/backfill_pilot_tickers_v1.json` — pilot 30종(유니버스와 교집합)
- **CLI**: `smoke-backfill`, `backfill-universe`, `report-backfill-status`
- **pytest** `src/tests/test_backfill_orchestration.py`, `src/tests/test_staged_coverage.py`
- **문서**: README `## Full Universe Backfill`, `## Staged Coverage Expansion`

**재시도**: `summary_json.retry_tickers_all` + `--retry-failed-only --from-orchestration-run-id <UUID>`

---

## Phase 6 완료 범위 (state change)

- **마이그레이션** `20250407100000_phase6_state_change_engine.sql`: `state_change_runs`, `issuer_state_change_components`, `issuer_state_change_scores`, `state_change_candidates`
- **모듈** `src/state_change/`
- **CLI**: `run-state-change`, `report-state-change-summary`, `smoke-state-change`
- **pytest**: `src/tests/test_state_change_phase6.py`

**하지 않는 것**: `factor_market_validation_panels`의 forward 라벨을 state change **feature**로 사용 (금지).

---

## 이번 저장소에서 최근 추가·수정한 주요 파일 (Phase 7)

- `supabase/migrations/20250409100000_phase7_ai_harness_minimum.sql`
- `src/harness/**`, `src/research_lab/__init__.py`, `src/harness/routing_policy_doc.py`
- `src/harness/run_batch.py`
- `src/db/records.py`, `src/main.py`
- `src/tests/test_harness_phase7.py`
- `docs/founder-surface-contract.md`, `docs/phase7_future_seams.md`
- `README.md`, `HANDOFF.md`, `src/db/schema_notes.md`
