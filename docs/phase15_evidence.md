# Phase 15 증거 — Recipe Validation Lab & Comparator

**범위**: Phase 14 가설 중 `candidate_recipe`·`sandboxed`만, **리뷰 1건 이상** 있을 때 검증 가능. `next_quarter` excess(`excess_return_1q`) + 동일 시그널일 `issuer_state_change_scores` 조인. **프리미엄 불필요. 제품 스코어링/워치리스트 비침투.**

## 잠금 검증 질문 (Phase 15 심화)

Phase 14와 동일 테마: 분기 내 반응 비대칭·지연 인식에 대해, **결정적 베이스라인 대비** 후보 레시피가 무엇을 더 설명하는가 — 실패·취약성은 어디인가.

## 명시 베이스라인 (최소 3종)

| 이름 | 정의 |
|------|------|
| `state_change_score_only` | `state_change_score_v1`로 분위 스프레드(상·하 꼬리 excess 평균 차) |
| `naive_null` | 무신호(델타 0) 대비 후보 스프레드 |
| `market_cap_inverse_rank` | `-log(market_cap)` 랭크 프록시(단순 규모 틸트 대조) |

## 코호트·창

- **품질**: 프로그램 `linked_quality_context_json.quality_class` 기록(행 메타); `thin_input`·`failed`/`degraded`는 정책 상한.
- **크기**: 표본 내 `market_cap` 3분위(`size_small`/`size_mid`/`size_large`).
- **창**: `signal_available_date` 연도별 슬라이스 + 풀드; 연도별 레시피 스프레드 변동으로 안정도 프록시.

## 생존 상태

`survives` | `weak_survival` | `demote_to_sandbox` | `archive_failed` — `sandboxed` 가설은 **`survives` 불가**; `thin_input` 맥락은 **`survives` 캡(최대 weak)**; `failed`/`degraded` 품질은 **상한 `demote_to_sandbox`**.

## 실패 메모리 (`recipe_failure_cases`)

코호트에서 state_change 대비 열세, `contradictory_public_signal` 잔차 링크, `thin_input_program_context_dependence` 등 구조화 저장.

## 테이블

- `recipe_validation_runs`, `recipe_validation_results`, `recipe_validation_comparisons`, `recipe_survival_decisions`, `recipe_failure_cases`

마이그레이션: `20250418100000_phase15_recipe_validation_lab.sql`

## 코드 위치

- `src/research_validation/` — 메트릭, 정책, 스코어카드, 서비스
- `src/db/records.py` — CRUD
- `src/main.py` — CLI
- `src/research_registry/promotion_rules.py` — `research_validation` 스코어 경로 차단 문자열

## 테스트

`src/tests/test_phase15.py` — 리뷰 필수·상태·thin_input/sandbox 캡·생존 enum·실패 적재·스코어카드·runner 비참조 등.

## 다음 단계 판단 (증거 기반)

운영 DB에서 `run-recipe-validation` 후 `report-recipe-survivors`로 **`survives` 유무**를 본 뒤:

- 잔여가 대부분 `archive_failed`/`weak_survival`이면 **공개 데이터 백필·패널 깊이** 우선.
- 구조적 `contradictory_public_signal`·프리미엄 힌트가 반복되면 **단일 프리미엄 seam PoC** 검토.
