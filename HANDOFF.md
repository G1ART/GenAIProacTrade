# 연구 엔진 상위 레이어 — 프로젝트 요약 (Phase 40 이후)

**Public-core frozen (MVP)**: 동일 — `freeze_public_core_and_shift_to_research_engine` (`phase36_1` 번들). 광역 기판 수리 **비목표**.

**연구 엔진은 이제 패밀리별 PIT 실행을 지원한다**: `run-phase40-family-spec-bindings` 가 동일 **8행 `join_key_mismatch` 픽스처**에 대해 **5개 패밀리**를 DB 결합으로 돌린다. 행 단위 결과는 **`spec_results: { spec_key → outcome_cell }`** 동적 키이며, 네 가지 표준 outcome 버킷·**공통 누수 감사 규칙**은 Phase 38과 동일하다.

**지속 mismatch는 단일 challenged 가설이 아니라 실행된 패밀리들로 분해된다** (baseline trio + cadence + filing-proxy + governance registry lag + fixture-only replay). 신규 가설 4건은 실행·누수 통과 시 **`conditionally_supported`** 로 갱신되고, 패밀리별 적대적 리뷰·**게이트 schema v3**(`conditionally_supported_but_not_promotable` 등)·**설명 v3**가 붙는다. **자동 승격 없음·제네릭 추천 UI 비목표.**

**Phase 41·42 (구현·실측 완료)**: Phase 41 `run-phase41-falsifier-substrate` 가 **filing_index**·**market_metadata_latest.sector** 로 두 패밀리를 재실행 (`2026-04-11T02:45:40Z`, 게이트 **`deferred_due_to_proxy_limited_falsifier_substrate`**). Phase 42 `run-phase42-evidence-accumulation` 은 Phase 41 번들로 **증거 스코어카드·판별·게이트 phase42·설명 v5** (`2026-04-11T04:52:28Z`, 번들 재생은 **`--bundle-substrate-only`**; **Supabase-fresh** 별도 번들은 `phase42_evidence_accumulation_bundle_supabase.json`). `promotion_gate_v1.json` 의 **`phase`** 는 **phase42** 로 갱신. 광역 기판 수리·자동 승격 **비목표**.

**Phase 43 (실측 완료, 2026-04-11 UTC)**: `run-phase43-targeted-substrate-backfill` 로 8행만 filing `run_sample_ingest`·메타 수화 후 Phase 41 pit·Phase 42 **Supabase-fresh** 재실행(`phase42_rerun_used_supabase_fresh: true`). **스코어카드 sector** `no_market_metadata_row_for_symbol` **8** → `sector_field_blank_on_metadata_row` **8**(행 단위 before/after와 일치); **filing** 7+1(ADSK post-signal) **유지**. **stable_run_digest** `edfd0b7d36ecb2de` → `285b046cc5bcb307`. **게이트** `primary_block_category` **`deferred_due_to_proxy_limited_falsifier_substrate`** 동일. **Phase 43 번들의 `phase44` 필드**는 레거시 낙관 분기 문자열일 수 있음 — **권위 해석은 Phase 44** 번들 — **운영 클로즈아웃 단일 패키지는 Phase 45** `phase45_canonical_closeout_bundle.json` / `phase45_canonical_closeout_review.md`. **파운더 대면 표면(첫 제품 레이어)은 Phase 46** `phase46_founder_decision_cockpit_*` / `phase46_founder_pitch_surface.md`. **브라우저 런타임은 Phase 47** `src/phase47_runtime/` · `phase47_founder_cockpit_runtime_*` · `phase47_runtime_deploy_notes.md`. **선행 연구 단일 사이클 런타임은 Phase 48** (**종료**, `docs/operator_closeout/phase48_closeout.md`) `src/phase48_runtime/` · `run-phase48-proactive-research-runtime` · `data/research_runtime/*.json`. **다중 사이클·집계 메트릭은 Phase 49** `src/phase49_runtime/` · `run-phase49-daemon-scheduler-multi-cycle-triggers-and-metrics-v1` · `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_bundle.json` / `phase49_daemon_scheduler_multi_cycle_review.md`. **런타임 제어 평면·비영 스모크는 Phase 50** (**종료**, `docs/operator_closeout/phase50_closeout.md`) `src/phase50_runtime/` · `run-phase50-registry-controls-and-operator-timing` · `run-phase50-positive-path-smoke` · **`docs/phase50_evidence.md`**, **`docs/phase50_patch_report.md`**. 증거 **`docs/phase43_evidence.md`**, **`docs/phase43_patch_report.md`** · Phase 44 **`docs/phase44_evidence.md`**, **`docs/phase44_patch_report.md`** · Phase 45 **`docs/phase45_evidence.md`**, **`docs/phase45_patch_report.md`** · Phase 46 **`docs/phase46_evidence.md`**, **`docs/phase46_patch_report.md`** · Phase 47 **`docs/phase47_evidence.md`**, **`docs/phase47_patch_report.md`** · Phase 48 **`docs/phase48_evidence.md`**, **`docs/phase48_patch_report.md`** · Phase 50 **`docs/phase50_evidence.md`**, **`docs/phase50_patch_report.md`**.

**CLI (Phase 40, Supabase)**: `run-phase40-family-spec-bindings --universe …` → `phase40_family_spec_bindings_bundle.json`, `phase40_family_spec_bindings_review.md`, `phase40_explanation_surface_v3.md`. 증거·패치: **`docs/phase40_evidence.md`**, **`docs/phase40_patch_report.md`**.

**CLI (Phase 41, Supabase)**: `run-phase41-falsifier-substrate --universe …` → `phase41_falsifier_substrate_bundle.json`, `phase41_falsifier_substrate_review.md`, `phase41_explanation_surface_v4.md`. 증거·패치: **`docs/phase41_evidence.md`**, **`docs/phase41_patch_report.md`**. (선택 `--phase40-bundle-in` 으로 before/after 비교.)

**CLI (Phase 42, Phase 41 번들)**: `run-phase42-evidence-accumulation` — `--bundle-substrate-only` 로 pit `per_row` 재생 가능; 생략 시 Supabase 재조회. 산출: `phase42_evidence_accumulation_bundle.json`, `phase42_evidence_accumulation_review.md`, `phase42_explanation_surface_v5.md`. 증거·패치: **`docs/phase42_evidence.md`**, **`docs/phase42_patch_report.md`**.

**Phase 39 실측 (참고)**: `2026-04-10T21:28:28Z` 번들 — `docs/phase39_evidence.md`.

**Phase 40 실측 (참고)**: `2026-04-11T00:09:06Z` 번들 — `docs/phase40_evidence.md`.

**Phase 41 실측 (참고)**: `2026-04-11T02:45:40Z` 번들 — `docs/phase41_evidence.md`.

**Phase 42 실측 (참고)**: `2026-04-11T04:52:28Z` 번들 — `docs/phase42_evidence.md`.

**Phase 43 실측 (참고)**: `2026-04-11T19:03:56Z` 번들 — `docs/phase43_evidence.md`.

**CLI (Phase 43, 8행 코호트만)**: `run-phase43-targeted-substrate-backfill` — Phase 42 Supabase-fresh 번들의 `row_level_blockers` **8행**에 filing·메타 수화(상한) 후 Phase 41·Phase 42 **Supabase-fresh** 재실행 (`phase42_rerun_used_supabase_fresh: true`). 산출: `phase43_targeted_substrate_backfill_bundle.json`, `phase43_targeted_substrate_backfill_review.md`, `phase43_targeted_substrate_before_after_audit.md`, `phase43_explanation_surface_v6.md`. 증거·패치: **`docs/phase43_evidence.md`**, **`docs/phase43_patch_report.md`**. (광역 기판 재개 **아님**.)

**CLI (Phase 44, 번들만·DB 없음)**: `run-phase44-claim-narrowing-truthfulness` — Phase 43·Phase 42 Supabase 번들을 읽어 **출처 분리 감사**, **보수적 material 판정**, **머신 리더블 claim narrowing**, **retry 레지스트리(신규 명명 경로 필요)**, **Phase 45 권고**를 쓴다. 산출: `phase44_claim_narrowing_truthfulness_bundle.json`, `phase44_claim_narrowing_truthfulness_review.md`, `phase44_provenance_audit.md`, `phase44_explanation_surface_v7.md`. MD만: `write-phase44-claim-narrowing-truthfulness-review --bundle-in …`. 테스트: `pytest src/tests/test_phase44_claim_narrowing_truthfulness.py -q`. 증거·패치: **`docs/phase44_evidence.md`**, **`docs/phase44_patch_report.md`**.

**CLI (Phase 45, 번들만·DB 없음·기판 작업 없음)**: `run-phase45-operator-closeout-and-reopen-protocol` — Phase 44·Phase 43 번들로 **권위 우선순위**, **canonical closeout**, **재진입(reopen) 프로토콜**, **Phase 46** 기본 hold 를 쓴다. 선택 `--operator-registered-new-named-source` 시 Phase 46 대체 권고 문자열. 산출: `phase45_canonical_closeout_bundle.json`, `phase45_canonical_closeout_review.md`. MD만: `write-phase45-operator-closeout-and-reopen-protocol-review --bundle-in …`. 테스트: `pytest src/tests/test_phase45_operator_closeout_and_reopen_protocol.py -q`. 증거·패치: **`docs/phase45_evidence.md`**, **`docs/phase45_patch_report.md`**.

**CLI (Phase 46, 제품 표면·번들만·기판 없음)**: `run-phase46-founder-decision-cockpit` — Phase 45·Phase 44 번들로 **founder read model**, **cockpit 카드**, **결정론적 대표 피치**, **drill-down 예시**, **UI 계약**, **알림/결정 레저 스냅샷**을 쓴다. 산출: `phase46_founder_decision_cockpit_bundle.json`, `phase46_founder_decision_cockpit_review.md`, `phase46_founder_pitch_surface.md`. 레저: `data/product_surface/alert_ledger_v1.json`, `decision_trace_ledger_v1.json`. MD만: `write-phase46-founder-decision-cockpit-review --bundle-in …`. 테스트: `pytest src/tests/test_phase46_founder_decision_cockpit.py -q`. 증거·패치: **`docs/phase46_evidence.md`**, **`docs/phase46_patch_report.md`**.

**CLI (Phase 47, 브라우저 런타임·DB 없음)**: `run-phase47-founder-cockpit-runtime` — Phase 46 번들 경로로 **런타임 메타 번들**·리뷰 MD 생성. **실제 UI**: `PYTHONPATH=src python3 src/phase47_runtime/app.py` (기본 `http://127.0.0.1:8765`). 산출: `phase47_founder_cockpit_runtime_bundle.json`, `phase47_founder_cockpit_runtime_review.md`. 배포: **`docs/operator_closeout/phase47_runtime_deploy_notes.md`**. 테스트: `pytest src/tests/test_phase47_founder_cockpit_runtime.py -q`. 증거·패치: **`docs/phase47_evidence.md`**, **`docs/phase47_patch_report.md`**.

**CLI (Phase 48, 선행 연구·단일 사이클·기판 없음)**: `run-phase48-proactive-research-runtime` — Phase 46 번들 + 결정 레저 + 잡 레지스트리 메타로 **트리거 → 잡(상한) → 실행 →(선택) 경계 토론 → 프리미엄·디스커버리 후보 → cockpit 표면 레코드**. 산출: `phase48_proactive_research_runtime_bundle.json`, `phase48_proactive_research_runtime_review.md`. 지속: `data/research_runtime/research_job_registry_v1.json`, `discovery_candidates_v1.json`. 선택 `--skip-alerts`, `--registry-path`, `--discovery-path`, `--decision-ledger-path`. 테스트: `pytest src/tests/test_phase48_proactive_research_runtime.py -q`. 증거·패치: **`docs/phase48_evidence.md`**, **`docs/phase48_patch_report.md`**. **운영 클로즈**: **`docs/operator_closeout/phase48_closeout.md`**.

**CLI (Phase 49, Phase 48 N회·집계·메트릭)**: `run-phase49-daemon-scheduler-multi-cycle-triggers-and-metrics-v1` — 동일 입력·상태 파일로 Phase 48 단일 사이클을 `--cycles` 회 반복하고 집계한다. 산출: `phase49_daemon_scheduler_multi_cycle_bundle.json`, `phase49_daemon_scheduler_multi_cycle_review.md`. 선택 `--sleep-seconds`, `--skip-alerts`, `--registry-path`, `--discovery-path`, `--decision-ledger-path`. 테스트: `pytest src/tests/test_phase49_daemon_scheduler_multi_cycle.py -q`.

**CLI (Phase 50, 제어 평면·스모크)**: `run-phase50-registry-controls-and-operator-timing` — Phase 49 번들 + 제어 평면·감사 요약 번들. `run-phase50-positive-path-smoke` — 운영자 시드 `manual_watchlist` + 격리 레지스트리로 **비영(non-empty)** 권위 스모크. 산출: `phase50_registry_controls_and_operator_timing_*`, `phase50_positive_path_smoke_*`. 지속: `data/research_runtime/runtime_control_plane_v1.json`, `cycle_lease_v1.json`, `runtime_audit_log_v1.json`. 테스트: `pytest src/tests/test_phase50_registry_controls_and_operator_timing.py -q`. 증거·패치·클로즈: **`docs/phase50_evidence.md`**, **`docs/phase50_patch_report.md`**, **`docs/operator_closeout/phase50_closeout.md`**.

**CLI (Phase 51, 외부 트리거 인제스트·런타임 헬스)**: `run-phase51-external-positive-path-smoke` — **파일 드롭** 외부 이벤트 → 정규화·중복 제거 → Phase 48 **`supplemental_triggers`** 로 사이클 소비(`manual_triggers_v1` 시드 없음). `submit-external-trigger-json`, `refresh-runtime-health-summary`. 산출: `phase51_external_trigger_ingest_bundle.json`, `phase51_external_trigger_ingest_review.md`, `phase51_runtime_health_surface_review.md`. Cockpit: `GET /api/runtime/health`, `POST /api/runtime/external-ingest`(본문 **≤32768** 바이트). 테스트: `pytest src/tests/test_phase51_external_trigger_ingest_and_runtime_health.py -q`. 증거·패치·클로즈: **`docs/phase51_evidence.md`**, **`docs/phase51_patch_report.md`**, **`docs/operator_closeout/phase51_closeout.md`**.

**CLI (Phase 52, 거버넌스 웹훅·소스 예산·라우팅·큐)**: `run-phase52-governed-webhook-auth-routing-smoke` — 소스 레지스트리(`shared_secret_hash` = SHA-256(비밀값))·분당/윈도 예산·원시/정규화 트리거 화이트리스트·선택 큐(`enqueue_before_cycle`) 후 플러시 → Phase 48. Cockpit: **`POST /api/runtime/external-ingest/authenticated`** + 헤더 **`X-Source-Id`**, **`X-Webhook-Secret`** (운영은 TLS 필수). 격리 스모크 산출: `data/research_runtime/phase52_external_smoke_*_v1.json`; 운영 기본 경로는 `external_source_registry_v1.json` 등. 산출: **`docs/operator_closeout/phase52_webhook_auth_routing_bundle.json`**, **`phase52_webhook_auth_routing_review.md`**, **`phase52_runtime_health_surface_review.md`**. 테스트: `pytest src/tests/test_phase52_webhook_auth_routing.py -q` (Phase 51·50 회귀 유지). 증거·패치·클로즈: **`docs/phase52_evidence.md`**, **`docs/phase52_patch_report.md`**, **`docs/operator_closeout/phase52_closeout.md`**.

**Phase 46 실측 (참고)**: 저장소 기록 번들 `generated_utc` `2026-04-12T20:40:43Z` — `docs/phase46_evidence.md`.

**Phase 47 실측 (참고)**: 메타 번들 `generated_utc` `2026-04-12T22:02:36Z` — `docs/phase47_evidence.md`.

**Phase 48 실측 (참고)**: 단일 사이클 번들 `generated_utc` `2026-04-13T00:50:42Z` — `docs/phase48_evidence.md`.

**Phase 49 실측 (참고, Phase 48 클로즈 검증)**: 집계 번들 `generated_utc` `2026-04-13T01:10:08Z` — `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md`.

**Phase 50 실측 (참고)**: 제어 평면 번들 `generated_utc` `2026-04-13T05:50:40Z`, 스모크 번들 `2026-04-13T05:50:46Z`, `smoke_metrics_ok: true` — `docs/operator_closeout/phase50_positive_path_smoke_review.md`, `phase50_registry_controls_and_operator_timing_review.md`, **`docs/phase50_evidence.md`**, **`docs/phase50_patch_report.md`**, **`docs/operator_closeout/phase50_closeout.md`**.

**Phase 51 실측 (참고)**: 번들 `generated_utc` **`2026-04-13T06:38:15.299044+00:00`**, `ok: true`, `smoke_metrics_ok: true` — 외부 1건 승인·사이클 `f36b11ba-f3e9-4d6e-902c-f24fcbe396c1`, `manual_watchlist`→`debate.execute`, 헬스 `healthy`. 산출: `docs/operator_closeout/phase51_external_trigger_ingest_bundle.json`, `phase51_external_trigger_ingest_review.md`, `phase51_runtime_health_surface_review.md`, **`docs/phase51_evidence.md`**, **`docs/phase51_patch_report.md`**, **`docs/operator_closeout/phase51_closeout.md`**; 격리 `data/research_runtime/phase51_external_*_v1.json`.

**Phase 52 실측 (참고)**: 번들 `generated_utc` **`2026-04-14T05:03:19.383370+00:00`**, `ok: true`, `smoke_metrics_ok: true` — 인증 실패·라우팅 거절·레이트리밋·큐+플러시·supplemental 3건·잡 생성·실행 각 3, 사이클 `81395afa-235b-4598-952d-52b973a49358`, 감사 `why_cycle_started`: **`phase52_governed_webhook_smoke`**, 헬스 `healthy`. 산출: **`docs/operator_closeout/phase52_webhook_auth_routing_bundle.json`**, **`phase52_webhook_auth_routing_review.md`**, **`phase52_runtime_health_surface_review.md`**, **`docs/phase52_evidence.md`**, **`docs/phase52_patch_report.md`**, **`docs/operator_closeout/phase52_closeout.md`**; 격리 `data/research_runtime/phase52_external_smoke_*_v1.json`. 다음 권고 **`phase53`**: `signed_payload_hmac_source_rotation_and_dead_letter_replay_v1`.

---

_Legacy 요약 (Phase 38 실측 숫자)_: `sp500_current`, `experiment_id` `41dea3b0-02fe-46d8-951d-e2778af01e9f`, 8/8 mismatch, 게이트 blocked → Phase 39 권고 `broaden_hypothesis_families…` 반영·**실측 완료**. Phase 38 상세 **`docs/phase38_evidence.md`**, Phase 39 상세 **`docs/phase39_evidence.md`**, Phase 40 **`docs/phase40_evidence.md`**, Phase 41 **`docs/phase41_evidence.md`**, Phase 42 **`docs/phase42_evidence.md`**, Phase 43 **`docs/phase43_evidence.md`**, Phase 44 **`docs/phase44_evidence.md`**, Phase 45 **`docs/phase45_evidence.md`**, Phase 46 **`docs/phase46_evidence.md`**, Phase 47 **`docs/phase47_evidence.md`**, Phase 48 **`docs/phase48_evidence.md`**, Phase 49 **`docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_review.md`**, Phase 50 **`docs/phase50_evidence.md`**, **`docs/phase50_patch_report.md`**, **`docs/operator_closeout/phase50_closeout.md`**, Phase 51 **`docs/phase51_evidence.md`**, **`docs/phase51_patch_report.md`**, **`docs/operator_closeout/phase51_closeout.md`**, Phase 52 번들·리뷰·증거·클로즈 **`docs/operator_closeout/phase52_webhook_auth_routing_*`**, **`phase52_runtime_health_surface_review.md`**, **`docs/phase52_evidence.md`**, **`docs/phase52_patch_report.md`**, **`docs/operator_closeout/phase52_closeout.md`**.

