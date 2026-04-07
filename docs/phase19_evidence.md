# Phase 19 증거 메모 — Public Repair Campaign & Revalidation Loop

## 목적

Phase 17/18로 **기판 스냅샷·타깃 수리·개선**까지 가능해진 뒤에도, "수리가 **연구 결과**(레시피 생존·Phase 16 권고)를 실제로 바꿨는가?"를 **하나의 감사 가능한 루프**로 답한다. `state_change.runner`는 `public_repair_campaign`을 **참조하지 않는다**.

## 스키마

| 객체 | 설명 |
|------|------|
| `public_repair_campaign_runs` | `program_id`, 베이스라인 커버리지·제외 액션·캠페인 FK, 빌드아웃·after 커버리지·개선, `reran_phase15`/`reran_phase16`, `final_decision`, `rationale_json`, `after_campaign_run_id` |
| `public_repair_campaign_steps` | `baseline_capture`, `targeted_buildout`, `phase15_rerun`, `phase16_rerun`, `revalidation_comparison`, `final_decision` 등 스텝 추적 |
| `public_repair_revalidation_comparisons` | 전후 생존 분포 JSON, 전후 캠페인 권고 문자열, 해석 JSON(런당 1건) |
| `public_repair_campaign_decisions` | 정책 버전·근거와 함께 최종 분기 행 |

## 재실행 게이트

`run-public-repair-campaign`은 수리 직후 `build_revalidation_trigger`와 동일한 조건으로 **`recommend_rerun_phase15`와 `recommend_rerun_phase16`이 모두 true**일 때만 `run_validation_campaign(..., run_mode="force_rerun")`을 호출한다. 그렇지 않으면 스텝을 `skipped`로 남기고 `rerun_skip_reason_json`에 이유를 기록한다.

## 최종 분기 (3값)

- `continue_public_depth` — 재실행 후 공개 쪽 개선·권고가 여전히 공개 우선에 가깝거나 생존이 나아진 경우 등.
- `consider_targeted_premium_seam` — **재실행이 실제로 수행된 경우에만** 후보; Phase 16 권고가 `targeted_premium_seam_first`이거나, 캠페인 집계에서 프리미엄 신호 쉐어가 정책 임계를 넘는 경우.
- `repair_insufficient_repeat_buildout` — 기판 개선 부족, 재실행 스킵/실패, 또는 재실행 후에도 불충분한 경우.

## CLI (재현)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase19-public-repair-campaign
python3 src/main.py run-public-repair-campaign --program-id <research_programs.id>
python3 src/main.py report-public-repair-campaign --repair-campaign-id <UUID>
python3 src/main.py compare-repair-revalidation-outcomes --repair-campaign-id <UUID>
python3 src/main.py export-public-repair-decision-brief --repair-campaign-id <UUID> --out docs/public_repair/briefs/latest.json
python3 src/main.py list-repair-campaigns --program-id <research_programs.id>
```

옵션: `--dry-run-buildout`(타깃 빌드아웃만 시뮬), `--skip-reruns`(캠페인 재실행 생략; 비교·결정은 진행).

마이그레이션: `supabase/migrations/20250422100000_phase19_public_repair_campaign.sql`.

---

## 테스트 결과 (기록)

**기준일**: 2026-04-06  

| 스위트 | 명령 | 결과 |
|--------|------|------|
| Phase 19 전용 | `PYTHONPATH=src python3 -m pytest src/tests/test_phase19.py -q` | **14 passed** |
| 전체 `src/tests` | `PYTHONPATH=src python3 -m pytest src/tests -q` | **242 passed** (3 warnings: `edgar` 라이브러리 DeprecationWarning) |

### `test_phase19.py`가 다루는 내용(요약)

- Runner / 프로모션 가드: `public_repair_campaign` 비참조, 경계 문구에 Phase 19 포함
- `compare_survival_distributions` 델타·`outcome_improved_heuristic`
- `build_improvement_interpretation`의 프리미엄 쉐어 계산
- `substrate_improved_from_buildout`
- **프리미엄 분기는 `reruns_executed=False`이면 불가**
- 재실행+권고/메트릭에 따른 `consider_targeted_premium_seam`·`continue_public_depth`·`repair_insufficient_repeat_buildout`
- `FINAL_DECISIONS` enum 상한, `premium_evidence_from_campaign_metrics` 헬퍼
- Phase 19 CLI 서브커맨드 6개 등록, 정책 버전 상수

---

## 운영 스모크·브리프 (동일 주기 검증)

| 검사 | 기대 |
|------|------|
| `smoke-phase19-public-repair-campaign` | `{"db_phase19_public_repair_campaign": "ok"}` |
| `export-public-repair-decision-brief ...` | `ok: true`, 지정 경로에 `.json` + `.md` |

완료 보고서(클로징 체크리스트·정책 요약): [phase19_completion_report.md](./phase19_completion_report.md).
