# METIS Scale-Readiness Engineering Note — Patch 9 (v1)

**작성 근거**: AGH v1 Patch 9 작업지시서 §C "scale closure — 3 개 carry-forward blocker 실코드 해소".
**전제 문서**: [METIS_Scale_Readiness_Note_Patch8_v1.md](./METIS_Scale_Readiness_Note_Patch8_v1.md) §4.3 의 Patch 9 후보 리스트 (CF-8·A / CF-8·B / CF-8·C / CF-8·D). 본 노트는 그중 **CF-8·A (retention) / CF-8·B (JSONB 인덱스) / CF-8·C (message snapshot lazy-generation)** 3 건이 실코드로 닫힌 뒤의 상태를 기록하며, **CF-8·D 만 Patch 10 범위로 이월** 되었다는 사실 + 500 티커 **operational green verdict (conditional → operational 전환)** 를 단일 문서로 정리한다.

**주의**:
- 본 노트는 2026-04-21 기준 `main` + Patch 9 브랜치 코드를 근거로 한다.
- Patch 7 / Patch 8 노트의 용어 (Finding N·, CF-7·*, CF-8·*) 는 그대로 계승한다. 본 패치에서 새로 이월되는 remedy 는 `CF-9·*` 로 구분한다.
- LLM 비용·Ask AI 자기호출 루프는 본 노트 범위 밖이다.

---

## 1. Scope · 비-scope

### 1.1 본 노트가 다루는 것
- Patch 8 Scale Readiness Note §4.3 의 CF-8·A / CF-8·B / CF-8·C 가 **실코드로 닫힌 상태** 를 수치 없이 코드 수준에서 기록.
- CF-8·D 가 **왜 본 패치에서 닫히지 않는가** 와 이월 순서 (CF-9·A, CF-9·B 와의 우선순위).
- 500 티커 verdict 를 Patch 8 의 **conditional green** 에서 Patch 9 의 **operational green (5 체크)** 로 이동시키는 근거.

### 1.2 다루지 않는 것
- 실제 S&P 500 라이브 전환 타임라인: 본 패치에서 시작하지 않음.
- 유료 외부 feed 확장: 여전히 Product Spec §8 "제외".
- Reliability / SLA: Stage 6 Trust closeout 영역.

---

## 2. 본 패치에서 **실제로 닫은 것** (C·A + C·B + C·C)

### Finding 5 · (CF-8·A 해소) — 패킷/잡 retention + server-side count

- **Before (Patch 8 까지)**: `agentic_harness_packets_v1` / `agentic_harness_queue_jobs_v1` 는 시간 경과에 따라 무한 증가. `count_packets_by_layer` 는 Python-side loop (read → group) 로 500 티커 × 장기 운영 구간에서 응답 시간이 표본 크기에 선형.
- **After (Patch 9 · C·A)**:
  - 마이그레이션 `supabase/migrations/20260420000000_agentic_harness_retention_archive_v1.sql`:
    - `public.agentic_harness_packets_v1_archive` / `public.agentic_harness_queue_jobs_v1_archive` 2 개 아카이브 테이블 생성 (원본 스키마 + `archived_at_utc timestamptz not null default now()`).
    - 인덱스: `(archived_at_utc)`, `(layer)` / `(queue_name)` 로 아카이브 조회 + retention-retention 재삭제 지원.
    - RPC `public.agentic_harness_count_packets_by_layer_v1()` 가 `(layer, layer_count)` 를 리턴하는 **서버측 GROUP BY**.
  - Python 모듈 `src/agentic_harness/retention/archive_v1.py`:
    - `ArchiveReport` dataclass (`scanned`, `copied`, `deleted`, `batches`, `dry_run`).
    - `archive_packets_older_than(client, *, days, batch_size=500, dry_run=False)` — **copy-then-delete** (아카이브 insert 성공 뒤에만 active delete), bounded batch, dry-run 기본 지원.
    - `archive_jobs_older_than(...)` — **terminal status 만** (`status in ('done','dlq','expired')`) 라이브 큐 잡은 절대 아카이브 안 함.
  - CLI: `python3 -m src.main harness-retention-archive [--days N] [--batch-size N] [--dry-run] [--skip-packets] [--skip-jobs]`.
  - `supabase_store.count_packets_by_layer()` 는 이제 RPC 를 먼저 시도하고 (`client.rpc("agentic_harness_count_packets_by_layer_v1").execute()`) 실패시 기존 Python-side 카운트로 fallback.
