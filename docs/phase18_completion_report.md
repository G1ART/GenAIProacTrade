# Phase 18 완료 보고서 — Targeted Public Substrate Build-Out

**문서 기준일**: 2026-04-06  
**워크오더**: `GenAIProacTrade_Phase18_Workorder_2026-04-06.md`  
**상태**: 구현·검증·운영 클로징 액션까지 반영 완료

---

## 1. 목적 및 완료 범위

Phase 18은 Phase 17에서 측정한 **공개 기판 커버리지·제외 사유**를 바탕으로 다음을 달성한다.

| 목표 | 완료 여부 |
|------|-----------|
| 제외 사유별 **타깃 수리** 오케스트레이션(상한·플래그) | 코드·CLI 반영 |
| 감사 흔적 DB 적재(`public_exclusion_action_reports`, `public_buildout_runs`, `public_buildout_improvement_reports`) | 마이그레이션·CRUD·스모크 |
| 전후 **개선 정량화**(제외 분포·기판 메트릭 델타) | `report-buildout-improvement` + `--persist` |
| Phase 15/16 **재검증 권고 불리언**(기계 판독) | `report-revalidation-trigger` |
| **프로덕션 스코어 경로**와의 분리 | `promotion_rules` + `state_change.runner` 비참조 가드 |
| 운영 재현용 CLI·문서 | 아래 클로징 절차 포함 |

---

## 2. 구현 산출물 (요약)

### 2.1 데이터베이스

- **마이그레이션**: `supabase/migrations/20250421100000_phase18_public_buildout.sql`
  - `public_exclusion_action_reports`
  - `public_buildout_runs`
  - `public_buildout_improvement_reports` (`public_buildout_run_id` nullable — CLI 단독 적재 허용)

### 2.2 코드

- **패키지**: `src/public_buildout/` — `constants`, `actions`, `improvement`, `revalidation`, `orchestrator`
- **진단 확장**: `src/public_depth/diagnostics.py` — `compute_substrate_coverage(..., symbol_queues_out=...)`
- **DB 레이어**: `src/db/records.py` — Phase 18 CRUD, `list_public_depth_coverage_reports_for_universe` (최신 N건 조회)
- **CLI**: `src/main.py` — Phase 18 서브커맨드 전부
- **거버넌스**: `src/research_registry/promotion_rules.py` — 경계 설명 보강, `public_buildout` 문자열 runner 금지
- **테스트**: `src/tests/test_phase18.py`

### 2.3 문서

- `docs/phase18_evidence.md` — 증거·스키마·CLI 스텁
- `docs/phase18_patch_report.md` — 패치 요약
- `HANDOFF.md`, `README.md`, `src/db/schema_notes.md` — Phase 18 반영

---

## 3. CLI 명령 (Phase 18 전용)

| 커맨드 | 역할 |
|--------|------|
| `smoke-phase18-public-buildout` | Phase 18 테이블 도달 확인 |
| `report-public-exclusion-actions` | 제외 분포·심볼 큐·액션 JSON (`--persist` 선택) |
| `run-targeted-public-buildout` | 사유별 상한 빌드 (`--dry-run` 권장 선행) |
| `report-buildout-improvement` | 전후 커버리지 비교·개선 요약 (`--persist` 선택) |
| `report-revalidation-trigger` | `recommend_rerun_phase15` / `recommend_rerun_phase16` |
| `export-buildout-brief` | JSON + Markdown 브리프 |

### 3.1 개선 리포트: UUID 자동 선택 (운영 편의)

수동으로 `before`/`after` UUID를 복사하지 않아도 되도록 다음이 추가되었다.

```bash
python3 src/main.py report-buildout-improvement \
  --universe sp500_current \
  --from-latest-pair \
  [--persist]
```

- 동일 `universe_name`의 `public_depth_coverage_reports`를 `created_at` 내림차순으로 2건 조회한다.
- **최신 = after**, **그다음 = before** 로 자동 매핑한다.
- 출력에 `resolved_before_report_id`, `resolved_after_report_id`가 포함된다.

수동 모드는 기존과 동일하다.

```bash
python3 src/main.py report-buildout-improvement \
  --before-report-id <UUID> \
  --after-report-id <UUID> \
  [--persist]
```

### 3.2 오류 진단 보강

`report-buildout-improvement`가 `coverage_report_not_found`를 반환할 때, 응답에 **`before_found` / `after_found`** 가 포함되어 어떤 ID가 조회에 실패했는지 구분할 수 있다.

---

## 4. 운영 클로징 액션 (실행 순서·의미)

아래는 **워크오더 대응 + 실제 검증에 사용한 절차**를 시간 순으로 정리한 것이다. 환경은 프로젝트 루트, `.env`에 Supabase 자격 증명이 있다고 가정한다.

### 4.1 사전 조건

1. Supabase에 `20250421100000_phase18_public_buildout.sql` 적용 완료.
2. Phase 17 커버리지 테이블(`public_depth_coverage_reports` 등)이 이미 존재.

### 4.2 스모크

```bash
cd /path/to/GenAIProacTrade
python3 src/main.py smoke-phase18-public-buildout
```

- Phase 18 테이블에 대한 최소 SELECT가 성공하면 된다.

### 4.3 유니버스·제외 액션 파악 (선택)

```bash
python3 src/main.py list-universe-names
python3 src/main.py report-public-exclusion-actions --universe sp500_current
# 스냅샷 DB 저장 시:
# python3 src/main.py report-public-exclusion-actions --universe sp500_current --persist
```

### 4.4 타깃 빌드아웃 (선행)

- **권장**: 첫 실운영 전 `--dry-run`으로 타깃 제외·부하 확인.

```bash
python3 src/main.py run-targeted-public-buildout --universe sp500_current --dry-run
```

