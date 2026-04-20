# METIS Scale-Readiness Engineering Note — Patch 7 (v1)

**작성 근거**: AGH v1 Patch 7 작업지시서 §6 (Scope C — Scale-readiness toward broader ticker coverage).
**목적**: 현재 ~200 티커 백필 상태에서 **S&P 500 (≈500 티커)** 커버리지로 확장할 때 어디가 먼저 막히는지, 본 패치(Patch 7) 범위에서 **low-risk** 로 해소 가능한 항목과 **이월** 항목을 근거 있게 구분한다. 이것은 **투자자용 약속 문서가 아니라 베타 사용자 확장 전** 엔지니어링 합의문이다.

**주의**:
- 본 노트는 2026-04-20 기준 `main` 코드를 근거로 한다.
- "현재 ≈200 티커" 는 `data/mvp/*BACKFILL_200_V1*` / `sp500_current` / `sp500_proxy_candidates_v1` 유니버스의 운영 상태를 가리키며, `METIS_MVP_Unified_Product_Spec_KR_v1.md` §8 의 "대규모 유료 데이터 확장 제외" 와는 독립된 **내부 백필·검증** 범위이다.
- 성능 상수(8000 / 200 / 50) 은 Supabase / SDK 의 무료·스타터 티어에서 관찰된 값이며, `METIS_MVP_Unified_Build_Plan_KR_v1.md` §12 "항상 지킬 문장" 을 깨지 않는 범위에서만 조정한다.

---

## 1. Scope · 비-scope

### 1.1 본 노트가 다루는 것
- 운영 파이프라인(검증 → 번들 → 거버넌스 → Today → Replay) 의 **per-ticker 비용 함수** 와 **Supabase / store 왕복 횟수**.
- Patch 7 에서 **즉시 닫을 수 있는** 4 개 저위험 수정 (`C2`).
- Patch 8 이후로 이월되는 구조적 작업 (`CF-7·*`).

### 1.2 다루지 않는 것
- LLM 품질·Ask AI 비용: §7 scope 밖 (`layer5_*` 는 read-path 만).
- 실제 S&P 500 라이브 롤아웃 타임라인: 본 패치에서 시작하지 않음.
- 데이터 공급자 단가: 유료 외부 feed 확장 자체가 Product Spec §8 "제외" 이므로 대상 아님.
- Reliability / SLA / 재해복구 등 Stage 6 Trust closeout 의 영역.

---

## 2. 6 Findings (파일·라인·현상·위험·처방)

각 항목은 다음 5개 필드로 구조화한다:
- **위치** = 파일:라인 (2026-04-20 기준 HEAD).
- **현재 동작**.
- **500 티커 시 구체적 제약**.
- **Patch 7 저위험 remedy** (본 패치에서 구현 or 의도적 보류).
- **이월 full remedy** (Patch 8+).

### Finding 1 — Factor validation cadence 비용 (per-factor × per-row)

- **위치**: [src/research/validation_runner.py](../../src/research/validation_runner.py) `run_factor_validation_research` (≈129–307), [src/db/records.py](../../src/db/records.py) `insert_factor_validation_summary` / `insert_factor_quantile_result` / `insert_factor_coverage_report` (≈1310–1318).
- **현재 동작**: `VALIDATION_FACTORS_V1` (~7 팩터) 각각에 대해 `factor_market_validation_panels` 전체(`panel_limit=8000`, `validation_runner.py:72–73`) 를 **팩터마다** 재스캔하고, quantile bucket·coverage row 마다 **건건이** Supabase `insert().execute()` 왕복. 동일 `(universe, horizon_type)` 에 대해서도 팩터마다 패널 row 를 처음부터 다시 읽는다.
- **500 티커 시 제약**:
  - 패널 row 수 R ≈ (티커 × 관측 분기 수) 가 `panel_limit=8000` 을 **silent truncation** 으로 잘라낼 여지 — 500 × 16 분기 (≈4 년) = 8 000 을 맞물림. 실측은 로깅 없이 넘어가므로 커버리지가 조용히 떨어질 수 있다.
  - 팩터 7 × bucket 5 × return_basis 2 (raw/excess) = **70 insert 왕복/run**. run 이 유니버스×호라이즌 수(현재 3 슬라이스 × 2 지평 = 6 이상) 로 곱해지면 수백 회 왕복.
