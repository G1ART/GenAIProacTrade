# Phase 15 패치 결과 보고서

**문서 기준일**: 2026-04-06  
**워크오더**: `GenAIProacTrade_Phase15_Workorder_2026-04-06.md`

## HEAD (커밋 체인)

| 구분 | 값 |
|------|-----|
| 패치 직전 | `c9767e0` |
| 기능 머지 | `0fc9f42` — `feat(phase15): recipe validation lab, baselines, survival, scorecard CLI` |
| 후속 수정 | `db3a4e9` — `fix(research_engine): pass program_id as keyword to fetch_research_program` |
| 후속 수정 | `bee1616` — `fix: use keyword args for keyword-only db fetch helpers (Phase 14/15)` |
| 후속 수정 | `20c7909` — `fix(phase15): join validation panels to state-change scores by CIK + as_of<=signal` |
| **현재 팁** | `20c7909` |

초기 Phase 15 머지 이후 **DB 헬퍼 키워드 전용 인자** 정정과 **state_change 조인 규칙(CIK 정규화·시그널일 이하 `as_of_date`)** 보강이 추가로 들어갔다.

## 변경 요약

Phase 14의 `candidate_recipe`/`sandbox`를 **공개 데이터만**으로 검증하는 **Recipe Validation Lab**을 추가했다. `factor_market_validation_panels`와 `issuer_state_change_scores`를 시그널일·CIK로 조인해 분위 스프레드를 계산하고, state_change·naive·규모 프록시 베이스라인과 비교한 뒤 생존 판정·실패 행·스코어카드를 DB에 남긴다. `state_change.runner`는 `research_validation`을 참조하지 않으며, 거버넌스 문자열도 갱신했다.

### 산출물 (파일·경로)

- **마이그레이션**: `supabase/migrations/20250418100000_phase15_recipe_validation_lab.sql`
- **패키지**: `src/research_validation/` (`constants`, `metrics`, `policy`, `scorecard`, `service`)
- **DB**: `src/db/records.py` — Phase 15 CRUD·스모크
- **엔진 연동**: `src/research_engine/service.py` — `fetch_research_program(program_id=…)` 등 키워드 전용 호출
- **CLI**: `src/main.py` — 6개 서브커맨드(스모크 포함), 가설 UUID 사전 검증(`_exit_unless_uuid`)
- **거버넌스**: `src/research_registry/promotion_rules.py` — `research_validation` 문자열 차단
- **테스트**: `src/tests/test_phase15.py`
- **문서**: `docs/phase15_evidence.md`, `HANDOFF.md`, `README.md`(쉘 안전 예시·플레이스홀더 주의), `src/db/schema_notes.md`
- **`.gitignore`**: `docs/research_validation/scorecards/*.{json,md}`

### 후속 패치에서 바뀐 동작 (요약)

1. **키워드 전용 DB 헬퍼**  
   `fetch_research_program`, `fetch_public_core_cycle_quality_run_by_id` 등이 키워드 전용 인자만 받도록 되어 있어, Phase 15 검증 경로에서 **위치 인자로 넘기면 `TypeError`**가 났다. `program_id=` / `run_id=` 형태로 통일했다 (`db3a4e9`, `bee1616`).

2. **조인 0행 / 불일치**  
   패널의 `cik`와 state_change의 `cik` 형식·`as_of_date`와 시그널일 관계가 맞지 않으면 조인이 비었다.  
   - CIK **10자리 정규화** (`norm_cik`)  
   - state_change 행은 **`as_of_date` ≤ 시그널일**인 것 중 **가장 최근** 선택 (`pick_state_change_at_or_before_signal`)  
   조인 실패 시 **`insufficient_joined_rows`**와 함께 `hint_ko`·`debug` 블록으로 원인 추적 가능 (`20c7909` 및 `metrics`/`service` 보강).