---

# HANDOFF — Phase 29 (Validation refresh + quarter snapshot backfill)

## Phase 29.1 성능 핫픽스 (2026-04-01)

- **병목**: `report_validation_registry_gaps` 가 `resolved_ciks` 마다 `fetch_ticker_for_cik`(REST 1회/CIK) N+1; Phase 29 `_snap()` 이 전·후 2회 호출되며, 동일 스냅 안에서 레지스트리 무거운 분석이 `report_factor_panel_materialization_gaps`·`report_quarter_snapshot_backfill_gaps` 경로로 **중복** 실행될 수 있었음.
- **조치**: `db.records.fetch_tickers_for_ciks`(청크 `in_("cik", …)`); 레지스트리 리포트는 배치 맵만 사용. `_snap()` 에서 레지스트리 1회 → `registry_report` / `materialization_report` 로 팩터·분기 스냅 리포트에 전달. 오케스트레이션·CLI에 **grep 친화적** 진행 태그 stdout(`phase29_snapshot_*`, `phase29_*_done`, `phase29_bundle_written`, `phase29_review_written`).
- **실 DB 완주 여부**: 이 저장소 패치만으로는 미검증 — 운영자가 아래 명령으로 1회 acceptance. 성공 시 산출물: `docs/operator_closeout/phase29_validation_refresh_and_snapshot_backfill_review.md`, `docs/operator_closeout/phase29_validation_refresh_and_snapshot_backfill_bundle.json`.
- **다음 단계 (명시)**: 실 run이 끝까지 완료·위 두 파일 생성·stdout에 진행 태그 확인되면 **`review_completed_phase29_results`**. 여전히 정체·타임아웃·KeyboardInterrupt면 **`more_phase29_runtime_hotfix_needed`**.

## 현재 제품 위치

- **Phase 29**: Phase 28에서 메타 행은 생겼으나 **검증 패널 `panel_json`에 `missing_market_metadata`가 남는** 경우를 **행 기반 재빌드**로 갱신한다. `market_metadata_latest` 조회는 **`pick_best_market_metadata_row` / `fetch_market_metadata_latest_row_deterministic`** 로 as_of·유동성 우선 결정적 선택(검증 빌드·메타 갭 드라이버 공통).
- **분기 스냅샷**: `report-quarter-snapshot-backfill-gaps` 로 `missing_quarter_snapshot_for_cik` 를 filing/raw/silver/스냅샷 결손 등으로 분류. `run-quarter-snapshot-backfill-repair` 는 **silver 있으나 스냅샷만 없는** CIK에 한해 `rebuild_quarter_snapshot_from_db` (상한); 전면 SEC 재수집은 **deferred**.
- **오케스트레이션**: `run-phase29-validation-refresh-and-snapshot-backfill` — 순서: 메타 수화 → stale 검증 갱신 → 분기 스냅샷 수리 → Phase 28 팩터 물질화. `--out-md`, `--bundle-out`. MD만: `write-phase29-validation-refresh-review --bundle-in …`
- **코드**: `src/phase29/`, `db.records`(메타 선택·factor/validation 단건 조회), `market.validation_panel_run`.
- **테스트**: `pytest src/tests/test_phase29_validation_refresh.py src/tests/test_db_fetch_tickers_for_ciks.py -q`
- **패치·증거**: `docs/phase29_patch_report.md`, `docs/phase29_evidence.md`
- **실측 클로즈아웃 후 채울 것**: stale 갱신 건수·플래그 해소·`joined_market_metadata_flagged_count` 델타·분기 스냅샷 분류 변화 — 번들·리뷰 MD에 반영. Phase 29 번들의 **`phase30`** 필드는 “다음 분기” 힌트이며, **Phase 30 실행 후**에는 `phase30_validation_substrate_bundle.json` 의 **`phase31`** 를 따른다.

---

# HANDOFF — Phase 30 (Upstream validation substrate: filing / silver / snapshot)

## 맥락 (Phase 29 번들에서의 해석)

- 메타 `missing_market_metadata` 스테일 이슈가 해소된 뒤에도 **`missing_validation_symbol_count`**·**`missing_quarter_snapshot_for_cik`** 가 크게 남으면, 헤드라인 병목은 **상류 SEC 기판**(filing_index → raw_xbrl → silver_xbrl → issuer_quarter_snapshots) 쪽으로 이동한 것으로 본다.
- Phase 30는 **유니버스 전면 스프린트가 아니라** Phase 29 **분기 스냅샷 분류**에서 나온 버킷별 **상한 수리**와, 수리에 **성공한 CIK에만** 스냅샷→팩터→검증 **좁은 하류 연쇄**를 수행한다.

## CLI (`p27` 공통 인자: `--universe`, `--panel-limit`, `--program-id`, `--price-lookahead-days`)

| 명령 | 역할 |
|------|------|
| `report-filing-index-gap-targets` | `no_filing_index_for_cik` 고유 CIK 타깃 |
| `run-filing-index-backfill-repair` | `run_sample_ingest`(SEC)로 filing_index 보강; **`filing_index_repaired_now`**·**`raw_xbrl_present_after_filing_ingest_count`**·**`downstream_snapshot_present_after_filing_ingest_count`** 로 하류 과장 방지 (`repaired_now` = filing 터치와 동일) |
| `export-filing-index-gap-targets` | 타깃 JSON/CSV |
| `report-silver-facts-materialization-gaps` | `raw_present_no_silver_facts` |
| `run-silver-facts-materialization-repair` | raw→`silver_xbrl_facts` 적재 후 스냅샷 재구성 시도, 분류 before/after 기록 |
| `report-empty-cik-gaps` | `empty_cik` 심볼 멤버십·레지스트리·issuer 매핑 진단(v1 자동 변경 없음) |
| `run-phase30-validation-substrate-repair` | 위 경로 일괄 + 하류 연쇄 + **`phase30_validation_substrate_bundle.json`** / **`phase30_validation_substrate_review.md`** |
| `write-phase30-validation-substrate-review` | 번들만으로 MD 재생성 |

## 코드

- `src/phase30/` (`metrics`, `filing_index_gaps`, `silver_materialization`, `empty_cik_cleanup`, `downstream_cascade`, `phase31_recommend`, `orchestrator`, `review`).

## 운영자가 번들로 채울 실측

- **실제 수리·지연·차단 건수**(filing·silver·empty_cik), **before/after** `missing_validation_symbol_count`·`missing_quarter_snapshot_for_cik`·분류 counts·`factor_panel_missing_for_resolved_cik`·`joined_recipe_substrate_row_count`·`thin_input_share`.
- 병목이 **filing_index 잔존**인지 **스냅샷/팩터/검증**으로 넘어갔는지 한 줄 요약.
- **Phase 31** 단일 권고: 번들 `phase31.phase31_recommendation` + `rationale`.

## 테스트

`pytest src/tests/test_phase30_validation_substrate.py -q`

## 패치 보고

`docs/phase30_patch_report.md`

---

# HANDOFF — Phase 31 (Raw-facts bridge after filing-index repair)

## 맥락 (Phase 30 실측)

- `run_sample_ingest` 는 **filing_index·raw_sec_filings** 등과 **`raw_xbrl_facts`** 가 다른 파이프라인이라, filing-only 수리 후 **`filing_index_present_no_raw_facts`** 가 늘 수 있음.
- Phase 31는 **`run_facts_extract_for_ticker`** 로 분류기가 읽는 **`raw_xbrl_facts`** 를 채우고, **GIS류**는 `concept` 문자열 정규화(`us-gaap_Foo` → `us-gaap:Foo`)로 silver 이음새를 좁히며, **NWSA류** `issuer_mapping_gap` 은 멤버십=레지스트리 CIK 일치 시 **`issuer_master` 결정적 upsert** 시도.

## CLI (`p27` 공통 인자)

| 명령 | 역할 |
|------|------|
| `report-raw-facts-gap-targets` | `filing_index_present_no_raw_facts` + 선택 `--extra-ciks` |
| `export-raw-facts-gap-targets` | JSON/CSV |
| `run-raw-facts-backfill-repair` | 상한 `run_facts_extract_for_ticker` → **repaired_to_raw_present** / deferred / blocked |
| `report-raw-present-no-silver-targets` | `raw_present_no_silver_facts` 목록 |
| `run-gis-like-silver-seam-repair` | silver 재물질화·스냅샷·**CIK당** 하류 (`--prioritize-symbols`, 상한) |
| `run-deterministic-empty-cik-issuer-repair` | empty_cik 중 안전한 issuer upsert |
| `run-phase31-raw-facts-bridge-repair` | 일괄 + **`phase31_raw_facts_bridge_bundle.json`** / **`phase31_raw_facts_bridge_review.md`** |
| `write-phase31-raw-facts-bridge-review` | 번들 → MD |

## 코드

- `src/phase31/`, `sec.facts.concept_map`(언더스코어 정규화), `sec.facts.facts_pipeline.run_facts_extract_for_ticker`

## 운영자가 번들로 채울 실측

- **before/after** 분류·헤드라인 지표, raw 수리·GIS silver·NWSA issuer 결과, **어느 CIK가 팩터/검증까지 갔는지**(`downstream_substrate_retry.per_cik`).
- 병목이 **raw → 스냅샷 → 팩터** 중 어디인지 한 줄.
- **Phase 31 번들의 `phase32` 필드**: Phase 31 시점 권고. **Phase 32 완주 후** 다음 스프린트 힌트는 Phase 32 번들의 **`phase33`** 를 본다.

## 테스트

`pytest src/tests/test_phase31_raw_facts_bridge.py -q`

## 패치 보고

`docs/phase31_patch_report.md`

---

# HANDOFF — Phase 32 (Forward unlock for Phase 31 touched + narrow snapshot cleanup)

## 병목이 validation에서 forward로 옮겨 갔는지

- **해석**: Phase 31 이후 검증 행이 늘면서 **`missing_excess_return_1q` 헤드라인**이 커질 수 있고, 동시에 **선행·excess(`forward_returns_daily_horizons`)** 백필로 심볼 단위 해소가 가능하다. 두 신호를 **섞어 읽지 말 것**: 번들의 `stage_transitions.forward_return_unlocked_now_count`·`silver_present_snapshot_materialization_repair`·제외 분포를 함께 본다.

## Phase 32.1 실측 클로즈아웃 (2026-04-08, `sp500_current`)

- **근거**: `docs/operator_closeout/phase32_forward_unlock_and_snapshot_cleanup_bundle.json`, 동명 **review.md** (생성 UTC `2026-04-08T20:59:45+00:00`), 입력 Phase 31 번들 `docs/operator_closeout/phase31_raw_facts_bridge_bundle.json`.

| 지표 | Before | After | 비고 |
|------|--------|-------|------|
| `joined_recipe_substrate_row_count` | 243 | 243 | **변화 없음** — `no_state_change_join` 8건 등 잔여 제외 유지 |
| `thin_input_share` | 1.0 | 1.0 | 동일 |
| `missing_excess_return_1q` (패널 행 기준) | 91 | **101** | 헤드라인 **증가**: 스냅샷·검증이 열린 심볼이 늘며 excess 공백 **행**이 더 집계됨 |
| `missing_validation_symbol_count` | 161 | **151** | −10 |
| `missing_quarter_snapshot_for_cik` | 158 | **148** | −10 |
| `factor_panel_missing_for_resolved_cik` | 158 | **148** | −10 |
| `silver_present_snapshot_materialization_missing` | 10 | **0** | 스냅 재구성 + cascade **전부 클리어** |
| `raw_present_no_silver_facts` | 1 | 1 | GIS 경로 1건 시도, 분류 카운트 동일 |

**단계 전이 (번들 `stage_transitions`)**: Phase 31 터치 CIK 30 기준 — `forward_return_unlocked_now_count` **23**, forward 빌드 패널 30·성공 op 51·실패 9(다수 `insufficient_price_history`). 스냅샷 물질화 **10**·팩터·검증 cascade 각 10. deferred raw 재시도 **7** 복구 / **3** 지속 외부 실패(Supabase·Cloudflare 500류).

**감사 요약**: 병목은 **검증-only에서 벗어나 forward·가격 창·상류 raw 외부 오류**가 동시에 보인다. `missing_excess_return_1q`만 보면 악화로 보이나, **검증·분기 스냅 상류는 개선**되었고 **23 심볼은 이번 런에서 forward excess 해소**(`repaired_to_forward_present`). Phase 33는 번들과 동일하게 **상한 forward·가격 커버리지 반복**이 자동 권고됨(`continue_bounded_forward_return_and_price_coverage`).

## CLI (`p27` + `--phase31-bundle-in`)

| 명령 | 역할 |
|------|------|
| `report-forward-return-gap-targets-after-phase31` | 터치 CIK ∩ `missing_excess_return_1q` 큐 — 행 단위 `diagnose_bucket` / `blockage_class` |
| `export-forward-return-gap-targets-after-phase31` | JSON export `--out` |
| `run-forward-return-backfill-for-phase31-touched` | `no_forward_row_next_quarter` 후보만 factor 패널 모아 `run_forward_returns_build_from_rows` (기본 CIK 상한 30) |
| `report-silver-present-snapshot-materialization-targets` | `silver_present_snapshot_materialization_missing` |
| `run-silver-present-snapshot-materialization-repair` | 스냅샷 재구성 + 팩터·검증 cascade |
| `retry-raw-facts-deferred-from-phase31-bundle` | `deferred_external_source_gap_all` 중 `facts_extract_exception` 만 백오프 재시도 |
| `run-phase32-forward-unlock-and-snapshot-cleanup` | 일괄 + 기본 `--bundle-out` / `--out-md` |
| `write-phase32-forward-unlock-and-snapshot-cleanup-review` | 번들 → MD (+선택 JSON) |

## 코드

- `src/phase32/`. Phase 31 `raw_facts_repair` 반환에 **`deferred_external_source_gap_all`** (최대 120행) 추가.

## 패치·증거

- `docs/phase32_patch_report.md`, `docs/phase32_evidence.md`

## 단계 이름 (번들 `stage_transitions`)

- **forward_return_unlocked_now_count**, **quarter_snapshot_materialized_now_count**, **factor_materialized_now_count**, **validation_panel_refreshed_count**, **raw_facts_recovered_on_retry_count** — Phase 31의 validation-unlock은 **`phase31_reference.validation_unblocked_cik_count_in_phase31`** 로만 참조(이번 런과 혼동 금지).

## 테스트

`pytest src/tests/test_phase32_forward_unlock_and_snapshot_cleanup.py -q`

---

# HANDOFF — Phase 33 (Forward coverage truth + price alignment)

## 병목

- Phase 32 이후 **헤드라인**은 `joined_recipe_substrate_row_count`·`thin_input_share`가 그대로인 경우가 많고, `missing_excess_return_1q`는 **행·심볼 큐 정의**와 어긋나 읽히기 쉽다. Phase 33는 **forward_row / symbol_queue / joined** 를 번들에서 **분리 표기**하고, Phase 32 번들의 **`insufficient_price_history`** 표본에 대해 **가격 커버리지 분류·결정적 백필·forward 재시도**를 상한으로 수행한다. 메타·광역 filing-index 헤드라인·임계·15/16·프리미엄·프로덕션 스코어 비목표.

## CLI

| 명령 | 역할 |
|------|------|
| `report-forward-metric-truth-audit` | `--phase32-bundle-in` — 터치 집합 기준 진실 분리 |
| `export-forward-metric-truth-audit` | JSON `--out` |
| `report-price-coverage-gaps-for-forward` | Phase 32 NQ 실패 샘플 가격 갭 분류 |
| `run-price-coverage-backfill-for-forward` | `missing_market_prices_daily_window` 만 프로바이더 일봉 수집 |
| `run-forward-return-retry-after-price-repair` | 위 심볼 factor 패널 상한 forward 재빌드 |
| `inspect-gis-deterministic-raw-silver-seam` | GIS 개념맵 샘플만 (대극모 silver 금지) |
| `run-phase33-forward-coverage-truth` | 일괄 + `phase33_forward_coverage_truth_bundle.json` / `review.md` |
| `write-phase33-forward-coverage-truth-review` | 번들 → MD |

`report-price-coverage-gaps-for-forward` / `run-price-coverage-backfill-for-forward` 는 `--phase32-bundle-in` + `--price-lookahead-days` 만 사용 (`p27` 불필요).

## 코드

- `src/phase33/`, `market.price_ingest.run_market_prices_ingest_for_symbols` (심볼 상한 일봉).

## 번들 `stage_semantics_truth`

- `forward_row_unblocked_now_count`, `symbol_cleared_from_missing_excess_queue_count`, `joined_recipe_unlocked_now_count`, `price_coverage_repaired_now_count` — 서로 대리 지표로 쓰지 말 것.

## Phase 33.1 실측 클로즈아웃 (2026-04-08, `sp500_current`)

- **근거**: `docs/operator_closeout/phase33_forward_coverage_truth_bundle.json`, `docs/operator_closeout/phase33_forward_coverage_truth_review.md` (리뷰 생성 UTC `2026-04-08T22:37:25+00:00`).

| 구분 | 결과 |
|------|------|
| **헤드라인** | `joined` 243·`thin_input` 1.0·`missing_excess_return_1q` 101 — **전후 동일** |
| **행/심볼/joined 진실** | `forward_row_unblocked_now_count`(이번 런 upsert op)=**5**, `symbol_cleared_from_missing_excess_queue_count`=**0**, `joined_recipe_unlocked_now_count` Δ=**0**, 터치 30 심볼 패널 행 **excess null 30/30** (라이브) |
| **가격** | NQ 실패 샘플 **7건** 모두 **`lookahead_window_not_matured`** → 일봉 백필 **미실시**(missing_window 아님) |
| **forward 재시도** | 심볼 7·패널 7, **성공 op 5 / 실패 9** — 잔여 `insufficient_price_history` |
| **GIS** | 샘플 13 concept 전부 unmapped → **`blocked_unmapped_concepts_remain_in_sample`** (대극모 캠페인 없음) |
| **Phase 34** | 구현됨 — 아래 **HANDOFF — Phase 34** (`run-phase34-forward-validation-propagation` 등) |

**병목 판단**: 검증 상류는 Phase 32에서 일부 풀린 뒤이나, **헤드라인 병목은 forward·가격 창 성숙·검증 excess 컬럼 동기화** 쪽으로 좁혀 진다. Phase 32 번들의 “23 심볼 해소”와 **라이브 패널 excess 전부 null**이 함께 나타나므로, **운영 리포트는 반드시 `stage_semantics_truth`·`metric_truth_audit_*`를 함께 본다.**

## 패치·증거

- `docs/phase33_patch_report.md`, `docs/phase33_evidence.md`

## 테스트

`pytest src/tests/test_phase33_forward_coverage_truth.py -q`

---

# HANDOFF — Phase 34 (Forward→validation propagation + maturity-aware retry)

## 병목이 가격 수집인지 전파(패널 갱신)인지

- Phase 33 실측에서 **forward upsert는 일부 진행**되었으나 **터치 심볼 검증 패널 `excess_return_1q`는 라이브에서 여전히 null**인 행이 다수였고, NQ 실패 샘플은 **`lookahead_window_not_matured`** 로 분류되어 **즉시 일봉 백필 대상이 아니었다**. Phase 34는 (1) **동일 심볼·시그널·accession 범위에서 forward 존재 vs validation excess null**을 감사·분류하고, (2) **forward excess는 이미 있는데 validation만 비어 있는 행**에 한해 `run_validation_panel_build_from_rows` 로 **좁은 패널 재빌드**, (3) Phase 32 NQ `insufficient_price_history` 중 **`would_compute_now`(성숙)** 만 forward 재시도, (4) 전파 감사 행 중 **`missing_market_prices_daily_window`** 만 **상한 일봉 수집**, (5) GIS는 Phase 33와 동일 **결정적 샘플만**(광역 silver/개념맵 비목표).