- **Patch 7 remedy**: **없음 (의도적 보류)**. 배치 upsert · 서버측 batch RPC 는 스키마/마이그레이션 영향이 커서 "low product risk" 기준 초과. 대신 **C3 verdict 에 명시**해 Patch 8 으로 이월.
- **이월 full remedy (CF-7·1)**:
  1. `factor_validation_summaries` / `factor_quantile_results` / `factor_coverage_reports` 에 서버측 배치 upsert RPC 도입.
  2. `fp_rows_for_cov` 를 팩터 공통 1-pass 로 재설계해 `for factor in VALIDATION_FACTORS_V1` 안의 panel re-scan 제거.
  3. `panel_limit` 초과 시 **명시적 truncation 경고** 를 `summary_json` 에 기록 (현재는 조용히 잘림).

### Finding 2 — Governance scan dedupe N+1 ★

- **위치**: [src/agentic_harness/agents/governance_scan_provider_v1.py](../../src/agentic_harness/agents/governance_scan_provider_v1.py) `deduplicate_specs` (287–326) + `_existing_evaluation_matches` (259–284).
- **현재 동작**: `deduplicate_specs` 가 **spec 마다** `_existing_evaluation_matches` 를 호출하고, 그 안에서 `store.list_packets(packet_type="ValidationPromotionEvaluationV1", limit=200)` 를 **매번** 재실행. spec K 개이면 Supabase `SELECT ... LIMIT 200` 이 **K 회** 반복된다. dedupe 는 `(registry_entry_id, horizon, derived_artifact_id, validation_run_id)` 4-튜플 동등성만 본다.
- **500 티커 시 제약**:
  - governance_scan cadence = 15 분 (`src/agentic_harness/scheduler/cadences.py:21`). 실 운영 시 15 분마다 spec K × 200-row select 가 발생. 레지스트리가 확장되면 K 가 유니버스×호라이즌×팩터 로 선형 증가.
  - 동일 패킷 집합을 매번 full deserialize → 파이썬 선형 루프로 비교하므로 CPU 측면 비용도 쌓인다.
- **Patch 7 remedy (C2a 로 구현)**:
  - `deduplicate_specs` 를 루프 밖에서 `list_packets(..., limit=max(200, K*2))` **1회** 호출 → `set[(reg, hz, art, run)]` in-memory 인덱스 → spec 들을 O(1) 로 필터. 의미 동일 (같은 4-튜플 동등성), 쿼리 K → 1.
  - 회귀 테스트 `test_agh_v1_patch7_governance_dedupe_no_n_plus_1.py` 가 fixture store 카운터로 잠금.
- **이월**: 해당 없음 (본 패치에서 종결).

### Finding 3 — 번들 joined fetch 중복 (per-gate panel re-read)

- **위치**: [src/metis_brain/bundle_full_from_validation_v1.py](../../src/metis_brain/bundle_full_from_validation_v1.py) 약 595–681 의 `build_bundle_full_from_validation_v1` gate_specs 루프.
- **현재 동작**: `gate_specs` 각각에 대해 `resolve_slice_symbols` → `fetch_factor_market_validation_panels_for_symbols(..., limit=8000)` → accession 배치 → `joined` 구축. 동일 `(universe, horizon_type)` 조합을 여러 gate 가 공유할 때 **패널 fetch 가 반복**.
- **500 티커 시 제약**: 번들 build 는 오프라인 CLI (`harness-build-metis-brain-bundle-from-factor-validation`) 에서 실행되므로 runtime 지연에는 영향이 없으나, **빌드 횟수 × gate 수 × 8000 row fetch** 가 운영자 로컬/CI 실행시간을 선형 증가시킨다.
- **Patch 7 remedy**: **없음 (의도적 보류)**. gate_specs 그룹핑은 스키마 영향 없지만 build 로직 전반을 건드려야 해 "low product risk" 기준과 거리.
- **이월 full remedy (CF-7·2)**: gate_specs 를 `(universe, horizon_type)` 으로 사전 그룹핑해 panel/accession fetch 를 **그룹당 1회** 로 공유. evaluator 측 `evaluate_registry_entries` (`layer4_promotion_evaluator_v1.py` ≈1126–1168) 에서도 spec 마다 `load_bundle_json` 하는 패턴이 동일한 형태로 있어 묶어서 정리.

