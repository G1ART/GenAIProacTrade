# Phase 24 증거 메모 — 공개 우선 경험층

## 목적

시리즈·멤버·플래토 위생 규칙을 유지한 채, **여러 호환 시리즈에 걸친** 에스컬레이션 브랜치·depth 신호·개선 분류를 한 번에 집계하고, **3가지 플래토 리뷰 결론**과 **교대 코디네이터**로 다음 행동을 설명 가능하게 만든다.

## CLI 재현

```bash
export PYTHONPATH=src
python3 src/main.py report-public-first-branch-census --program-id latest --universe YOUR_UNIVERSE
python3 src/main.py export-public-first-branch-census-brief --program-id latest --universe YOUR_UNIVERSE --out docs/operator_closeout/census_brief
python3 src/main.py export-public-first-plateau-review-brief --program-id latest --universe YOUR_UNIVERSE --out-stem docs/operator_closeout
python3 src/main.py advance-public-first-cycle --universe YOUR_UNIVERSE
```

## 산출물

| 경로 | 내용 |
|------|------|
| `docs/operator_closeout/public_first_plateau_review.json` | census + plateau_review 번들 |
| `docs/operator_closeout/latest_public_first_review.md` | 창업자용 요약(지배 브랜치·개선·다음 명령 권장) |
| `advance-public-first-cycle` 실행 시 | 동일 MD 갱신 + stdout에 chosen/executed 요약 |

## 2026-04-07 `sp500_current` (Phase 23 클로즈 직후 맥락)

- 클로즈아웃: `hold_and_repeat_public_repair` + `repeat_targeted_public_repair` → **수리 전진** 선택.
- **프리미엄 디스커버리**: 에스컬레이션이 `open_targeted_premium_discovery` 가 아니므로 Phase 24 규칙상 **`premium_discovery_review_preparable` 아님** (리뷰 준비 완료로 보지 않음).
- **공개 우선**: 스택·시리즈는 계속; 집계는 `report-public-first-branch-census` 로 시계열·다중 시리즈 관점 보강.

## 테스트

`pytest src/tests/test_phase24_public_first.py -q` — 전체 `pytest src/tests -q` **309 passed** (저장소 기준).

## 코드 위치

- `src/public_first/census.py`, `plateau_review.py`, `cycle.py`
- `src/main.py` 서브커맨드 등록
