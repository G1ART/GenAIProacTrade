# METIS MVP — 스펙 대비 진척·갭 (운영 스냅샷 v1)

권위: `METIS_MVP_Unified_Product_Spec_KR_v1.md`, `METIS_MVP_Unified_Build_Plan_KR_v1.md`  
목적: **북극성(Truth → Registry → Message → Today/Research/Replay)** 대비 지금 코드가 어디까지 왔는지, 플랜 §1의 “없는 것” 목록을 **현재 기준으로 재평가**한다.  
(빌드 플랜 §1은 문서 작성 시점 스냅샷이며, 이후 Brain 번들·게이트·Today registry 경로 등이 구현되었다.)

---

## 1. 북극성 한 줄

**Active Horizon Model Registry를 Today가 읽고**, 검증·승격된 아티팩트가 **message snapshot**으로 Research/Replay까지 이어지는 **연구 거버넌스형 의사결정 OS**.

---

## 2. 제품 스펙 §10 공식 판정 — 코드/데이터 기준 요약

| # | 질문 (스펙 원문) | 현재 상태 | 비고 |
|---|------------------|-----------|------|
| Q1 | Today가 registry만 읽는가? | **조건부 닫힘 (AGH v1 Patch 9 강화)** | 기본 `METIS_TODAY_SOURCE=registry` + `validate-metis-brain-bundle` 통과 번들이면 시드 미사용. Patch 7 의 `rows_limit` + Patch 8 의 3-tier bundle vocabulary 위에, Patch 9 는 (a) **A1 `brain_bundle_path()` 가 env>v2>v0 순서로 자동 감지** 하고 v2 가 quick integrity 를 통과할 때만 v2 를 사용 (그 외는 v0 fallback), (b) `/api/runtime/health.mvp_brain_gate` 에 `brain_bundle_path_resolved` / `brain_bundle_v2_exists` / `brain_bundle_v2_integrity_failed` / `brain_bundle_fallback_to_v0` 4 필드를 추가 + v2 integrity fail 시 `degraded_reasons.append("v2_integrity_failed")` 로 조용히 덮지 않음, (c) UI `hydrateBundleTierChip` 이 **fallback variant** (`tsr-chip--degraded`) 로 "번들: 폴백 (v0)" 를 운영자에게 상시 노출, (d) **A2 production-tier 4 integrity 체크** (active/challenger 일관성 / horizon 별 spectrum rows ≥ 1 / tier metadata coherence / write evidence) 가 `tier="production"` 호출시 활성. 즉 demo fingerprint 를 production 으로 잘못 승격할 수 없음. |
| Q2 | 각 시간축에 active family 존재? | **닫힘** | `metis_brain_bundle_v0` + `bundle_ready_for_horizon` |
| Q3 | challenger/active 구분? | **닫힘** | short challenger 등 |
| Q4 | artifact 없이 Today 불가? | **스키마상 닫힘** | 번들 무결성 검사; **실데이터 Heart→Artifact 자동 생산**은 별도(게이트 export/merge 파이프) |
| Q5 | message가 memo와 분리된 1급? | **대부분 닫힘** | `MessageObjectV1`, 스냅샷 스토어, Slice B Ask 연동 |
| Q6 | 카드에 headline·why_now·rationale? | **닫힘** | 시드/번들 스펙트럼 행 + object detail |
| Q7 | 동명 종목·지평별 위치 차이? | **닫힘** | 지평별 행·`horizon_lens_compare` |
| Q8 | price overlay가 rank movement 변경? | **닫힘** | `mock_price_tick=1` |
| Q9 | Research message→information→deeper? | **강화 닫힘 (Product Shell Patch 10B)** | Patch 5–7 의 intent router + `ResearchAnswerStructureV1` + 가드레일 + `locale_coverage` + 3-cluster + bounded contract card 위에, Patch 8 이 (a) **A1 — `ResearchAnswerStructureV1` 에 `what_changed_bullets_ko/en`** 2 스택을 추가해 Research 응답이 "What was asked / Current read / What changed recently / Why it matters" **4-stack** 으로 한 단계 더 분명해짐 (guardrail + `_SYSTEM_PROMPT` 동기화), (b) **A5 — tooltip `sub` 에 what_changed 와 confidence band 를 `SUB_SEP` 으로 합성**, (c) **B2 샌드박스 큐 4-state** (`queued/running/completed/blocked`) + `humanizeProducedRefs` + `B3` per-entry recent sandbox requests + `B4` contract card status_after 로 Ask→Research→Sandbox 경로의 "다음 한 걸음" 이 상태까지 UI 에 투명. |
| Q10 | Replay가 당시 family·결과 연결? | **강화 닫힘 (Product Shell Patch 10B)** | Patch 7 의 3-lane SVG + step count summary + time-delta tooltip 위에, Patch 8 이 (a) **A3 — `/api/replay/governance-lineage` 가 step note 를 포함** (각 step 의 작업·범위·결과 요약), (b) **30 일 이상 lineage 공백 annotation** 을 plot 에 overlay 해 "이 갭은 활동 부재였음" 을 시각적으로 선언. `humanizeActiveArtifactLabel` 은 계속 raw id 차단. |
| Q11 | signal quality 가 시간을 두고 누적되는가? | **닫힘 (Patch 11)** | `mvp_spec_survey_v0._q11_signal_quality_accumulation` — short/medium horizon 의 `residual_score_semantics_version` 커버리지 ≥ 0.8 일 때 `ok=True`. `residual_freshness_block` 이 네 표면에 동일 라벨을 반복. |
| Q12 | 장기 horizon 의 근거가 정직한 tier 로 표기되는가? | **닫힘 (Patch 11)** | `mvp_spec_survey_v0._q12_long_horizon_honest_tier` + `long_horizon_support_integrity_errors` — `horizon_provenance.source=real_derived` 와 `long_horizon_support_by_horizon.tier_key` 의 일관성 강제. 제품 쉘은 `long_horizon_support_note_block` 로 `production/limited/sample` 중 하나만 반복. |

