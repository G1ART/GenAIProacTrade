# Phase 11.1 · Phase 12 패치 결과 보고서

**문서 기준일**: 2026-04-06  
**메인 패치 커밋**: `23678f0` — `feat(phase11.1+12): PIT transcript audit, registry truth, public-core cycle`

---

## 1. Git / 브랜치

| 항목 | 값 |
|------|-----|
| 패치 **직전** (Phase 11 단독 끝) | `107beb5323bfc2fc1e1c9ef46a524068edc295fc` |
| 패치 **직후** (11.1+12) | `23678f0f14bf9a96f5bab083364cce8495fb7fdc` |
| 원격 | `https://github.com/G1ART/GenAIProacTrade.git` `main` |

**로컬 ↔ GitHub `main` 동기화**는 이 환경에서 인증 없이 `git fetch`/`pull`이 실패할 수 있으므로, 아래를 **본인 터미널**에서 실행하세요.

```bash
cd /Users/hyunminkim/GenAIProacTrade
git checkout main
git pull origin main
git status
git log -1 --oneline
# 기대: HEAD 가 origin/main 과 동일, 작업 트리는 추적 파일 기준 깨끗함
```

이미 `23678f0` 를 푸시한 상태라면 `git pull` 은 “Already up to date” 수준으로 끝납니다.

---

## 2. 변경 파일 요약 (커밋 `23678f0`)

`git show 23678f0 --stat`: **18 files changed, 1100 insertions(+), 80 deletions(-)**

| 경로 | 역할 |
|------|------|
| `supabase/migrations/20250415100000_phase111_transcript_audit_pit.sql` | Phase 11.1: `raw_transcript_payloads_fmp_history` |
| `src/db/records.py` | raw 감사·PIT 조회·normalized 기간 조회 등 |
| `src/scanner/transcript_enrichment.py` | 후보 `as_of_date` 기준 PIT-safe 보강 |
| `src/scanner/daily_build.py` | `transcript_enrichment` 에 as_of 전달 |
| `src/sources/transcripts_normalizer.py` | 전문 SHA-256 `revision_id`, `refresh_audit` |
| `src/sources/transcripts_ingest.py` | raw 감사, activation 동기화, 네트워크 시 inactive |
| `src/public_core/cycle.py`, `__init__.py` | 공개 코어 오케스트레이션 |
| `src/main.py` | ingest 차단 시 operational run, `run-public-core-cycle`, `report-public-core-cycle` |
| `src/tests/test_phase111_phase12.py` | 11.1+12 단위 테스트 |
| `src/tests/test_phase11_transcripts.py` | PIT·CLI 등 확장 |
| `docs/phase12_evidence.md`, `phase11_evidence.md` | 증거·동작 설명 |
| `docs/public_core_cycle/latest/README.md` | 생성물 디렉터리 안내 |
| `.gitignore` | `cycle_summary.json`, `operator_packet.md` 제외 |
| `HANDOFF.md`, `README.md`, `src/db/schema_notes.md` | 운영·스키마 문서 |

---

## 3. 데이터베이스 / 마이그레이션 (“테이블 푸시”)

### 3.1 적용 대상 SQL (순서)

| 마이그레이션 | Phase | 내용 |
|--------------|-------|------|
| `20250414100000_phase11_transcripts_fmp_poc.sql` | 11 | `transcript_ingest_runs`, `raw_transcript_payloads_fmp`, `normalized_transcripts`, `daily_watchlist_entries.transcript_enrichment_json`, registry 시드 등 |
| `20250415100000_phase111_transcript_audit_pit.sql` | 11.1 | **`raw_transcript_payloads_fmp_history`** (upsert 전 스냅샷, 불변 감사) |

Supabase에서는 **SQL Editor에 파일 내용 실행** 또는 프로젝트에 맞는 `supabase db push` 등으로 적용합니다.  
**원격 DB에 11.1 파일이 아직 없으면** 반드시 `20250415100000_phase111_transcript_audit_pit.sql` 을 추가 적용해야, 코드의 `archive_raw_transcript_payload_fmp_before_upsert` / history insert 가 런타임에서 성공합니다.

### 3.2 적용 확인용 SQL (예시)

```sql
-- Phase 11.1 history 테이블 존재
select to_regclass('public.raw_transcript_payloads_fmp_history') as history_table;

-- Phase 11 코어 테이블
select to_regclass('public.normalized_transcripts') as normalized_transcripts;

-- 샘플: 최근 히스토리 행 (ingest 재실행 후)
select id, symbol, fiscal_year, fiscal_quarter, fetched_at
from public.raw_transcript_payloads_fmp_history
order by fetched_at desc
limit 5;
```

### 3.3 런타임 증거 (사용자 환경에서 확인된 것)