### Finding 4 — Today payload 무한 (unbounded rows) ★

- **위치**: [src/phase47_runtime/today_spectrum.py](../../src/phase47_runtime/today_spectrum.py) `build_today_spectrum_payload` (560–681), `_horizon_lens_compare` (214–248), `persist_message_snapshots_for_spectrum_payload` (546–557), [src/phase47_runtime/routes.py](../../src/phase47_runtime/routes.py) `/api/today/spectrum` (886–890).
- **현재 동작**:
  - `build_today_spectrum_payload` 가 해당 호라이즌의 스펙트럼 row 를 **전부** 리스트로 반환. HTTP JSON 이 N 에 선형.
  - `_horizon_lens_compare` 는 **다른 3 호라이즌** 각각에 대해 `build_today_spectrum_payload` 를 재실행 → 스펙트럼 빌드 비용이 3 배.
  - `persist_message_snapshots_for_spectrum_payload` 가 row 마다 `upsert_message_snapshot` 호출 → 디스크 IO ~ N.
  - `/api/today/spectrum` 라우트는 `rows_limit` / `limit` 파라미터 없음.
- **500 티커 시 제약**:
  - 스펙트럼 row 수 ≤ 티커 수이므로 500 티커 = 500 row. JSON 페이로드가 수백 KB 이상으로 부풀어 **첫 화면 체감** 이 급감.
  - 스냅샷 upsert 500 회 × 호라이즌 수 × refresh 빈도 = 디스크 IO 병목.
  - `_horizon_lens_compare` 는 동일 비용을 3 배로 증폭.
- **Patch 7 remedy (C2b 로 구현)**:
  - `/api/today/spectrum` 에 **optional** `rows_limit` 쿼리 파라미터 (default 200, cap 1 000) 추가.
  - 응답에 `total_rows: int`, `truncated: bool` 선언적 필드 추가 (기존 계약 깨지 않음, 추가 필드 only).
  - `build_today_spectrum_payload` 가 `rows_limit` 을 수신받아 rows slice 및 두 필드 emit.
  - UI `loadTodaySpectrumDemo` 는 기본값(=200) 으로 계속 호출 → default 경로 변화 없음.
  - 회귀 테스트 `test_agh_v1_patch7_today_spectrum_rows_limit.py`.
- **이월 full remedy**:
  - `persist_message_snapshots_for_spectrum_payload` 를 행 단위 upsert → **object-detail 진입 시 지연 생성** 으로 전환 (스펙트럼 페이지 단독으로는 스냅샷 생성 안 함).
  - `_horizon_lens_compare` 결과를 번들 단위 캐시화.

### Finding 5 — 큐/패킷 retention 부재

- **위치**: [src/agentic_harness/store/supabase_store.py](../../src/agentic_harness/store/supabase_store.py) 의 `list_packets` / `count_packets_by_layer` / `list_jobs`, 마이그레이션 `supabase/migrations/20260417120000_agentic_harness_v1.sql` (agentic_harness_packets_v1 / jobs 테이블).
- **현재 동작**:
  - `count_packets_by_layer` 가 `select("target_layer")` 로 **전체 row** 를 가져와 파이썬에서 group-by.
  - 오래된 `done` 잡·패킷 삭제 또는 아카이브 정책 없음. 마이그레이션에서 TTL 트리거나 파티셔닝 선언 없음.
  - Health 패널의 `build_status_snapshot` 이 이 `count_packets_by_layer` 를 호출 → 운영 내내 성능이 선형 악화될 수 있음.
