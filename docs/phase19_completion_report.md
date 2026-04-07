# Phase 19 완료 보고서 — Public Repair Campaign & Revalidation Loop

**문서 기준일**: 2026-04-06  
**워크오더**: `GenAIProacTrade_Phase19_Workorder_2026-04-06.md`  
**상태**: 구현·자동 테스트·운영 스모크·브리프보내기 검증 반영 완료

---

## 1. 목적 및 완료 범위

Phase 19는 Phase 17/18의 **진단·수리**와 Phase 15/16의 **연구 결과** 사이의 간극을 메워, 한 번의 감사 가능한 런으로 다음을 달성한다.

| 목표 | 완료 여부 |
|------|-----------|
| 수리 캠페인 **객체 모델**(런·스텝·비교·결정) | 마이그레이션·CRUD·스모크 |
| 베이스라인 → 타깃 빌드아웃 → after 스냅샷 → **게이트된** 재실행 | `run-public-repair-campaign` |
| Phase 15/16 재실행을 **명시적 불리언**으로만 허용 | `recommend_rerun_phase15` **및** `recommend_rerun_phase16` 동시 true일 때만 `force_rerun` |
| 전후 **생존 분포·캠페인 권고** 영구 비교 | `public_repair_revalidation_comparisons` |
| **단일** 기계 분기(3값) | `continue_public_depth` \| `consider_targeted_premium_seam` \| `repair_insufficient_repeat_buildout` |
| **프로덕션 스코어 경로**와의 분리 | `promotion_rules` + `state_change.runner`에 `public_repair_campaign` 비참조 |
| 워크오더 CLI·문서·테스트 | 아래 절차·테스트 결과 참조 |

---

## 2. 구현 산출물 (요약)

### 2.1 데이터베이스

- **마이그레이션**: `supabase/migrations/20250422100000_phase19_public_repair_campaign.sql`
  - `public_repair_campaign_runs` — 베이스라인/after FK, 빌드아웃·개선 링크, `reran_phase15`/`reran_phase16`, `final_decision`, `after_campaign_run_id` 등
  - `public_repair_campaign_steps` — 스텝별 상태·`detail_json`
  - `public_repair_revalidation_comparisons` — 런당 1건(유니크 인덱스)
  - `public_repair_campaign_decisions` — 정책 버전·`rationale_json`과 함께 최종 분기 행

### 2.2 코드

- **패키지**: `src/public_repair_campaign/` — `constants`, `comparisons`, `decision_policy`, `service`, `__init__`
- **DB 레이어**: `src/db/records.py` — Phase 19 CRUD, `fetch_latest_validation_campaign_run_for_program`
- **CLI**: `src/main.py` — Phase 19 서브커맨드 전부
- **거버넌스**: `src/research_registry/promotion_rules.py` — Phase 19 경계·runner 가드
- **테스트**: `src/tests/test_phase19.py`

### 2.3 문서

- `docs/phase19_evidence.md` — 증거·스키마·CLI·**테스트 결과**
- `docs/phase19_patch_report.md` — 패치 요약
- `docs/phase19_completion_report.md` — 본 문서
- `HANDOFF.md`, `README.md`, `src/db/schema_notes.md` — Phase 19 반영

---

## 3. CLI 명령 (Phase 19 전용)

| 커맨드 | 역할 |
|--------|------|
| `smoke-phase19-public-repair-campaign` | Phase 19 테이블 도달 확인 |
| `run-public-repair-campaign` | 전체 폐쇄 루프 실행 |
| `report-public-repair-campaign` | 런·스텝·결정·비교 JSON 조회 |
| `compare-repair-revalidation-outcomes` | 저장된 비교 행 조회 |
| `export-public-repair-decision-brief` | JSON + Markdown 브리프 |
| `list-repair-campaigns` | 프로그램별 런 목록 |

### 3.1 실행 옵션 (운영 안전)

```bash
python3 src/main.py run-public-repair-campaign \
  --program-id <research_programs.id> \
  [--universe <name>] \
  [--dry-run-buildout] \
  [--skip-reruns]
```

- `--dry-run-buildout`: Phase 18 타깃 빌드아웃을 시뮬만(실제 수리 최소화).
- `--skip-reruns`: Phase 16 `force_rerun` 생략(비교·결정 로직은 진행; 재실행 없으면 프리미엄 분기 불가 불변식 유지).

### 3.2 재실행 게이트

수리 직후 `build_revalidation_trigger`와 동일한 임계로 **`recommend_rerun_phase15`와 `recommend_rerun_phase16`이 모두 true**일 때만 `run_validation_campaign(..., run_mode="force_rerun")`을 호출한다. 그 외에는 스텝을 `skipped`로 남기고 `rerun_skip_reason_json`에 사유를 기록한다.

### 3.3 최종 분기 정책 (요약)

- `consider_targeted_premium_seam`은 **재실행이 실제로 성공한 경우에만** 후보(워크오더: 재실행 없이 프리미엄만 권고 불가).
- 그 외 규칙은 `decision_policy.decide_final_repair_branch`에 결정적으로 구현됨.

---

## 4. 운영 클로징 액션 (실행 순서)

환경: 프로젝트 루트, `.env`에 Supabase 자격 증명.