## 정확한 델타(운영자가 번들로 채울 것)

- **`closeout_summary` / `validation_refresh`**: `validation_excess_filled_now_count`, `symbol_cleared_from_missing_excess_queue_count`(refresh 전·후 metric truth), `joined_recipe_unlocked_now_count`(헤드라인 `joined_recipe_substrate_row_count` after−before).
- **forward vs validation**: `propagation_gap_before` vs `propagation_gap_final` 의 `classification_counts`(특히 `forward_present_validation_not_refreshed` → 갱신 후 감소 여부).
- **joined 기판이 드디어 움직였는지**: 번들 `before`/`after` 의 `joined_recipe_substrate_row_count` 및 위 joined 델타.

## CLI (`p27` + `--phase32-bundle-in` 조합은 Phase 33과 동일)

| 명령 | 역할 |
|------|------|
| `report-forward-validation-propagation-gaps` | 터치 심볼 패널 행 단위 전파 갭 분류 |
| `export-forward-validation-propagation-gaps` | JSON `--out` |
| `run-validation-refresh-after-forward-propagation` | `forward_present_validation_not_refreshed` 만 factor 패널 경로로 validation 재빌드 |
| `report-matured-forward-retry-targets` | Phase 32 NQ 오류 → 성숙/비성숙/가격/레지스트리 버킷 |
| `export-matured-forward-retry-targets` | JSON `--out` |
| `run-matured-forward-retry` | `maturity_eligible` 만 forward 재빌드 |
| `run-phase34-forward-validation-propagation` | 일괄 + `phase34_forward_validation_propagation_bundle.json` / `review.md` |
| `write-phase34-forward-validation-propagation-review` | 번들 → MD (+ 선택 JSON) |

## 코드

- `src/phase34/` (`propagation_audit`, `validation_refresh`, `matured_forward_retry`, `price_backfill`, `orchestrator`, `review`, `phase35_recommend`), `market.validation_panel_run`, `market.forward_returns_run`, `market.price_ingest`.

## Phase 34.1 실측 클로즈아웃 (2026-04-09, `sp500_current`)

- **근거**: `docs/operator_closeout/phase34_forward_validation_propagation_bundle.json`, `docs/operator_closeout/phase34_forward_validation_propagation_review.md` (리뷰 생성 UTC `2026-04-09T00:36:33+00:00`). 상세 표·명령: `docs/phase34_evidence.md`, 패치 요약: `docs/phase34_patch_report.md`.

| 항목 | 결과 |
|------|------|
| **병목이 전파였는지** | **예.** 초기 감사 23/30행이 `forward_present_validation_not_refreshed`(forward NQ excess 있음·validation excess null). refresh 후 전부 `synchronized`, `refresh_failed` 0. 가격 백필 `ingest_attempted: false`, NQ 7건 전부 `still_lookahead_window_not_matured`. |
| **forward-present vs validation-filled** | `validation_excess_filled_now_count` **23**; 전파 분류 `forward_present_validation_not_refreshed` **23→0**, `synchronized` **0→23**. |
| **joined 이동** | 헤드라인 `joined_recipe_substrate_row_count` **243→243** (`joined_recipe_unlocked_now_count` Δ **0**). |
| **헤드라인 기타** | `missing_excess_return_1q` **101→78**; `no_state_change_join` **8→31** (excess 채운 뒤 recipe join 제외가 늘어난 것으로 해석). |
| **터치 집합 truth** | 패널 행 excess null **30→7**, present **0→23**; `symbol_cleared_from_missing_excess_queue_count` **0→23** (잔여 큐 7심볼 = 미성숙 NQ). |
| **성숙 forward / 가격** | `matured_forward_retry_success_count` **0**(eligible 0), `price_coverage_repaired_now_count` **0**. |
| **GIS** | `blocked_unmapped_concepts_remain_in_sample` (샘플 13 concept unmapped). |
| **Phase 35** | 구현·**실측 완료** — `joined` **243→266**, `no_state_change_join` **31→8**, 동기화 23행 refresh 후 전부 joined. **`docs/phase35_evidence.md`**, 아래 **HANDOFF — Phase 35**. |
| **Phase 36 / 36.1** | **실측 완료** (2026-04-10 UTC) — 초차는 메타 수화만으로 플래그 23 잔존; **36.1 2패스**로 검증 재빌드 **23건**·**`joined_market_metadata_flagged` 23→0**. 잔여 SC **8** 전부 `join_key_mismatch`·PIT defer. Freeze: **`freeze_public_core_and_shift_to_research_engine`**, Phase 37: **`execute_research_engine_backlog_sprint`**. **`docs/phase36_evidence.md`**, **`phase36_1_*` 번들**. |
| **Phase 37** | **Sprint 1 구현 완료** — 가설·스캐폴드·케이스북·적대적 리뷰·설명 MD·`phase37_*` 번들. 아래 **HANDOFF — Phase 37**. |
| **Phase 38** | **실측 완료** (2026-04-10 UTC, `sp500_current`) — 8행 세 스펙 모두 `still_join_key_mismatch` 8/8, 누수 감사 통과, 게이트 `blocked`, Phase 39 `broaden_hypothesis_families…`. `phase38_*` 번들·`docs/phase38_evidence.md`. 아래 **HANDOFF — Phase 38**. |
| **Phase 39** | **실측 완료** (번들 UTC `2026-04-10T21:28:28Z`) — 가설 5·게이트 `deferred_pending_more_hypothesis_coverage`·히스토리 2건·`docs/phase39_evidence.md`. 아래 **HANDOFF — Phase 39**. |
| **Phase 40** | **실측 완료** (번들 UTC `2026-04-11T00:09:06Z`) — 패밀리별 PIT·동적 `spec_results`·게이트 v3·설명 v3·`phase40_*` 번들. **`docs/phase40_evidence.md`**. 아래 **HANDOFF — Phase 40**. |
| **Phase 41** | **실측 완료** (번들 UTC `2026-04-11T02:45:40Z`) — 반증 기판·2패밀리 재실행·게이트 v4·설명 v4·`pytest …/test_phase41_substrate.py` **9 passed**. **`docs/phase41_evidence.md`**. 아래 **HANDOFF — Phase 41**. |
| **Phase 43** | **실측 완료** (번들 UTC `2026-04-11T19:03:56Z`) — 8행 한정 filing·메타 수화 후 Phase 41/42 Supabase-fresh 재실행; sector 스코어카드 **no_row→blank**·digest 변경. **`docs/phase43_evidence.md`**. 아래 **HANDOFF — Phase 43**. |
| **Phase 44** | **실측/번들 기록** — truthfulness·provenance·claim narrowing (DB 없음). **`docs/phase44_evidence.md`**, **`docs/phase44_patch_report.md`**. 아래 **HANDOFF — Phase 44**. |
| **Phase 45** | **실측/번들 기록** — canonical closeout·권위 supersede·reopen 프로토콜·Phase 46 (기판 작업 없음). **`docs/phase45_evidence.md`**, **`docs/phase45_patch_report.md`**. 아래 **HANDOFF — Phase 45**. |
| **Phase 46** | **제품 표면(번들만)** — founder cockpit·대표 피치·drill-down·UI 계약·알림/결정 레저. **`docs/phase46_evidence.md`**, **`docs/phase46_patch_report.md`**. 아래 **HANDOFF — Phase 46**. |

## 테스트

`pytest src/tests/test_phase34_forward_validation_propagation.py -q`

---

# HANDOFF — Phase 35 (Join displacement + state_change seam + maturity schedule)

## 맥락

- Phase 34로 **forward→validation 전파**는 해소되었으나 **`joined_recipe_substrate_row_count`는 정체**, **`no_state_change_join`은 증가**(Phase 34 실측 8→31)한 것으로 관측됨. Phase 35는 **Phase 34 `propagation_gap_final`의 `synchronized` 23행**이 `public_depth.diagnostics.compute_substrate_coverage`와 동일한 규칙으로 **joined recipe에 포함되는지**·아니면 **`pick_state_change_at_or_before_signal` 단계에서 떨어지는지**를 행 단위로 증명한다.
- **성숙 7심볼**(MCK, MDT, MKC, MU, NDSN, NTAP, NWSA)은 번들·`report_matured_window_schedule_for_forward`에서 **격리 검증**; `would_compute_now`일 때만 좁은 forward 재시도.
- **state_change 재실행**(C)은 **`state_change_not_built_for_row`**(해당 런에 CIK 점수 없음)에 한해 상한 `run_state_change` 1회; `join_key_mismatch`(시그널이 첫 `as_of`보다 이른 PIT 괴리)는 자동 대량 수리 대상에서 제외.
- 가격·GIS·메타·광역 filing·15/16·스코어 비목표(Phase 34와 동일).

## CLI (`p27` + `--phase34-bundle-in`)

| 명령 | 역할 |
|------|------|
| `report-forward-validation-join-displacement` | 동기화 23행 → joined / no_state_change / 기타 |
| `export-forward-validation-join-displacement` | JSON `--out` |
| `report-state-change-join-gaps-after-phase34` | 조인 이음새 버킷 상세 |
| `run-state-change-join-refresh-after-phase34` | 수리 가능 버킷만 상한 `run_state_change` |
| `report-matured-window-schedule-for-forward` | 미성숙 행 스케줄·`would_compute_now` 여부 |
| `export-matured-window-schedule-for-forward` | JSON `--out` |
| `run-phase35-join-displacement-and-maturity` | 일괄 + `phase35_join_displacement_and_maturity_bundle.json` / `review.md` |
| `write-phase35-join-displacement-and-maturity-review` | 번들 → MD (+ 선택 JSON) |

`report-matured-window-schedule-for-forward` / `export-…` 는 `--phase34-bundle-in` + `--price-lookahead-days` 만 사용 (`p27` 불필요).

## 코드

- `src/phase35/` — `join_displacement`, `state_change_join_gaps`, `state_change_refresh`, `matured_window_schedule`, `orchestrator`, `review`, `phase36_recommend`, `phase34_bundle_io`.

## Phase 35.1 실측 클로즈아웃

| 항목 | 측정값 |
|------|--------|
| Review 생성 (UTC) | `2026-04-09T04:53:34.557864+00:00` |
| joined_recipe_substrate_row_count | **243 → 266** |
| joined_market_metadata_flagged_count | **0 → 23** |
| no_state_change_join | **31 → 8** |
| missing_excess_return_1q | 78 (유지) |
| 동기화 23행 초기 변위 | 전부 `excluded_no_state_change_join`, 이음새 **`state_change_not_built_for_row`** (런 `39208f19…`, scores_loaded 313) |
| state_change_join_refresh | 대상 23 CIK, 런 `223e2aa5…` (scores_written 353); **unlocked / cleared 23** |
| 동기화 23행 최종 변위 | 전부 **`included_in_joined_recipe_substrate` / `joined_now`** |
| 가설 (`hypothesis_phase34_excess_to_no_state_change_join`) | **초기 true** (23이 no_sc로 분류) → **최종 false** (수리 후 전부 joined) |
| 미성숙 7심볼 | 격리 OK; `matured_eligible_now` 0, forward retry 스킵 |
| 가격·GIS | 가격 백필 없음; GIS **차단 유지** |
| Phase 36 권고 | `continue_join_audit_after_substrate_headline_moved` — 잔여 `no_state_change_join`(8)·메타 플래그 23. **후속(36.1)**: 2패스로 **`joined_market_metadata_flagged` 23→0**, 공개 코어 freeze. |

상세 수치·재현: **`docs/phase35_evidence.md`**, 번들·review 경로는 위 Phase 35 절과 동일.

## 테스트

`pytest src/tests/test_phase35_join_displacement_and_maturity.py -q`

---

# HANDOFF — Phase 36 (Substrate freeze + metadata reconciliation + residual join)

## 맥락

- Phase 35 이후 **헤드라인 joined**는 움직였고, 좁은 정합 대상이었던 **메타 플래그 23**은 **Phase 36.1 2패스**로 **0**까지 내려갔다. **잔여 `no_state_change_join` 8**은 **`join_key_mismatch`만** 남아 **PIT defer**로 고정. Phase 36 계열은 **광역 filing/forward/GIS 확대 없이** 이음새를 분류·상한 수리하고, **공개 코어 기판 freeze**(`freeze_public_core_and_shift_to_research_engine`)와 **연구 엔진 handoff**를 문서화한다.

## CLI (`p27` + `--phase35-bundle-in` + 선택 `--state-change-scores-limit`)

| 명령 | 역할 |
|------|------|
| `report-joined-metadata-flag-reconciliation-targets` | Phase 35 `forward_validation_join_displacement_final` 신규 joined 행 → 메타 플래그 정합 버킷 |
| `export-joined-metadata-flag-reconciliation-targets` | `--out` JSON/CSV |
| `run-joined-metadata-reconciliation-repair` | **2패스**(수화 → `report_mid` → stale 재빌드 → `report_after`); 구 Phase 36 시퀀싱 갭 해소 |
| `run-joined-metadata-reconciliation-repair-two-pass` | 위와 동일(명시적 별칭) |
| `run-phase36-1-complete-narrow-integrity-round` | 2패스 메타 + 잔여 SC **감사만(PIT defer)** + freeze 재평가 + handoff → `phase36_1_*` 번들/리뷰 |
| `write-phase36-1-complete-narrow-integrity-round-review` | Phase 36.1 번들 → MD |
| `report-residual-state-change-join-gaps` | excess 있는 패널 중 `no_state_change_join` 잔여 행 버킷 |
| `export-residual-state-change-join-gaps` | `--out` JSON/CSV |
| `run-residual-state-change-join-repair` | `state_change_not_built_for_row` 만 상한 `run_state_change` |
| `report-substrate-freeze-readiness` | 스냅샷 + 메타·잔여·GIS 입력 → `substrate_freeze_recommendation` |
| `export-research-engine-handoff-brief` | 완료된 Phase 36 번들 `--bundle-in` → brief JSON |
| `run-phase36-substrate-freeze-and-research-handoff` | 일괄 + 기본 번들/리뷰 경로 + 선택 `--handoff-brief-out` |
| `write-phase36-substrate-freeze-and-research-handoff-review` | 번들 → MD (+ 선택 JSON) |

## 코드

- `src/phase36/` — `joined_metadata_reconciliation`(2패스 수리), `residual_state_change_join`, `residual_pit_deferral`, `substrate_freeze_readiness`, `research_handoff_brief`, `phase37_recommend`, `orchestrator`(Phase 36 + **36.1**), `review`, `phase35_bundle_io`.

## Phase 36.1 실측 클로즈아웃 (권위, 2026-04-10 UTC)

번들: **`docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json`** · Review MD 생성 UTC: **`2026-04-10T06:50:18.520557+00:00`** · Handoff brief UTC: **`2026-04-10T06:50:18.515921+00:00`**

1. **2패스 메타 정합 (좁은 무결성 라운드)**
   - **타깃**: Phase 35 신규 joined **23** (`phase35_newly_joined_target_count`).
   - **report_before / report_mid**: `reconciliation_bucket_counts` 모두 **`stale_metadata_flag_after_join` 23** (패널 `panel_json` 스테일 플래그).
   - **수화**: 번들 `joined_metadata_reconciliation_two_pass.hydration` — **`skipped: true`** (이미 DB 메타는 갖춰진 상태에서 스테일 플래그만 남은 케이스).
   - **검증 재빌드**: **`validation_rebuild_target_count_after_hydration` 23** → **`validation_rebuild_factor_panels_submitted` 23**, `status` **`completed`**, **`rows_upserted` 23**, **`failures` 0**.
   - **report_after**: 플래그 해소 후 타깃 집합 `metadata_flagged_in_target_set_count` **0**; 버킷 **`other_join_metadata_seam` 23**(분류만 이동, 헤드라인 플래그는 0).
   - **`metadata_flags_cleared_now_count`: 23** · **`metadata_flags_still_present_count`: 0** · 헤드라인 **`joined_market_metadata_flagged_count` 23 → 0** (`before` / `after` 스냅샷).

2. **잔여·defer (고신호)**
   - **`no_state_change_join` 8** — 전부 **`state_change_built_but_join_key_mismatch`**; **`residual_pit_deferral`**에 심볼·행 기록, **광역 SC 수리 없음**.
   - **레지스트리·스냅샷 tail**: `missing_validation_symbol_count` **151**, `factor_panel_missing` / `missing_quarter_snapshot` **148** — 저ROI defer (freeze rationale에 포함).
   - **GIS**: `blocked_unmapped_concepts_remain_in_sample` (샘플 unmapped **13**).
   - **캘린더**: `maturity_deferred_symbol_count` **7**.

3. **Freeze + Phase 37 (재평가 결과)**
   - **`substrate_freeze_recommendation`**: **`freeze_public_core_and_shift_to_research_engine`**
   - **`phase37_recommendation`**: **`execute_research_engine_backlog_sprint`**
   - 번들 `rationale` 요지: 헤드라인 joined 안정·레지스트리 tail 저ROI defer·잔여 SC 8은 비수리 버킷만 PIT 실험실 defer → **상위 레이어(연구 엔진·설명)로 에너지 이동**.

4. **참고: Phase 36 초차 (동일 일자, 이전 번들)**
   - `docs/operator_closeout/phase36_substrate_freeze_and_research_handoff_bundle.json` (Review UTC `2026-04-10T04:33:00…`) — 당시 **`validation_rebuild` skipped**, 메타 플래그 **23 유지**, freeze 권고 **`one_more_narrow_integrity_round_then_freeze`**. 시퀀싱 갭은 **Phase 36.1 2패스**로 해소됨.

**헌장**: 본 도구는 일반 AI 주식 추천기가 아니라, **공개 데이터 우선·PIT·연구 거버넌스**를 전제로 시장 해석력을 민주화하는 투자 인텔리전스 시스템이다.

## 테스트

`pytest src/tests/test_phase36_substrate_freeze.py -q`

---

# HANDOFF — Phase 37 (Research engine backlog sprint)

## Sprint 1 완료 (구현 + 클로즈아웃)

- **상태**: 공개 코어 **frozen** 가정 하에 상위 레이어 **스캐폴드**가 저장소에 존재한다 (가설 1건·PIT 스캐폴드 1건·케이스북 4건·적대적 리뷰 1건·설명 MD 프로토타입).
- **헌장·필러 매핑**: `docs/research_engine_constitution.md`, `phase37.constitution.RESEARCH_ENGINE_ARTIFACTS`.
- **코드**: `src/phase37/` — `hypothesis_registry`, `pit_experiment`, `adversarial_review`, `casebook`, `explanation_surface`, `orchestrator`, `review`, `phase38_recommend`, `persistence`.
- **CLI**: `run-phase37-research-engine-backlog-sprint` (`--phase36-1-bundle-in`, `--research-data-dir`, `--explanation-out`, `--bundle-out`, `--out-md`) · `write-phase37-research-engine-backlog-sprint-review --bundle-in …`
- **산출물**: `docs/operator_closeout/phase37_research_engine_backlog_sprint_bundle.json`, `..._review.md`, `phase37_explanation_prototype.md`, `data/research_engine/*.json`.
- **증거·패치**: `docs/phase37_evidence.md`, `docs/phase37_patch_report.md` · Phase 39+: `docs/phase39_evidence.md`, `docs/phase39_patch_report.md` · Phase 40+: `docs/phase40_evidence.md`, `docs/phase40_patch_report.md` · Phase 41+: `docs/phase41_evidence.md`, `docs/phase41_patch_report.md` · Phase 42+: `docs/phase42_evidence.md`, `docs/phase42_patch_report.md` · Phase 43+: `docs/phase43_evidence.md`, `docs/phase43_patch_report.md` · Phase 44+: **`docs/phase44_evidence.md`**, **`docs/phase44_patch_report.md`** · Phase 45+: **`docs/phase45_evidence.md`**, **`docs/phase45_patch_report.md`** · Phase 46+: **`docs/phase46_evidence.md`**, **`docs/phase46_patch_report.md`**.
- **Phase 38 (실측 완료)**: DB-bound PIT — `run-phase38-db-bound-pit-runner`, 번들 `phase38_db_bound_pit_runner_*`, 증거 `docs/phase38_evidence.md`. 실측 요약은 문서 상단·**HANDOFF — Phase 38** 참고.

