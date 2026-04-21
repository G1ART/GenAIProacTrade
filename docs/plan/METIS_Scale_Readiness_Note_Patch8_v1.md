# METIS Scale-Readiness Engineering Note — Patch 8 (v1)

**작성 근거**: AGH v1 Patch 8 작업지시서 §C "scale closure — top 2 bottlenecks".
**전제 문서**: [METIS_Scale_Readiness_Note_Patch7_v1.md](./METIS_Scale_Readiness_Note_Patch7_v1.md) 의 Findings 1–6 그대로 유효. 본 노트는 그중 **F1 (factor validation 배치 IO)** 과 **F3 (번들 panel 중복 fetch + evaluator 번들 재로드)** 를 실제 코드로 닫은 뒤의 상태를 기록하며, **F2/F4/F5/F6 중 본 패치가 건드리지 않은 것** 과 **남은 500-티커 conditional green verdict** 를 단일 문서로 정리한다.

**주의**:
- 본 노트는 2026-04-21 기준 `main` + Patch 8 브랜치 코드를 근거로 한다.
- Patch 7 노트의 용어(Finding N·, CF-7·*)는 그대로 계승한다. 추가된 remedy 는 `CF-8·*` 로 구분한다.
- LLM 비용·Ask AI 자기호출 루프는 본 노트 범위 밖이다 (`layer5_*` 는 read-path 만).

---

## 1. Scope · 비-scope

### 1.1 본 노트가 다루는 것
- Patch 7 Findings 1 / 3 에 해당하는 경로를 실제 구현으로 닫았음을 **수치 없이 코드 수준에서** 기록 (실측 수치는 운영자가 Railway 배포 후 수집 예정).
- Patch 7 Findings 2 / 4 / 5 / 6 가 **왜 본 패치에서 닫히지 않는가** 와 이월 순서.
- 500 티커 conditional green verdict 업데이트 (Patch 7 노트 §4.3 에서 5 개였던 blocker → 본 패치 후 3 개).

### 1.2 다루지 않는 것
- 실제 S&P 500 라이브 전환 타임라인: 본 패치에서 시작하지 않음.
- 유료 외부 feed 확장: 여전히 Product Spec §8 "제외".
- Reliability / SLA: Stage 6 Trust closeout 영역.

---

## 2. 본 패치에서 **실제로 닫은 것** (C1 + C2)

### Finding 1 · (F1 해소) — Factor validation 배치 IO

- **Before (Patch 7)**: `validation_runner.run_factor_validation_research` 가 팩터 × quantile bucket × return_basis 의 **건건이** `factor_validation_summaries` / `factor_quantile_results` / `factor_coverage_reports` 테이블에 `insert().execute()` 왕복. run 당 수십 회 (`7 * 5 * 2 = 70` insert) + 팩터마다 panel re-scan.
- **After (Patch 8 · C1)**:
  - `src/db/records.py` 에 3 개 배치 upsert 헬퍼 신규 도입:
    - `upsert_factor_validation_summaries` (`on_conflict = factor_validation_summary_uniq`)
    - `upsert_factor_quantile_results` (`on_conflict = factor_quantile_result_uniq`)
    - `upsert_factor_coverage_reports` (`on_conflict = factor_coverage_report_uniq`)
  - `src/research/validation_runner.py` 는 팩터 루프 바깥에서 3 개 in-memory 버퍼로 누적 → run 1 회당 테이블당 upsert 1 회로 flush.
  - 패널 truncation 가시성: `summary_json` 에 `panel_truncated_at_limit` / `panel_rows_fetched` 필드 추가 (Patch 7 에서 silent truncation 위험 지적한 부분).
- **의미**: run 당 DB 왕복이 `O(factors × buckets × basis)` → `O(3)` 로 떨어진다. 의미론은 `on_conflict` 로 보존.
- **잠긴 회귀 테스트**: `src/tests/test_research_phase5.py::test_run_factor_validation_mock_rerun_shape` (memory mock 이 upsert 경로를 통과), `src/tests/test_agh_v1_patch8_production_graduation_surface.py` 의 `c1_*` 블록.