---

## 3. 빌드 플랜 Stage 대비 (문서 Stage 순)

| Stage | 목표 | 진척 |
|-------|------|------|
| 0 Brain Lock | Artifact·Gate·Registry·Today 소스 계약 | **닫힘**(스키마+번들+검증 CLI+DB→게이트 빌드) |
| 1 Today 수직 | Registry 스펙트럼·밴딩·워치·rank | **닫힘**(registry 우선·폴백 시드) |
| 2 Message v1 | 1급 객체·스냅샷 | **거의 닫힘**(저장·해석·Ask 스레드) |
| 3 Research 최소 | 계층·Ask·샌드박스 | **강화 닫힘 (Product Shell Patch 10B)** — `/api/product/research` landing + deepdive + `/api/product/ask` 4 라우트 (context + quick + free-text + request state). 3-rail 디프다이브 (claim / 5 evidence / 3 actions) + 6 결정론 quick chip + retrieval-grounded 자유 입력 (실패 시 `_degraded_answer` 자동 전환). |
| 4 Replay | lineage·counterfactual·결정 | **강화 닫힘 (Product Shell Patch 10B)** — Patch 8 step note + 30일 공백 annotation 위에, Patch 10B 의 `/api/product/replay` 가 타임라인 + 공백 주석 + 시작/최근 체크포인트 + baseline/weakened/stressed **3 시나리오** 를 고객 표면 언어로 돌려준다. `advanced_disclosure` 는 payload 를 숨기고 "/ops" 로만 가리킴. |
| 5 Shell/KO-EN/데모 동결 | — | **Patch 10A Product Shell 분리로 상향 (2026-04-23)** — 사용자용 `/` 와 운영자용 `/ops` 를 **하드 2-파일 분리** (`METIS_OPS_SHELL=1` env 게이트, 미설정 시 /ops 404), 신규 `product_shell.css` design tokens + 8 priority components + SVG hand-roll 스파크라인, `product_shell.*` 46 키 KO/EN parity, HTML/JS/CSS/DTO 4 면 no-leak regex 스캐너로 엔지니어링 ID 누수 차단. 여전히 Patch 9 production actualization 으로 상향된 기반: **Patch 9 production actualization 으로 상향**: Patch 8 의 `demo`→`sample` 로캘 graduation + bundle-tier chip 위에, Patch 9 가 (a) **D1 — bundle-tier chip fallback variant** (`tsr-chip--degraded` + `tsr-tier-chip--fallback`) 로 "번들: 폴백 (v0)" 을 운영자에게 상시 노출 + tooltip 에 `degraded_reasons` 언급, (b) **D2 — primary nav 강조 / utility demote** (feature 제거 0, 폰트·opacity 차등), (c) **B4 — invoke copy 에 "운영자 게이트 · 대기열 · 자동 승격 없음"** 명시 (no-leak 스캐너 `test_agh_v1_patch9_copy_no_leak.py` 가 이 문구들의 실존을 파라미터 테스트로 강제), (d) `screenshots_patch_9/freeze_*.html` + `sha256_manifest.json` 7 개 snapshot. playwright 기반 실 브라우저 스크린샷은 여전히 이월. |
| 6 Trust | — | **부분 닫힘 (AGH v1 Patch 9)** — Patch 7/8 의 bounded contract card + operator gate + cli_hint + 3-tier bundle chip + degraded 200 위에, Patch 9 가 (a) **B1 recent sandbox requests 드로어** (humanize 된 kind·result·blocking·input·lifecycle-aware next step hint) 로 운영자가 액션을 요청한 뒤 "내 요청이 어디까지 갔는지" 를 SPA 안에서 확인 가능, (b) **B2 워커 tick hint** 로 "워커가 주기적으로 큐를 확인합니다" 를 queued/running 에서만 노출 (자동 승격 환상 제거), (c) **A1 A2 — production bundle integrity 4 체크 + v2 integrity fail 시 `degraded_reasons`** 로 프로덕션 번들이 은밀히 demo fingerprint 로 오용되는 리스크 차단. 전용 Trust 패널 / surface-level signature 는 후속. |

---

## 3.9 Private Beta — Invite-Only Auth + Account-Level Usage Tracking (Patch 12, 2026-04-23)