- **의미**: 운영 6–12 개월 경과 후에도 (a) active table 크기가 운영 정책 (days 파라미터) 에 의해 bounded, (b) layer 분포 집계가 DB 쿼리 한 번으로 상수 시간, (c) retention archive 는 copy-then-delete 로 **원본 감사 기록은 절대 손실되지 않는다**.
- **잠긴 회귀 테스트**: `src/tests/test_agh_v1_patch9_production_surface.py` 의 C·A 3건 (`test_ca_archive_packets_copy_then_delete` / `test_ca_archive_jobs_terminal_only` / `test_ca_count_packets_by_layer_rpc_fallback`).

### Finding 6 · (CF-8·B 해소) — Research structured lookup linear scan

- **Before (Patch 8 까지)**: `layer5_orchestrator._collect` 가 `store.list_packets(asset_id=...)` 호출 후 **Python-side 에서** target_scope JSON 을 파싱해 필터. `agentic_harness_packets_v1` 에 `target_scope->>asset_id` / `target_scope->>horizon` 인덱스 없음 → 500 티커 × 수천 패킷 규모에서 full scan.
- **After (Patch 9 · C·B)**:
  - 마이그레이션 `supabase/migrations/20260420010000_agentic_harness_packets_target_scope_index_v1.sql`:
    - `agentic_harness_packets_v1_target_asset_id_idx` on `((target_scope->>'asset_id'))`
    - `agentic_harness_packets_v1_target_horizon_idx` on `((target_scope->>'horizon'))`
  - `HarnessStoreProtocol.list_packets` 시그니처에 `target_asset_id: Optional[str] = None` / `target_horizon: Optional[str] = None` 옵션 파라미터 추가.
  - `supabase_store.list_packets` 가 `q.eq("target_scope->>asset_id", target_asset_id)` / `q.eq("target_scope->>horizon", target_horizon)` 로 **DB 필터로 push down**.
  - `fixture_store.list_packets` 는 동일 semantic 을 in-memory 에서 미러링 (회귀 보호).
  - `src/agentic_harness/agents/layer5_orchestrator.py::_collect` 가 `asset_id` 존재 + `allow_asset_neutral=False` 케이스에서 이 파라미터를 DB 에 넘겨 전체 스캔을 회피. `allow_asset_neutral=True` (broader set 필요) 는 JSONB 단일 `eq` 로 OR semantic 을 표현할 수 없으므로 Python-side 필터 유지.
- **의미**: asset-specific research 응답에서 `agentic_harness_packets_v1` 조회가 `O(table_size)` → `O(log N)` (인덱스 seek). 500 티커 수년 운영 시에도 Ask AI 응답 지연이 표본 크기에 선형이 아님.
- **잠긴 회귀 테스트**: C·B 4 건 (`test_cb_list_packets_asset_filter_pushdown` / `test_cb_list_packets_horizon_filter_pushdown` / `test_cb_list_packets_backcompat_no_filter` / `test_cb_layer5_collect_uses_filter_when_strict`).

### Finding 4 (부분) · (CF-8·C 해소) — Message snapshot per-row IO

