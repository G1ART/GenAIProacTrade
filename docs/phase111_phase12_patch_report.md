# Phase 11.1 · Phase 12 패치 결과 보고서

**문서 기준일**: 2026-04-01  
**기능 패치 커밋**: `23678f0` — `feat(phase11.1+12): PIT transcript audit, registry truth, public-core cycle`  
**문서·보고서 커밋**: `62cd3ce` — `docs: Phase 11.1/12 patch report (tests, migrations, ops evidence)`  
**원격**: `https://github.com/G1ART/GenAIProacTrade.git` 브랜치 `main`

---

## 1. Git / 브랜치 · 동기화 상태

| 항목 | 값 |
|------|-----|
| Phase 11 단독 직전 | `107beb5` — `feat(phase11): FMP earnings transcript PoC, overlay wiring, watchlist enrichment` |
| 11.1+12 기능 반영 | `23678f0` |
| 보고서·증거 문서 정리 | `62cd3ce` |
| **2026-04-01 기준** | 로컬 `main` = `origin/main` = `62cd3ce` (`git push origin main` 완료) |

추가 머신에서 맞출 때:

```bash
cd /Users/hyunminkim/GenAIProacTrade
git checkout main
git pull origin main
git log -1 --oneline   # 기대: 62cd3ce (또는 그 이후 최신)
```

작업 트리에는 이번 패치와 무관한 **미추적** 디렉터리가 있을 수 있음: `docs/phase7_real_samples/latest/`, `docs/phase9_samples/latest/` (정책에 따라 커밋 여부 결정).

---

## 2. 변경 파일 요약 (기능 커밋 `23678f0`)

`git show 23678f0 --stat`: **18 files changed, 1100 insertions(+), 80 deletions(-)**

| 경로 | 역할 |
|------|------|
| `supabase/migrations/20250415100000_phase111_transcript_audit_pit.sql` | Phase 11.1: `raw_transcript_payloads_fmp_history` |
| `src/db/records.py` | raw 감사·PIT 조회·normalized 기간 조회·archive 헬퍼 |
| `src/scanner/transcript_enrichment.py` | 후보 `as_of_date` 기준 PIT-safe 보강 |
| `src/scanner/daily_build.py` | `transcript_enrichment` 에 as_of 전달 |
| `src/sources/transcripts_normalizer.py` | 전문 SHA-256 `revision_id`, `refresh_audit` |
| `src/sources/transcripts_ingest.py` | raw 감사, activation 동기화, 네트워크 시 inactive |
| `src/public_core/cycle.py`, `__init__.py` | 공개 코어 오케스트레이션 |
| `src/main.py` | ingest 차단 시 operational run, `run-public-core-cycle`, `report-public-core-cycle` |
| `src/tests/test_phase111_phase12.py` | 11.1+12 단위 테스트 |
| `src/tests/test_phase11_transcripts.py` | PIT·CLI·프로브 등 확장 |
| `docs/phase12_evidence.md`, `phase11_evidence.md` | 증거·동작 설명 |
| `docs/public_core_cycle/latest/README.md` | 생성물 디렉터리 안내 |
| `.gitignore` | `cycle_summary.json`, `operator_packet.md` 제외 |
| `HANDOFF.md`, `README.md`, `src/db/schema_notes.md` | 운영·스키마 문서 |

커밋 `62cd3ce`는 위 기능에 대한 **본 보고서**(`docs/phase111_phase12_patch_report.md`) 중심 정리.

---

## 3. 데이터베이스 / 마이그레이션 (“테이블 푸시”)

### 3.1 적용 순서

| 마이그레이션 파일 | Phase | 내용 |
|-------------------|-------|------|
| `20250414100000_phase11_transcripts_fmp_poc.sql` | 11 | `transcript_ingest_runs`, `raw_transcript_payloads_fmp`, `normalized_transcripts`, `daily_watchlist_entries.transcript_enrichment_json`, registry 시드 등 |
| `20250415100000_phase111_transcript_audit_pit.sql` | 11.1 | **`raw_transcript_payloads_fmp_history`** — upsert 전 raw 스냅샷(불변 감사) |