### Finding 3 · (F3 해소) — 번들 panel 중복 fetch + evaluator 재로드

- **Before (Patch 7)**: `build_bundle_full_from_validation_v1` 가 gate_specs 각각에 대해 `fetch_factor_market_validation_panels_for_symbols(..., limit=8000)` 재실행. `evaluate_registry_entries` 는 spec 마다 `load_bundle_json` 을 반복.
- **After (Patch 8 · C2a)**:
  - `src/metis_brain/bundle_full_from_validation_v1.py` 가 **per-invocation in-process 캐시** `_panel_cache` + `_resolve_shared_panels` 도입. `(universe, horizon_type)` 키로 동일 panel fetch 를 재사용한다.
  - `fetch_joined` 콜러블을 cache-aware 래퍼로 감싸 gate_specs 전반에 전파.
- **After (Patch 8 · C2b)**:
  - `src/agentic_harness/agents/layer4_promotion_evaluator_v1.py::evaluate_registry_entries` 가 `reload_between_specs` 파라미터를 도입. 기본은 **한 번만 로드** + **번들 mutation 이 실제로 발생한 경우에만** 다시 로드한다. 이전엔 spec 마다 무조건 재로드.
- **의미**: 번들 build 오프라인 실행 시간, cadence 내 evaluator tick 비용이 gate_specs / spec 수의 선형 증가를 벗어난다.
- **잠긴 회귀 테스트**: `src/tests/test_agh_v1_patch8_production_graduation_surface.py::test_c2_*`.

---

## 3. 본 패치에서 **닫지 않은 것** (이월)

Patch 7 노트의 Finding 2 / 4 / 5 / 6 가 본 패치의 scope 밖이다. 근거는 다음과 같다.

- **Finding 2 (governance scan dedupe N+1)** — **이미 Patch 7 C2a 로 종결**. 본 패치는 터치하지 않는다.
- **Finding 4 (Today payload 무한 + message snapshot 행단위 IO)** — Patch 7 C2b 가 `rows_limit` + `total_rows` + `truncated` 로 응답 크기 cap 까지 해결. 이월 remedy (`persist_message_snapshots_for_spectrum_payload` 의 object-detail 지연 생성 전환, `_horizon_lens_compare` 번들 단위 캐시) 는 Build Plan §12 "Today registry-only" 계약과 저촉하지 않도록 **지연 생성 경계 설계** 가 선행해야 해서 Patch 9 이후 과제.
- **Finding 5 (패킷/잡 retention)** — migration + archive 테이블 도입이 Supabase 운영 정책 변화를 요구. 본 패치는 "원클릭 Railway 배포" 를 추가하는 작업이라 scope 경쟁. **CF-8·A (이월)** = `agentic_harness_packets_v1_archive` / `agentic_harness_queue_jobs_v1_archive` 테이블 + 야간 배치 + `count_packets_by_layer` 서버측 GROUP BY 치환.
- **Finding 6 (Research structured lookup linear scan)** — `agentic_harness_packets_v1` 의 `target_scope` JSONB 인덱스가 필요. **CF-8·B (이월)** = `target_scope->>'asset_id'` + `target_scope->>'horizon'` 인덱스 + `list_packets` 의 선택적 필터 인자.

---

## 4. C3 Verdict — S&P 500 (~500 ticker) readiness (Patch 8 버전)

### 4.1 **충분한 것** (Patch 7 대비 추가분만)
- **Factor validation write path**: F1 해소로 run 당 DB 왕복이 상수 시간으로 접혔다. 팩터 / bucket / return_basis 확장에도 runner 자체 비용은 일정.
- **번들 build + evaluator tick cost**: F3 해소로 gate_specs / spec 수에 대해 선형이 아니라 상수 시간 재로드 (mutation 발생 시 제외).
- **Operator-visible scale hazards**: `summary_json.panel_truncated_at_limit` / `panel_rows_fetched` 가 이제 가시적이라 500 티커 panel_limit(8000) overrun 을 더 이상 silent 로 놓치지 않는다.
- **3-tier 번들 graduation**: `demo` / `sample` / `production` vocabulary + 자동 추론 + UI 뱃지. 500 티커 운영 시 `v2` bundle 이 `production` tier 로 승격되었는지 `/api/runtime/health` 한 번으로 확인 가능.
- **Runtime 하드닝**: `/api/runtime/health` 가 degraded 를 200 + reasons 로 노출. 500 티커 스케일에서 부분 장애(오버레이 빌더 일시 실패 등) 가 전체 가용성으로 증폭되지 않는다.