### 4.1 사전 조건

1. `20250422100000_phase19_public_repair_campaign.sql` 적용 완료.
2. Phase 17/18 선행 테이블·(필요 시) Phase 18 패키지가 배포 환경과 일치.

### 4.2 스모크

```bash
cd /path/to/GenAIProacTrade
export PYTHONPATH=src
python3 src/main.py smoke-phase19-public-repair-campaign
```

### 4.3 자동 테스트

```bash
python3 -m pytest src/tests/test_phase19.py -q
python3 -m pytest src/tests -q
```

### 4.4 캠페인 실행(단계적 권장)

1. `--dry-run-buildout`으로 타깃·게이트만 확인.  
2. 필요 시 풀 런(시간·DB 부하 큼).  
3. 출력 `repair_campaign_run_id`로 `report-public-repair-campaign` / `export-public-repair-decision-brief`로 증거 고정.

```bash
python3 src/main.py export-public-repair-decision-brief \
  --repair-campaign-id <UUID> \
  --out docs/public_repair/briefs/latest.json
```

### 4.5 클로징 체크리스트

- [ ] 마이그레이션 적용됨
- [ ] `smoke-phase19-public-repair-campaign` 성공
- [ ] `pytest src/tests/test_phase19.py` 통과
- [ ] (선택) 전체 `pytest src/tests` 통과
- [ ] (선택) `run-public-repair-campaign` 증거 런 1건 이상 + 브리프 export
- [ ] Git: 커밋·원격 푸시(팀 정책)

---

## 5. 테스트 결과 (검증 기록)

다음은 **2026-04-06** 기준 로컬/CI 재현용 명령과 결과이다.

| 구분 | 명령 | 결과 |
|------|------|------|
| Phase 19 단위 | `PYTHONPATH=src python3 -m pytest src/tests/test_phase19.py -q` | **14 passed** (실행 시간 약 1–5초대) |
| 전체 회귀 | `PYTHONPATH=src python3 -m pytest src/tests -q` | **242 passed** (프로젝트 전체 `src/tests`; 경고는 외부 `edgar` DeprecationWarning 수준) |

커버하는 주요 케이스(요약):

- `state_change.runner`에 `public_repair_campaign` 문자열 없음
- `promotion_rules` 가드·경계 문구에 Phase 19 반영
- 생존 분포 비교 델타·프리미엄 쉐어 해석 JSON
- **재실행 없으면** `consider_targeted_premium_seam` 불가
- 재실행+substrate 개선+Phase 16 권고/메트릭에 따른 분기
- 최종 결정 enum 상한
- Phase 19 CLI 서브커맨드 등록

---

## 6. 운영 스모크·브리프 (본 패치 주기에서 수행됨)

| 단계 | 결과 |
|------|------|
| Supabase에 Phase 19 SQL 적용 | 사용자 확인 |
| `smoke-phase19-public-repair-campaign` | HTTP 200, `{"db_phase19_public_repair_campaign": "ok"}` |
| 실제 캠페인 런 후 `export-public-repair-decision-brief` | `ok: true`, `docs/public_repair/briefs/latest.json` 및 동명 `.md` 생성 |

(구체 `repair_campaign_run_id`는 환경·실행마다 다름; DB `public_repair_campaign_runs`에서 조회.)

---

## 7. 거버넌스·비침투성

- `state_change.runner` 소스에 **`public_repair_campaign` 문자열이 없어야** 한다.
- `promotion_rules.describe_production_boundary`에 Phase 19 비참조가 명시되어 있다.
- Phase 19는 **연구·감사·수리 캠페인** 계층이며, 프로덕션 스코어링이 이 모듈을 읽도록 **연결하지 않는다**.

---

## 8. 이슈·메모 (구현·운영)

| 이슈 | 조치 |
|------|------|
| 원격 저장소에 Phase 18 패키지 누락 가능성 | `main`이 Phase 18 CLI를 참조하므로 `src/public_buildout/`·Phase 18 마이그레이션·`test_phase18`을 동일 브랜치에 포함할 것(별도 동기화 커밋). |
| 로컬 전용 브리프·샘플 디렉터리 | `docs/public_repair/briefs/`, `docs/public_depth/` 등은 팀 정책에 따라 커밋 또는 `.gitignore`. |

---

## 9. 후속 권고 (비블로킹)

1. 게이트 미통과 시 `rerun_skip_reason_json`을 기준으로 기판 추가 수리(Phase 17/18) 후 캠페인 재시도.
2. `final_decision`이 `repair_insufficient_repeat_buildout`이면 빌드아웃 상한·축 플래그를 조정한 뒤 재실행.
3. 브리프·비교 행을 리뷰·아카이브 정책에 맞게 버전 관리.

---

## 10. 참조 문서

- 상세 증거·스키마·CLI·테스트 기록: [phase19_evidence.md](./phase19_evidence.md)
- 패치 파일 요약: [phase19_patch_report.md](./phase19_patch_report.md)
- 핸드오프: [../HANDOFF.md](../HANDOFF.md)

---

**Phase 19 워크오더 대응, 문서화된 클로징 절차 및 기록된 테스트 결과는 위 내용으로 종료한다.**