## 맥락 (36.1에서의 진입)

- Phase 36.1 번들 권고 **`execute_research_engine_backlog_sprint`** 에 따라 상위 레이어로 전환.
- 잔여 SC **8**건은 **`join_key_mismatch`** — 케이스북·PIT 픽스처로만; 광역 `run_state_change` **비목표**.
- 기판 실측: **`docs/phase36_evidence.md`**, `docs/operator_closeout/phase36_1_complete_narrow_integrity_round_bundle.json`.

## 테스트

`pytest src/tests/test_phase37_research_engine.py -q`


---

# HANDOFF — Phase 38 (DB-bound PIT runner)

## 요약

- **목적**: Phase 37 권고대로 **DB 결합 PIT** 한 사이클 (가설 1건 유지, 깊이 우선).
- **코드**: `src/phase38/` — `pit_join_logic`, `pit_runner`, `adversarial_update`, `promotion_gate_v1`, `phase39_recommend`, `explanation_phase38`, `orchestrator`, `review`.
- **CLI**: `run-phase38-db-bound-pit-runner --universe …` · `write-phase38-db-bound-pit-runner-review --bundle-in …`
- **산출물**: `docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json`, `..._review.md`, `phase38_explanation_surface.md`
- **영속 갱신**: `data/research_engine/adversarial_reviews_v1.json`, `casebook_v1.json`, **`promotion_gate_v1.json`**
- **증거·패치**: `docs/phase38_evidence.md`, `docs/phase38_patch_report.md`
- **Phase 39 (실측 완료)**: `run-phase39-hypothesis-family-expansion` — 증거 `docs/phase39_evidence.md` (Phase 38 번들의 권고 `broaden_hypothesis_families…` 반영됨)
- **테스트 (DB 불요)**: `pytest src/tests/test_phase38_pit_join_logic.py -q`

## Phase 38 실측 클로즈아웃 (2026-04-10 UTC, `sp500_current`)

- **근거**: `docs/operator_closeout/phase38_db_bound_pit_runner_bundle.json` (`ok: true`, `generated_utc` `2026-04-10T18:26:47.398074+00:00`), `docs/operator_closeout/phase38_db_bound_pit_runner_review.md` (리뷰 생성 UTC `2026-04-10T18:26:47.398780+00:00`).
- **실험 id**: `41dea3b0-02fe-46d8-951d-e2778af01e9f`.
- **런**: baseline `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`, alternate `39208f19-8d0e-4c35-9950-78963bb59a97`; `completed_runs_considered` **13**.
- **점수 로드**: baseline **353**행, alternate **313**행 (`pit_execution.scores_loaded`).
- **8행 픽스처**: baseline / alternate_prior_run / lag_signal_bound 각 **`still_join_key_mismatch` 8**; 표준 롤업에서 joined·other_exclusion·invalid **전부 0**.
- **누수 감사**: `passed: true`, `violations: []`.
- **적대적 리뷰**: `phase38_resolution_status` `deferred_with_evidence_reinforces_baseline_mismatch`, `phase38_leakage_audit_passed` true.
- **프로모션 게이트 v1**: `gate_status` **`blocked`** (`hypothesis_under_test_not_eligible_for_product_promotion`, `adversarial_challenge_not_cleared`).
- **Phase 39 권고**: `broaden_hypothesis_families_and_harden_explanation_under_persistent_mismatch` (번들 `phase39.rationale` 참고).

**운영자 추가 필수 작업 없음.** (선택) `data/research_engine/*.json` 커밋 정책, 재현 고정용 `--baseline-run-id` / `--alternate-run-id`, Phase 39 스프린트 착수.

## Phase 37과의 관계

- Sprint 1 산출물(`phase37_*` 번들, `data/research_engine/*.json`)을 입력·갱신 대상으로 사용.
- `adversarial_reviews_v1.json`·`casebook_v1.json` 은 Phase 38 오케스트레이터가 **덮어쓰기/병합**할 수 있음.


---

# HANDOFF — Phase 39 (Hypothesis family expansion + governance)

## 요약

- **목적**: Phase 38 증거(누수 통과·8행 지속 mismatch)에 맞춰 **가설 패밀리 확장**, **라이프사이클 감사**, **다중 stance 적대적 리뷰**, **PIT 패밀리 계약**, **라이프사이클 연동 게이트**, **설명 v2**.
- **코드**: `src/phase39/` — `hypothesis_seeds`, `lifecycle`, `adversarial_batch`, `pit_family_contract`, `promotion_gate_phase39`, `explanation_v2`, `phase40_recommend`, `orchestrator`, `review`.
- **CLI**: `run-phase39-hypothesis-family-expansion` (`--phase38-bundle-in`, `--research-data-dir`, `--explanation-out`, `--gate-history-filename`, `--bundle-out`, `--out-md`) · `write-phase39-hypothesis-family-expansion-review --bundle-in …`
- **산출물**: `docs/operator_closeout/phase39_hypothesis_family_expansion_bundle.json`, `phase39_hypothesis_family_expansion_review.md`, `phase39_explanation_surface_v2.md`
- **영속 갱신**: `hypotheses_v1.json` (가설 5+, `lifecycle_transitions`), `adversarial_reviews_v1.json` (append), `promotion_gate_v1.json` (schema v2), **`promotion_gate_history_v1.json`** (append-only 이력)
- **테스트**: `pytest src/tests/test_phase39_hypothesis_family.py -q`
- **Phase 40 (실측 완료)**: `run-phase40-family-spec-bindings` — `docs/phase40_evidence.md` (번들 `2026-04-11T00:09:06Z`)
- **Phase 41 (실측 완료)**: `run-phase41-falsifier-substrate` — `docs/phase41_evidence.md` (번들 `2026-04-11T02:45:40Z`)
- **Phase 42 (실측 완료)**: `run-phase42-evidence-accumulation` — `docs/phase42_evidence.md` (번들 `2026-04-11T04:52:28Z`, `--bundle-substrate-only`; Supabase-fresh·Phase 43 후속은 동 문서 § Phase 43 후속)
- **Phase 43 (실측 완료)**: `run-phase43-targeted-substrate-backfill` — `docs/phase43_evidence.md` (번들 `2026-04-11T19:03:56Z`)
- **Phase 44 (번들 기록)**: `run-phase44-claim-narrowing-truthfulness` — `docs/phase44_evidence.md` (`phase44_claim_narrowing_truthfulness_bundle.json`)
- **Phase 45 (번들 기록)**: `run-phase45-operator-closeout-and-reopen-protocol` — `docs/phase45_evidence.md` (`phase45_canonical_closeout_bundle.json`)
- **Phase 46 (제품 표면)**: `run-phase46-founder-decision-cockpit` — `docs/phase46_evidence.md` (`phase46_founder_decision_cockpit_bundle.json`)
- **증거·패치**: `docs/phase39_evidence.md`, `docs/phase39_patch_report.md` · Phase 40–43: 위 각 evidence/patch · Phase 44–46: **`docs/phase44_evidence.md`**, **`docs/phase44_patch_report.md`**, **`docs/phase45_evidence.md`**, **`docs/phase45_patch_report.md`**, **`docs/phase46_evidence.md`**, **`docs/phase46_patch_report.md`**

## 비목표

광역 기판 수리, 자동 승격, 제네릭 종목 추천 UX, 프리미엄 데이터 확장을 헤드라인으로 두지 않음.

## Phase 39 실측 클로즈아웃 (2026-04-10 UTC)

- **근거 번들**: `docs/operator_closeout/phase39_hypothesis_family_expansion_bundle.json` — `generated_utc` **`2026-04-10T21:28:28.683360+00:00`**, `ok: true`
- **리뷰 MD**: `docs/operator_closeout/phase39_hypothesis_family_expansion_review.md` (생성 UTC `2026-04-10T21:28:28.683688+00:00`)
- **가설**: 총 **5** — `challenged` 1 (`hyp_pit_join_key_mismatch_as_of_boundary_v1`) · `draft` 4 (cadence / filing boundary / sector cadence / governance join policy)
- **적대적 리뷰**: stance **4** (data_lineage_auditor + skeptical_fundamental + skeptical_quant + regime_horizon_reviewer)
- **게이트**: `gate_status` **`deferred`**, `primary_block_category` **`deferred_pending_more_hypothesis_coverage`**
- **게이트 이력**: `data/research_engine/promotion_gate_history_v1.json` — 엔트리 **2**건 (동일 일 CLI 2회; 재실행 시 계속 append)
- **설명 v2**: `docs/operator_closeout/phase39_explanation_surface_v2.md`
- **문서**: **`docs/phase39_evidence.md`**, **`docs/phase39_patch_report.md`**

**운영자 추가 필수 작업 없음.**

---

# HANDOFF — Phase 40 (Family PIT spec bindings + shared leakage audit)

## 요약

- **목적**: Phase 39 패밀리를 **DB 결합 PIT**로 실행한다. 행 단위 **`spec_results` (spec_key → outcome_cell)**·네 가지 표준 outcome·**공통 누수 감사**·라이프사이클·패밀리 태그 적대적 리뷰·**프로모션 게이트 schema v3**·설명 v3. 자동 승격 없음.
- **코드**: `src/phase40/` — `pit_engine`, `family_execution`, `orchestrator`, `lifecycle_phase40`, `adversarial_family`, `promotion_gate_phase40`, `explanation_v3`, `phase41_recommend`, `review`, `contract_manifest`.
- **CLI**: `run-phase40-family-spec-bindings --universe sp500_current --bundle-out docs/operator_closeout/phase40_family_spec_bindings_bundle.json --out-md docs/operator_closeout/phase40_family_spec_bindings_review.md` · `write-phase40-family-spec-bindings-review --bundle-in … --out-md …`
- **산출물**: `docs/operator_closeout/phase40_family_spec_bindings_bundle.json`, `phase40_family_spec_bindings_review.md`, `phase40_explanation_surface_v3.md`
- **영속 갱신**: `data/research_engine/hypotheses_v1.json`, `adversarial_reviews_v1.json`, `promotion_gate_v1.json`, `promotion_gate_history_v1.json`
- **증거·패치**: `docs/phase40_evidence.md`, `docs/phase40_patch_report.md` · Phase 41·42·43: **`docs/phase41_evidence.md`**, **`docs/phase41_patch_report.md`**, **`docs/phase42_evidence.md`**, **`docs/phase42_patch_report.md`**, **`docs/phase43_evidence.md`**, **`docs/phase43_patch_report.md`** · Phase 44·45·46: **`docs/phase44_evidence.md`**, **`docs/phase44_patch_report.md`**, **`docs/phase45_evidence.md`**, **`docs/phase45_patch_report.md`**, **`docs/phase46_evidence.md`**, **`docs/phase46_patch_report.md`**

## Phase 40 실측 클로즈아웃 (2026-04-11 UTC)

- **근거 번들**: `docs/operator_closeout/phase40_family_spec_bindings_bundle.json` — `generated_utc` **`2026-04-11T00:09:06.788705+00:00`**, `ok: true`
- **리뷰 MD**: `docs/operator_closeout/phase40_family_spec_bindings_review.md` (`write-phase40-family-spec-bindings-review` 재실행 시 선행 `_Generated (UTC)` 줄만 갱신됨)
- **실험 id** (`pit_execution`): `b0ed1cdd-19ee-448a-9748-a295784a9a94`
- **런·점수**: baseline `223e2aa5-3879-4dee-b28f-3d579cbf4cbd`, alternate `39208f19-8d0e-4c35-9950-78963bb59a97`; `completed_runs_considered` **13**; `fixture_row_count` **8**; `scores_loaded` baseline **353** / alternate **313**
- **패밀리·스펙**: **5** 패밀리, **7** 스펙 바인딩; 패밀리별 `joined_any_row` **전부 false**; 각 패밀리·각 spec 롤업 **`still_join_key_mismatch` 8** (그 외 버킷 0)
- **누수**: `all_families_leakage_passed` **true**
- **라이프사이클 (after)**: `challenged` **1** (`hyp_pit_join_key_mismatch_as_of_boundary_v1`) · `conditionally_supported` **4**
- **적대적 리뷰**: `adversarial_reviews_after_count` **8**; `adversarial_review_count_by_family_tag` — 네 패밀리 태그 각 **1**
- **프로모션 게이트 v3**: `gate_status` **`deferred`**, `primary_block_category` **`conditionally_supported_but_not_promotable`**
- **Phase 41 권고**: `wire_filing_and_sector_substrate_for_hypothesis_falsification_and_explanation_v4` — **실측 완료** (`docs/phase41_evidence.md`)

**운영자 추가 필수 작업 없음.**

---

# HANDOFF — Phase 41 (Falsifier substrate: filing_index + sector metadata)

## 요약

- **목적**: Phase 40 권고대로 **반증 기판**만 최소 연결 — `filing_index`(accepted_at / filed_at)·`market_metadata_latest.sector`. **2개 패밀리만** 재실행 (`signal_filing_boundary_v1`, `issuer_sector_reporting_cadence_v1`). 동일 누수 규칙.
- **코드**: `src/phase41/` — `substrate_filing`, `substrate_sector`, `pit_rerun`, `lifecycle_phase41`, `adversarial_phase41`, `promotion_gate_phase41`, `explanation_v4`, `phase42_recommend`, `orchestrator`, `review`.
- **CLI**: `run-phase41-falsifier-substrate --universe sp500_current --bundle-out docs/operator_closeout/phase41_falsifier_substrate_bundle.json --out-md docs/operator_closeout/phase41_falsifier_substrate_review.md` · 선택 `--phase40-bundle-in` (before/after) · `write-phase41-falsifier-substrate-review --bundle-in …`
- **산출물**: `phase41_falsifier_substrate_bundle.json`, `phase41_falsifier_substrate_review.md`, `phase41_explanation_surface_v4.md`
- **영속 갱신**: `hypotheses_v1.json` (`substrate_audit_log`), `adversarial_reviews_v1.json` (append), `promotion_gate_v1.json` (**schema v4**), `promotion_gate_history_v1.json`
- **테스트**: `pytest src/tests/test_phase41_substrate.py -q`
- **증거·패치**: **`docs/phase41_evidence.md`**, **`docs/phase41_patch_report.md`** · 후속 Phase 42: **`docs/phase42_evidence.md`**, **`docs/phase42_patch_report.md`**

## Phase 41 실측 클로즈아웃 (2026-04-11 UTC)

- **근거 번들**: `docs/operator_closeout/phase41_falsifier_substrate_bundle.json` — `generated_utc` **`2026-04-11T02:45:40.253079+00:00`**, `ok: true`
- **리뷰 MD**: `docs/operator_closeout/phase41_falsifier_substrate_review.md`
- **설명 v4**: `docs/operator_closeout/phase41_explanation_surface_v4.md`
- **실험 id**: `f85f3524-73eb-4403-bf0e-c347c06d011f` · baseline 런 `223e2aa5-3879-4dee-b28f-3d579cbf4cbd` · `scores_loaded` **353**
- **픽스처**: **8**행 · 재실행 패밀리 **2** · `all_families_leakage_passed` **true**
- **Filing 기판**: 8행 전부 `filing_public_ts_unavailable`, 명시적 signal 프록시 **8** (`filing_substrate.summary`)
- **Sector 기판**: 8행 `sector_metadata_missing`, 스트라텀 **unknown**만 (`sector_substrate.summary`, `sector_stratified_signal_pick_v1`)
- **Outcome**: 양 패밀리 `still_join_key_mismatch` **8**/8
- **Phase 40 대비**: filing 롤업 동일; sector 패밀리는 spec 키만 변경·수치 동일 (`family_rerun_before_after`)
- **라이프사이클**: `challenged` 1 · `conditionally_supported` 4 (가설 `substrate_audit_log` append)
- **게이트 v4**: `deferred` · `deferred_due_to_proxy_limited_falsifier_substrate`
- **Phase 42 (코드 권고, Phase 41 번들)**: `accumulate_evidence_and_narrow_hypotheses_under_stronger_falsifiers_v1` — **실측 완료** (`docs/phase42_evidence.md`, 게이트 `phase: phase42`)
- **테스트**: `pytest src/tests/test_phase41_substrate.py -q` → **9 passed**

**운영자 추가 필수 작업 없음.** (선택) 메타 수화·filing_index 적재 후 Phase 41 재실행 시 기판 분류가 달라질 수 있음.

---

# HANDOFF — Phase 42 (Evidence accumulation + gate phase42)

## 요약

- **목적**: Phase 41 pit·기판을 입력으로 **행 단위 블로커·스코어카드·outcome 시그니처 판별·가설 축소 라벨·프로모션 게이트(`phase`: phase42)·설명 v5·Phase 43 권고**를 남긴다. 자동 승격 없음.
- **코드**: `src/phase42/` — `blocker_taxonomy`, `evidence_accumulation`, `hypothesis_narrowing`, `promotion_gate_phase42`, `explanation_v5`, `phase43_recommend`, `orchestrator`, `review`.
- **CLI**: `run-phase42-evidence-accumulation` (`--phase41-bundle-in`, `--bundle-substrate-only`, `--research-data-dir`, `--bundle-out`, `--out-md`, `--explanation-out`) · `write-phase42-evidence-accumulation-review --bundle-in …`
- **산출물**: `phase42_evidence_accumulation_bundle.json`, `phase42_evidence_accumulation_review.md`, `phase42_explanation_surface_v5.md`
- **영속 갱신**: `promotion_gate_v1.json` (**덮어씀**, `phase: phase42`), `promotion_gate_history_v1.json` (append)
- **테스트**: `pytest src/tests/test_phase42_evidence_accumulation.py -q` → **8 passed**
- **증거·패치**: **`docs/phase42_evidence.md`**, **`docs/phase42_patch_report.md`**

## Phase 42 실측 클로즈아웃 (2026-04-11 UTC)

- **근거 번들**: `docs/operator_closeout/phase42_evidence_accumulation_bundle.json` — `generated_utc` **`2026-04-11T04:52:28.074748+00:00`**, `ok: true`
- **입력**: Phase 41 `phase41_falsifier_substrate_bundle.json` · 실행 플래그 **`--bundle-substrate-only`** (pit `per_row` 재생)
- **스코어카드**: 코호트 **8**행 · filing `only_post_signal_filings_available` **8** · sector `no_market_metadata_row_for_symbol` **8**
- **판별**: `any_family_outcome_discriminating` **true** — 리뷰어는 **spec 키가 시그니처에 포함**됨을 확인할 것 (`docs/phase42_evidence.md` 표)
- **게이트**: `deferred` · `deferred_due_to_proxy_limited_falsifier_substrate` · `phase42_context.filing_proxy_row_count` **8**, `sector_missing_row_count` **8**
- **stable_run_digest**: `1cc5113aeff11483`
- **Phase 43 (후속 실행됨)**: 번들 `phase43_targeted_substrate_backfill_bundle.json` (`2026-04-11T19:03:56Z`) — bounded backfill 후 Phase 42 Supabase-fresh 재실행. 스코어카드 sector 버킷 **정밀화**(no_row → blank-field), digest 변경. 상세 **`docs/phase43_evidence.md`**.