- **`run-public-core-cycle`** 성공 후 `docs/public_core_cycle/latest/cycle_summary.json`, `operator_packet.md` 생성.
- **`operational_runs`** 에 `run_type = 'public_core_cycle'`, `component = 'run_public_core_cycle_v1'`, `status = 'success'` 기록 (예: `d75c8d8a-...`, `0b571240-...`).
- State change 요약에서 **후보 전원 `insufficient_data` / `gating_high_missingness`** 인 경우는 **파이프라인 실패가 아니라 입력 커버리지가 얇을 때의 정상적인 출력**에 해당 (워치리스트 0 허용 설계).

---

## 4. 테스트 결과 (로컬, 2026-04-06 기준)

실행 디렉터리: `src/` (또는 `PYTHONPATH=src`)

### 4.1 Phase 11 / 11.1 / 12 타깃

```bash
cd /Users/hyunminkim/GenAIProacTrade/src
python -m pytest tests/test_phase111_phase12.py tests/test_phase11_transcripts.py -q
```

**결과**: **16 passed** (약 0.5s)

포함 내용 요약:

- PIT-safe 트랜스크립트 선택(미래 행 제외, 날짜 없는 행 제외)
- `revision_id` 전체 SHA-256 길이(64)
- raw 감사 히스토리 insert 경로
- 프로브 `not_configured` 시 registry `inactive`
- ingest 키 없을 때도 `OperationalRunSession` 진입 + `configuration_error`
- `run_public_core_cycle` 목업: 빈 워치리스트여도 `ok`, run 없으면 `ok: false`
- Phase 12 CLI 등록

### 4.2 전체 스위트

```bash
cd /Users/hyunminkim/GenAIProacTrade/src
python -m pytest tests/ -q
```

**결과**: **166 passed**, 3 warnings (edgar deprecation), 약 4s

---

## 5. 새 CLI

| 명령 | 설명 |
|------|------|
| `run-public-core-cycle` | 공개 코어 end-to-end + `docs/public_core_cycle/latest/` 번들 |
| `report-public-core-cycle` | 마지막 `cycle_summary.json` 재출력 |

(Phase 11 트랜스크립트 CLI는 Phase 11 커밋에서 이미 추가됨.)

---

## 6. Phase 11.1 동작 요약 (코드 관점)

1. **PIT**: 워치리스트 `transcript_enrichment_json` 은 `available_at` → `published_at` → `event_date` 중 첫 유효 날짜가 **후보 `as_of_date` 이하**인 정규화 행만 사용.
2. **ingest 차단**: `FMP_API_KEY` 없으면 세션 연 뒤 `finish_failed` (`configuration_error`), JSON에 `truthful_blocked` 등.
3. **Registry activation**: 프로브/ingest 결과가 `partial`·`available` 일 때만 `active`, 그 외 **`inactive`** 로 내려가 stale-active 방지.
4. **감사**: 동일 `(symbol, year, quarter)` 재 ingest 시 **이전 raw** 가 `raw_transcript_payloads_fmp_history` 에 남음.
5. **revision_id**: 트랜스크립트 전문 UTF-8 기준 **SHA-256 전체 hex**; `provenance_json.refresh_audit` 에 이전 normalized id / ingest_run 등.

---

## 7. Phase 12 동작 요약 (한 단락)

최신(또는 지정) **completed `state_change_run`** 을 기준으로 **harness 입력 적재 → investigation memos → outlier casebook → daily scanner/watchlist** 를 순서대로 호출하고, `cycle_summary.json` 에 단계별 상태·경고·프리미엄 오버레이 **요약만** 담아 **결정적 스코어 경로와 분리**한다. 스캐너 단계만 하드 실패가 아니면 전체 `ok` 로 마칠 수 있으며, 빈 워치리스트는 실패로 간주하지 않는다.

---

## 8. 알려진 잔여 / 주의

- **미추적 디렉터리**: `docs/phase7_real_samples/latest/`, `docs/phase9_samples/latest/` 등은 이번 패치에 포함되지 않음; 커밋 대상에서 제외하거나 별도 정책 결정.
- **`docs/public_core_cycle/latest/`** 의 생성 JSON/md 는 `.gitignore` 로 **커밋 제외** (로컬·운영 증거용).
- **GitHub 동기화**는 PAT/SSH 설정된 로컬에서 `git pull` / `git push` 로 마무리.

---

## 9. 재현 체크리스트

1. 마이그레이션 11 + 11.1 적용 확인 (§3.2).
2. `python -m pytest tests/ -q` → 166 passed.
3. `python3 src/main.py run-public-core-cycle --universe sp500_current` → `ok: true` (선행 state change 존재 시).
4. `operational_runs` 에서 `public_core_cycle` success 조회.

---

*본 보고서는 저장소 문서로 유지하며, 이후 커밋이 쌓이면 상단 커밋 SHA만 갱신하면 됩니다.*