- **500 티커 시 제약**: 티커 수가 아니라 **운영 시간** 에 선형. ~3–6 개월 운영 후 DB 테이블이 수십만 row 에 달하면 health 조회·replay lineage 조회가 동시 느려짐.
- **Patch 7 remedy**: **없음 (의도적 보류)**. retention 정책은 DB migration + 운영 런북 변화가 필요.
- **이월 full remedy (CF-7·4)**: (a) `agentic_harness_packets_v1_archive`, `agentic_harness_queue_jobs_v1_archive` 테이블 도입, (b) `done` 이후 N 일 초과 row 를 야간 배치로 archive, (c) `count_packets_by_layer` 를 DB 측 `count(*) GROUP BY target_layer` 로 치환.

### Finding 6 — Research structured lookup linear scan

- **위치**: [src/phase47_runtime/today_spectrum.py](../../src/phase47_runtime/today_spectrum.py) `_latest_research_structured_v1_for_asset` (≈1090–1149), `build_today_object_detail_payload` (≈1152–1285).
- **현재 동작**: `list_packets(packet_type="UserQueryActionPacketV1", limit=200)` 으로 최대 200 건을 가져와 파이썬에서 `asset_id` + `horizon` 매칭 최신 1건을 선택. 반환 비용은 티커 수가 아니라 **누적 Ask 패킷 수** 에 비례.
- **500 티커 시 제약**: 대부분의 티커는 Ask 기록이 없음(대부분 none 반환) → 매 object-detail 요청이 200 row 를 가져와 파이썬 선형 스캔하는 비용을 지불. Ask 빈도가 누적될수록 "200 cap" 안에 원하는 자산이 없어 조용히 missing 으로 퇴화할 위험.
- **Patch 7 remedy**: **없음 (의도적 보류)**. 서버측 JSONB 인덱스 또는 `target_scope` 필터 쿼리 추가가 필요.
- **이월 full remedy (CF-7·3)**: `agentic_harness_packets_v1` 에 `target_scope->>'asset_id'` + `target_scope->>'horizon'` GIN/BTREE 인덱스 추가하고 `list_packets` 에 `asset_id` / `horizon` 필터 인자 투입.

---

## 3. Patch 7 에서 실제 구현하는 것 (C2 요약)

아래 4 건만 본 패치에서 구현한다. 각각은 (a) 계약 backcompat 유지, (b) 단일 PR 수준의 범위, (c) 명확한 회귀 테스트로 잠긴다.

| # | 작업 | 파일 | 의미 |
|---|------|------|------|
| **C2a** | `deduplicate_specs` N+1 fix (list_packets 루프 밖 1회) | [src/agentic_harness/agents/governance_scan_provider_v1.py](../../src/agentic_harness/agents/governance_scan_provider_v1.py) | 쿼리 K → 1, 의미 동일 |
| **C2b** | `/api/today/spectrum?rows_limit=N` + `total_rows` / `truncated` | [src/phase47_runtime/today_spectrum.py](../../src/phase47_runtime/today_spectrum.py), [src/phase47_runtime/routes.py](../../src/phase47_runtime/routes.py) | 응답 크기 explicit cap, UI default 경로 불변 |
| **C2c** | `/api/replay/governance-lineage?limit=N` + cap(500) | [src/phase47_runtime/routes.py](../../src/phase47_runtime/routes.py) | 운영자가 줄일 수 있도록 |
| **C2d** | `perf_counter` stderr JSON 로그 4 지점 | `build_today_spectrum_payload` / `build_today_object_detail_payload` / `run_one_tick` / `deduplicate_specs` | 의존성 0, 향후 Patch 8 에서 근거 데이터로 사용 |

본 패치는 DB 마이그레이션을 추가하지 않으며, 새로운 환경변수도 도입하지 않는다 (Patch 6 `METIS_HARNESS_UI_INVOKE_ENABLED` 유지).

---

## 4. C3 Verdict — S&P 500 (~500 ticker) readiness