**운영자 추가 필수 작업 없음.** (선택) Supabase 경로로 재실행하면 filing 블로커 원인 코드가 번들 재생과 달라질 수 있음.

---

# HANDOFF — Phase 43 (Bounded targeted substrate backfill + Supabase-fresh retest)

## 요약

- **목적**: Phase 42 **Supabase-fresh** 입력(`phase42_evidence_accumulation_bundle_supabase.json`)의 **정확히 8행** `row_level_blockers`에 대해 filing_index·`market_metadata_latest` 만 **상한** 보강한 뒤, 동일 두 패밀리로 Phase 41을 다시 돌리고 Phase 42를 **`use_supabase=True`** 로 재실행한다. **유니버스 확장·public-core 광역 수리 비목표.**
- **코호트 (실측 번들)**: 심볼 `BBY, ADSK, CRM, CRWD, DELL, DUK, NVDA, WMT` (8행). Phase 42 입력 시점 filing: ADSK `only_post_signal_filings_available`, 나머지 `no_10k_10q_rows_for_cik`; sector: 전 행 `no_market_metadata_row_for_symbol`. **Phase 41 번들 경로**: `phase41_falsifier_substrate_bundle.json` (`merge_fixture_residual`용).
- **코드**: `src/phase43/` — `target_cohort`, `filing_audit`, `filing_backfill`, `sector_audit`, `sector_backfill`, `before_after_audit`, `orchestrator`, `review`, `explanation_v6`, `phase44_recommend`.
- **CLI**: `run-phase43-targeted-substrate-backfill` (`--phase42-supabase-bundle-in`, `--universe`, `--phase41-bundle-in` 선택, `--filing-index-limit`, `--max-filing-cik-repairs`, `--before-after-audit-out`, `--explanation-out`, `--bundle-out`, `--out-md`) · `write-phase43-targeted-substrate-backfill-review --bundle-in …` (선택 `--before-after-audit-out`). **옵션 사이 공백 필수**(`…review.md` 와 `--before-after…` 붙이면 파싱 오류).
- **산출물**: `phase43_targeted_substrate_backfill_bundle.json`, `phase43_targeted_substrate_backfill_review.md`, `phase43_targeted_substrate_before_after_audit.md`, `phase43_explanation_surface_v6.md`
- **권위 경로**: 번들 필드 **`phase42_rerun_used_supabase_fresh: true`** — 클로즈아웃에 Phase 42 **`--bundle-substrate-only` 아님** (`phase43.AUTHORITATIVE_CLOSEOUT_USES_SUPABASE_FRESH_PHASE42`).
- **테스트**: `pytest src/tests/test_phase43_targeted_substrate_backfill.py -q` → **13 passed**
- **증거·패치**: **`docs/phase43_evidence.md`**, **`docs/phase43_patch_report.md`** · 후속 클로즈아웃 체인: **`docs/phase44_evidence.md`**, **`docs/phase44_patch_report.md`**, **`docs/phase45_evidence.md`**, **`docs/phase45_patch_report.md`**

## Phase 43 실측 클로즈아웃 (2026-04-11 UTC)

- **근거 번들**: `docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json` — `generated_utc` **`2026-04-11T19:03:56.022392+00:00`**, `ok: true`, `universe_name` **`sp500_current`**
- **입력**: Phase 42 Supabase `phase42_evidence_accumulation_bundle_supabase.json` · Phase 41 `phase41_falsifier_substrate_bundle.json`
- **한정 수리**: filing **8/8** CIK `run_sample_ingest` 시도, `filing_index_updated` 위주(번들에 `raw_inserted`/`silver_inserted` false). sector **Yahoo chart** 8심볼, `rows_already_current` **8**, `rows_upserted` **0**
- **행 단위 before/after (요지)**: **filing 블로커 코드** 8행 모두 **변경 없음**(ADSK post-signal 유지, 나머지 `no_10k_10q_rows_for_cik`). **sector** 8행 모두 `no_market_metadata_row_for_symbol` → **`sector_field_blank_on_metadata_row`** (`raw_row_count` 1 유지 — “행 없음”에서 “행 있으나 sector 비어 있음”으로 **분류 정밀화**)
- **Phase 42 스코어카드 (번들 `scorecard_before` → `scorecard_after`)**: filing `no_10k_10q_rows_for_cik` **7** + `only_post_signal_filings_available` **1** **동일** · sector **`no_market_metadata_row_for_symbol` 8** → **`sector_field_blank_on_metadata_row` 8**
- **게이트**: `gate_before` / `gate_after` 모두 `deferred` · `primary_block_category` **`deferred_due_to_proxy_limited_falsifier_substrate`** 동일 · `phase42_context.sector_missing_row_count` **8** 유지(게이트 집계는 블로커 세분과 완전 동기화되지 않을 수 있음 — 리뷰어는 **스코어카드·행 감사** 우선)
- **stable_run_digest**: **`edfd0b7d36ecb2de`** → **`285b046cc5bcb307`**
- **Phase 41 pit (재실행)**: `experiment_id` **`5ae2780b-5978-4522-b1f5-0ece15844e0f`**, `fixture_row_count` **8**, `ok: true`
- **Phase 42 번들 내 Phase 43 권고** (`phase42_rerun…`): 여전히 `substrate_backfill_or_narrow_claims_then_retest_v1` (코드 권고 문자열)
- **번들 내 `phase44` (Phase 43 오케스트레이터가 채움)**: 레거시 휴리스틱으로 `continue_bounded_falsifier_retest_or_narrow_claims_v1` 가 남을 수 있음 — **실제 재시도 정당성·주장 축소는 Phase 44 번들**을 본다.
- **본 질적 결론**: **광역 기판 없이** 한정 수리만으로는 **falsifier filing 상태가 코호트 전체에서 바뀌지 않았고**, sector는 **관측 그레인이 달라졌을 뿐** usable sector 라벨로 이어지지는 않음. Phase 44는 이를 **material falsifier 개선이 아님**으로 분류하고 **주장 축소·프록시 한계 수용** 경로를 권한다.

---

# HANDOFF — Phase 44 (Claim narrowing + audit truthfulness)

## 요약

- **목적**: Phase 43 결과를 **과대 낙관 해석하지 않도록** — (1) 입력 번들 라벨과 런타임 스냅샷을 **출처 분리**하고, (2) `no_row → blank-field` **단독**은 material 개선이 **아님**, (3) **머신 리더블 claim narrowing**, (4) bounded retry는 **새로 명명한 소스/경로** + material 신호가 있을 때만 레지스트리상 허용, (5) **Phase 45** 권고를 확정한다. **광역 public-core 재개 비목표.**
- **Phase 43이 material 로 치지 않는 이유 (실측 코호트)**: `exact_public_ts_available`·`sector_available` **증가 없음**, 게이트·판별 롤업 시그니처 **동일**, filing 스코어카드 버킷 **동일** — sector 버킷만 no_row→blank로 **진단 정밀화**.
- **Provenance 원칙**: 행마다 `input_bundle_before`(Phase 42 코호트) vs `runtime_snapshot_before_repair` vs `runtime_snapshot_after_repair`(수치·메트릭 기반 추론) — 혼합 컬럼 금지. MD: `phase44_provenance_audit.md`.
- **Claim narrowing**: 패밀리별 `family_claim_limits`·코호트 `cohort_claim_limits`·`bounded_retry_eligibility` — 실측 번들 기준 코호트 상태 **`narrowed`**, filing/sector retry **비활성**(신규 경로 미등록).
- **Bounded retry**: `retry_eligibility` — `declared_new_filing_source` / `declared_new_sector_source` 가 Phase 43에서 이미 쓴 문자열과 **다를 때만** material과 함께 `*_retry_eligible` true 가능.
- **Phase 44 번들 내 `phase45` 블록 (truthfulness 레이어)**: **`narrow_claims_document_proxy_limits_operator_closeout_v1`** — 광역 기판 재개 없음. **단일 운영 클로즈아웃 패키지**는 Phase 45 번들/리뷰를 본다.
- **코드**: `src/phase44/` — `provenance_audit`, `audit_render`, `recommendation_truth`, `claim_narrowing`, `retry_eligibility`, `phase45_recommend`, `orchestrator`, `review`.
- **CLI**: `run-phase44-claim-narrowing-truthfulness` (`--phase43-bundle-in`, `--phase42-supabase-bundle-in`, `--declared-new-filing-source`, `--declared-new-sector-source`, `--audit-out`, `--explanation-out`, `--bundle-out`, `--out-md`) · `write-phase44-claim-narrowing-truthfulness-review --bundle-in …`
- **산출물**: `phase44_claim_narrowing_truthfulness_bundle.json`, `phase44_claim_narrowing_truthfulness_review.md`, `phase44_provenance_audit.md`, `phase44_explanation_surface_v7.md`
- **테스트**: `pytest src/tests/test_phase44_claim_narrowing_truthfulness.py -q`
- **증거·패치**: **`docs/phase44_evidence.md`**, **`docs/phase44_patch_report.md`**

## Phase 44 운영 클로즈아웃 (저장소 내 생성)

- **근거 입력**: `docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json`, `docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json`
- **산출**: 위 네 파일(리포지토리에 기록됨) — `phase44_truthfulness_assessment.material_falsifier_improvement: false`, `optimistic_sector_relabel_only: true`, `phase45.phase45_recommendation` = `narrow_claims_document_proxy_limits_operator_closeout_v1`
- **기록본 `generated_utc` (예)**: `2026-04-12T06:44:44.839337+00:00` — 재실행 시 번들의 `generated_utc`를 본다

---

# HANDOFF — Phase 45 (Canonical closeout + reopen protocol)

## 요약

- **목적**: Phase 44를 **현재 코호트에 대한 단일 권위 해석**으로 고정하고, Phase 43 번들에 남은 **낙관적 레거시 권고 문자열을 현재 가이드에서 배제**하며, **한 개의 canonical closeout 패키지**와 **전향적(명명 소스) 재진입 규칙**을 게시한다. **신규 기판·DB 캠페인·광역 수리 없음.**
- **권위 우선순위**: `authoritative_resolution.authoritative_phase` = **`phase44_claim_narrowing_truthfulness`** — `phase43.phase44.phase44_recommendation` 등은 `superseded_recommendations` 로 **감사용 보존**만.
- **Phase 43 레거시 `continue_bounded…` 가 superseded 되는 이유**: Phase 43 중첩 필드는 행/스코어카드 델타 휴리스틱 기반; Phase 44는 provenance·truthfulness로 **동일 코호트에 대해 보수적 종결**을 정의함.
- **Canonical closeout 상태**: `current_closeout_status.current_closeout_status` = **`closed_pending_new_evidence`** — 지원되지 않는 해석은 `canonical_closeout.explicit_unsupported_interpretations` 에 명시.
- **재진입 조건**: `future_reopen_protocol` — **구체적 명명 filing/sector 경로**, Phase 43 경로와의 **실질 차이 서술**, **8행·상한 유지**, **원샷 bounded retest**; **광역 public-core·묵시적 재개 금지** 축은 `forbidden_reopen_axes`.
- **관찰된 material 개선 vs 명명 소스 등록**: `future_reopen_protocol.distinction` — 회고적 material 판정(Phase 44)과 전향적 재진입 조건을 **분리**.
- **Phase 45 번들 내 `phase46` 권고 (기본)**: **`hold_closeout_until_named_new_source_or_new_evidence_v1`** — 무분별 재시도 권고 없음. `--operator-registered-new-named-source` 시에만 **`register_new_source_then_authorize_one_bounded_reopen_v1`** 노출. **파운더 UI 표면**은 별도 **Phase 46** `run-phase46-founder-decision-cockpit` 산출물을 본다.
- **코드**: `src/phase45/` — `authoritative_resolver`, `closeout_package`, `reopen_protocol`, `phase46_recommend`, `orchestrator`, `review`.
- **CLI**: `run-phase45-operator-closeout-and-reopen-protocol` (`--phase44-bundle-in`, `--phase43-bundle-in`, `--operator-registered-new-named-source`, `--bundle-out`, `--out-md`) · `write-phase45-operator-closeout-and-reopen-protocol-review --bundle-in …`
- **산출물**: `phase45_canonical_closeout_bundle.json`, `phase45_canonical_closeout_review.md`
- **테스트**: `pytest src/tests/test_phase45_operator_closeout_and_reopen_protocol.py -q`
- **증거·패치**: **`docs/phase45_evidence.md`**, **`docs/phase45_patch_report.md`**

## Phase 45 운영 클로즈아웃 (저장소 내 생성)

- **입력**: `phase44_claim_narrowing_truthfulness_bundle.json`, `phase43_targeted_substrate_backfill_bundle.json`
- **산출**: `phase45_canonical_closeout_bundle.json`, `phase45_canonical_closeout_review.md` — 리뷰 상단에 Phase 44 권위·Phase 43 레거시 비권위 문장 명시
- **기록본 `generated_utc` (예)**: `2026-04-12T19:18:33.685667+00:00` — 재실행 시 번들의 `generated_utc`를 본다

---

# HANDOFF — Phase 46 (Founder-facing decision cockpit)

## 요약

- **목적**: Phase 45 권위 클로즈아웃·Phase 44 truthfulness를 **원시 JSON/MD만 뒤지지 않고** 한 번에 읽을 **파운더 대면 계층**(결정·메시지·정보·연구·추적)으로 올린다. **첫 번째 제품 표면 패치**이며, **기판·DB·광역 수리 없음.**
- **대표 에이전트**: 결정론적 템플릿 조립만 — **권위 번들에서만** 피치 생성; Phase 43 낙관 레거시 권고 문자열은 피치에 **주입하지 않음**(테스트로 검증).
- **Drill-down**: `decision`, `message`, `information`, `research`, `provenance`, `closeout` — 번들 `drilldown_examples`에 샘플.
- **Trace**: `data/product_surface/alert_ledger_v1.json`, `data/product_surface/decision_trace_ledger_v1.json` — 알림·운영자/파운더 결정 기록(파일 기반 v1).
- **UI 준비**: 번들 `ui_surface_contract` — 자산 리스트/디테일 카드·피치 패널·드릴다운·피드 스키마 명시.
- **코드**: `src/phase46/` — `read_model`, `cockpit_state`, `representative_agent`, `drilldown`, `alert_ledger`, `decision_trace_ledger`, `ui_contract`, `phase47_recommend`, `orchestrator`, `review`.
- **CLI**: `run-phase46-founder-decision-cockpit` (`--phase45-bundle-in`, `--phase44-bundle-in`, `--bundle-out`, `--out-md`, `--pitch-out`) · `write-phase46-founder-decision-cockpit-review --bundle-in …`
- **산출물**: `phase46_founder_decision_cockpit_bundle.json`, `phase46_founder_decision_cockpit_review.md`, `phase46_founder_pitch_surface.md`
- **테스트**: `pytest src/tests/test_phase46_founder_decision_cockpit.py -q`
- **증거·패치**: **`docs/phase46_evidence.md`**, **`docs/phase46_patch_report.md`**

## Phase 46 운영 클로즈아웃 (저장소 내 생성)

- **입력**: `phase45_canonical_closeout_bundle.json`, `phase44_claim_narrowing_truthfulness_bundle.json`
- **산출**: 위 세 파일 + 레저 JSON (초기 빈 배열)
- **기록본 `generated_utc`**: `2026-04-12T20:40:43.768261+00:00` — 재실행 시 항상 번들·리뷰 상단 값을 본다

### 이 레포에서 Phase 46 **엔진**만 쓸 때 추가 필수 작업

- **없음** (Phase 45·44 입력이 그대로면 번들·테스트 관점 추가 작업 불필요).

### 선택 / 제품 측

- 브라우저 표면이 필요하면 **Phase 47** `app.py` + `run-phase47-founder-cockpit-runtime`.
- 입력 번들이 바뀌면 `run-phase46-founder-decision-cockpit` 재실행 후 evidence·본 절 타임스탬프 갱신.
- Git 커밋·PR·배포는 팀 프로세스.

---

# HANDOFF — Phase 47 (Founder cockpit browser runtime)

## 요약

- **목적**: Phase 46 산출물을 **실제 브라우저 런타임**으로 제공한다. **stdlib HTTP + 얇은 HTML/JS**; DB 불필요. **기판·수리·연구 패밀리 확장 없음.**
- **입력**: `phase46_founder_decision_cockpit_bundle.json` (+ 번들이 가리키는 레저 JSON). 다른 머신에서는 번들 내 절대경로가 깨질 수 있으므로 **`PHASE47_PHASE46_BUNDLE`** 및 레저를 로컬 경로로 맞추거나 Phase 46을 재실행한다.
- **화면 (Phase 47d 이후)**: **홈 피드 우선** — 상단 내비 **Home · Watchlist · Research · Replay · Journal · Ask AI · Advanced**. 기본 랜딩은 **Home** 에서 **Today / Watchlist / Research in progress / Alerts(미리보기) / Decision journal(미리보기) / Ask AI brief / Replay preview(시그니처 티저) / Portfolio 스텁** 카드 그리드(요약만, 기본 블록에 원시 JSON 없음). **Research** 패널에 예전 `This object` 탭(**Brief · Why now · … · Advanced**) — 클로즈드 리서치 픽스처·아카이브 맥락은 여기서 다루고 **Home 히어로로 올리지 않음**. **Journal** 은 결정 카드 + 기록 폼(원시 JSON 배열 비주력). **전체 알림 필터·ack/resolve 등**은 **Advanced** 로 이동; Home 은 짧은 미리보기 + Advanced 링크. **Ask AI** 상단에 **copilot brief(한 줄)** + 워크오더 계약 숏컷(“What matters now?” 등, “Open Replay for this item” 은 Replay 패널로 이동). **Replay preview** 카드는 마지막 결정(있으면)·타임축 안내·“Open full Replay” 로 시그니처 노출. Replay 서브모드는 기존과 동일(**Replay** / **Counterfactual Lab**).
- **API**: `GET /api/home/feed` — Home 블록용 조합 페이로드. `GET /api/overview` 의 `user_first.navigation.primary_navigation` 은 Phase 47d 셸과 동일. 나머지: `GET /api/user-first/section/…`, **Replay** `GET /api/replay/*`, **런타임** `GET /api/runtime/health`, `POST /api/runtime/external-ingest` (32KB 상한), **`POST /api/runtime/external-ingest/authenticated`** (Phase 52: `X-Source-Id` + `X-Webhook-Secret`). 구현: **`home_feed.py`**, **`ui_copy.py`**, **`traceability_replay.py`**, **`phase51_runtime`**, **`phase52_runtime`**.
- **거버넌스 대화 지원 의도**: `decision_summary`, `information_layer`, `research_layer`, `why_closed`, `provenance`, `what_changed`, `what_unproven`, `message_layer`, `closeout_layer` (**`what could change` 문구도 closeout_layer**); 범위 밖은 `outside_governed_cockpit_scope`.
- **레저 쓰기**: `alert_ledger_v1.json`(상태 갱신), `decision_trace_ledger_v1.json`(hold/watch/defer/reopen_request/buy/sell/dismiss_alert).
- **알림**: `notification_hooks` 인메모리 이벤트 + UI 폴링(`/api/notifications`). Phase 47 메타 번들의 `phase48` 권고 문자열(`external_notification_connectors…`)은 **구현 전 스텁**; 외부 커넥터·감사 로그는 **별도 스프린트**(Phase 49는 **선행 연구 다중 사이클·메트릭**에 해당)에서 검토.
- **리프레시**: `POST /api/reload`, UI **Reload bundle**; `GET /api/meta` 의 `bundle_stale`.
- **코드**: `src/phase47_runtime/` — `app`, `routes`, `runtime_state`, `governed_conversation`, `notification_hooks`, `orchestrator`, `review`, `phase48_recommend`, **`ui_copy`**, **`home_feed`**, **`phase47b_orchestrator`**, **`phase47b_review`**, **`traceability_replay`**, **`phase47c_orchestrator`**, **`phase47c_review`**, **`phase47d_orchestrator`**, **`phase47d_review`**, `static/`.
- **CLI**: `run-phase47-founder-cockpit-runtime` — 메타 번들·리뷰 MD. **서버**: `python3 src/phase47_runtime/app.py`.
- **CLI (Phase 47b, IA 계약 번들)**: `run-phase47b-user-first-ux` — `docs/DESIGN.md` 경로·`phase47b_user_first_ux_bundle.json` / `phase47b_user_first_ux_review.md`. 테스트: `pytest src/tests/test_phase47b_user_first_ux.py -q`.
- **CLI (Phase 47c, 추적성·리플레이 계약)**: `run-phase47c-traceability-replay` — 기본 `--design-source` 누락 시 `docs/DESIGN_V3_MINIMAL_AND_STRONG.md` 등 3종; 산출 `phase47c_traceability_replay_bundle.json` / `phase47c_traceability_replay_review.md`. 플롯 문법 메모: **`docs/operator_closeout/phase47c_plot_grammar_notes.md`**. 테스트: `pytest src/tests/test_phase47c_traceability_replay.py -q`.
- **CLI (Phase 47d, thick-slice UX 셸 리셋)**: `run-phase47d-thick-slice-home-feed` — 기본 `--design-source` `docs/DESIGN_V3_MINIMAL_AND_STRONG.md`; 권위 산출 **`docs/operator_closeout/phase47d_thick_slice_ux_shell_bundle.json`**, **`phase47d_thick_slice_ux_shell_review.md`** (기본 실행 시 이전 파일명 `phase47d_thick_slice_home_feed_*` 에도 동기화). 보조: **`docs/operator_closeout/phase47d_shell_before_after.md`**, 상세 맵 **`phase47d_shell_map_before_after.md`**. 테스트: `pytest src/tests/test_phase47d_thick_slice_ux_shell.py -q`.
- **배포**: **`docs/operator_closeout/phase47_runtime_deploy_notes.md`** (내부 HTTPS 리버스 프록시 + VPN 권장).
- **테스트**: `pytest src/tests/test_phase47_founder_cockpit_runtime.py src/tests/test_phase47b_user_first_ux.py src/tests/test_phase47c_traceability_replay.py src/tests/test_phase47d_thick_slice_ux_shell.py -q`
- **증거·패치**: **`docs/phase47_evidence.md`**, **`docs/phase47_patch_report.md`**

