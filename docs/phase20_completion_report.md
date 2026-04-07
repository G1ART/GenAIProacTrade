# Phase 20 완료 보고서 — Public Repair Iteration Manager & Escalation Gate

**문서 기준일**: 2026-04-07  
**워크오더**: `GenAIProacTrade_Phase20_Workorder_2026-04-06_revised.md`  
**상태**: 구현·자동 테스트·운영 CLI 검증·원격 반영(푸시)까지 반영 완료

---

## 1. 목적 및 완료 범위

Phase 20은 Phase 19 **단일** 수리 캠페인을 **시간 축에서 반복**할 때, UUID 추적 부담을 줄이고(골든 패스: `latest` 선택자), **트렌드·플래토·에스컬레이션**을 감사 가능한 행으로 남긴다.

| 목표 | 완료 여부 |
|------|-----------|
| `public_repair_iteration_series` / `members` / `escalation_decisions` | 마이그레이션·CRUD·스모크 |
| 결정적 플래토·에스컬레이션 3분기 | `continue_public_depth` \| `hold_and_repeat_public_repair` \| `open_targeted_premium_discovery` |
| 운영자 해석 레이어(`latest`) | `resolver.py` + Phase 19/20 CLI 연동 |
| **프로덕션 스코어 경로**와의 분리 | `promotion_rules` + `state_change.runner`에 `public_repair_iteration` 비참조 |
| 테스트·문서·HANDOFF | 아래 검증 표·증거 문서 참조 |

---

## 2. 구현 산출물 (요약)

### 2.1 데이터베이스

- **마이그레이션**: `supabase/migrations/20250423100000_phase20_repair_iteration.sql`
  - `public_repair_iteration_series` — `program_id`, `universe_name`, `policy_version`, `status`
  - `public_repair_iteration_members` — `series_id`, `repair_campaign_run_id`, `sequence_number`, `trend_snapshot_json`
  - `public_repair_escalation_decisions` — `recommendation`, `plateau_metrics_json`, `counterfactual_json`

### 2.2 코드

- **패키지**: `src/public_repair_iteration/` — `constants`, `resolver`, `escalation_policy`, `service`, `__init__`
- **DB 레이어**: `src/db/records.py` — Phase 20 CRUD, `list_research_programs_for_universe` 등
- **CLI**: `src/main.py` — Phase 20 서브커맨드, Phase 19 일부에 `latest`/`--universe` 보강
- **거버넌스**: `src/research_registry/promotion_rules.py`
- **테스트**: `src/tests/test_phase20.py` (11개)

### 2.3 문서

- `docs/phase20_evidence.md` — 스키마·resolver·CLI·테스트·운영 검증 스냅샷
- `docs/phase20_patch_report.md` — 패치 요약
- `docs/phase20_completion_report.md` — 본 문서
- `HANDOFF.md`, `README.md`, `src/db/schema_notes.md` — Phase 20 반영

---

## 3. CLI 명령 (Phase 20 전용)

| 커맨드 | 역할 |
|--------|------|
| `smoke-phase20-repair-iteration` | Phase 20 테이블 REST 도달 확인 |
| `run-public-repair-iteration` | Phase 19 1회 + 시리즈 멤버 + 에스컬레이션 행 적재 |
| `report-public-repair-iteration-history` | 시리즈·멤버·에스컬레이션 이력 JSON |
| `report-public-repair-plateau` | 활성 시리즈 기준 **재계산**(비삽입, `ephemeral` 표기) |
| `export-public-repair-escalation-brief` | JSON + Markdown 브리프 |
| `list-public-repair-series` | 프로그램별 시리즈 목록 |
| `report-latest-repair-state` | 최근 수리 캠페인 런 + 활성 시리즈 + 플래토 요약 |
| `report-premium-discovery-readiness` | `open_targeted_premium_discovery` 준비 여부 요약 |

### 3.1 골든 패스 예시 (`sp500_current`)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase20-repair-iteration
python3 src/main.py report-public-repair-iteration-history --program-id latest --universe sp500_current
python3 src/main.py report-public-repair-plateau --program-id latest --universe sp500_current
python3 src/main.py export-public-repair-escalation-brief \
  --program-id latest --universe sp500_current \
  --out docs/public_repair/escalation_latest.json
python3 src/main.py report-premium-discovery-readiness --program-id latest --universe sp500_current
python3 src/main.py report-latest-repair-state --program-id latest --universe sp500_current
python3 src/main.py list-public-repair-series --program-id latest --universe sp500_current
```

Phase 19 보조: `list-repair-campaigns`, `report-public-repair-campaign`에 `latest` 선택자.

---

## 4. 검증·테스트 결과 (운영자 실행)

| 항목 | 결과 |
|------|------|
| 마이그레이션 `20250423100000_phase20_repair_iteration.sql` | 적용 완료 |
| `smoke-phase20-repair-iteration` | `db_phase20_repair_iteration: ok` |
| `python3 -m pytest src/tests -q` | **253 passed** (edgar DeprecationWarning 3건) |
| `pytest src/tests/test_phase20.py` | **11 passed** |
| `report-public-repair-iteration-history` (`latest`, `sp500_current`) | `ok: true`; 멤버 seq 1·에스컬레이션 행 |
| `report-public-repair-plateau` | `hold_and_repeat_public_repair`, `insufficient_iterations` |
| `export-public-repair-escalation-brief` | `docs/public_repair/escalation_latest.json` + `.md` |
| `report-premium-discovery-readiness` | `premium_discovery_ready: false` |
| `report-latest-repair-state` / `list-public-repair-series` | `ok: true` |
| `list-repair-campaigns` | `ok: true`; 과거 1건 **502**로 `failed` 가능(인프라 일시 장애) |
| `report-public-repair-campaign --repair-campaign-id latest` | 스텝·비교·`repair_insufficient_repeat_buildout` 일관 |

### 4.1 운영 시 유의 (502 실패 런)

`error_message`에 Supabase **502**·Cloudflare HTML이 있으면 **엣지/게이트웨이 일시 장애**로 보는 것이 타당하다. 재시도하거나 이후 `completed` 런을 증거로 쓴다.

---

## 5. 에스컬레이션 정책 (현장 스냅샷)

멤버 1건에서 `hold_and_repeat_public_repair` + `insufficient_iterations`는 **정책대로**(최소 2회 스냅샷 필요).

---

## 6. Git·원격 반영

- 커밋 **550961a**: Phase 20 패치
- `git push origin main` 성공 (`54e99dd..550961a`)

---

## 7. 거버넌스 (재확인)

프로덕션 스코어링은 `public_repair_iteration`·`public_repair_campaign`을 참조하지 않는다. `open_targeted_premium_discovery`는 발견 궤도이며 라이브 통합 자동 허용이 아니다.

---

## 8. 후속 권장

1. 동일 프로그램으로 수리 캠페인을 한 번 더 완료해 멤버 2+ 후 플래토 재확인.
2. 재검증 게이트 개방 시 Phase 19 비교·결정 교차 확인.
3. 브리프 아티팩트를 감사·티켓에 고정.

---

## 9. 참조

- `docs/phase20_evidence.md`
- `docs/phase20_patch_report.md`
- `HANDOFF.md` (Phase 20 상단)
- `README.md`