### 4.1 이미 **충분한 것**
- **Truth spine**: `factor_validation_*` 스키마, PIT 계약 (`summary_json.pit_certified`), `forward_returns_daily_horizons.horizon_type`, risk-free `FRED DTB3` 결정적 pipeline 이 이미 ~200 티커에서 실측되어 green. 스키마 자체는 500 으로 확장해도 불변.
- **Registry / Brain bundle 무결성**: `validate_active_registry_integrity` 가 호라이즌마다 active/challenger 구분과 spectrum row 정합을 강제. 500 ticker 로 확장해도 스키마 제약은 동일하게 유효 (cost 는 Finding 4 별도).
- **Governance bridge**: Patch 4–5 의 `ValidationPromotionEvaluationV1` + proposal → decision → apply → spectrum refresh + sandbox follow-up 체인은 logical 레벨에서 티커 수에 무관. 운영 속도만 Finding 2 로 눌린다.
- **Operator gate / LLM write-zero**: Patch 2–6 모든 가드 (Build Plan §12) 가 그대로. LLM 은 레지스트리/번들에 단 한 바이트도 쓰지 못한다.
- **KO/EN shell + locale coverage honesty**: Patch 6 `locale_coverage` 계약 + `tsr.*` 로캘 + no-leak 스캐너. 500 티커 확장과 독립적으로 유지됨.

### 4.2 아직 **막는 것**
1. **Panel build per-row I/O** (Finding 1·3) — 배치 RPC 또는 서버측 집계 없이는 빌드 시간이 선형 × 상수 (gate_specs) 로 증폭.
2. **Governance evaluator per-spec 번들 재로드** (Finding 2 관련, `layer4_promotion_evaluator_v1.py::evaluate_registry_entries`) — cadence tick 마다 K 번 full JSON 파싱. Finding 2 fix 가 쿼리 측만 해결.
3. **`universe_memberships` / packets `target_scope` 인덱스 부재** (Finding 6) — linear scan 한계를 인덱스로만 깰 수 있음.
4. **Today JSON 페이로드 크기** — Finding 4 C2b 로 응답 cap 은 해결하지만, `persist_message_snapshots_for_spectrum_payload` 의 행단위 IO 는 그대로.
5. **패킷/잡 retention 정책 부재** (Finding 5) — 운영 3–6 개월 스케일로 들어가면 health/replay 조회가 DB 크기에 비례해 느려짐.

### 4.3 **다음 concrete patch (Patch 8 "Scale Expansion")**
본 노트는 Patch 8 의 구체 구현이 아니라 **범위 추정** 이다:
1. **Supabase 배치 RPC** — `factor_validation_summaries` / `factor_quantile_results` / `factor_coverage_reports` / `factor_market_validation_panels` 다중 행 upsert.
2. **인덱스 + migration** — `universe_memberships (universe_name, as_of_date)`, `agentic_harness_packets_v1 (target_scope->>'asset_id', target_scope->>'horizon')`.
3. **패킷/잡 archive 테이블 + 야간 배치** — done N 일 후 archive.
4. **gate_specs (universe, horizon_type) 그룹핑** — 번들 빌드 + evaluator 양쪽에서 동일 panel/accession fetch 재사용.
5. **`_horizon_lens_compare` 캐시 / 스냅샷 지연 생성** — Today runtime 응답 시간 단축.

위 5 개가 닫히면 실측 기준으로 500 티커 운영이 현실적이다. **본 패치(Patch 7) 는 위 5 개를 시작하지 않으며**, Patch 8 착수 전에 (필요 시) 성능 수치를 `perf_counter` 로그(C2d) 로 일주일 정도 수집해 우선순위를 재확정한다.

---

## 5. 참고

- 본 노트는 `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md` §8 의 "대규모 유료 데이터 확장 제외" 를 침해하지 않는다 (S&P 500 은 **기존 무료 구성종목 목록** 범위, 유료 feed 확장이 아님).
- `docs/plan/METIS_MVP_Unified_Build_Plan_KR_v1.md` §12 "항상 지킬 문장" 6 개는 Patch 7 범위 전체에서 유효 (Today registry-only, Artifact required, Memo≠Message, Heart free / Brain strict, Skin closes on Brain, Replay needs lineage).
- Patch 6 HANDOFF CF-6·1 ~ CF-6·4 는 본 노트 §4.3 Patch 8 후보와 **독립적인 스코프** 이며 동시에 진행하지 않는다.