- **Before (Patch 8 까지)**: `build_today_spectrum_payload` 가 hot path 에서 `persist_message_snapshots_for_spectrum_payload(repo_root, out)` 를 호출 → 모든 spectrum row 에 대해 `metis_brain/message_object_v1.py` 의 snapshot upsert 를 수행. 500 티커 × 4 horizon × stage 별 상태 변화 = page load 당 수천 건 JSON IO.
- **After (Patch 9 · C·C)**:
  - `src/phase47_runtime/today_spectrum.py::build_today_spectrum_payload` 에서 `persist_message_snapshots_for_spectrum_payload` 호출 제거.
  - 신규 helper `persist_message_snapshot_for_spectrum_row(repo_root, payload, row)` 를 도입.
  - `src/phase47_runtime/today_spectrum.py::build_today_object_detail_payload` 가 해당 row 진입 시 **단 한 건** lazy persist — 사용자가 실제로 object detail 을 열 때에만 snapshot 이 생긴다.
  - 전체 스윕 helper `persist_message_snapshots_for_spectrum_payload` 는 backfill / evidence 스크립트 용도로 정의를 유지 (docstring 에 "no longer called from the main spectrum build path" 명시).
- **의미**: Today 스펙트럼 페이지 load 당 snapshot IO 비용이 `O(rows)` → `O(1, on-detail-click)`. object detail 진입은 사용자 트래픽 분포상 상위 ticker 에 집중되므로 평균 IO 폭발 없음.
- **잠긴 회귀 테스트**: C·C 2 건 + 기존 `test_metis_brain_v0.py::test_today_registry_only_no_seed` / `test_today_row_message_has_contract_fields` 가 "spectrum build 후 스냅샷 파일 없고, object-detail 진입 후에만 생긴다" 는 새 계약으로 업데이트.

---

## 3. 본 패치에서 **닫지 않은 것** (이월)

Patch 8 Scale Note §4.3 의 CF-8·D 와 운영 자동화 2 건을 본 패치의 scope 밖으로 둔다. 근거는 다음과 같다.

- **CF-8·D (Today `_horizon_lens_compare` 번들 단위 캐시)** — 본 패치는 Today message snapshot IO 를 lazy 로 전환 (C·C) 해 페이지 load 당 IO 를 지배적으로 낮췄다. `_horizon_lens_compare` fan-out (horizon 4개 × asset 500개) 은 여전히 spectrum build 안에서 반복되지만 CPU-bound 이고, 캐시 도입 시 **번들 mutation 과의 stale risk** 가 생겨 (Patch 8 의 evaluator single-reload 와 유사한) 정합성 게이트 설계가 선행해야 한다. **CF-10·A (이월)** = `_horizon_lens_compare` 결과를 `(bundle_fingerprint, horizon_type)` 키 cache + invalidate-on-bundle-swap.
- **CF-9·A (`harness-retention-archive` 주기화)** — 본 패치는 CLI 와 archive_v1 코드를 닫았지만 **실제 운영 스케줄** (Railway cron 또는 `worker:` 사이드채널) 은 운영자의 배포 정책 결정을 요구한다. **CF-10·B (이월)** = retention 을 Railway scheduled job 으로 등록 + 주기·batch_size 기본값 운영 가이드.
- **CF-9·B (production bundle graduation 의 Supabase r-branch 자동화)** — 현재 `scripts/agh_v1_patch_8_production_bundle_graduation.py` 는 운영자가 수동 트리거. **CF-10·C (이월)** = R-branch 스테이징 → integrity 4 체크 → atomic swap 을 CI/CD pipeline 으로 옮김.

---

## 4. C3 Verdict — S&P 500 (~500 ticker) readiness (Patch 9 버전)

### 4.1 **충분한 것** (Patch 8 대비 추가분만)
- **Packet/queue retention 상수 시간화**: CF-8·A 해소로 active table 크기가 days 파라미터에 의해 bounded, 레이어 집계가 서버측 GROUP BY 로 상수 시간.
- **Research asset lookup 로그 시간화**: CF-8·B 해소로 `list_packets(target_asset_id=..., target_horizon=...)` 가 JSONB 인덱스 seek.
- **Today 페이지 load IO 상수 시간화**: CF-8·C 해소로 spectrum build 에서 snapshot IO 제거, object detail 진입 시 lazy persist.
- **Production bundle 오용 차단**: Patch 9 A2 production-tier 4 integrity 체크로 demo fingerprint 가 production 으로 승격되는 리스크 closed.
- **v2 integrity fail 투명성**: Patch 9 A1 의 `brain_bundle_integrity_report_for_path` + `/api/runtime/health.mvp_brain_gate.*` + UI fallback chip 으로 v2 가 깨졌을 때 조용히 덮지 않음.

