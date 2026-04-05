# Phase 9 증거 번들 (운영 가시성 + 연구 레지스트리 + Phase 8 실DB 마감)

## 문서 권위 (워크오더 0절)

저장소 루트의 `.docx` 대신 다음 Markdown 등가본을 사용함: `docs/spec/tech500_factor_ai_architecture_blueprint_ko_v2.md`, `docs/spec/tech500_cursor_agent_protocol_ko.md`, `docs/spec/tech500_plan_mode_roadmap_ko.md`, `docs/spec/tech500_phase0_cursor_workorder_ko.md`.

## 마이그레이션

- **파일**: `supabase/migrations/20250412100000_phase9_observability_research_registry.sql`
- **내용**: `operational_runs`, `operational_failures`; `hypothesis_registry` / `promotion_gate_events` 강화.

원격 DB에 미적용이면 `smoke-phase9-observability`가 `PGRST205`(테이블 없음)로 실패한다. **아래 실측은 마이그레이션 적용 후** 수집된 스냅샷이다.

---

## 실측 잠금 스냅샷 (Supabase 프로젝트, 2026-04-05 UTC 근처)

### Phase 8 파이프라인 핵심 ID

| 항목 | 값 |
|------|-----|
| `state_change_run_id` | `d9e455d8-9646-4d34-a30c-97950c6556e6` |
| `scanner_run_id` | `de476a50-ffc8-41ac-ab5f-0d09ea9c61dc` |
| `daily_signal_snapshots.id` (위 scanner_run 1:1) | `1c22f0b0-7ffc-4678-a074-5819b7720a9e` |
| `casebook_run_id` (최신, 동일 state_change 기준) | `be111443-ddba-4306-9f38-54a18732e0b2` |
| `casebook_run_id` (이전 실행) | `ce2a8ac2-92f5-4343-9698-f927a315720c` |
| 케이스북 `entries_created` | 165 (각 casebook run) |
| 스캐너 `candidates_scanned` | 200 |
| 스캐너 `watchlist_selected` | **0** (후보 클래스 전원 `insufficient_data`에 가까운 분포 → 게이트 통과 0, 설계상 허용) |
| `daily_watchlist_entries` 샘플 ID | **없음** (워치리스트 0건) |

### `export-casebook-samples` 산출물 (심각도 상위 10건, `regime_mismatch`)

경로: `docs/phase9_samples/latest/` — `manifest.json`, `casebook_run_id.txt`, `entries.json`

| `entry_id` | `ticker` | `outlier_type` |
|------------|----------|----------------|
| `b323fde0-5df6-46d3-99fe-b369cc741bd3` | DLTR | regime_mismatch |
| `b8939bc8-d201-42de-873f-00f7fbc84410` | BXP | regime_mismatch |
| `db3254a7-050d-41bd-9686-936b08b9cf63` | CSGP | regime_mismatch |

(나머지 7건은 동일 디렉터리 `manifest.json` 참조.)

### SQL로 확인한 동일 run 엔트리 샘플 (`unexplained_residual`, `created_at` 기준)

`casebook_run_id = be111443-ddba-4306-9f38-54a18732e0b2` (Supabase SQL B-3와 동일 10건):

| `outlier_casebook_entries.id` | `candidate_id` |
|-------------------------------|----------------|
| `a4a6cbd9-b5d0-4e1a-aa81-55e32a74b6ef` | `ba2a7e48-5c17-44bc-9142-582fcc03f717` |
| `b5a80c98-c891-4424-a1b8-ac35070f3435` | `0c4d475b-e0a4-4c2f-9b1c-8f5f383791c9` |
| `3e6900a6-b16e-4932-a7cd-cc41150922ce` | `e62e2adc-09d1-45a5-bddb-1e142559b2ce` |
| `d81835f3-f4f0-4992-8a95-9f53e138546d` | `0a0ee7fa-5cc1-4ae3-a067-70334021d186` |
| `9a1e6fa8-0fe1-447e-8962-abaa524b160a` | `03ba2fe7-3b5f-479c-a20a-2c1abeafed72` |
| `3ca7eede-ff9c-4c89-8cee-f6d74fe7519b` | `0a2935b3-bf3b-4dc6-b7cb-68a5c87d616f` |
| `bf6acd56-91fa-4f0a-b7fc-3e09444c375a` | `1b765cb4-a2fb-4194-bb48-0365aa738b3c` |
| `568c0192-a4fe-4708-a2fb-deb4b4b1c676` | `0f56efe0-1163-43e4-9765-3417841954bd` |
| `bfa9863c-99f2-4f55-a1c2-0607a7e92ea9` | `0d8c3644-9402-4aff-86cc-96fb19d052c6` |
| `f5b49ea2-3683-41fb-bd0d-9a42e9b900fd` | `0d46c1f6-f506-4216-bbe6-42b68a2dcdc7` |