Patch 12 는 **제품 외부 경계 (인증 / 세션 / 이벤트 / 배포 / RLS) 만 추가하는 온라인 전환 패치** 다. Patch 11 까지 닫은 Brain bundle 계약, Product DTO 언어, Q1..Q12 spec survey, `strip_engineering_ids` 는 **한 줄도 수정하지 않는다**. `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md` §8 의 "MVP 비범위: 공개 signup / billing / entitlement / 마케팅 사이트" 경계는 그대로 유지되며, invite-only 경계만 열린다.

- **DB (스펙 §6 1급 객체 보완이 아닌 운영 레이어 추가)**. `supabase/migrations/20260423100000_patch_12_private_beta_auth_tracking_v1.sql` 가 `beta_users_v1` (status ∈ {invited,active,paused,revoked} × role ∈ {beta_user,admin,internal}) + `profiles_v1` (자기 row SELECT/UPDATE) + `product_usage_events_v1` (service_role only SELECT/INSERT, bounded taxonomy 만 저장) 3 테이블, 3 인덱스, 4 admin view (`v_beta_users_active_v1`, `v_beta_sessions_recent_v1`, `v_beta_top_events_v1`, `v_beta_trust_signals_v1`) 를 idempotent 하게 설치. RLS 로 유저는 자기 row 만 읽고, events 는 반드시 서버 `POST /api/events` 를 경유.
- **Auth 스택 (stdlib-only)**. `src/phase47_runtime/auth/` 는 외부 라이브러리 0 건으로 구성: `jwt_verifier.py` (HS256 verify, constant-time compare, aud/exp/iat/sub/role 검사), `supabase_rest.py` (`urllib.request` 기반 최소 PostgREST client), `beta_allowlist.py` (`enforce/shadow/off` 3 모드 + 60 초 TTL 캐시), `guard.py` (`require_auth` — 공개 path 4 개 bypass + OPTIONS bypass + Bearer 누락 401 + JWT 검증 실패 401 + revoked/paused 401 + **JWT secret 미설정 시 graceful downgrade**). `routes.py` `dispatch_json` 최상단에 가드가 박혀 모든 `/api/*` 가 동일 체크를 받는다. `user_id_alias(user_id)="bu_"+sha256[:12]` 가 raw UUID 의 DTO/로그/UI 노출을 원천 차단.
- **Login UI + SPA bootstrap**. `static/login.html` + `login.js` 가 supabase-js v2 ESM CDN 1건만 import 해 `signInWithOtp` magic link 를 초기화하고, `/api/runtime/auth-config` 로 공개 anon_key 만 받아 온다. `auth_bootstrap.js` 는 Product Shell 첫 렌더 **전**에 세션 체크 → 없으면 `/login.html` 리다이렉트 + 있으면 `window.fetch` 전역 래핑으로 `Authorization: Bearer` 자동 주입 + `window.metisEmitEvent(name, meta)` 텔레메트리 헬퍼 발행. Vanilla JS SPA 원칙 유지 (supabase-js 1건만 예외).
- **Telemetry 인제스트**. `event_taxonomy.py` 의 **13-event allowlist** (session_started / page_view / research_opened / replay_opened / ask_opened / ask_quick_action_clicked / ask_free_text_submitted / ask_answer_rendered / ask_degraded_shown / sandbox_enqueue_clicked / sandbox_request_blocked / out_of_scope_shown / hero_card_focused) + surface/horizon/lang allowlist + metadata 2KB 상한 + strip_engineering_ids 재사용으로 **audit-friendly schema**. `ingest.py` 의 in-memory sliding-window rate limit (100/min/user, 101 건째 429). `POST /api/events` + `POST /api/events/batch` (최대 50 건, partial save 금지).
- **/ops Beta Admin 탭 (customer 엔 여전히 404)**. `static/ops.html` + `ops_admin.js` 가 기존 `/ops` (env-gated `METIS_OPS_SHELL=1`) 의 utility nav 에 "Beta Admin" 1 탭 추가. 4 섹션 (Invited users / Recent sessions 24h / Top events 7d / Trust signals) 를 SVG hand-roll 로 렌더. `routes_admin.py` 는 `beta_users_v1.role ∈ {'admin','internal'}` 만 통과 + 모든 DTO 에서 raw UUID 는 `bu_<12hex>` alias, 이메일은 `{prefix[0..2]}***@{domain}` 로 마스킹.
- **PII 디시플린**. raw `user_id` UUID 는 클라이언트/로그/DTO 에 0 회 노출, 오직 `bu_<12hex>` alias 만 순환. 이메일은 서버 측 `beta_users_v1` 에만 저장, Product DTO 엔 display_name 만 돌림. JWT secret 은 서버 환경변수에만 존재, `/login.html` + 정적 자산 어디에도 substring 0.
- **환경 변수 (Patch 12 에서 추가 5 개, 모두 optional)**. `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_AUTH_REDIRECT_URL`, `METIS_BETA_ALLOWLIST_MODE`, `METIS_TELEMETRY_ENABLED`. 전부 미설정 시 서버는 `/api/*` 에 인증을 요구하지 않고 (graceful downgrade) `/login.html` 은 "not configured" 안내만 보여줌 — 로컬 개발 / 기존 CI 전부 무중단.
- **Q1..Q12 불변**. Patch 12 는 spec §10 survey question 을 **추가하지 않는다** (인증/배포는 제품 답안 차원이 아니라 운영 레이어). 모든 Q1..Q12 는 `build_mvp_spec_survey_v0` 에서 여전히 동일한 `question_id` / 순서 / 판단 로직으로 green 을 유지.
- **Evidence + Docs**. `data/mvp/evidence/patch_12_{auth_flow,beta_allowlist,event_taxonomy,telemetry_ingest,admin_surface,private_beta_runbook}_evidence.json` 6 건 + `screenshots_patch_12/` (12 파일 + SHA256 manifest). 운영 문서 2 추가: [`METIS_Private_Beta_Deployment_Runbook_v1.md`](../ops/METIS_Private_Beta_Deployment_Runbook_v1.md) (Supabase 마이그레이션 → Auth UI → Railway env → 첫 invite SQL → smoke test 9 단계 copy-paste), [`METIS_Beta_Invite_Checklist_v1.md`](../ops/METIS_Beta_Invite_Checklist_v1.md) (invite/activate/pause/revoke SQL + 확인 쿼리).