## Phase 47b (user-first IA — DESIGN.md 정렬)

- **헌장**: **`docs/DESIGN.md`** (저장소에 전문 포함; 제품 표면 문구·탭·객체 구분의 권위).
- **구분**: 픽스처/코호트는 **`closed_research_fixture`** 배지 등으로 **투자 기회 카드와 혼동되지 않게** 표시. 상태 코드는 `ui_copy.STATUS_TRANSLATIONS` 로 기본 UI에서 완곡어로 표시; **원문·드릴다운 JSON은 Advanced** 에만 기본 노출.
## Phase 47c (traceability & replay — DESIGN_V3 정렬)

- **Replay vs Counterfactual Lab**: 타임라인 카피는 **당시 알려진 사실** 범위; 가설·미래 암시 구문은 삭제/치환. 가상 분기는 **별도 모드**·`counterfactual_scaffold`(축 미표시). **결정 품질**(당시 과정)과 **결과 품질**(사후) 문구 분리.
- **포트폴리오**: API `portfolio_traceability` **스텝** — 포지션 단위 계보는 후속.

## Phase 47d (thick-slice UX shell reset — Home & navigation)

- **권위 번들·리뷰**: `phase47d_thick_slice_ux_shell_bundle.json`, `phase47d_thick_slice_ux_shell_review.md` — 필드에 `replay_preview_contract`, `home_blocks`(Replay preview 포함), `phase` = `phase47d_thick_slice_ux_shell_reset`.
- **번들 `phase47e` 권고 (구현 후 다음 슬라이스)**: `live_watchlist_multi_asset_and_portfolio_attribution_v1` — 다중 자산·심볼 훅(여전히 거버넌스), 포트폴리오 카드 데이터; **기판 수리 비목표**.
- **Ask AI brief 블록**: 짧은 “now” 한 줄 + 계약된 숏컷(What matters now?, What changed?, …, Open Replay for this item); 거대한 채팅창을 중앙 히어로로 두지 않음.
- **Replay preview (Home)**: API `replay_preview` + UI 카드 — 마지막 결정 티저 또는 저널 비었을 때 Replay 역할 설명, **Open full Replay** 로 이동.
- **클로즈드 픽스처 위치**: Home **Today** 에서 아카이브 맥락을 설명하고 **Watchlist / Research / Alerts** 로 안내; 상세 카드·드릴다운은 **Research** 탭 및 **Advanced**.

## Phase 46 번들 내 레거시 Phase 47 권고 문자열

- `phase47.phase47_recommendation` = `wire_alert_and_decision_ledgers_to_ui_and_notification_hooks_v1` — **본 Phase 47 패치가 구현 목표였던 작업**을 가리킨다. 런타임 메타 번들의 `phase` 는 **`phase47_founder_cockpit_runtime`** 로 구분한다.

---

# HANDOFF — Phase 48 (Proactive research runtime — single cycle)

## 상태

- **클로즈 완료** — 수락 요약·증거 링크: **`docs/operator_closeout/phase48_closeout.md`**. 후속 스케줄·메트릭: **Phase 49** (`HANDOFF.md` 동명 섹션).

## 요약

- **목적**: 정적 번들만 있던 연구층에 **예산·정지 규칙이 있는 첫 선행 루프**를 얹는다. **한 번의 CLI = 한 사이클**; 무한 에이전트 루프 금지. **기판·DB 수리 없음.**
- **트리거 (결정론)**: Phase 46 `generated_utc` 변화(`changed_artifact_bundle`); 결정 레저의 `last_cycle_utc` 이후 `watch` / `reopen_request`; 클로즈아웃+노트 토큰 기반 `named_source_signal`; `data/research_runtime/manual_triggers_v1.json` 의 `pending`(`manual_watchlist`, 잡 생성 시 파일 비움).
- **잡 타입**: `evidence.refresh`, `hypothesis.check`, `debate.execute`, `premium.escalation_candidate`, `discovery.publish_candidate` (MVP에서 후자는 파이프라인으로 주로 생성).
- **경계 토론**: 역할 최대 5·턴 상한(`budget_policy.max_debate_turns`); 결과는 `supported` / `unsupported` / `unknown` / `premium_required` / `reopen_candidate` / `no_action` 중 하나. **LLM 없음** — 번들 요약 문장.
- **프리미엄**: `premium_escalation` 은 **후보만** 출력; 강제 구매·자동 과금 없음.
- **디스커버리**: `discovery_candidates_v1.json` — **추천 아님**(`not_a_recommendation`).
- **Cockpit 연동**: `cockpit_surface_outputs` 번들 필드; 토론 결과가 `reopen_candidate` 이고 `--skip-alerts` 미사용 시 `alert_ledger_v1.json` 에 한 건까지(사이클 상한).
- **예산**: `budget_policy` — `max_jobs_per_run`, `max_debate_turns`, `max_candidate_publishes_per_cycle`, `max_alerts_per_cycle` 등.
- **코드**: `src/phase48_runtime/` — `job_registry`, `trigger_engine`, `bounded_debate`, `premium_escalation`, `discovery_pipeline`, `budget_policy`, `orchestrator`, `review`, `phase49_recommend`.
- **CLI**: `run-phase48-proactive-research-runtime` (경로 오버라이드 인자는 `docs/phase48_patch_report.md` 참고).
- **테스트**: `pytest src/tests/test_phase48_proactive_research_runtime.py -q`
- **증거·패치**: **`docs/phase48_evidence.md`**, **`docs/phase48_patch_report.md`**

## Phase 49 (권고 → 구현됨)

- **`daemon_scheduler_multi_cycle_triggers_and_metrics_v1`** — **Phase 49** CLI로 구현·실측. cron/systemd 에서는 동 CLI를 주기 호출하면 된다. 상세: 아래 **HANDOFF — Phase 49**.

## Phase 50 (제어 평면·스모크 → 구현·클로즈)

- **제어 평면·리스·감사·비영 스모크** — **`HANDOFF — Phase 50`**, **`docs/phase50_evidence.md`**, **`docs/operator_closeout/phase50_closeout.md`**. Phase 48 트리거/오케스트레이터는 `budget_policy`·`manual_triggers_path`·수동 `suggested_job_type` 로 Phase 50과 연동.

---

# HANDOFF — Phase 49 (Daemon scheduler — multi-cycle triggers & metrics)

## 요약

- **목적**: Phase 48 단일 사이클을 **N회 연속** 실행하고 **트리거·잡·토론·후보·알림 append** 를 **집계**한다. **기판·DB 수리 없음.**
- **입력**: Phase 46 번들 경로(`--phase46-bundle-in`); Phase 48과 동일한 레저·레지스트리 경로 오버라이드 가능.
- **코드**: `src/phase49_runtime/` — `orchestrator`, `review`, `phase50_recommend` 등.
- **CLI**: `run-phase49-daemon-scheduler-multi-cycle-triggers-and-metrics-v1` — `--cycles`(기본 2), `--sleep-seconds`, `--skip-alerts`, `--registry-path`, `--discovery-path`, `--decision-ledger-path`.
- **산출**: `docs/operator_closeout/phase49_daemon_scheduler_multi_cycle_bundle.json`, `phase49_daemon_scheduler_multi_cycle_review.md`.
- **테스트**: `pytest src/tests/test_phase49_daemon_scheduler_multi_cycle.py -q`

## Phase 50 (구현됨)

- **제어 평면·스모크**: 아래 **HANDOFF — Phase 50** 참고. 번들 `phase50_registry_controls_and_operator_timing_*`, `phase50_positive_path_smoke_*`.

---

# HANDOFF — Phase 50 (Runtime control plane & positive-path smoke)

## 요약

- **목적**: 선행 런타임(Phase 48/49)에 **운영 제어 평면**(케이던스·트리거 on/off·윈도 캡)·**사이클 리스**(중복 실행 방지)·**append-only 감사 로그**를 두고, **권위 있는 비영(non-empty) 스모크** 번들로 루프가 실제 산출을 낸다는 것을 증명한다. **기판·DB 캠페인·무제한 데몬 없음.**
- **제어 레지스트리**: `data/research_runtime/runtime_control_plane_v1.json` — `enabled`, `maintenance_mode`, `max_concurrent_cycles`, `default_cycle_profile`, `allowed_trigger_types` / `disabled_trigger_types`, `max_cycles_per_window`, `window_seconds`, `last_operator_override_at`, `operator_note`, `positive_path_smoke_enabled`.
- **리스**: `data/research_runtime/cycle_lease_v1.json` — 단일 활성 사이클; 만료 시 재획득 가능; 획득 실패 시 사이클 스킵 + 감사.
- **타이밍 프로파일**: `manual_debug`, `low_cost_polling`, `alert_sensitive` — `should_run_cycle_now` 가 실행 여부·이유를 반환.
- **감사 로그**: `data/research_runtime/runtime_audit_log_v1.json` — 타임스탬프, `cycle_id`, 리스 여부, 적용 제어, 트리거/잡 수, 스킵 여부 등.
- **트리거 병합**: `trigger_controls.effective_budget_policy` 가 제어 평면과 예산 정책을 결합. 수동 트리거 항목에 **`suggested_job_type`** 이 있으면 Phase 48이 허용된 잡 타입으로 실행(스모크는 `debate.execute`).
- **Positive-path smoke**: `manual_watchlist` 시드 + **격리** 레지스트리/디스커버리(`phase50_positive_path_smoke_*_v1.json`); Phase 46 `generated_utc` 와 레지스트리 메타를 맞춰 **번들 변경 트리거만** 뜨지 않게 함. 산출: `phase50_positive_path_smoke_bundle.json` — `n_triggers≥1`, 잡 생성/실행≥1, 토론·프리미엄·디스커버리·cockpit 중 최소 하나 비어 있지 않음.
- **코드**: `src/phase50_runtime/` — `control_plane`, `cycle_lease`, `timing_policy`, `runtime_audit_log`, `trigger_controls`, `orchestrator`, `review`, `phase51_recommend`.
- **CLI**: `run-phase50-registry-controls-and-operator-timing` (Phase 49 번들 입력), `run-phase50-positive-path-smoke` (Phase 46 입력; `--strict-timing` 시 타이밍 차단 존중, `--no-skip-alerts` 시 알림 append 가능).
- **테스트**: `pytest src/tests/test_phase50_registry_controls_and_operator_timing.py -q`

## 운영 실측 (저장소 권위 번들, 참고)

- `phase50_registry_controls_and_operator_timing_bundle.json` — `generated_utc` `2026-04-13T05:50:40.090764+00:00`, `ok: true`; 감사 요약·제어 평면 스냅샷 포함(재실행 시 갱신).
- `phase50_positive_path_smoke_bundle.json` — `generated_utc` `2026-04-13T05:50:46.368148+00:00`, `ok: true`, `smoke_metrics_ok: true`; 시드 `manual_watchlist` → `debate.execute`.

## Phase 51 (구현됨)

- **외부 트리거·헬스 표면**: 아래 **HANDOFF — Phase 51** 참고. 번들 `phase51_external_trigger_ingest_*`, `phase51_runtime_health_surface_review.md`.

---

# HANDOFF — Phase 51 (External trigger ingest & runtime health surface)

## 요약

- **목적**: 운영자 `manual_triggers_v1` 시드만이 아니라 **거버넌스된 외부 이벤트**가 적재·정규화·중복 제거·감사된 뒤 Phase 48 사이클에 **`supplemental_triggers`** 로 합류한다. 파운더 표면에 **런타임 헬스**(활성/점검, 최근 스킵, 외부 적재 카운트)를 **사람이 읽는 카드**로 노출한다. **기판 수리·무제한 웹훅·자율 매매 없음.**
- **적재 레지스트리**: `data/research_runtime/external_trigger_ingest_v1.json` — `event_id`, `received_at`, `source_type`/`source_id`, `raw_event_type`, `normalized_trigger_type`, `asset_scope`, `status`, `dedupe_key`, `accepted_or_rejected_reason`, `linked_cycle_id` 등.
- **외부 감사 로그**: `data/research_runtime/external_trigger_audit_log_v1.json` — 수신·정규화·거절·중복·소비(`consumed`) 기록(사이클 감사와 분리).
- **정규화**: `phase51_runtime.trigger_normalizer` — 허용 `raw_event_type` → `named_source_signal` / `operator_research_signal` / `manual_watchlist` / `closeout_reopen_candidate` / `changed_artifact_bundle` 만; 미지면 거절 문자열. `dedupe_key`는 결정론적 SHA 기반.
- **제어 평면**: 적재 시 `effective_budget_policy` 로 **허용되지 않은 트리거 타입**은 거절; 선택적으로 **maintenance_mode** 에서 적재 자체를 억제(`maintenance_blocks_accept`).
- **Phase 48 훅**: `evaluate_triggers(..., supplemental_triggers=…)` — 예산·중복 키는 기존과 동일.
- **헬스 요약**: `runtime_health_summary_v1.json` — 제어 평면 발췌, 감사 꼬리, 외부 적재 카운트, 최근 스킵 이유, `health_status` 분류.
- **Cockpit API**: `GET /api/runtime/health`, `POST /api/runtime/external-ingest`, **`POST /api/runtime/external-ingest/authenticated`** (Phase 52); `GET /api/overview` 에 `runtime_health` 포함(소스·큐 요약은 레지스트리에 소스가 있을 때 `external_source_activity_v52` 병합). Brief 패널 하단 **Research runtime (Phase 51)**.
- **어댑터 (MVP)**: 파일 드롭 JSON 배열·단일 객체, CLI `submit-external-trigger-json`, 로컬 HTTP POST(본문 상한).
- **권위 스모크**: `run-phase51-external-positive-path-smoke` — 격리 레지스트리/적재/감사 + `phase51_external_drop_smoke_v1.json` 생성 후 비영 사이클; `smoke_metrics_ok` 필수.
- **코드**: `src/phase51_runtime/` — `external_trigger_ingest`, `trigger_normalizer`, `external_ingest_adapters`, `external_trigger_audit`, `runtime_health`, `cockpit_health_surface`, `orchestrator`, `review`, `phase52_recommend`.
- **Phase 52 (종료)**: `src/phase52_runtime/` — 소스 레지스트리·비밀 해시·예산·라우팅·선택 큐·`phase53_recommend`(번들에 Phase 53 토큰). 증거·클로즈 **`docs/phase52_evidence.md`**, **`docs/operator_closeout/phase52_closeout.md`**. **Phase 53 권고**: 번들 `phase53` — `signed_payload_hmac_source_rotation_and_dead_letter_replay_v1`.

## CLI

| 명령 | 역할 |
|------|------|
| `run-phase51-external-positive-path-smoke` | 외부 파일 드롭 → 적재 → supplemental → Phase 48; 번들·리뷰 MD 기본 출력; `--persist-runtime-health` |
| `submit-external-trigger-json --json-file …` | 단건 외부 이벤트 적재 + 감사 |
| `refresh-runtime-health-summary` | `runtime_health_summary_v1.json` 재생성 |

## 테스트

`pytest src/tests/test_phase51_external_trigger_ingest_and_runtime_health.py -q` (Phase 50·49 회귀는 워크오더대로 유지).

## 운영 실측 (저장소 권위 번들, 2026-04-13)

- `phase51_external_trigger_ingest_bundle.json` — `generated_utc` **`2026-04-13T06:38:15.299044+00:00`**, `ok: true`, `smoke_metrics_ok: true`; 외부 이벤트 1건 승인·소비, 사이클 ID `f36b11ba-f3e9-4d6e-902c-f24fcbe396c1`, 트리거 `manual_watchlist`·잡 `debate.execute`, `runtime_health_summary.health_status` **`healthy`** (재실행 시 갱신).
- 클로즈·체크리스트: **`docs/operator_closeout/phase51_closeout.md`**, **`docs/phase51_evidence.md`**, **`docs/phase51_patch_report.md`**.

---

# HANDOFF — Phase 28 (Provider metadata & factor panel materialization)

## 현재 제품 위치

- **Phase 28**: Yahoo chart로 **`fetch_market_metadata`** 가 `avg_daily_volume`·`as_of_date`·`exchange` 를 채운다. **`run_market_metadata_hydration_for_symbols` / `run_market_metadata_refresh`** 는 `provider_rows_returned`, `rows_upserted`, `rows_already_current`, `rows_missing_after_requery` 를 반환하며, 프로바이더가 **0행**이면 **`status=blocked`**, `blocked_reason=provider_returned_zero_metadata_rows` (stub은 메타 행을 주므로 차단 아님).
- **팩터 물질화**: `report-factor-panel-materialization-gaps` → 스냅샷 없음 / 스냅샷만 있고 factor 없음 / factor 있는데 validation 누락 등으로 세분. `run-factor-panel-materialization-repair` 는 CIK당 상한으로 `run_factor_panels_for_cik` + `run_validation_panel_build_from_rows` 호출.
- **오케스트레이션**: `run-phase28-provider-metadata-and-panel-repair` (`--out-md`, `--bundle-out`, `--max-factor-cik-repairs`, `--max-validation-cik-repairs`). MD만 번들에서: `write-phase28-provider-metadata-review --bundle-in …`.
- **코드**: `src/phase28/`, `src/market/providers/yahoo_chart_provider.py`, `src/market/price_ingest.py`.
- **테스트**: `pytest src/tests/test_phase28_provider_metadata_and_factor_panel.py -q`
- **패치·증거**: `docs/phase28_patch_report.md`, `docs/phase28_evidence.md` (리뷰에 넘길 문건 목록은 evidence 하단 표 참고)

