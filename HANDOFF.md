# HANDOFF — Phase 7.1 마감 (하네스 하드닝)

## HEAD / 마이그레이션 진실

- **패치 적용 후** `git rev-parse HEAD` 로 SHA 확인·기록 (main-only 운영).
- **마이그레이션 순서**: `20250409100000_phase7_ai_harness_minimum.sql` → `20250410100000_phase71_harness_hardening.sql`.

## Phase 7.1에서 닫힌 것

1. **클레임 단위 추적**: `investigation_memo_claims` 확장 — `claim_id`, `claim_role`, `statement`, `support_summary`, `counter_evidence_summary`, `trace_refs`, `needs_verification`, `verdict`, `claim_revision`, `candidate_id`; `(memo_id, claim_id)` 유니크.
2. **재실행 정책**: 동일 `input_payload_hash` + `GENERATION_MODE` → **in-place** 메모 갱신 + 해당 메모의 클레임 **전부 삭제 후 재삽입**; 해시/모드 불일치 또는 `--force-new-memo-version` → `memo_version = max+1` 신규 행.
3. **리뷰 큐 의미**: `reviewed` / `needs_followup` / `blocked_insufficient_data` 는 메모 재생성 시 **유지**; 신규 큐 행은 referee 통과 시 `pending`, 실패 시 `needs_followup`. `status_reason`, `reviewed_at` 컬럼.
4. **Referee 강화**: 반론 차원 누락, synthesis의 `thesis_preserved`/`challenge_preserved`, 한계 서술 과소(heuristic), thesis 내 허용 컨텍스트 밖 수치, 기존 매매·과장·반론·uncertainty·합성 검사 유지.
5. **CLI**: `set-review-queue-status`, `export-phase7-evidence-bundle`; `generate-investigation-memos` 에 `--candidate-ids`, `--force-new-memo-version`.
6. **스펙 MD**: `docs/spec/*.md` + `scripts/docx_to_spec_md.py` (원본 docx는 `~/Downloads`).
7. **실데이터 번들 절차**: `docs/phase7_evidence_bundle.md`, 출력 디렉터리 `docs/phase7_real_samples/` (JSON은 운영자 실행으로 생성; 가짜 샘플 금지).
8. **테스트**: `src/tests/test_harness_phase71.py` + 기존 Phase 7 테스트 갱신.

## Founder north-star (문서·구조, Phase 7과 동일)

- 대립·협력 하네스, R&D 레인 분리, 평가 사다리(설명≠예측), 지평·레짐 툴킷 훅, 크로스 도메인 철학 — `docs/phase7_future_seams.md`, `docs/spec/` 블루프린트 참고.

## 운영 명령 (요약)

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py smoke-harness
python3 src/main.py build-ai-harness-inputs --universe sp500_current --limit 200
python3 src/main.py generate-investigation-memos --universe sp500_current --limit 200
python3 src/main.py export-phase7-evidence-bundle --from-run <RUN_UUID> --sample-n 3 --out-dir docs/phase7_real_samples/latest
python3 src/main.py set-review-queue-status --candidate-id <UUID> --status reviewed --reason "audit note"
python3 src/main.py report-review-queue --limit 50
```

## 의도적으로 아직 안 한 것 (다음 단계 전 금지/비범위)

- LLM 연동, UI/대시보드, 알림, 실거래, 포트폴리오, walk-forward 실구현, 연구 샌드박스 조합 엔진, 벤치마크 마케팅.

## 남은 리스크

- **마이그레이션 미적용** 환경에서는 새 클레임 컬럼 insert 실패.
- Referee **수치·한계** 검사는 휴리스틱이며 오탐/미탐 가능.
- `export-phase7-evidence-bundle` 은 DB에 harness 입력이 없는 후보는 스킵/불완전할 수 있음 — 먼저 `build-ai-harness-inputs` 확인.

## 다음 권장 단계

- 운영 DB에서 번들 생성 후 `manifest.json` 의 실제 `candidate_id` 3건을 이슈/핸드오프에 첨부.
- (선택) LLM은 **문장 보강**만, 수치는 입력에서만 인용.

---

## Universe Backfill (변경 없음)

- 마이그레이션 `20250408100000_backfill_orchestration.sql`, 모듈 `src/backfill/`, CLI `smoke-backfill`, `backfill-universe`, `report-backfill-status`.
- README `## Full Universe Backfill`, `## Staged Coverage Expansion`.

## Phase 6 (변경 없음)

- `20250407100000_phase6_state_change_engine.sql`, `src/state_change/`, `run-state-change`, `report-state-change-summary`, `smoke-state-change`.