**Unified Product Spec §10 대비 갭 (Patch 12 이후)**: Q1..Q12 모두 코드 수준 불변식 + no-leak 테스트로 여전히 pin. Brain / Product 계약 변경 0. 남은 candidate 는 순수 운영 규율 (real forward-returns 파이프라인 스케줄, custom SMTP 이관, Railway scale > 1 대비 Redis 기반 rate-limit) 이며 스펙 §10 question set 에는 영향 없음.

---

## 3.8 Brain Bundle v3 / Signal Quality / Long-Horizon Truth (Patch 11, 2026-04-23)

Patch 11 은 **Brain layer 로 올라가는 패치** 다. 10A/10B/10C 에서 닫힌 네 고객 표면 (Today / Research / Replay / Ask AI) 의 "제품 언어" 는 그대로 두고, 그 아래 Brain bundle 계약을 (1) long-horizon 근거의 정직한 tier 분류, (2) residual-score 의미의 제품 쉘 실전 배선, (3) brain overlay (non-quant 보정) 의 공유 focus 노출, (4) Q11/Q12 자동 spec survey 확장으로 봉인한다. 새 sandbox kind·새 surface·새 LLM 직접 기록 경로 없음 — 모든 non-quant 보정은 `BrainOverlayV1` 을 통해만 흐른다.