---

# HANDOFF — Phase 27 (Targeted backfill: registry, metadata, maturity, PIT)

## Phase 27.5 hotfix (2026, 계측·wiring·수리 범위)

1. **`fetch_cik_map_for_tickers`**: `out[t]=...` 대입이 `for row in r.data` **루프 안**에 있도록 수정. 이전에는 청크당 마지막 행만 반영되어 `n_issuer_resolved_cik` 등이 비정상적으로 작아질 수 있었음.
2. **`rerun_readiness`**: `build_revalidation_trigger`는 **최상위**에 `recommend_rerun_phase15`/`16`을 둠. 번들은 `_extract_rerun_readiness`로 채우며, 비정상 시 `wiring_warnings`에 명시(침묵 실패 금지).
3. **Phase 28 집계**: `registry_gap_rollup` — `issuer_master_missing_for_resolved_cik` 등 전 버킷 합산 `registry_blocker_symbol_total`; 자동 수리 후보 vs 상류/파이프라인 지연 분리.
4. **`run-validation-registry-repair`**: `symbol_to_cik_registry_miss`(멤버십 CIK로 registry upsert), `issuer_master_missing…`(멤버십·registry CIK 정합 시 `issuer_master` upsert), `factor_panel_missing…`(재검증 후 blocked/deferred), norm mismatch·validation omission은 **blocked** 명시. `blocked_actions` / `deferred_actions` 항상 반환.
5. **시맨틱**: `write-phase27-targeted-backfill-review` = **review-only**. 수리+리뷰 한 번에: **`run-targeted-backfill-repair-and-review`** (`--repair-forward` 선택, `--bundle-out` 선택).
6. **핫픽스 후**에만 Phase 28 분기를 신뢰 — 번들·리뷰의 `n_issuer_resolved_cik`·rerun bool·`phase28`를 재확인.

### Phase 27.5 클로즈아웃 (재생성 번들, 2026-04-07 UTC)

- **패치 보고**: `docs/phase27_5_hotfix_patch_report.md`
- **실측 증거**: `docs/phase27_5_hotfix_evidence.md`
- **핵심 숫자**: `n_issuer_resolved_cik=313`, `n_issuer_with_factor_panel=312`, `wiring_warnings=[]`, rerun15/16 **bool false**, `registry_blocker_symbol_total=191`, **`phase28_recommendation=continue_targeted_backfill`**
- **다음 권고**: 제네릭 스프린트가 아니라 **타깃 백필 실행**(`run-validation-registry-repair` / `run-market-metadata-hydration-repair` 또는 `run-targeted-backfill-repair-and-review`) 후 동일 리뷰로 델타 확인. Rerun 15/16은 thin 게이트로 아직 닫힘.

## 현재 제품 위치

- **Phase 27 (본 패치)**: Phase 26에서 확정한 블로커를 **좁은 진단·수리**로 분해한다. **제네릭 기판 스프린트·임계 완화·Phase 15/16 강제·프리미엄 오픈·프로덕션 스코어 변경 없음**.
- **CLI** (`--universe`, `--panel-limit`, `--program-id`, `--price-lookahead-days` 등):  
  - `report-validation-registry-gaps` / `run-validation-registry-repair` / `export-validation-registry-gap-symbols`  
  - `report-market-metadata-gap-drivers` / `run-market-metadata-hydration-repair` / `export-market-metadata-gap-rows`  
  - `report-forward-gap-maturity` / `export-forward-gap-maturity-buckets` (`--eval-date` 선택)  
  - `report-state-change-pit-gaps` / `export-state-change-pit-gap-rows` / `run-state-change-history-backfill-repair` (`--history-backfill-days`, `--state-change-limit`)  
  - `write-phase27-targeted-backfill-review` → **review-only** → `docs/operator_closeout/phase27_targeted_backfill_review.md` (선택 `--bundle-out` JSON)  
  - `run-targeted-backfill-repair-and-review` → registry+metadata 수리 후 동일 리뷰·번들 (`--repair-forward`, `--out`, `--bundle-out`)  
  - **Phase 28** (동일 `--universe` 등): `report-factor-panel-materialization-gaps` / `run-factor-panel-materialization-repair` / `run-phase28-provider-metadata-and-panel-repair` / `write-phase28-provider-metadata-review`  
  - **Phase 29**: `report-stale-validation-metadata-flags` / `run-validation-refresh-after-metadata-hydration` / `export-stale-validation-metadata-rows` / `report-quarter-snapshot-backfill-gaps` / `run-quarter-snapshot-backfill-repair` / `export-quarter-snapshot-backfill-targets` / `run-phase29-validation-refresh-and-snapshot-backfill` / `write-phase29-validation-refresh-review`
  - **Phase 30**: `report-filing-index-gap-targets` / `run-filing-index-backfill-repair` / `export-filing-index-gap-targets` / `report-silver-facts-materialization-gaps` / `run-silver-facts-materialization-repair` / `report-empty-cik-gaps` / `run-phase30-validation-substrate-repair` / `write-phase30-validation-substrate-review`
  - **Phase 31**: `report-raw-facts-gap-targets` / `export-raw-facts-gap-targets` / `run-raw-facts-backfill-repair` / `report-raw-present-no-silver-targets` / `run-gis-like-silver-seam-repair` / `run-deterministic-empty-cik-issuer-repair` / `run-phase31-raw-facts-bridge-repair` / `write-phase31-raw-facts-bridge-review`
- **코드**: `src/targeted_backfill/`, `src/phase28/`, `src/phase29/`, `db.records`(레지스트리·메타·멤버십 배치 조회), `market.price_ingest.run_market_metadata_hydration_for_symbols`, `market.validation_panel_run`.
- **실측 수치**: 저장소만으로 고정 숫자 없음 — 운영자가 위 report/export 및 리뷰 작성으로 **증거·수리 후 블로커 카운트**를 채운다.
- **Phase 28 권고(정확히 하나)**: 번들/stdout의 `phase28` — `rerun_phase15_16_now_open` \| `continue_targeted_backfill` \| `quality_policy_review_needed` \| `public_first_plateau_without_quality_unlock`.

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase27_targeted_backfill.py -q`
- `pytest src/tests/test_phase27_5_hotfix.py -q`

## 패치 보고·증거

- `docs/phase27_patch_report.md` (본패치 + 27.5 요약 절)
- `docs/phase27_evidence.md` — Phase 27 재현·선택 수리
- **27.5 hotfix**: `docs/phase27_5_hotfix_patch_report.md`, `docs/phase27_5_hotfix_evidence.md`
- 번들·리뷰: `docs/operator_closeout/phase27_targeted_backfill_review.md`, `phase27_targeted_backfill_bundle.json`

---

# HANDOFF — Phase 26 (Thin-input root cause: drivers, repair audit, exports)

## 현재 제품 위치

- **Phase 26 (본 패치)**: Phase 25가 **제로 델타**였던 환경에서, `thin_input_share=1.0`이 **사이클 품질 정책(Phase 13)** 축인지 **기판 제외 축**인지 분해하고, Phase 25 수리 경로의 **no-op 여부**를 감사한다. **거버넌스·프리미엄 자동 오픈·임계 자동 완화 없음**.
- **CLI** (`--universe`, `--panel-limit`, `--program-id latest`, `--quality-run-lookback`):  
  - `report-thin-input-drivers` — thin 사이클 드라이버 + **joined recipe** 행의 `panel_json` 플래그 분해  
  - `report-validation-repair-effectiveness` / `report-forward-backfill-effectiveness` / `report-state-change-repair-effectiveness`  
  - `export-unresolved-validation-symbols` / `export-unresolved-forward-return-rows` / `export-unresolved-state-change-joins` (`--out`, `--format json|csv`)  
  - `report-quality-threshold-sensitivity` — **검토 전용** 가상 임계 시나리오 (`no_automatic_threshold_mutation`)  
  - `write-thin-input-root-cause-review` → `docs/operator_closeout/thin_input_root_cause_review.md` (선택 `--bundle-out` JSON)  
  - `report-thin-input-root-cause-bundle` — 단일 JSON 번들
- **코드**: `src/thin_input_root_cause/`, `public_depth.diagnostics.compute_substrate_coverage(..., joined_panels_out=)`, `db.records.fetch_ingest_runs_by_run_types_recent` / `fetch_state_change_runs_for_universe_recent`.
- **1차 블로커 분류 (리뷰 번들)**: `data_absence` \| `join_logic` \| `quality_policy` \| `mixed` — joined 행이 전부 `panel_json` 깨끗하고 thin 사이클이 지속되면 **quality_policy** 쪽으로 기울어 분류.
- **광범위 기판 스프린트**: 검증·forward 효과 감사에서 `likely_no_op: true`가 동시에면 **또 다른 제네릭 스프린트는 비효율 가능성이 높다**고 리뷰 MD에 명시.
- **Phase 27 권고(정확히 하나)**: `targeted_data_backfill_next` \| `quality_policy_review_needed` \| `rerun_phase15_16_now_open` \| `public_first_plateau_without_quality_unlock` — 번들의 `phase27` 필드.

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase26_thin_input_root_cause.py -q`

## 패치 보고·증거

- `docs/phase26_patch_report.md`
- 실측 클로즈아웃 실행 기록·산출물 목록: `docs/phase26_evidence.md` (`docs/operator_closeout/thin_input_root_cause_review.md`, `phase26_root_cause_bundle.json`, 미해결 export 3종)

---

# HANDOFF — Phase 25 (Substrate closure: validation / forward / state-change join)

## 현재 제품 위치

- **Phase 25 (본 패치)**: Phase 24 증거에서 드러난 **기판 병목**(`thin_input_share`, `no_validation_panel_for_symbol`, `missing_excess_return_1q`, `no_state_change_join`)을 **진단·타깃 수리**한다. **거버넌스 레이어 추가 없음**, **프리미엄 디스커버리·라이브 통합 자동 오픈 없음**.
- **CLI (유니버스·`--panel-limit`·선택 `--program-id latest`)**  
  - `report-validation-panel-coverage-gaps` / `run-validation-panel-coverage-repair`  
  - `report-forward-return-gaps` / `run-forward-return-backfill`  
  - `report-state-change-join-gaps` / `run-state-change-join-repair`  
  - `report-substrate-closure-snapshot` — 메트릭+제외+`build_revalidation_trigger` 스냅샷 JSON  
  - `write-substrate-closure-review` — before/after JSON → `docs/operator_closeout/substrate_closure_review.md`  
  - `run-substrate-closure-sprint` — `--repair-validation` / `--repair-forward` / `--repair-state-change` 선택 + `--refresh-validation-after-forward` + 리뷰 MD·선택 `--out-stem` JSON
- **코드**: `src/substrate_closure/`, `src/market/validation_panel_run.py`(`run_validation_panel_build_from_rows`), `src/market/forward_returns_run.py`(`run_forward_returns_build_from_rows`).
- **실 DB before/after 숫자**: 이 저장소 패치만으로는 고정치가 없음 — 운영자가 스프린트 전후 `report-substrate-closure-snapshot` 또는 스프린트 JSON으로 **실측 델타**를 채운다.
- **Rerun 게이트(Phase 15/16)**: 스냅샷의 `recommend_rerun_phase15` / `recommend_rerun_phase16` 및 스프린트 종료 시 stdout `=== Rerun readiness (after sprint) ===` 로 확인. **열리지 않았다면** `joined_recipe_substrate_row_count`·`thin_input_share` 임계(`public_buildout.constants`)가 블로커.
- **프리미엄 리뷰**: **여전히 공개 우선 기본** — 자동 프리미엄 오픈 없음; `substrate_closure_review.md`에 Premium 섹션 명시.

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase25_substrate_closure.py -q`

## 패치 보고·증거

- `docs/phase25_patch_report.md`

---

# HANDOFF — Phase 24 (Public-first empirical layer)

## 현재 제품 위치

- **Phase 24 (본 패치)**: 반복 공개 우선 운영을 **집계·판독 가능한 경험층**으로 올린다. **`report-public-first-branch-census`**, **`export-public-first-branch-census-brief`**, **`export-public-first-plateau-review-brief`** / **`run-public-first-plateau-review`**, **`advance-public-first-cycle`**(교대 리듬 + 혼합 시 Phase 23 chooser 위임). 결론 타입: `public_first_still_improving` \| `mixed_or_insufficient_evidence` \| `premium_discovery_review_preparable`(리뷰 전용, **라이브·자동 프리미엄 오픈 없음**). 산출: `docs/operator_closeout/latest_public_first_review.md` 등.
- **포함/제외 위생**: 기본 **정책 버전 불일치 시리즈 제외**, **인프라 실패 런 제외(플래토와 동일)**, **동일 repair/depth 런 ID 중복 집계 제외**, **closed 시리즈는 옵션으로만**(`--include-closed-series`).
- **비협상 유지**: 프로덕션 스코어는 `public_repair_iteration` / `public_repair_campaign` 미참조(`state_change.runner` + `test_phase24_public_first`).

## Phase 24로 가능해진 것

1. 다중 호환 시리즈에 대한 **브랜치·신호·개선 분류 집계** + 제외 사유 목록
2. **플래토 리뷰 결론** 3종 (프리미엄은 *preparable* 만, 자동 오픈 없음)
3. **교대 코디네이터**: 개선 증거가 명확하면 마지막 멤버 기준 repair↔depth 교대, 아니면 Phase 23 chooser

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase24_public_first.py -q`
- 전체: `pytest src/tests -q` — **356 passed** (Phase 29 포함)

## 관측 분포·정책 자세 (2026-04-07, `sp500_current`, Phase 23 클로즈아웃 직후 맥락)

| 관측 | 해석 |
|------|------|
| 클로즈아웃 chooser | `advance_repair_series`, 에스컬레이션 `hold_and_repeat_public_repair`, 신호 `repeat_targeted_public_repair` |
| **프리미엄 디스커버리 리뷰** | **아직 preparable 아님** — 활성 에스컬레이션이 `open_targeted_premium_discovery` 가 아님(리뷰 “획득” 전) |
| **공개 우선 궤도** | **유지** — 수리 반복 쪽 가중이나 공개 스택·시리즈는 계속 운용 |
| **Plateau review 결론(코드 규칙)** | depth 분류 표본이 부족하거나 혼재 시 **`mixed_or_insufficient_evidence`**; 다회 `meaningful_progress`+`marginal_progress` 다수 시 **`public_first_still_improving`** — **실 DB에서** `export-public-first-plateau-review-brief` 로 확정 |

## 마이그레이션 (누적)

- **새 DDL 없음**(Phase 24는 집계·CLI·리뷰 문서).

## 패치 보고·증거

- `docs/phase24_patch_report.md`
- `docs/phase24_evidence.md`

---

# HANDOFF — Phase 23 (One-command post-patch closeout)

## 현재 제품 위치

- **Phase 23 (본 패치)**: 패치 후 클로즈아웃을 **`run-post-patch-closeout --universe U`** 한 번으로 수행한다. **정상 경로에서 운영자는 시리즈 UUID를 조회·복붙할 필요가 없다**(내부 ID는 `latest_closeout_summary.md`·JSON 산출물에 감사용으로 남음). **`report-required-migrations`**, **`verify-db-phase-state`**, **`export-public-depth-series-brief`** 의 무 UUID 운영 모드(`--program-id`+`--universe`, `--series-id` 생략), 결정적 **`choose_post_patch_next_action`**(verify_only / advance_repair / advance_depth / hold_plateau). **프리미엄 디스커버리 자동 오픈 없음** — 에스컬레이션 `open_targeted_premium_discovery` 는 **hold_for_plateau_review** 로만 처리.
- **비협상 유지**: 프로덕션 스코어는 `public_repair_iteration` / `public_repair_campaign` 미참조(`state_change.runner` + `test_phase23_operator_closeout`).

## Phase 23로 가능해진 것

1. **`run-post-patch-closeout`** — 마이그레이션 리포트(가능 시) → phase17–22 스모크 → 시리즈 자동 해석·오픈 슬롯 생성 → 전진·브리프·요약 MD
2. **`report-required-migrations`** / **`--write-bundle`** — 누락 파일명·순서·사유·선택적 SQL 번들
3. **`verify-db-phase-state`** — 단일 명령 스모크 체인
4. **프리셋** — `.operator_closeout_preset.json` 또는 `docs/operator_closeout_preset.example.json` 참고
5. **브리프 export 무 UUID** — `export-public-depth-series-brief` + latest + universe

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase23_operator_closeout.py -q`
- 전체: `pytest src/tests -q` — **356 passed** (Phase 29 포함) (Phase 24 포함; 외부 `edgar` DeprecationWarning만)

## 검증·운영 스냅샷 (2026-04-07, `sp500_current`, 원 커맨드 클로즈아웃)

| 항목 | 결과 |
|------|------|
| `run-post-patch-closeout --universe sp500_current` | 완료; 요약 `docs/operator_closeout/latest_closeout_summary.md` |
| `schema_migrations` API 프로브 | 미노출(`PGRST106`) — **스모크가 스키마 진실로 전부 통과** |
| phase17–22 스모크 | **통과** |
| 시리즈 해석 | `active_compatible_series` (UUID는 요약·JSON에만 감사 기록) |
| 자동 전진 | `advance_repair_series` **성공**; 브리프 `docs/operator_closeout/closeout_advance_repair.*`, `closeout_depth_series_brief.*` |
| 운영자 추가 **필수** 액션 | **없음** — 브리프 검토·다음 주기 판단은 선택 |
| 증거 상세 | `docs/phase23_evidence.md` |

**다음 담당자:** 다음 패치 후 동일 명령으로 재클로즈. 마이그레이션 이력을 API로 맞추고 싶다면 Supabase 대시보드에서 별도 확인(프로브 실패만으로는 스모크를 대체하지 않음).

## 마이그레이션 (누적)

- Phase 22까지 SQL 파일은 기존과 동일; **새 DDL 없음**(Phase 23은 오케스트레이션·CLI만).

## 패치 보고·증거

- `docs/phase23_patch_report.md`
- `docs/phase23_evidence.md` — 실측 클로즈아웃·PGRST106 설명·필수 후속 없음 명시
- 정상 운영 절차: `docs/OPERATOR_POST_PATCH.md` (상단 3스텝 + 부록)

---

# HANDOFF — Phase 22 (Public-depth iteration evidence)

## 현재 제품 위치

- **Phase 11–21**: 이전과 동일(선택자·라이프사이클·인프라 격리·`advance-public-repair-series`·에스컬레이션 브리프 v2).
- **Phase 22 (본 패치)**: 동일 `public_repair_iteration_series` 아래에 **공개 깊이 확장 런**을 `member_kind=public_depth` 멤버로 적재하고, **`phase22_ledger`**(thin/joined/제외/준비도/rerun 게이트/빌드 액션/개선 분류)를 남긴다. **`advance-public-depth-iteration`** 골든 패스, **`export-public-depth-series-brief`** 다회 증거 요약, 에스컬레이션 위에 **`public_depth_operator_signal`**(continue buildout / repeat targeted repair / near-plateau review)을 얹는다. **프리미엄 디스커버리 자동 오픈·라이브 통합 없음**; Phase 15/16 재검증 캠페인은 **`--execute-phase15-16-revalidation`** 이고 게이트가 **새로 열린 경우에만** 실행.
- **비협상 유지**: 프로덕션 스코어는 `public_repair_iteration` / `public_repair_campaign` 미참조(`state_change.runner` 테스트 유지).

## Phase 22로 가능해진 것

1. **`smoke-phase22-public-depth-iteration`** — 멤버 스키마( `member_kind`, `public_depth_run_id` ) 도달
2. **`advance-public-depth-iteration`** — 활성 시리즈(없으면 생성) → readiness/trigger 스냅샷 → `run_public_depth_expansion` → ledger·멤버 append(동일 `public_depth_run_id` 멱등) → 플래토·에스컬레이션·depth 신호·depth+repair 브리프
3. **`export-public-depth-series-brief`** — 런 수, 포함/제외, 개선 분류 분포, 저장된 에스컬레이션 브랜치 카운트, 최종 권고, 미해결 제외 힌트
4. **`marginal_policy` / `depth_signal`** — 투명 임계값 기반 `improvement_classification` 및 운영자 신호
5. 플래토 수집 경로에서 **`public_depth_runs` 실패·인프라 패턴 제외**(기본)

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase22_public_depth_iteration.py -q` — **15 passed**
- `pytest src/tests -q` — **356 passed** (Phase 29까지; 외부 `edgar` DeprecationWarning 3건)

