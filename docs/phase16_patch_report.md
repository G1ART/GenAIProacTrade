# Phase 16 패치 결과 보고서

**문서 기준일**: 2026-04-06  
**워크오더**: `GenAIProacTrade_Phase16_Workorder_2026-04-06_revised.md`

## HEAD

| 구분 | 값 |
|------|-----|
| 패치 직전 | `20c7909` |
| 패치 적용 후 | `4469190` — Phase 16 기능 `8540a5c` + 패치 리포트 SHA 정리 |

## 한 문단 요약

Phase 15가 남긴 **가설별 검증 행**을 프로그램 단위로 묶어, 자격 규칙과 **`join_policy_version`(CIK·`as_of≤signal` 조인)** 을 기준으로 **호환 시 재사용·불가 시 재실행**한 뒤 생존·베이스라인 열세·실패 사유·프리미엄 힌트를 집계하고, 코드에 고정된 **결정 게이트**로 세 가지 전략 분기 중 하나만 고른다. 이로써 “스코어카드를 수작업으로 읽고 다음 빌드를 감으로 정하기” 대신, **동일 입력에 동일 권고**가 나오는 캠페인 레이어가 생긴다.

## 변경 파일 (요약)

- **마이그레이션**: `supabase/migrations/20250419100000_phase16_validation_campaign.sql`
- **패키지**: `src/validation_campaign/` (`constants`, `compatibility`, `decision_gate`, `service`, `__init__.py`)
- **Phase 15 정렬**: `src/research_validation/constants.py`, `src/research_validation/service.py` — `join_policy_version`, `cohort_config_version`, `WINDOW_STABILITY_METRIC_KEY` 등 **캠페인 호환 메타**를 검증 실행에 심음
- **DB**: `src/db/records.py` — Phase 16 CRUD·스모크
- **CLI**: `src/main.py` — 6개 서브커맨드
- **거버넌스**: `src/research_registry/promotion_rules.py` — runner·문서 경계에 `validation_campaign` 명시
- **테스트**: `src/tests/test_phase16.py`
- **문서**: `docs/phase16_evidence.md`, `HANDOFF.md`, `README.md`, `src/db/schema_notes.md`, 본 파일

## 새 CLI

| 커맨드 | 역할 |
|--------|------|
| `smoke-phase16-validation-campaign` | 테이블 도달 |
| `list-eligible-validation-hypotheses` | 캠페인 자격 가설 |
| `run-validation-campaign` | 캠페인 실행·적재 |
| `report-validation-campaign` | 캠페인 JSON |
| `report-program-survival-distribution` | 프로그램별 최근 완료 검증 생존 분포 |
| `export-validation-decision-brief` | 권고 브리프 JSON+Markdown |

## 테스트

```bash
cd src
python3 -m pytest tests/test_phase16.py tests/ -q
```

**결과**: **212 passed** (Phase 16 반영 시점).

## 재현 (요약)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase16-validation-campaign
python3 src/main.py run-validation-campaign --program-id <PROGRAM_UUID> --run-mode reuse_or_run
python3 src/main.py export-validation-decision-brief --campaign-run-id <CAMPAIGN_UUID> --out docs/validation_campaign/briefs/latest.json
```

Supabase에 **Phase 16 마이그레이션 선적용** 필요.