- **Brain Bundle v3 (Scope A)**. `src/metis_brain/bundle.py` 의 `BrainBundleV0` 에 `long_horizon_support_by_horizon: dict | None` + `brain_overlays: list | None` 을 optional 로 확장 (graduation-safe — 기존 v0/v2 번들은 그대로 파싱된다). `src/metis_brain/long_horizon_evidence_v1.py` 가 `LongHorizonSupportV1` + `classify_long_horizon_tier` (`production` ≥0.8&≥30 / `limited` ≥0.4&≥10 / `sample`) + `summarize_long_horizon_support` + `long_horizon_support_integrity_errors` (`horizon_provenance=real_derived` 인데 tier=sample 이면 "거짓말" 로 flag) 를 제공. `validate_active_registry_integrity` 가 integrity 검사를 호출해 **현실 대비 과장이 bundle 수준에서 막힘**.
- **Residual semantics 제품 쉘 실전 배선 (Scope A)**. `src/phase47_runtime/message_layer_v1.py` 에 `residual_score_semantics_version` / `invalidation_hint` / `recheck_cadence` 3 키를 `MESSAGE_LAYER_V1_KEYS` 에 포함. `view_models_common.py` 에 `RESIDUAL_WORDING` (KO/EN × recheck·invalidation 축, 11 버킷) + `normalize_recheck_cadence` / `normalize_invalidation_hint` (raw slug → controlled key) + `residual_freshness_block` 을 추가하고 `build_shared_focus_block` 에서 `block["residual_freshness"]` 로 네 표면에 동일 라벨을 반복. `compute_coherence_signature` 는 `recheck_cadence_key + invalidation_hint_kind` 를 지문 입력에 흡수.
- **Signal quality accumulation (Scope B)**. `view_models_common.long_horizon_support_note_block` + `SHARED_WORDING.long_horizon_support.*` (KO/EN × production/limited/sample 3 버킷) 이 장기 근거 품질을 네 표면에 동일 라벨로 반복. `src/metis_brain/mvp_spec_survey_v0.py` 에 (1) `_q11_signal_quality_accumulation` — short/medium horizon 의 residual semantics 커버리지 ≥ `Q11_MIN_COVERAGE_SHORT_MEDIUM=0.8` 일 때 `ok=True`, (2) `_q12_long_horizon_honest_tier` — `long_horizon_support_by_horizon` 가 provenance 와 일관되고 integrity errors 가 0 일 때 `ok=True`. `build_mvp_spec_survey_v0` 가 기존 Q1..Q10 뒤에 Q11, Q12 를 **추가** (기존 질문 `question_id` / 순서 / 판단 로직 **불변**).
- **Product-facing truth uplift (Scope C)**. `view_models_common.overlay_note_block` 이 `bundle.brain_overlays` 에서 focus horizon 에 해당하는 overlay 를 가중평균 priority 로 뽑아 `{dominant_kind_key, count, counter_interpretation_present, note_ko, note_en}` 로 요약. Today hero (via shared_focus) / Research `_evidence_cards.counter_or_companion` / Ask AI `_quick_answer.why_confidence` + `whats_missing` 가 동일 overlay note 를 consume 하되 어느 표면도 `ovr_*` / `pcp_*` / `persona_candidate_id` / `overlay_id` / `brain_overlay_ids` 엔지니어링 ID 를 노출하지 않도록 `strip_engineering_ids` regex 5 개를 pin. `BRAIN_OVERLAY_WORDING` 는 5 kind (catalyst_window / regime_shift / liquidity_caveat / invalidation_warning / counter_interpretation) × KO/EN parity.
- **Ask AI 의미적 품질 회귀 (Scope D)**. `data/mvp/ask_semantic_golden_set_v1.json` 18 엔트리 (in_scope ground / in_scope counter / low_evidence / out_of_scope advice / out_of_scope off_topic / out_of_scope foreign_ticker × KO/EN). `src/tests/test_agh_v1_patch_11_ask_semantic_quality.py` 가 각 엔트리에 대해 `compose_ask_*_dto` 를 실행하고 `score = 0.4*grounded + 0.3*bounded + 0.3*useful` 를 계산, `regression_score >= 0.75` 와 `bounded_strict = 1.0` (`claim`/`evidence` 에 매수/매도/가격 목표가 0 글자) 를 강제. `scripts/agh_v1_patch_11_ask_semantic_regression.py` 는 오퍼레이터용 러너.
- **No-leak / Coherence / Freeze / Runbook (Scope E)**. `test_agh_v1_patch_11_copy_no_leak.py` 가 10A/10B/10C 금지 패턴 계승 + Patch 11 신규 (residual raw slug, `ovr_*`/`pcp_*`/`overlay_id` 등) + `SHARED_WORDING` 중첩 구조 KO/EN parity 를 강제. `test_agh_v1_patch_11_coherence_with_residual.py` 가 residual cadence·invalidation·overlay dominant kind 변경이 12-hex 지문을 바꿈, 언어만 바꾸면 지문 유지, 네 표면 fingerprint 문자 단위 동일을 단언. `scripts/agh_v1_patch_11_brain_truth_freeze.py` 가 `AAPL/short` 의 12 DTO + manifest 를 기록 (`all_ok=true, cross_surface_ok=true, engineering_id_leaks=[]`). `scripts/agh_v1_patch_11_brain_truth_runbook.py` 가 S1..S7 을 전부 green.

**Unified Product Spec §10 대비 갭 (Patch 11 이후)**: Q1..Q10 여전히 코드 수준 불변식 + no-leak 테스트로 pin. **Q11 (signal quality accumulation) / Q12 (long-horizon honest tier) 추가** 및 자동 spec survey 에서 green. 남은 후보는 real forward-returns production 파이프라인 운영 규율이며 Brain 계약 자체의 구조적 갭은 없음.

상세: [`docs/plan/METIS_Residual_Score_Semantics_v1.md` §Product Shell Connection](./METIS_Residual_Score_Semantics_v1.md).

---

## 3.7 Product Shell Coherence / Trust Closure (Patch 10C, 2026-04-23)

Patch 10C 는 **seal patch** 다. 10A 가 "하드 2-파일 분리 + Today 한 장", 10B 가 "Research/Replay/Ask AI 제품 언어" 를 닫았다면, 10C 는 그 위에 펼쳐진 **네 고객 표면이 같은 focus 에 대해 같은 진실을 같은 제품 언어로 말한다** 를 코드 수준 불변식으로 **봉인**한다. 새 페이지나 새 sandbox kind 를 추가하지 않는다.