적용 방법 예시:

- Supabase **SQL Editor**에 각 파일 본문을 순서대로 실행하거나,
- CLI 사용 시 프로젝트 설정에 맞게 `supabase db push` / `supabase migration up` 등.

**원격 DB에 11.1 파일이 없으면** 런타임에서 `archive_raw_transcript_payload_fmp_before_upsert` 및 history insert 경로가 실패할 수 있으므로, Phase 11 적용 후 **반드시** `20250415100000_phase111_transcript_audit_pit.sql` 까지 적용해야 한다.

### 3.2 Phase 11.1 테이블 스키마 요약 (`raw_transcript_payloads_fmp_history`)

| 컬럼 | 설명 |
|------|------|
| `id` | UUID PK, `gen_random_uuid()` |
| `symbol`, `fiscal_year`, `fiscal_quarter` | 식별·조회 키 |
| `http_status` | 마지막 fetch HTTP 상태(선택) |
| `raw_response_json` | 스냅샷 본문(JSONB) |
| `fetched_at` | 스냅샷 시각 |
| `superseded_raw_payload_id` | FK → `raw_transcript_payloads_fmp.id` (on delete set null) |
| `ingest_run_id` | FK → `transcript_ingest_runs.id` (on delete set null) |

인덱스: `(symbol, fiscal_year, fiscal_quarter, fetched_at desc)` — 분기별 최신 히스토리 조회에 유리.

### 3.3 적용 확인용 SQL

```sql
select to_regclass('public.raw_transcript_payloads_fmp_history') as history_table;
select to_regclass('public.normalized_transcripts') as normalized_transcripts;

select id, symbol, fiscal_year, fiscal_quarter, fetched_at
from public.raw_transcript_payloads_fmp_history
order by fetched_at desc
limit 5;
```

ingest를 한 번 이상 돌린 뒤 history에 행이 쌓이는지 확인하면 end-to-end와 맞는다.

### 3.4 런타임·운영에서 관찰된 동작 (참고)

- `run-public-core-cycle` 성공 시 로컬에 `docs/public_core_cycle/latest/cycle_summary.json`, `operator_packet.md` 생성(`.gitignore`로 커밋 제외).
- `operational_runs` 에 `run_type = 'public_core_cycle'`, `component = 'run_public_core_cycle_v1'`, `status = 'success'` 등 기록 가능.
- State change 요약에서 후보가 전부 **`insufficient_data` / `gating_high_missingness`** 인 경우: **오케스트레이션 실패가 아니라** 입력·커버리지가 얇을 때의 **정상 범주** 출력(빈 워치리스트 허용 설계와 일치).

---

## 4. 테스트 결과 (로컬, 2026-04-01 재실행)

실행 디렉터리: `src/` (또는 `PYTHONPATH=src`).

### 4.1 Phase 11 / 11.1 / 12 타깃 스위트

```bash
cd /Users/hyunminkim/GenAIProacTrade/src
python -m pytest tests/test_phase111_phase12.py tests/test_phase11_transcripts.py -q
```

**결과**: **16 passed**, 약 1.4s

#### `test_phase111_phase12.py` (7개)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_normalize_revision_id_is_full_sha256` | 정규화 산출물의 `revision_id`가 SHA-256 전체 hex 길이(64) |
| `test_archive_raw_inserts_history_when_prior_exists` | 기존 raw가 있을 때 history insert(감사 경로) |
| `test_probe_marks_registry_inactive_when_not_configured` | 프로브 `not_configured` 시 registry `inactive` |
| `test_ingest_blocked_still_enters_operational_session` | FMP 키 없음 등 차단 시에도 operational 세션 + 실패 종료 |
| `test_run_public_core_cycle_empty_watchlist_still_ok` | 빈 워치리스트여도 사이클 `ok` |
| `test_run_public_core_cycle_fails_without_run` | 선행 state change run 없으면 `ok: false` |
| `test_phase12_cli_registered` | `run-public-core-cycle` / `report-public-core-cycle` CLI 등록 |