> `export-casebook-samples` 기본 정렬(`outlier_severity` desc)과 SQL `order by created_at`이 다르므로 **엔트리 id 집합은 같아도 상위 10건 목록이 다를 수 있음** — 둘 다 유효한 실측 샘플이다.

---

## 연구 레지스트리 (시드 + 게이트 이벤트)

### `seed-phase9-research-samples` 실행 결과

- **출력**: `"created": []`, `"skipped"`: 두 제목 모두 — **이미 동일 제목 행이 있어 idempotent skip** (정상).

### `hypothesis_registry` (실측 행)

| `id` | `title` | `research_item_status` | `promotion_decision` | `rejection_reason` |
|------|---------|--------------------------|----------------------|--------------------|
| `8fd62a16-a55b-45e4-92c2-8fef71e61cd0` | [Phase9 sample] Social sentiment overlay (blocked) | `rejected` | `denied` | Unverified third-party feed; leakage and staleness risk unacceptable. |
| `441bf25c-407a-4e6e-a908-59c68431426b` | [Phase9 sample] Alt momentum window (sandbox review) | `sandbox_only` | `none` | null |

### `promotion_gate_events` (실측 행)

| `id` | `hypothesis_id` | `event_type` | `decision_summary` | `actor` |
|------|-----------------|--------------|-------------------|---------|
| `2b0df9fe-7554-4221-96a1-766d70deb49f` | `8fd62a16-a55b-45e4-92c2-8fef71e61cd0` | `rejection` | Not approved for experiment | `phase9_seed` |
| `39aa8569-8440-4cde-979e-b6b200956ca0` | `441bf25c-407a-4e6e-a908-59c68431426b` | `status_set` | Remain sandbox until leakage review completes | `phase9_seed` |

---

## `operational_runs` 샘플 (최근 5건, 실측)

| `id` | `run_type` | `component` | `status` | 비고 |
|------|------------|-------------|----------|------|
| `62e78c93-f062-4f86-a1dd-7859aa40f63b` | `ai_harness` | `investigation_memo_batch` | `empty_valid` | harness 입력 없음 → `trace_json.note`: `no_inputs_or_all_filtered` |
| `ed638a9e-7be7-4262-92bc-743dacb81dbe` | `daily_scanner` | `scanner_daily_build_v1` | `empty_valid` | 워치리스트 0, `scanner_run_id` 위 표와 동일 |
| `1de5d3b3-c357-40c8-9321-5ad5eaa0cd9f` | `outlier_casebook` | `casebook_build_v1` | `success` | `casebook_run_id` = `be111443-…` |
| `9fd54592-f3fa-4a79-8723-d4311a58fd9b` | `outlier_casebook` | `casebook_build_v1` | `success` | `casebook_run_id` = `ce2a8ac2-…` |
| `bf2d2d3f-79cc-40fd-a545-0b95399d1799` | `state_change` | `state_change_engine_v1` | `success` | `state_change_run_id` 위 표와 동일 |

`operational_failures`: 해당 구간 조회 시 **0건** (정상 가능).

---

## 재현 절차 (복붙, UUID 자리표시자 없음)

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py smoke-phase9-observability
python3 src/main.py seed-phase9-research-samples
python3 src/main.py report-research-registry --limit 50
python3 src/main.py build-outlier-casebook --universe sp500_current --candidate-limit 600
python3 src/main.py build-daily-signal-snapshot --universe sp500_current
python3 src/main.py report-daily-watchlist --universe sp500_current
python3 src/main.py export-casebook-samples --universe sp500_current --limit 10 --out-dir docs/phase9_samples/latest
python3 src/main.py report-run-health --limit 50
python3 src/main.py report-failures --limit 50
```

---

## 선택 후속 (메모 배치를 `empty_valid`가 아니게 하려면)

`investigation_memo_batch`가 입력 0이면 `empty_valid`로 남는다. 아래를 **같은 universe / run**에 대해 선행한다.

```bash
cd ~/GenAIProacTrade && source .venv/bin/activate && export PYTHONPATH=src
python3 src/main.py build-ai-harness-inputs --universe sp500_current --limit 500
python3 src/main.py generate-investigation-memos --universe sp500_current --limit 200
python3 src/main.py report-run-health --limit 10
```

---

## 메시지 계층 진실성

- `src/message_contract/__init__.py` 의 `MESSAGE_LAYER_TRUTH_GUARDS` — 포트폴리오/실행 금지, 휴리스틱 표기, 결손 가시성.