- **Cross-surface coherence signature (Scope A)**. `src/phase47_runtime/product_shell/view_models_common.py` 에 (1) `compute_coherence_signature` — `(asset_id, horizon_key, 양자화된 position, grade_key, stance_key, source_key, digest(what_changed), digest(rationale_summary))` 로부터 언어 독립적 12-hex SHA-256 지문, `contract_version="COHERENCE_V1"`, (2) `build_shared_focus_block` — 네 표면이 문자 단위 동일하게 embed 하는 SSOT, (3) `SHARED_WORDING` — 10 버킷 (sample/preparing/limited_evidence/production/freshness/bounded_ask/next_step/what_changed/knowable_then/out_of_scope) 의 KO/EN 공통 카피 사전. Today 는 `hero_cards[*].shared_focus + coherence_signature + cta_more` + top-level `primary_focus` 로, Research deepdive / Replay / Ask-landing / Ask-quick 는 top-level `shared_focus + coherence_signature + evidence_lineage_summary + shared_wording + breadcrumbs` 로 통합 배선. `test_agh_v1_patch_10c_coherence.py` 가 네 표면 KO·EN 지문 동일성 + 언어 불변을 강제.
- **Ask AI retrieval-grounded trust closure (Scope B)**. `view_models_ask.py` 에 3 단 guard: (1) pre-LLM `classify_question_scope` — advice (매수/매도/목표가/추천) / off_topic (옵션·파생 등) / foreign_ticker (화면에 없는 티커) / in_scope 로 분류 후 out-of-scope 는 **LLM 호출 없이** 단락, (2) `surfaced_context_summary` — 화면에 보이는 focus 만 scrubbed 한 문단으로 묶어 `copilot_context.surfaced_evidence` + `bounded_contract` 지시어와 함께 `api_conversation` 에 주입, (3) post-LLM `scan_response_for_hallucinations` — 반환 body 를 advice/foreign ticker/price target 로 스캔, 1 건이라도 걸리면 body 자체를 폐기하고 `partial` 로 downgrade. `test_agh_v1_patch_10c_ask_golden_set.py` 가 in_scope / advice / off_topic / foreign_ticker / low_evidence / degraded / hallucinating 7 분기 골든셋을 전부 green.
- **Product-state continuity (Scope C)**. `product_shell.js` 에 (1) `renderFocusRibbon(dto, surface)` 공통 컴포넌트 — 같은 `(asset_id, horizon_key)` 의 grade/stance/confidence chip + 네 표면 soft-link 버튼 그룹 + 12-hex 지문을 persistent strip 으로 표시, (2) `ps-hero-card-softlinks` — Today hero 카드 하단에 cta_more (Replay/Ask AI) chip row, (3) Research deepdive / Replay / Ask breadcrumb 를 `Today / <surface> / <ticker>` 로 통일. `product_shell.css` 의 `.ps-focus-ribbon[data-source]` 는 live / preparing / sample 별로 좌측 accent bar 색이 달라져 신뢰 상태를 시각으로 전달.
- **DTO/mapper refinement (Scope D)**. 네 view-model 이 공통 `shared_focus_block` / `coherence_signature` / `evidence_lineage_summary` 를 각자 맞는 키에 embed 하도록 refine. `strip_engineering_ids` 는 `coherence_signature` 와 `COHERENCE_V1` 을 손대지 않음을 테스트로 pin. `test_agh_v1_patch_10c_ops_product_parity.py` 가 synthetic `api_governance_lineage_for_registry_entry` 페이로드로 (1) 타임라인 이벤트 수 일치, (2) summary 일치, (3) 엔지니어링 regex 누수 0, (4) outcome 라벨 humanized, (5) gap annotation 일치를 강제.
- **Language contract tightening (Scope E)**. `phase47e_user_locale.py` 에 `product_shell.continuity.*` (10) + `product_shell.trust.*` (5) + `product_shell.ask.out_of_scope.*` (3) = 18 쌍 KO/EN parity. `test_agh_v1_patch_10c_language_contract.py` 가 네 표면의 `shared_wording` 블록 존재 + preparing/sample 포커스 body 가 `SHARED_WORDING` 과 문자 단위 일치 + Ask AI out-of-scope banner 가 공유 bucket 과 동일함을 강제. `test_agh_v1_patch_10c_copy_no_leak.py` 가 10A/10B 금지 패턴 계승 + 10C 내부 헬퍼 이름 (`_quantize_position`, `_short_hash`, `classify_question_scope`, `scan_response_for_hallucinations`) UI/DTO 노출 0 + 3 로캘 패밀리 KO/EN parity 를 함께 강제 (141 파라미터 green).
- **Freeze / Runbook / Evidence (Scope F)**. `scripts/agh_v1_patch_10c_product_coherence_freeze.py` 가 동일 focus (`AAPL/short`) 의 6 DTO × 2 언어 = 12 파일 + `coherence_manifest_AAPL_short.json` 을 `data/mvp/evidence/screenshots_patch_10c/` 에 저장 (manifest invariants 에서 4 표면 지문 완전 일치). `scripts/agh_v1_patch_10c_product_coherence_runbook.py` 가 S1..S6 (cross-surface coherence / Ask trust closure / focus continuity UI / DTO refinement / language contract / no-leak+fingerprint) 를 전부 green. 산출 evidence 6: `patch_10c_product_coherence_{runbook,bridge}_evidence.json`, `patch_10c_{coherence,ask_trust_golden_set,cross_surface_alignment,language_contract}_evidence.json`.

**Unified Product Spec §10 대비 갭 (Patch 10C 이후)**: Q1 (Today registry-only) / Q2 (message 1급) / Q3 (Research lineage) / Q4 (Replay lineage) / Q5 (Ask AI bounded) / Q6 (Honest degraded) / Q7 (Product language contract) **모두 코드 수준 불변식 + no-leak 테스트로 pin 됨**. Q8/Q9 (signal quality 누적 / 장기 관점 grid) 는 brain bundle 레이어 Patch 11 후보.

상세: [`docs/plan/METIS_Product_Shell_Rebuild_v1_Spec_KR.md` §11](./METIS_Product_Shell_Rebuild_v1_Spec_KR.md).

---

## 3.6 Research / Replay / Ask AI 정식 재설계 (Patch 10B, 2026-04-23)

