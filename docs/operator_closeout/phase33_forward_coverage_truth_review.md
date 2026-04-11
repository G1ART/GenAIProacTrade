# Phase 33 — Forward coverage truth + metric alignment

_Generated (UTC): `2026-04-08T22:37:25.854463+00:00`_

## 운영 감사 요약 (post-run)

- **헤드라인은 한 치도 움직이지 않았다** (joined 243, missing_excess 101 유지). 대신 **truth 블록**이 이유를 분리해 준다: 터치 30 심볼에 대해 라이브 검증 패널 **30행 모두 `excess_return_1q` null** → **`symbol_cleared_from_missing_excess_queue_count` 0**과 정합.
- **가격 백필 0건**은 실패가 아니라 분류 결과: 샘플 7건이 모두 **`lookahead_window_not_matured`** 라서 `missing_market_prices_daily_window` 백필 경로에 들어가지 않았다.
- **forward 재시도**는 upsert **5**건 성공·**9**건 실패로 부분적 진행; joined/excess 헤드라인에는 아직 반영되지 않음.
- **GIS**는 개념맵 샘플에서 전부 unmapped로 **명시적 차단** — 워크오더대로 대극모 silver 확장 없음.
- 상세 표·표본: `docs/phase33_evidence.md`.

## Truth semantics (do not conflate)

- **forward_row_unblocked_now_count** (forward upsert ops this run): `5`
- **symbol_cleared_from_missing_excess_queue_count** (touched-set truth, live): `0`
- **joined_recipe_unlocked_now_count** (delta): `0`
- **price_coverage_repaired_now_count**: `0`
- excess-null rows on touched symbols (live): `30`

## Headline substrate (Before → After)

| Metric | Before | After |
| --- | --- | --- |
| joined_recipe_substrate_row_count | `243` | `243` |
| thin_input_share | `1` | `1` |
| missing_excess_return_1q | `101` | `101` |
| missing_validation_symbol_count | `151` | `151` |
| missing_quarter_snapshot_for_cik | `148` | `148` |
| factor_panel_missing_for_resolved_cik | `148` | `148` |

## Quarter snapshot classification (end of run)

- `no_filing_index_for_cik`: `147`
- `raw_present_no_silver_facts`: `1`

## Price coverage classification (Phase 32 NQ failures)

- `lookahead_window_not_matured`: `7`

## Price backfill

- repaired: `0`
- deferred: `0`
- blocked: `0`

## Why Phase 32 repair count vs headline

Phase 32의 repaired_to_forward_present는 심볼당 대표 시그널일 1건 기준으로 next_quarter excess가 채워졌는지 본 것이다. missing_excess_return_1q 큐는 해당 심볼의 검증 패널 행 중 excess가 하나라도 비면 심볼 전체를 큐에 넣는다. 따라서 일부 시그널만 채워도 심볼은 큐에 남을 수 있고, 다른 심볼/행이 새로 들어오면 헤드라인 카운트는 오히려 늘어난다.

## GIS (narrow)

- outcome: `blocked_unmapped_concepts_remain_in_sample`
- blocked_reason: `concept_map_misses_for_sampled_raw_concepts`

## Phase 34 recommendation

- `continue_forward_and_price_coverage_with_truth_metrics`
- 가격·forward 재시도에 진전이 있으나 joined/excess 헤드라인은 아직 — 시그널일·창 성숙·추가 심볼 확장을 상한 내에서 계속.

---

_Phase 34 후속 (2026-04-09): 터치 30행 중 forward excess 대비 validation 미동기화 23행을 패널 재빌드로 해소, `missing_excess_return_1q` 101→78. **`docs/operator_closeout/phase34_forward_validation_propagation_review.md`**, **`docs/phase34_evidence.md`**._
