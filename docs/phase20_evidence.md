# Phase 20 증거 메모 — Public Repair Iteration Manager & Escalation Gate

## 목적

Phase 19 **단일** 수리 캠페인 루프를 시간에 따라 반복하면서, 기판·재실행·생존·프리미엄 힌트 **추세**를 감사하고 **스톱/반복/에스컬레이션**을 한 값으로 고정한다. 운영자 **골든 패스**에서는 `latest` 선택자로 UUID를 줄인다. `state_change.runner`는 `public_repair_iteration`을 **참조하지 않는다**.

## 스키마

| 객체 | 설명 |
|------|------|
| `public_repair_iteration_series` | `program_id`, `universe_name`, `policy_version`, `status`(active/closed/paused) |
| `public_repair_iteration_members` | `series_id`, `repair_campaign_run_id`, `sequence_number`, `trend_snapshot_json` |
| `public_repair_escalation_decisions` | 시리즈 단위 권고 3분기, `plateau_metrics_json`, `counterfactual_json` |

## 에스컬레이션 권고 (프로그램 단위)

- `continue_public_depth` — 추세상 공개 쪽에 여지가 있음.
- `hold_and_repeat_public_repair` — 데이터·반복 부족 또는 신호 혼재.
- `open_targeted_premium_discovery` — **다회 반복**·플래토·프리미엄 신호 등 **엄격 조건** 충족 시만(라이브 프리미엄 통합 아님).

## Resolver (`src/public_repair_iteration/resolver.py`)

- `--program-id latest` + `--universe U`: 해당 유니버스 비아카이브 프로그램 중 `created_at` 최신.
- `--program-id latest` 단독: 최근 프로그램들이 **단일 유니버스**로만 해석될 때만 허용; 아니면 `ambiguous_latest_program_need_universe`.
- `--repair-campaign-id latest`: `--program-id`로 스코프한 뒤 최신 런(export 브리프는 완료+`final_decision` 있는 런만).

## CLI

```bash
export PYTHONPATH=src
python3 src/main.py smoke-phase20-repair-iteration
python3 src/main.py run-public-repair-iteration --program-id latest --universe sp500_current
python3 src/main.py report-public-repair-iteration-history --program-id latest --universe sp500_current
python3 src/main.py report-public-repair-plateau --program-id latest --universe sp500_current
python3 src/main.py export-public-repair-escalation-brief --program-id latest --universe sp500_current --out docs/public_repair/escalation_latest.json
python3 src/main.py list-public-repair-series --program-id latest --universe sp500_current
python3 src/main.py report-latest-repair-state --program-id latest --universe sp500_current
python3 src/main.py report-premium-discovery-readiness --program-id latest --universe sp500_current
```

Phase 19: `report-public-repair-campaign`, `compare-repair-revalidation-outcomes`, `export-public-repair-decision-brief`, `list-repair-campaigns`, `run-public-repair-campaign` — `latest` / `--universe` 지원.

마이그레이션: `supabase/migrations/20250423100000_phase20_repair_iteration.sql`.

## 테스트

`PYTHONPATH=src python3 -m pytest src/tests/test_phase20.py -q` → **11 passed** (전체 `src/tests` **253 passed** 기준).
