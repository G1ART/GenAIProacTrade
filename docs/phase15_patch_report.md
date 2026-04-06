# Phase 15 패치 결과 보고서

**문서 기준일**: 2026-04-06  
**워크오더**: `GenAIProacTrade_Phase15_Workorder_2026-04-06.md`

## HEAD

| 구분 | 값 |
|------|-----|
| 패치 직전 | `c9767e0` |
| 패치 적용 후 | `0fc9f42` — `feat(phase15): recipe validation lab, baselines, survival, scorecard CLI` |

## 변경 요약

Phase 14의 `candidate_recipe`/`sandbox`를 **공개 데이터만**으로 검증하는 **Recipe Validation Lab**을 추가했다. `factor_market_validation_panels`와 `issuer_state_change_scores`를 시그널일·CIK로 조인해 분위 스프레드를 계산하고, state_change·naive·규모 프록시 베이스라인과 비교한 뒤 생존 판정·실패 행·스코어카드를 DB에 남긴다. `state_change.runner`는 `research_validation`을 참조하지 않으며, 거버넌스 문자열도 갱신했다.

- **마이그레이션**: `supabase/migrations/20250418100000_phase15_recipe_validation_lab.sql`
- **패키지**: `src/research_validation/` (`constants`, `metrics`, `policy`, `scorecard`, `service`)
- **DB**: `src/db/records.py` — Phase 15 CRUD·스모크
- **CLI**: `src/main.py` — 6개 서브커맨드(스모크 포함)
- **거버넌스**: `src/research_registry/promotion_rules.py`
- **테스트**: `src/tests/test_phase15.py`
- **문서**: `docs/phase15_evidence.md`, `HANDOFF.md`, `README.md`, `src/db/schema_notes.md`
- **`.gitignore`**: `docs/research_validation/scorecards/*.{json,md}`

## 테스트

```bash
cd src
python3 -m pytest tests/test_phase15.py tests/ -q
```

**결과**: 전체 **200 passed** (Phase 15 추가 시점).

## 재현 CLI (요약)

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase15-recipe-validation
python3 src/main.py run-recipe-validation --hypothesis-id <UUID>
python3 src/main.py export-recipe-scorecard --hypothesis-id <UUID> --out docs/research_validation/scorecards/latest.json
```