- 실제 빌드는 축별 플래그(`--no-attack-validation` 등)로 나누는 것이 운영상 안전하다(워크오더·이전 검토 권고와 동일).

### 4.5 커버리지 스냅샷 (Phase 17 CLI, Phase 18 전후 비교용)

```bash
python3 src/main.py report-public-depth-coverage --universe sp500_current --persist
```

- 출력의 **`persisted_report_id`** 가 한 시점의 스냅샷 ID이다.
- 전·후 비교를 하려면 **데이터 보강 전후로 최소 2회** `--persist` 실행하여 리포트가 2건 이상 쌓이게 한다.

### 4.6 빌드아웃 개선 리포트

**자동 페어(권장, 2026-04-06 패치 이후):**

```bash
python3 src/main.py report-buildout-improvement \
  --universe sp500_current \
  --from-latest-pair
```

**DB에 개선 행까지 남기기:**

```bash
python3 src/main.py report-buildout-improvement \
  --universe sp500_current \
  --from-latest-pair \
  --persist
```

- 성공 시 `public_buildout_improvement_reports`에 INSERT되며, 응답에 **`persisted_improvement_id`** 가 포함된다.
- `public_buildout_run_id`는 null일 수 있다(CLI 단독 적재 설계).

**해석 예시(실행에서 관측 가능한 패턴):**

- `substrate_uplift.joined_recipe_substrate_row_count` 전후 증가 → `joined_substrate_improved: true` 가능.
- `thin_input_share`가 전후 모두 높게 유지되면 `thin_input_improved: false` 로 남을 수 있다 — HANDOFF에도 있듯 **코드가 “충분하다”고 단정하지 않으며** 운영자 판단이 필요하다.

### 4.7 재검증 권고 불리언

```bash
python3 src/main.py report-revalidation-trigger --program-id <research_programs.id>
```

- `--program-id`는 **`research_programs` 테이블의 PK**이다. `list-research-programs` 출력의 각 행 `id`를 사용한다.
- 커버리지 리포트 ID·개선 리포트 ID와 **혼동하면 안 된다**.
- 프로그램의 `universe_name`과 일치하는 유니버스(예: `sp500_current`)로 `compute_substrate_coverage`가 다시 돌아간다.
- `recommend_rerun_phase15` / `recommend_rerun_phase16`이 **false**여도, 이는 **휴리스틱이 자동 재실행을 권하지 않는다**는 뜻이며 Phase 15/16을 **수동으로 금지하지는 않는다**(자동 연결 없음).

### 4.8 브리프 아티팩트

```bash
python3 src/main.py export-buildout-brief \
  --universe sp500_current \
  --out docs/public_depth/briefs/buildout_latest.json
```

- JSON 경로와 함께 동명의 **Markdown** 파일이 생성된다(응답의 `markdown` 필드).

### 4.9 클로징 체크리스트

- [ ] 마이그레이션 적용됨
- [ ] `smoke-phase18-public-buildout` 성공
- [ ] (선택) `run-targeted-public-buildout` dry-run 또는 단계적 실런
- [ ] 전후 `report-public-depth-coverage --persist` ≥ 2건
- [ ] `report-buildout-improvement --from-latest-pair` 성공
- [ ] (선택) 동 명령 `--persist` 로 `public_buildout_improvement_reports` 적재
- [ ] `report-revalidation-trigger` 로 불리언·`substrate_snapshot` 확인
- [ ] `export-buildout-brief` 로 로컬 증거 파일 갱신
- [ ] Git: 변경분 커밋·원격 푸시(팀 정책에 따름)

---

## 5. 테스트

```bash
cd /path/to/GenAIProacTrade
python3 -m pytest src/tests/test_phase18.py -q
```

- `test_phase18` 및 프로젝트 전체 스위트는 Phase 18 추가 후 통과를 전제로 한다.

---

## 6. 거버넌스·비침투성

- `state_change.runner` 소스에 **`public_buildout` 문자열이 없어야** 한다(자동 프로모션·스코어 경로 오염 방지).
- `promotion_rules.describe_production_boundary`에 Phase 18 경계가 명시되어 있다.
- Phase 18은 **연구·진단·빌드아웃** 계층이며, 프로덕션 스코어링이 이 모듈을 읽도록 **연결하지 않는다**.

---

## 7. 이슈·해결 (구현·운영)

| 이슈 | 조치 |
|------|------|
| `report-buildout-improvement` 수동 UUID 혼동·누락 | `--universe` + `--from-latest-pair` 추가 |
| `coverage_report_not_found` 원인 불명 | 응답에 `before_found` / `after_found` 추가 |
| `_cmd_report_buildout_improvement` 내 잘못된 할당·중복 persist 로직 | 단일 올바른 `--persist` 블록으로 정리(이전 세션) |

---

## 8. 후속 권고 (비블로킹)

1. `thin_input_share`가 여전히 높으면 추가 기판 확장(Phase 17/18 빌드 축 조정)을 검토한다.
2. `recommend_rerun_phase15/16`이 true가 될 때만이 아니라, **캠페인·연구 목적**에 따라 Phase 15/16을 수동 재실행할 수 있다.
3. `export-buildout-brief` 산출물을 리뷰·아카이브 정책에 맞게 버전 관리한다.

---

## 9. 참조 문서

- 상세 증거·스키마: [phase18_evidence.md](./phase18_evidence.md)
- 패치 파일 목록 요약: [phase18_patch_report.md](./phase18_patch_report.md)
- 핸드오프: [../HANDOFF.md](../HANDOFF.md)

---

**Phase 18 본 워크오더 대응 및 문서화된 운영 클로징 절차는 위 내용으로 종료한다.**