## 검증·운영 스냅샷 (2026-04-01, 시리즈 브리프 + 전체 테스트 클로징)

| 항목 | 결과 |
|------|------|
| `pytest src/tests/test_phase22_public_depth_iteration.py -q` | **15 passed** |
| `PYTHONPATH=src pytest src/tests -q` | **356 passed** (Phase 29까지); 경고 **3건**은 `edgar` 패키지 deprecation(테스트 실패 아님) |
| Supabase `20250425100000_phase22_public_depth_iteration.sql` | 대상 프로젝트에 적용했다면 `smoke-phase22-public-depth-iteration`으로 REST/스키마 확인 |
| 시리즈 브리프 | `report-latest-repair-state --program-id latest --universe <U> --active-series-id-only`로 얻은 UUID로 `export-public-depth-series-brief --series-id … --out …` 실행 완료 시 증거 체인 완료 |
| 증거 상세 | `docs/phase22_evidence.md` |

**다음 담당자:** 활성 시리즈는 `close` 후 재사용하지 않는다. 새 슬롯이 필요하면 `advance-public-repair-series` 또는 `advance-public-depth-iteration`으로 연 뒤 다시 `active_series_id`를 확인한다.

## 실측 브랜치·분포 (코드베이스)

- **단위/픽스처**: `improvement_classification` 네 갈래 전부 `test_phase22_public_depth_iteration`에서 검증; `persisted_escalation_branch_counts`·`improvement_classification_counts`는 운영 시리즈에 대해 **`export-public-depth-series-brief`** JSON으로 집계(저장소 CI에는 실 DB 없음).
- **Phase 23 권고**: 에스컬레이션이 `continue_public_depth` / `hold_and_repeat_public_repair`인 동안은 **공개 깊이·수리 반복 증거 축적(Phase 23 동일 궤도)** 을 우선. **`open_targeted_premium_discovery`** 및 브리프 v2 게이트가 성립할 때만 **타깃 프리미엄 디스커버리 검토 준비**(라이브 통합 아님). `public_depth_near_plateau_review_required`는 운영자 **플래토 리뷰** 트리거.

## 마이그레이션 (누적)

- **Phase 22**: `20250425100000_phase22_public_depth_iteration.sql` — 적용 후 `smoke-phase22-public-depth-iteration`.

## 패치 보고·증거

- `docs/phase22_patch_report.md`
- `docs/phase22_evidence.md` — 클로징 체크리스트, pytest·브리프 재현, 핸드오프 질문표

## 패치마다 동일한 운영 순서 (고정)

- **권장(Phase 23+)**: `docs/OPERATOR_POST_PATCH.md` 상단 — `run-post-patch-closeout`
- **스모크 일괄(레거시/부록)**: `./scripts/operator_post_patch_smokes.sh` (phase17→22)

---

# HANDOFF — Phase 21 (Iteration governance, selectors, infra quarantine)

## 현재 제품 위치

- **Phase 11–20**: 이전과 동일하되, Phase 21에서 **선택자 완성**(`latest-success`, `latest-compatible`, `latest-for-program`, `from-latest-pair` → `resolve-repair-campaign-pair`, `latest-active-series`), **시리즈 라이프사이클**(pause / resume / close + `governance_audit_json`), **플래토 기본값에서 인프라 실패 런 격리**(`included_run_count`, `excluded_infra_failure_count`), **`advance-public-repair-series` 단일 골든 패스**, **에스컬레이션 브리프 v2**(포함/제외 런, 호환 근거, 트렌드 델타, 카운터팩추얼, 프리미엄 게이트 체크리스트)가 추가됨.
- **비협상 유지**: 프로덕션 스코어는 `public_repair_iteration` / `public_repair_campaign` 출력을 참조하지 않음(`state_change.runner` 검증 테스트 유지). 프리미엄 **라이브** 통합 자동 오픈 없음.

## Phase 21로 가능해진 것

1. **`smoke-phase21-iteration-governance`**, **`pause-public-repair-series`**, **`resume-public-repair-series`**, **`close-public-repair-series`**
2. **`advance-public-repair-series`** — 호환 활성 시리즈 → (캠페인 1회 또는 attach) → 멤버 append(동일 `repair_campaign_run_id` 멱등) → 플래토/에스컬레이션 → 브리프 JSON+MD + 요약 한 줄
3. **`resolve-repair-campaign-pair`**, Phase 19/20 보고용 **`--repair-campaign-id`** 확장 선택자
4. **`report-public-repair-plateau --include-infra-failed-runs`** (기본은 인프라 격리 유지)
5. Transient REST 오류에 대한 **리스트 조회 재시도**(resolver 경로) 및 캠페인 실패 시 **`rationale_json.failure_audit`**

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase21_iteration_governance.py -q` — **10 passed**
- 전체 테스트 개수는 상단 **Phase 22** 절 참고.

## 검증·운영 스냅샷 (2026-04-07, 운영 DB + 로컬 CLI)

| 항목 | 결과 |
|------|------|
| `20250424100000_phase21_iteration_governance.sql` | 운영자 적용 완료 |
| `smoke-phase21-iteration-governance` | 통과(이전 스텝과 일관) |
| `advance-public-repair-series` (골든 패스) | 실행 완료; 활성 시리즈·멤버·플래토/에스컬레이션·브리프 흐름 확인 |
| **시리즈 라이프사이클** (`--series-id` = 해당 시리즈의 `public_repair_iteration_series.id`, 예: `advance`/`list-public-repair-series` 출력) | `pause-public-repair-series` → `{"ok": true, "status": "paused"}` → `resume-public-repair-series` → `active` → `close-public-repair-series` → `closed` (REST 200) |
| 원격 저장소 | `git push origin main` 완료 — **28026fb** (`main`), 구현 베이스 **3d956e9** |

**참고:** 한 시리즈를 `close`하면 동일 `(program_id, universe_name, policy_version)`에 대해 새 **active/paused** 슬롯이 비므로, 다음 반복은 `advance-public-repair-series` 또는 `get_or_create_iteration_series` 경로로 **새 시리즈**가 잡힌다.

## 마이그레이션 (누적)

- **Phase 21**: `20250424100000_phase21_iteration_governance.sql` — 운영 DB에 적용 후 `smoke-phase21-iteration-governance` 권장.
- **Phase 22**: `20250425100000_phase22_public_depth_iteration.sql`

## 패치 보고·증거

- `docs/phase21_patch_report.md`

## Phase 23 방향 제안 (Phase 22 이후)

- 공개 우선 증거가 쌓이는 동안 **`advance-public-depth-iteration`** / **`advance-public-repair-series`**를 교대로 쓰며 `export-public-depth-series-brief`로 분포를 고정.
- 에스컬레이션·게이트가 **`open_targeted_premium_discovery`**로 수렴할 때만 Phase 24급 **프리미엄 디스커버리 설계**(라이브 아님) 검토.

## Git

- **구현 커밋** **3d956e9ece1fbd5ecc9722dc16d3acc83c853a7f** (`3d956e9`) — `Phase 21: iteration governance, repair selectors, infra quarantine, advance CLI`.
- **문서·HANDOFF 정리** **28026fb** — `docs: Phase 21 README, HANDOFF commit SHA, patch report MCP note` (원격 `origin/main`에 푸시됨, 2026-04-07 확인).
- 이후 로컬만 앞서 있는 경우: `git log -1 --oneline` 로 HEAD 확인.

---

# HANDOFF — Phase 20 (Public Repair Iteration Manager & Escalation Gate)

## 현재 제품 위치

- **Phase 11–19**: 이전과 동일(공개 기판·타깃 빌드아웃·수리 캠페인 폐쇄 루프 등).
- **Phase 20 (본 패치)**: 동일 프로그램에 대해 **반복된 Phase 19 런**을 `public_repair_iteration_series` / `public_repair_iteration_members`로 묶고, `trend_snapshot_json`을 쌓아 **플래토·에스컬레이션**을 결정한다. 권고는 **`continue_public_depth`** \| **`hold_and_repeat_public_repair`** \| **`open_targeted_premium_discovery`**(프리미엄 **발견** 궤도만 열지, 라이브 통합 아님). **골든 패스**: `--program-id latest`(+필요 시 `--universe`)·`--repair-campaign-id latest`로 UUID 수동 추적 최소화. **프로덕션 스코어 경로는 `public_repair_iteration` 미참조**.

## Phase 20로 가능해진 것

1. **`run-public-repair-iteration`**: Phase 19 캠페인 1회 실행 후 시리즈에 멤버 추가 + `public_repair_escalation_decisions` 적재.
2. **`report-public-repair-iteration-history`**: `--series-id` 또는 `--program-id`(latest 가능).
3. **`report-public-repair-plateau` / `export-public-repair-escalation-brief`**: 활성 시리즈 기준 재계산·브리프.
4. **`list-public-repair-series`**, **`report-latest-repair-state`**, **`report-premium-discovery-readiness`**.
5. Phase 19 **`report-public-repair-campaign` / `compare-*` / `export-public-repair-decision-brief` / `list-repair-campaigns` / `run-public-repair-campaign`**: `latest` 선택자 및 `--universe` 지원.

## 검증·테스트 (로컬)

- `pytest src/tests/test_phase20.py` — **11 passed**
- 전체 테스트 개수는 상단 **Phase 21** 절 참고 (Phase 20 단독 카운트는 위 명령 기준).

## 검증·운영 스냅샷 (2026-04-07, `sp500_current`, `--program-id latest`)

| 항목 | 결과 |
|------|------|
| `smoke-phase20-repair-iteration` | `db_phase20_repair_iteration: ok` |
| `report-public-repair-iteration-history` | `ok: true`; 시리즈·멤버(seq 1)·에스컬레이션 행 |
| `report-public-repair-plateau` | `ok: true`; `hold_and_repeat_public_repair`, 근거 `insufficient_iterations` |
| `export-public-repair-escalation-brief` → `docs/public_repair/escalation_latest.json` | `ok: true`, 동명 `.md` |
| `report-premium-discovery-readiness` | `premium_discovery_ready: false` |
| `report-latest-repair-state` / `list-public-repair-series` | `ok: true` |
| `list-repair-campaigns` | `ok: true`; 과거 1건은 REST **502**로 `failed` 기록 가능(일시 인프라) |
| `report-public-repair-campaign --repair-campaign-id latest` | `ok: true`; 스텝·비교·`repair_insufficient_repeat_buildout` 일관 |
| 후속 (Phase 21, 동일 시리즈 UUID 기준) | `pause` → `resume` → `close` 라이프사이클 CLI REST 200·`ok: true`; 시리즈는 **closed** — 상세·SHA·테스트 카운트는 **상단 Phase 21** 스냅샷 |

상세: `docs/phase20_completion_report.md` · 증거: `docs/phase20_evidence.md`.

## 마이그레이션 (누적)

- **Phase 20**: `20250423100000_phase20_repair_iteration.sql`
- **Phase 21**: `20250424100000_phase21_iteration_governance.sql`
- **Phase 22**: `20250425100000_phase22_public_depth_iteration.sql`

---

# HANDOFF — Phase 19 (Public Repair Campaign & Revalidation Loop)

## 현재 제품 위치

- **Phase 11–18**: 이전과 동일(공개 기판 진단·타깃 빌드아웃·재검증 트리거 불리언 등).
- **Phase 19 (본 패치)**: **수리 → (게이트 충족 시) Phase 15/16 재실행 → 전후 연구 결과 비교 → 단일 최종 분기**를 한 번에 감사 가능한 행으로 남긴다. `run-public-repair-campaign`은 베이스라인 커버리지·제외 액션 스냅샷·최신 캠페인 권고를 고정한 뒤 `run-targeted-public-buildout`을 호출하고, `report-revalidation-trigger`와 동일한 **양쪽 불리언**이 모두 true일 때만 `run_validation_campaign(..., force_rerun)`을 수행한다. **프로덕션 스코어 경로는 `public_repair_campaign` 미참조**(`state_change.runner`에 해당 문자열 없음).

## Phase 19로 “증명” 가능해진 것

- 한 캠페인 런에 대해 **무엇을 시도했는지**, **기판이 개선됐는지**, **재실행이 실제로 돌았는지**, **생존 분포·캠페인 권고가 어떻게 바뀌었는지**, **다음 분기(`continue_public_depth` \| `consider_targeted_premium_seam` \| `repair_insufficient_repeat_buildout`)**가 무엇인지 DB·CLI로 재현한다.
- **`consider_targeted_premium_seam` 분기는 재실행 증거 없이는 나오지 않는다**(정책 코드 불변식).

## 검증·테스트 결과 (2026-04-06 기준)

| 항목 | 결과 |
|------|------|
| Supabase 마이그레이션 `20250422100000_phase19_public_repair_campaign.sql` | 적용 완료(운영자 확인) |
| `smoke-phase19-public-repair-campaign` | 네 테이블 REST 조회 200, `db_phase19_public_repair_campaign: ok` |
| `pytest src/tests/test_phase19.py -q` | **14 passed** |
| `pytest src/tests -q` (전체) | **242 passed** (외부 `edgar` DeprecationWarning만) |
| `export-public-repair-decision-brief --out docs/public_repair/briefs/latest.json` | `ok: true`, 동명 `.md` 생성(실캠페인 런 ID는 실행마다 상이) |

상세 체크리스트·클로징 순서: `docs/phase19_completion_report.md` · 증거 메모: `docs/phase19_evidence.md`.

## 운영 후 HANDOFF에 채울 항목 (실행 증거 기준)

| 질문 | 어디서 확인 |
|------|-------------|
| 수리 후 기판이 실질적으로 나아졌는가? | `public_repair_campaign_runs.improvement_report_id` → `public_buildout_improvement_reports` 또는 전후 `baseline_coverage_report_id` / `after_coverage_report_id` |
| Phase 15/16 재실행이 실제로 있었는가? | `reran_phase15`, `reran_phase16`, `after_campaign_run_id`; `rerun_skip_reason_json`이 비어 있지 않으면 스킵 이유 |
| 레시피 생존·캠페인 권고가 개선됐는가? | `public_repair_revalidation_comparisons` |
| 다음이 공개 깊이 우선인가, 프리미엄 seam 검토인가, 추가 빌드아웃인가? | `final_decision` + `public_repair_campaign_decisions.rationale_json` |

## 마이그레이션 (누적)

- **Phase 19**: `20250422100000_phase19_public_repair_campaign.sql`
- **Phase 20**: `20250423100000_phase20_repair_iteration.sql`

---

# HANDOFF — Phase 18 (Targeted Public Build-Out)

## 현재 제품 위치

- **Phase 11–17**: 이전과 동일(연구 엔진·캠페인·공개 기판 깊이 확장·커버리지/uplift).
- **Phase 18 (본 패치)**: **제외 사유 기반 타깃 수리** — 우세 제외 키에 맞춰 상한 있는 빌드(검증 패널·선행수익·factor 패널·state change)를 오케스트레이션하고, `public_buildout_*`·`public_exclusion_action_reports`에 감사 흔적을 남긴다. **제품 스코어 경로는 `public_buildout` 미참조**(`state_change.runner` 소스에 해당 문자열 없음; 빌드 경로에서만 `run_state_change` 호출).

## Phase 18으로 가능해진 것

1. **`report-public-exclusion-actions`**: 제외 분포·심볼 큐·권장 액션 JSON(`--persist`).
2. **`run-targeted-public-buildout`**: 플래그·상한으로 타깃 제외만 공격; `dry_run` 시 DB 작업 최소화.
3. **`report-buildout-improvement`**: 두 커버리지 리포트 UUID로 제외·기판 델타; `--persist` 시 `public_buildout_run_id` 없이도 개선 행 저장 가능.
4. **`report-revalidation-trigger`**: 프로그램 유니버스 기준 **명시적** `recommend_rerun_phase15` / `recommend_rerun_phase16`.
5. **`export-buildout-brief`**: JSON+Markdown 브리프.

## 다음 단계 권고 (증거 기준)

1. `20250421100000_phase18_public_buildout.sql` 적용 후 `smoke-phase18-public-buildout`.
2. `report-public-depth-coverage`로 기준선 → 필요 시 Phase 17 확장 또는 Phase 18 **타깃** 빌드.
3. 전후 커버리지로 `report-buildout-improvement` 또는 오케스트레이션 결과의 `improvement_summary_json` 확인.
4. 기판이 임계를 넘으면 `report-revalidation-trigger`의 불리언을 보고 Phase 15/16 재실행을 **수동** 검토(자동 연결 없음).

## 마이그레이션 (누적)

- **Phase 18**: `20250421100000_phase18_public_buildout.sql`
- **Phase 19**: `20250422100000_phase19_public_repair_campaign.sql`
- **Phase 20**: `20250423100000_phase20_repair_iteration.sql`

---

## Phase 17 요약

### Phase 17으로 가능해진 것

1. **`report-public-depth-coverage`**: 최신 멤버십 as_of 기준 조인 행 수·품질 쉐어·제외 분포 JSON.
2. **`run-public-depth-expansion`**: before/after 커버리지 + uplift 행 생성(플래그로 빌드 단계 제어).
3. **`report-quality-uplift`**: 두 커버리지 리포트 UUID로 델타 계산(옵션 DB 저장).
4. **`report-research-readiness`**: 프로그램의 `universe_name`으로 기판 스냅샷을 보고 **Phase 15/16 재실행 권고 불리언**(휴리스틱 임계: `MIN_SAMPLE_ROWS * 5` joined 행 + `thin_input_share` 완화).
5. **`export-public-depth-brief`**: JSON+Markdown 아티팩트(`--universe` 또는 `--program-id`).

## `thin_input`이 “실제로” 줄었는지

- **코드가 자동으로 단정하지 않는다.** 확장 전후 `public_depth_coverage_reports.metrics_json`의 `thin_input_share` 및 `joined_recipe_substrate_row_count`를 비교해 운영자가 판단한다. `public_core_cycle_quality_runs`는 **해당 유니버스** 최근 N건으로 쉐어를 추정한다.

## 다음 단계 권고 (증거 기준)

1. Supabase에 `20250420100000_phase17_public_depth.sql` 적용 후 `smoke-phase17-public-depth`.
2. 대상 유니버스로 `report-public-depth-coverage` → 기준선 저장(`--persist` 또는 확장 러의 before).
3. 필요 시 `run-public-depth-expansion --run-validation-panels` 등으로 **상한 있는** 공개 빌드 실행 → after·uplift 확인.
4. **`joined_recipe_substrate_row_count`가 눈에 띄게 증가**하고 **thin_input 쉐어가 완화**되면: **Phase 15/16 재실행**을 우선 검토.
5. 그렇지 않으면: **공개 기판 추가 확장**(유니버스 전용 factor/패널 빌드 설계 등)을 이어가고, 캠페인이 `targeted_premium_seam_first`로 바뀐 **별도 증거**가 있을 때만 프리미엄 seam을 헤드라인으로 올린다.

### Phase 17 마이그레이션

- `20250420100000_phase17_public_depth.sql`

---

## Phase 16 이전 요약

- `docs/phase16_evidence.md`, Phase 15 이하 문서 참고.