Patch 10B 는 10A 에서 분리한 `/` Product Shell 에 **세 표면을 제품 언어로 올린다**. 10A 가 "엔지니어링 ID 누수 0 + Today 한 장" 을 아키텍처로 닫았다면, 10B 는 그 위에 Research / Replay / Ask AI 를 **서로 연결되고 길을 잃지 않게** 붙인다. 단일 북극성 ("노출된 근거 안에서만 답한다") 과 단일 제품 톤 (권유 명령형 금지, 과장된 예측 확신 금지) 을 유지한다.

- **Research**: `GET /api/product/research?presentation=landing` = `PRODUCT_RESEARCH_LANDING_V1` (horizon 4 컬럼 × top-N 타일, 각 타일 grade / stance / confidence / 한 줄 요약 / deep-link). `presentation=deepdive&asset_id=&horizon_key=` = `PRODUCT_RESEARCH_DEEPDIVE_V1` (claim / 5 evidence cards `{what_changed, strongest_support, counter_or_companion, missing_or_preparing, peer_context}` / 3 action chips `{open_replay, ask_ai, back_to_today}`). `src/phase47_runtime/product_shell/view_models_research.py`. Empty state 는 "해당 종목에 등록된 근거가 아직 없어요" 로 정직하게 말한다.
- **Replay**: `GET /api/product/replay?asset_id=&horizon_key=` = `PRODUCT_REPLAY_V1`. `api_governance_lineage_for_registry_entry` 의 governance chain + sandbox followups 를 (a) 타임라인 이벤트 (proposal / decision / applied / spectrum_refresh / validation_evaluation / sandbox_request / sandbox_result), (b) 30 일 이상 공백 annotation (kind=gap), (c) 시작/최근 체크포인트 (kind=checkpoint), (d) baseline / weakened_evidence / stressed 3 시나리오 (baseline position 에 ±shift 해 grade/stance 재계산) 로 번역. `advanced_disclosure` 는 원본 payload 를 노출하지 않고 "/ops 에서 확인" 만 가리킨다 — 고객 표면 누수 0.
- **Ask AI**: 4 라우트. (1) `GET /api/product/ask` = focus context card (보고 있는 종목/구간/grade/stance/confidence 한 장) + 6 quick-action chips (`explain_claim, show_support, show_counter, other_horizons, why_confidence, whats_missing`). (2) `GET /api/product/ask/quick?intent=&...` = **노출된 근거 안에서만** 결정론적으로 생성된 답변 (Brain bundle 너머로 추측하지 않음). (3) `POST /api/product/ask` = `api_conversation` 래퍼 (실패·빈 응답 시 `_degraded_answer` 구조로 자동 전환, `grounded:false` + banner 명시). (4) `GET /api/product/requests` = sandbox followups 를 `{status_key: running|completed|blocked}` 상태 카드로 번역.
- **시각 시스템 v2**: `product_shell.css` 에 Research / Replay / Ask AI / request-state / advanced drawer / 3 tooltip variants 포함 18 신규 컴포넌트 추가. 10A 다크 프리미엄 톤 + system UI stack 유지, 외부 차트 라이브러리 없음, 반응형 (1100 / 820 / 640 px fallback).
- **프론트엔드 연결성**: `STATE.focus = {asset_id, horizon_key}` + URL hash routing (`#research?asset=AAPL&h=short` 왕복 동기화 + 브라우저 back/forward). Today hero secondary CTA "리서치 열기" 활성화 (10A 에서 disabled) + selected_movers "자세히 보기 →" soft-link 가 Research deep-dive 로 직결.
- **언어 계약 + No-leak**: `product_shell.research.*` 21 + `product_shell.replay.*` 17 + `product_shell.ask.*` 24 = 62 쌍 추가 (KO/EN parity). `strip_engineering_ids` 10B 확장 패턴 (`job_*`, `sandbox_request_id`, `process_governed_prompt`, `counterfactual_preview_v1`, `sandbox_queue`) + `test_agh_v1_patch_10b_copy_no_leak.py` 118 파라미터 green.
- **Evidence + Runbook**: `scripts/agh_v1_patch_10b_product_shell_freeze_snapshots.py` (DTO 샘플 14 + Shell HTML/JS/CSS + SHA256 manifest), `scripts/agh_v1_patch_10b_product_shell_runbook.py` (S1..S7 × `all_ok`).

상세: [`docs/plan/METIS_Product_Shell_Rebuild_v1_Spec_KR.md`](./METIS_Product_Shell_Rebuild_v1_Spec_KR.md).

---

## 3.5 Product Shell vs Ops Cockpit (Patch 10A, 2026-04-23)

스펙 §5 (Today/Research/Replay) 는 **사용자 표면** 에 대한 계약이다. Patch 10A 이전까지 이 표면은 운영자용 Cockpit UI 와 물리적으로 같은 번들에 묶여 있었고, 그 결과 엔지니어링 ID (`art_*`, `reg_*`, `factor_*`, `horizon_provenance` 등) 가 사용자에게 노출되는 구조적 누수가 상존했다.

Patch 10A 는 이 누수를 **UI 튜닝이 아닌 아키텍처 분리**로 닫는다:

- **하드 2-파일 분리**: `/` → `static/index.html` + `product_shell.js` + `product_shell.css` (사용자용). `/ops` → `static/ops.html` + `static/ops.js` (운영자용, `METIS_OPS_SHELL=1` 환경변수 게이트, 미설정 시 404).
- **/api/product/* 접두어**: 사용자 DTO 는 `src/phase47_runtime/product_shell/view_models.py` 의 mapper 레이어를 지나 `strip_engineering_ids` 재귀 스크러버 → `PRODUCT_TODAY_V1` 계약으로 내보낸다. 기존 `/api/*` 는 Cockpit 전용으로 보존.
- **Today 계약 (스펙 §5.1 강화)**: `trust strip → today-at-a-glance → hero horizon cards ×4 → selected movers → watchlist strip (subdued) → advanced disclosure` 레이아웃, hero 카드에 **grade chip (신호 강도 A+~F) + stance label (방향성) + confidence badge (데이터 품질)** 3축 분리 병치, CTA 주 "근거 보기" 는 **Today 내부 inline evidence drawer** 로 확장 (Research 하드 네비 없음), SVG hand-roll 스파크라인, 샘플 시 honest degraded 문구.
- **언어 계약**: `product_shell.*` 46 키 KO/EN parity + `test_agh_v1_patch_10a_copy_no_leak.py` 가 HTML/JS/CSS/DTO 4 면을 regex 스캔해 엔지니어링 토큰 / 권유 명령형 부재를 강제.
- **Research / Replay / Ask AI**: 10A 에서는 "곧 도착" 제품 톤 스텁 카드만 — 매수/매도 권유 문구 없음, 과장된 예측 확신 없음 (Spec §4.3, §5.1 준수). 10B 에서 정식 재설계.

상세: [`docs/plan/METIS_Product_Shell_Rebuild_v1_Spec_KR.md`](./METIS_Product_Shell_Rebuild_v1_Spec_KR.md), 운영 절차: [`docs/ops/METIS_Product_Shell_vs_Ops_Cockpit_Split_Runbook_v1.md`](../ops/METIS_Product_Shell_vs_Ops_Cockpit_Split_Runbook_v1.md).

---

## 4. 형태/기능적으로 아직 “제품 완성”에 남은 큰 것

1. **실검증 → 번들 스펙트럼 행** 자동 생성(지금은 게이트·pointer 중심; spectrum rows는 시드/데모 번들 의존 가능).  
2. **운영 단일 경로**: `build-metis-brain-bundle-from-factor-validation` 성공률·실패 리포트를 팀이 매일 볼 수 있게 CI/헬스에 고정.  
3. **Replay ↔ outcome**: 결정 ledger·알림과 **동일 message_snapshot_id**로 끝까지 조인 검증(이벤트 빌더 확장).  
4. **스펙 §7**: free-form 승격·registry 우회 방지 — 정책 테스트·리뷰 체크리스트.
5. **S&P 500 스케일 준비 (Patch 9 Scale Readiness Note 요약)**: Patch 8 F1/F3 closure 위에 Patch 9 가 **CF-8·A (packet/queue retention archive + server-side count RPC) + CF-8·B (target_scope JSONB 인덱스 + list_packets filter push-down) + CF-8·C (message snapshot lazy-generation)** 를 **실코드로 닫음**. 500 티커 **operational green (Patch 9)**: (a) `v2` 번들이 `production` tier, (b) `/api/runtime/health.health_status == ok` + `brain_bundle_tier == production`, (c) `brain_bundle_v2_integrity_failed == false`, (d) `panel_truncated_at_limit == false`, (e) `harness-retention-archive` 가 운영 주기로 돌고 있음 — 5 개가 green 이면 운영 시작 가능. 남은 Patch 10 후보: CF-8·D `_horizon_lens_compare` 번들 단위 캐시 (Today fan-out), CF-9·A `harness-retention-archive` 주기화 (Railway cron 또는 worker 사이드채널), CF-9·B production bundle graduation 의 Supabase r-branch 자동화. 상세: `docs/plan/METIS_Scale_Readiness_Note_Patch9_v1.md`.

---

## 5. 자동 점검 (런타임)

`GET /api/runtime/health` 응답에 **`mvp_product_spec_survey_v0`** 블록이 포함된다.  
CLI: `PYTHONPATH=src python3 src/main.py print-mvp-spec-survey --repo-root .` (CI: `--fail-on-false`).  
(자동 가능한 Q1–Q5 신호 + 나머지는 수동 증명 목록.)

---

## 6. 다음 스프린트(데모 문서 제외)

**Sprint “Brain surface truth”** (2주 압축 가정):

1. 검증 run → **spectrum row / artifact 메타**까지 번들 빌더 확장(또는 최소 1지평 E2E).  
2. Replay 타임라인 이벤트에 **registry_entry_id·message_snapshot_id** 필수화 및 테스트.  
3. `mvp_product_spec_survey` Q6–Q10을 가능한 범위에서 자동화(예: 샘플 API 스모크).

이 문서는 구현이 바뀔 때마다 버전을 올려 갱신한다.