3. **CLI·문서**  
   `--hypothesis-id YOUR_HYPOTHESIS_UUID` 또는 `<UUID>`를 그대로 붙여넣어 발생하던 오류를 줄이기 위해 **UUID 형식 검증**과 README의 **꺾쇠/플레이스홀더 주의**를 추가했다.

## 테스트

```bash
cd src
python3 -m pytest tests/test_phase15.py tests/ -q
```

**결과**: Phase 15 단독 시점에는 **200 passed**; Phase 16 테스트 추가 후 동일 명령으로 전체 **212 passed** (2026-04-06 기준).

## 운영 증거 (실 Supabase·로컬 CLI, 2026-04-06)

아래는 사용자 환경에서 실행된 로그를 요약한 것이다. HTTP는 모두 **200/201**이었고, 검증 런이 완료·스코어카드 export까지 이어졌다.

### `run-recipe-validation`

| 가설 UUID (접두) | `validation_run_id` (접두) | `n_rows` | `survival_status` | 비고 |
|------------------|----------------------------|----------|-------------------|------|
| `8ffeefc1-…bcb7` | `af5011c4-…f386` | 151 | `weak_survival` | `rationale`: `fragile_across_windows` |
| `eaba687b-…0e7f` | `c38e5c1c-…ea8e` | 151 | `weak_survival` | 동일 |
| `aad2f805-…b948` | `ed1568ab-…2f4b` | 151 | `weak_survival` | 동일 |

공통 `summary` 예: `recipe_pooled_spread ≈ 0.02818`, `window_stability_ratio = 0.45`, `program_quality_class`: `thin_input`, 가설 상태 `sandboxed`로 **최대 클린 등급 `weak_survival`** 캡 적용. `residual_contradiction_count`: 0.

### `export-recipe-scorecard`

- `eaba…` → `docs/research_validation/scorecards/eaba.json`, `eaba.md`
- `aad2…` → `docs/research_validation/scorecards/aad2.json`, `aad2.md`
- (동일 세션에서 다른 가설용 `latest` 경로 사용 이력 있음; scorecard 디렉터리는 `.gitignore` 대상)

### `report-recipe-survivors --limit 20`

`survival_status in (survives, weak_survival)` 조회 시, 위 세 건이 **`weak_survival`**로 나열됨. 해당 시점 결과 집합에는 **`survives` 단독 행은 없음** (모두 약한 생존 구간).

### `compare-recipe-baselines --hypothesis-id 8ffeefc1-625b-454c-a3bb-08e74937bcb7`

- **`state_change_score_only`**: `recipe`와 `baseline` 스프레드 동일 → `delta: 0`, `beats: false` (`eps` 해석)
- **`naive_null`**: `beats: true`
- **`market_cap_inverse_rank`**: `beats: true` (후보가 베이스라인 대비 유리한 방향)

## 재현 CLI (요약)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase15-recipe-validation
python3 src/main.py run-recipe-validation --hypothesis-id 00000000-0000-4000-8000-000000000001
python3 src/main.py export-recipe-scorecard --hypothesis-id <실제-UUID> --out docs/research_validation/scorecards/latest.json
python3 src/main.py report-recipe-survivors --limit 20
python3 src/main.py compare-recipe-baselines --hypothesis-id <실제-UUID>
```

`<실제-UUID>` 자리에는 **유효한 UUID v4 문자열**만 넣는다. README에 적힌 대로 `YOUR_HYPOTHESIS_UUID`·`<...>` 리터럴은 쓰지 않는다.

## 결론

- Phase 15 **스키마·코드·테스트·문서**는 `0fc9f42` 기준으로 반영되었고, **실행 오류(키워드 인자)·조인 실패·CLI 혼동**은 `20c7909`까지의 후속 커밋으로 정리되었다.
- 실 DB 기준으로 **세 가설 모두 검증 완료**, 행 수 **151**, 생존은 **`weak_survival`**(창 안정성·얇은 입력·샌드박스 캡). 스코어카드 export·생존자 리포트·베이스라인 비교 CLI가 **기대대로 동작**함을 터미널 로그로 확인했다.
