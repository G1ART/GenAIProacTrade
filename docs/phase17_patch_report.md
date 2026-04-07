# Phase 17 패치 리포트 — Public Substrate Depth Expansion & Quality Lift

## 검증 상태 (2026-04-06 운영 런 기준)

다음이 **모두 성공**한 것으로 확인되었다.

| 항목 | 결과 |
|------|------|
| `report-research-readiness --program-id 45ec4d1a-fd77-4254-9390-462da04d1d11` | `ok: true`, JSON 정상 반환 |
| `export-public-depth-brief --universe sp500_current --out docs/public_depth/briefs/latest.json` | `ok: true`, `latest.json` 및 `latest.md` 생성 |
| `python3 -m pytest -q` | **219 passed** |
| `git push origin main` | `b696888..d116f15  main -> main` (원격 반영 완료) |

터미널에 `httpx` INFO 로그가 다수 찍히는 것은 Supabase REST 호출 로깅이며, **오류가 아니다**.

---

## Git

- **구현 직전 로컬 `main` tip (참고)**: `e822e9c265b2e1f3c83d2db15d01b26f0dbbd985`
- **Phase 17 기능 커밋(초기)**: `f273b88` — `feat(phase17): public substrate depth coverage, expansion, uplift evidence`
- **후속**: 문서·`list-universe-names`·플레이스홀더 안내 등이 `main`에 누적 반영되었고, **2026-04-06 기준 원격 `main` tip**은 사용자 푸시 로그상 `d116f15` 부근이다. 정확한 해시는 `git log -1 origin/main` 으로 확인하면 된다.

---

## 변경 범위 (파일)

| 영역 | 경로 |
|------|------|
| 마이그레이션 | `supabase/migrations/20250420100000_phase17_public_depth.sql` — `public_depth_runs`, `public_depth_coverage_reports`, `public_depth_uplift_reports` |
| 패키지 | `src/public_depth/` — `constants`, `diagnostics`, `uplift`, `expansion`, `readiness`, `__init__` |
| DB 레이어 | `src/db/records.py` — Phase 17 CRUD, `fetch_public_core_cycle_quality_runs_for_universe`, `fetch_universe_catalog_for_operators` |
| CLI | `src/main.py` — 아래 CLI 전부 |
| 거버넌스 | `src/research_registry/promotion_rules.py` — `public_depth` 비침투 문구·`assert_no_auto_promotion_wiring` |
| 테스트 | `src/tests/test_phase17.py` |
| 문서 | `docs/phase17_evidence.md`, `docs/phase17_patch_report.md`(본 파일), `HANDOFF.md`, `README.md`, `src/db/schema_notes.md` |

---

## 마이그레이션

- 단일 파일: `20250420100000_phase17_public_depth.sql`
- 적용 후 PostgREST/RLS 정책이 프로젝트 표준과 맞는지(서비스 롤 읽기/쓰기)는 기존 Phase와 동일하게 점검.

---

## 신규·관련 CLI

| 명령 | 역할 |
|------|------|
| `list-universe-names` | DB의 `universe_memberships` 기준 유효 `universe_name` 나열; Phase 17의 `--universe`에 **복사해 쓸 값**(`use_for_phase17_cli`) 안내 |
| `smoke-phase17-public-depth` | Phase 17 모듈·가드 스모크 |
| `run-public-depth-expansion` | before → (선택 빌드) → after → uplift DB 적재 |
| `report-public-depth-coverage` | 커버리지 스냅샷 (`--persist` 선택) |
| `report-quality-uplift` | 두 커버리지 리포트 ID 간 델타 (`--persist` 선택) |
| `report-research-readiness` | 프로그램 UUID 기준, 기판이 Phase 15/16 재실행에 **충분히 나아졌는지** 휴리스틱 요약 |
| `export-public-depth-brief` | 유니버스 커버리지를 JSON/Markdown 브리프로보내기 |

실행 시 **`python3 src/main.py ...`** 형태를 사용한다(`src/main.py` 직접 실행 시 셸 실행 권한 문제 방지).

---

## 테스트

- `python3 -m pytest -q` → **219 passed** (본 문서 갱신 시점 기준, 사용자 로컬와 일치).
- `src/tests/test_phase17.py`: 커버리지 키 상한, 업리프트, 제외 사유 순위 결정성, readiness, CLI 등록, `state_change.runner`가 `public_depth`를 참조하지 않음 등.

---

## 운영 런에서 확인된 스냅샷 (참고)

`sp500_current`, `as_of_date=2026-04-05`, 프로그램 `45ec4d1a-fd77-4254-9390-462da04d1d11` 기준 `report-research-readiness` 출력 요지:

- **프로그램 품질 힌트**: `program_quality_context_hint: thin_input` (레지스트리 맥락과 정합).
- **기판 스냅샷(발췌)**:
  - `n_issuer_universe`: 503
  - `thin_input_share`: 1.0 (최근 품질 런 집계)
  - `joined_recipe_substrate_row_count`: 151
  - 임계: `min_sample_rows` 24, `readiness_joined_threshold` 120 → 조인 행 수는 임계 **이상**이나, **동시에 `thin_input_share` 완화** 조건을 만족하지 않아 Phase 15/16 재실행은 권고되지 않음.
- **제외 사유 상위**: `no_validation_panel_for_symbol`(192), `no_state_change_join`(99), `missing_excess_return_1q`(61).
- **권고 플래그**: `recommend_rerun_phase_15_16: false`, `recommend_escalate_premium_seam: false`.

이는 “구현이 잘못되었다”가 아니라, **현재 DB 상태에 대한 진단 결과**이다. 기판을 더 두껍게 한 뒤 `run-public-depth-expansion` 또는 수동 빌드 후 다시 커버리지/리드니스를 찍으면 플래그가 바뀔 수 있다.

---

## 한 줄 요약

운영자는 유니버스별로 **레시피 검증용 PIT 조인 행 수·품질 쉐어·제외 사유**를 스냅샷으로 저장하고, **선택적 공개 파이프라인 빌드 전후**의 델타를 DB에 남긴 뒤, 프로그램 단위로 **Phase 15/16 재실행이 의미 있는지**를 `report-research-readiness`로 1차 판단할 수 있다. **`list-universe-names`로 실제 `--universe` 문자열을 확정**할 수 있게 했다. 제품 스코어 경로는 이 레이어를 읽지 않으며, `promotion_rules` 가드에 `public_depth`가 포함된다.

---

## 비목표·주의 (재확인)

- Phase 17은 **연구/진단 증거**용이며, 프로덕션 스코어링에 자동 연결되지 않는다.
- `report-research-readiness`의 권고는 **휴리스틱**이며, 최종 캠페인 여부는 운영 정책과 함께 판단한다.
- UUID·유니버스 인자는 문서의 플레이스홀더 문자열을 그대로 붙여 넣지 말고, **`list-research-programs` / `list-universe-names` 출력에서 복사**한다.