### 4.2 **아직 막는 것** (Patch 8 대비 감산)

Patch 8 노트 §4.2 의 3 개 중 **1·2·3 전부 닫혔다**. 남은 0 개 + 본 패치에서 새로 드러난 0 개:

(없음. Patch 8 의 기존 blocker 3 개가 전부 닫힘.)

**다만 이월 1 개**: `_horizon_lens_compare` 번들 단위 캐시 (CF-10·A) 는 CPU 측면에서 500 티커 운영시 지배 비용이 될 수 있다. 본 패치는 **IO 측면을 우선 닫았다**.

### 4.3 **다음 concrete patch (Patch 10 "Today compute cache + retention automation")**
본 노트는 Patch 10 의 구체 구현이 아니라 **범위 추정** 이다. 다음 3 건이 한 PR 묶음으로 적절하다.

1. **CF-10·A** — `_horizon_lens_compare` 결과를 번들 단위 캐시 + invalidate-on-bundle-swap. Today 응답에서 horizon × asset fan-out 증폭을 없앤다.
2. **CF-10·B** — `harness-retention-archive` 를 Railway scheduled job 으로 등록 (`schedule: "0 3 * * *"` 기준, `days=90 batch_size=500`).
3. **CF-10·C** — production bundle graduation 의 Supabase r-branch 자동화 (스테이징 → integrity 4 체크 → atomic swap).

### 4.4 최종 verdict
> 500 티커 운영은 **Patch 9 기준으로 operational green** 이다 (Patch 8 의 conditional 에서 한 단계 상향). 조건:
> - (a) `v2` bundle 이 `production` tier 로 승격되었는가,
> - (b) `/api/runtime/health.health_status == ok` + `mvp_brain_gate.brain_bundle_tier == 'production'` 인가,
> - (c) `mvp_brain_gate.brain_bundle_v2_integrity_failed == false` (즉 `degraded_reasons` 에 `v2_integrity_failed` 없음) 인가,
> - (d) `panel_truncated_at_limit == false` 인가,
> - (e) `harness-retention-archive` 가 운영 주기로 돌고 있어 `agentic_harness_packets_v1` / `agentic_harness_queue_jobs_v1` 가 bounded 인가.
>
> 이 5 개가 green 이면 운영 시작 가능. Patch 10 의 `_horizon_lens_compare` 캐시 전까지는 **Today 응답 CPU 비용이 horizon × asset fan-out 에 선형** 이라는 전제를 유지해야 한다.

---

## 5. 참고

- 본 노트는 `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md` §8 "대규모 유료 데이터 확장 제외" 를 침해하지 않는다 (S&P 500 은 기존 무료 구성종목 범위).
- `docs/plan/METIS_MVP_Unified_Build_Plan_KR_v1.md` §12 "항상 지킬 문장" 6 개는 Patch 9 범위 전체에서 유효 (Today registry-only, Artifact required, Memo≠Message, Heart free / Brain strict, Skin closes on Brain, Replay needs lineage).
- 본 노트의 자매 문서:
  - [METIS_Production_Bundle_Graduation_Note_v1.md](./METIS_Production_Bundle_Graduation_Note_v1.md) — 3-tier 번들 규약.
  - [docs/ops/METIS_Production_Bundle_Graduation_Runbook_v1.md](../ops/METIS_Production_Bundle_Graduation_Runbook_v1.md) — v2 graduation 런북.
  - [docs/ops/METIS_Harness_Retention_Archive_Runbook_v1.md](../ops/METIS_Harness_Retention_Archive_Runbook_v1.md) — retention archive 운영 런북.
  - [docs/ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md](../ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md) — 배포 런북.