#### `test_phase11_transcripts.py` (9개)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_phase11_cli_registered` | Phase 11 트랜스크립트 관련 CLI 등록 |
| `test_classify_fmp_http_response` | FMP HTTP 응답 분류 |
| `test_overlay_availability_after_probe` | 프로브 이후 오버레이 가용성 |
| `test_normalize_fmp_payload_ok` | FMP 페이로드 정규화 성공 경로 |
| `test_transcript_enrichment_no_row` | 행 없을 때 보강 동작 |
| `test_pit_transcript_excludes_future_row` | PIT: 미래 행 제외 |
| `test_pit_transcript_no_anchor_excluded` | 앵커 날짜 없는 행 제외 |
| `test_run_fmp_probe_not_configured` | 프로브 미설정 |
| `test_run_fmp_probe_available` | 프로브 available 경로 |

### 4.2 전체 스위트

```bash
cd /Users/hyunminkim/GenAIProacTrade/src
python -m pytest tests/ -q
```

**결과**: **166 passed**, **3 warnings** (edgar `ChunkedDocument` deprecation 안내), 약 4.2s

---

## 5. 새 CLI

| 명령 | 설명 |
|------|------|
| `run-public-core-cycle` | 공개 코어 end-to-end + `docs/public_core_cycle/latest/` 번들 |
| `report-public-core-cycle` | 마지막 `cycle_summary.json` 재출력 |

(Phase 11 트랜스크립트 ingest/probe CLI는 Phase 11 커밋에서 이미 추가됨.)

---

## 6. Phase 11.1 동작 요약 (코드 관점)

1. **PIT**: 워치리스트 `transcript_enrichment_json` 은 `available_at` → `published_at` → `event_date` 중 첫 유효 날짜가 **후보 `as_of_date` 이하**인 정규화 행만 사용.
2. **ingest 차단**: `FMP_API_KEY` 없으면 세션 연 뒤 `finish_failed` (`configuration_error`), JSON에 `truthful_blocked` 등.
3. **Registry activation**: 프로브/ingest 결과가 `partial`·`available` 일 때만 `active`, 그 외 **`inactive`** 로 내려가 stale-active 방지.
4. **감사**: 동일 `(symbol, year, quarter)` 재 ingest 시 **이전 raw** 가 `raw_transcript_payloads_fmp_history` 에 남음.
5. **revision_id**: 트랜스크립트 전문 UTF-8 기준 **SHA-256 전체 hex**; `provenance_json.refresh_audit` 에 이전 normalized id / ingest_run 등.

---

## 7. Phase 12 동작 요약

최신(또는 지정) **completed `state_change_run`** 을 기준으로 **harness 입력 적재 → investigation memos → outlier casebook → daily scanner/watchlist** 를 순서대로 호출하고, `cycle_summary.json` 에 단계별 상태·경고·프리미엄 오버레이 **요약만** 담아 **결정적 스코어 경로와 분리**한다. 스캐너 단계만 하드 실패가 아니면 전체 `ok` 로 마칠 수 있으며, 빈 워치리스트는 실패로 간주하지 않는다.

---

## 8. 알려진 잔여 / 주의

- **`docs/public_core_cycle/latest/`** 생성물은 `.gitignore` 로 **커밋 제외** (로컬·운영 증거용).
- 미추적 샘플 디렉터리(`docs/phase7_real_samples/latest/` 등)는 별도 정책.

---

## 9. 재현 체크리스트

1. 마이그레이션 11 + 11.1 적용 확인 (§3.3).
2. `python -m pytest tests/ -q` → 166 passed.
3. `python3 src/main.py run-public-core-cycle --universe sp500_current` → 선행 state change 존재 시 `ok: true` 기대.
4. `operational_runs` 에서 `public_core_cycle` success 조회.

---

*이후 커밋이 쌓이면 상단 SHA·테스트 개수만 갱신하면 된다.*