### 4.2 **아직 막는 것** (Patch 7 대비 감산)

Patch 7 노트 §4.2 에서 열거한 5 개 중 **1·2 는 닫혔다**. 남은 3 개 + 본 패치에서 새로 드러난 0 개:

1. **`universe_memberships` / packets `target_scope` 인덱스 부재** (Patch 7 F6 그대로) — `CF-8·B`.
2. **Today JSON 페이로드 per-row snapshot IO** (Patch 7 F4 이월분) — object-detail 진입 시 지연 생성으로 전환 필요.
3. **패킷/잡 retention 정책 부재** (Patch 7 F5 그대로) — `CF-8·A`.

본 패치는 위 3 개에 **의도적으로 착수하지 않는다**. 근거: 각각이 DB migration + 운영 런북 변화를 동반해 "production graduation" 의 다른 축 (UX wow, deployment harness) 과 PR 범위 경쟁을 일으키기 때문.

### 4.3 **다음 concrete patch (Patch 9 "Retention + Today lazy snapshot")**
본 노트는 Patch 9 의 구체 구현이 아니라 **범위 추정** 이다. 다음 4 건이 한 PR 묶음으로 적절하다.

1. **CF-8·A** — `agentic_harness_packets_v1_archive` + `agentic_harness_queue_jobs_v1_archive` 테이블, 야간 배치, `count_packets_by_layer` 서버측 GROUP BY.
2. **CF-8·B** — `agentic_harness_packets_v1 (target_scope->>'asset_id', target_scope->>'horizon')` 인덱스 + `list_packets` 필터 인자.
3. **CF-8·C** — `persist_message_snapshots_for_spectrum_payload` 를 object-detail 진입 시 지연 생성으로 전환. 스펙트럼 페이지 단독으로 snapshot 을 생성하지 않는다.
4. **CF-8·D** — `_horizon_lens_compare` 결과를 번들 단위 캐시화해 Today 응답에서 3 배 증폭을 없앤다.

### 4.4 최종 verdict
> 500 티커 운영은 **Patch 8 기준으로 conditional green** 이다. 조건: (a) `v2` bundle 이 `production` tier 로 승격되었는가, (b) `/api/runtime/health` 가 `ok` 이고 `mvp_brain_gate.brain_bundle_tier == 'production'` 인가, (c) `panel_truncated_at_limit == false` 인가. 이 3 개가 green 이면 운영 시작은 가능하다. Patch 9 의 retention + Today lazy snapshot 이 닫히기 전까지는 **운영 3–6 개월 경과 후 health 응답 시간이 DB 크기에 선형** 이라는 전제를 유지해야 한다.

---

## 5. 참고

- 본 노트는 `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md` §8 "대규모 유료 데이터 확장 제외" 를 침해하지 않는다 (S&P 500 은 기존 무료 구성종목 목록 범위).
- `docs/plan/METIS_MVP_Unified_Build_Plan_KR_v1.md` §12 "항상 지킬 문장" 6 개는 Patch 8 범위 전체에서 유효 (Today registry-only, Artifact required, Memo≠Message, Heart free / Brain strict, Skin closes on Brain, Replay needs lineage).
- 본 노트의 자매 문서:
  - [METIS_Production_Bundle_Graduation_Note_v1.md](./METIS_Production_Bundle_Graduation_Note_v1.md) — 3-tier 번들 규약.
  - [docs/ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md](../ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md) — 배포 런북.
