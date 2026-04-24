# Brain Surface Truth MVP — 현재 위치 (2026-04-16 이후)

**단일 목표**: Today/Research/Replay 세 표면을 **Metis Brain bundle + registry + message snapshot store** 라는 하나의 계약 위에 올리고, `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md` §10 의 Q1–Q10 이 **자동 spec survey** 에서 전부 `ok=true` 가 되게 한다. (Build Plan §14 수직 슬라이스, §12 항상 지킬 문장.)

## 2026-04-23 — Patch 12.1 — ES256 JWT REST Fallback + Magic Link Hash Fix (field hotfix)

> **Patch 12 를 실제 Supabase 프로젝트 (metisprism.up.railway.app) 에 배포하면서 발견된 두 가지 실전 이슈를 고정 패치.** (1) `emailRedirectTo` 에 `#callback` hash 를 붙여 보냈더니 Supabase 가 자기 토큰을 뒤에 덧붙여 `/login.html#callback#access_token=...` **이중 hash** 가 만들어지고 supabase-js 가 세션 파싱에 실패해 localStorage 에 세션이 남지 않음 → 로그인 루프. (2) 2025 년 이후 신규 Supabase 프로젝트는 기본 JWT 서명이 **ES256 (비대칭 키)** 이고 HS256 legacy secret 은 더 이상 기본이 아님 → Patch 12 의 stdlib-only HS256 verifier 가 `unsupported_alg` 로 거부. 가시 변화: magic link → 세션 파싱 성공 + ES256 토큰도 `/api/auth/session` / `/api/auth/me` 에서 정상 통과. Brain / Product DTO 계약은 여전히 0 byte 변경.

**Green run 실증 (Patch 12.1)**

- **Fix A — hash 단순화**. `src/phase47_runtime/static/login.js` 의 `emailRedirectTo` 를 `window.location.origin + "/login.html"` 로 바꿔 Supabase 가 `#access_token=...` 만 붙이도록 정리. 기존 `#callback` marker 는 login.js 로직상 불필요 (supabase-js `detectSessionInUrl: true` 가 자동 파싱).
- **Fix B — ES256 REST fallback (stdlib 유지)**. `src/phase47_runtime/auth/supabase_user_verify.py` 가 `urllib.request` 만 써서 `GET {SUPABASE_URL}/auth/v1/user` 에 `Authorization: Bearer <token>` + `apikey: <anon>` 로 토큰 유효성을 Supabase 에 위임 (ECDSA 검증을 Supabase 가 대신 수행). `src/phase47_runtime/auth/access_token_resolver.py` 의 `resolve_access_token` 이 로컬 HS256 verify → (실패 reason 이 `unsupported_alg` / `bad_signature` / `empty_secret` 일 때만) REST fallback 순서를 묶고 **정의 가능한 claim 위반 (expired / wrong_audience / malformed / missing_sub / missing_role / not_yet_valid) 에는 fallback 을 타지 않도록** 명시적 allowlist `_FALLBACK_TRIGGERS` 를 고정. `guard.py:require_auth` 와 `routes_auth.py:api_auth_session` 둘 다 기본 verifier 를 `resolve_access_token` 으로 전환. **auth-configured 판정** 도 (HS256 secret) OR (SUPABASE_URL + ANON_KEY) 로 확장 — 이전에는 HS256 secret 없으면 guard 를 무조건 graceful downgrade 했으나, ES256 + REST fallback 으로만 동작하는 Supabase 기본 프로젝트도 정상 auth-required 모드로 잡힘.
- **14 테스트 추가**. `src/tests/test_agh_v1_patch_12_1_es256_rest_fallback.py` 가 (1) REST verify 200 성공 + claims 형상, (2) `SUPABASE_URL` / `ANON_KEY` 미설정 시 `supabase_not_configured`, (3) HTTP 401/403 mapping, (4) empty token / missing sub 분기, (5) resolver HS256 성공 시 **REST 0-round-trip** (성능 보장), (6) `unsupported_alg` 시 fallback, (7) `bad_signature` 시 fallback, (8) `empty_secret` 시 fallback, (9) `expired` 시 **fallback 금지** (forgery 회피), (10) REST 미설정이면 원래 HS256 reason 유지, (11) REST 실패 시 `rest_<reason>` prefix 로 구분, (12) guard 가 HS256 secret 없이 anon-only 구성에서도 ES256 토큰 accept, (13) HS256/REST 둘 다 미설정이면 `auth_not_configured` graceful 유지 등 14 케이스 all green. **기존 Patch 12 테스트 62 건 + 새 14 건 = 76 / 76 all green**, 전체 2007 passed (사전 존재 phase39 실패 1 건 외 무관).

**운영 지침 변화**

- Supabase Dashboard 에서 Legacy HS256 secret 을 쓸 필요 없이 **기본 ES256 그대로** 사용 가능. `SUPABASE_ANON_KEY` 만 Railway 에 세팅되어 있으면 `/auth/v1/user` REST 로 검증됨.
- `SUPABASE_JWT_SECRET` 은 여전히 선택 사항 — 있으면 fast-path (local HS256) 로 무-네트워크 검증, 없으면 REST fallback 1-round-trip.
- `docs/ops/METIS_Private_Beta_Deployment_Runbook_v1.md` 의 env 표에서 `SUPABASE_JWT_SECRET` 을 "optional — only needed if your project still uses legacy HS256 signing" 으로 해석하면 된다. `SUPABASE_ANON_KEY` + `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` 3 개면 최소 구성 성립.

---

## 2026-04-23 — Private Beta: Invite-Only Auth + Account-Level Usage Tracking Patch 12 (plan `patch-12-private-beta-auth`)

> **Patch 12 는 온라인 전환 패치다 — Patch 11 까지 닫은 Brain 계약과 Product DTO 언어는 한 글자도 건드리지 않고, 제품 외부 경계 (인증 / 세션 / 이벤트 / 배포 / RLS) 만 추가했다.** 가시 제품 차이: (1) `/login.html` 에 이메일 한 줄 입력 + "Send secure sign-in link" 를 누르면 Supabase magic link 로 invite-only 로그인이 열리고, (2) 로그인한 beta 유저의 panel 전환 / Ask quick-chip / free-text / degraded banner 가 account-level 텔레메트리로 `product_usage_events_v1` 에 적재되며, (3) admin/internal role 유저만 `/ops` 에 새로 생긴 **Beta Admin** 탭에서 "초대 상태 · 최근 24h 세션 · 최근 7일 top events · trust signals" 를 본다. 데모 장면: invite 된 유저가 매직 링크 → `/` → Today → Research 로 이동하면 서버가 `session_started, page_view(today), research_opened` 3 건을 차곡차곡 쌓고, revoked 된 유저는 `/login.html` 에서도 `/api/auth/session` 이 401 `beta_revoked` 로 막힌다.

**Green run 실증 (Patch 12)**

- **M0 — DB 마이그레이션 + RLS + admin view**. `supabase/migrations/20260423100000_patch_12_private_beta_auth_tracking_v1.sql` 가 (1) `beta_users_v1 (user_id uuid pk → auth.users, email, status∈{invited,active,paused,revoked}, role∈{beta_user,admin,internal}, invited_at, activated_at, notes)`, (2) `profiles_v1 (user_id pk, display_name, company, timezone, preferred_lang∈{ko,en}, created_at, last_seen_at)`, (3) `product_usage_events_v1 (id, occurred_at, user_id, session_id, event_name, surface∈{today,research,replay,ask_ai,system,auth,admin}, route, asset_id, horizon_key∈{short,medium,medium_long,long}, result_state, lang∈{ko,en}, metadata jsonb)` 세 테이블과 3 인덱스 (`user_id+occurred_at desc`, `event_name+occurred_at desc`, `session_id`) 그리고 (a) `v_beta_users_active_v1` (status 별 count + 가장 최근 활성화 시각), (b) `v_beta_sessions_recent_v1` (최근 24h 유저 별 세션 수 + 첫/마지막 이벤트), (c) `v_beta_top_events_v1` (최근 7d event_name 별 count), (d) `v_beta_trust_signals_v1` (ask_degraded / sandbox_blocked / out_of_scope 카운트 + 전체 ask 대비 비율) 네 admin view 를 전부 idempotent 하게 설치. **RLS 정책**: `beta_users_v1` 은 유저가 자기 row SELECT + service_role 은 전부, `profiles_v1` 은 유저가 자기 row SELECT/UPDATE + service_role INSERT/전부, `product_usage_events_v1` 는 **SELECT/INSERT 모두 service_role only** — 유저는 직접 읽거나 쓰지 못하고 반드시 서버 `POST /api/events` 를 경유.
- **M1 — 서버 Auth 스택 (stdlib-only)**. `src/phase47_runtime/auth/jwt_verifier.py` 가 **외부 의존 0** 으로 HS256 JWT 를 검증 (header/payload/sig split → b64url decode → `hmac.compare_digest` constant-time 비교 + `aud/exp/iat/sub/role=authenticated` claim 체크) 하고 테스트용 `sign_hs256_for_tests` 를 제공. `supabase_rest.py` 는 stdlib `urllib.request` 기반 최소 PostgREST client (service_role 키로 select/insert/update, `supabase-py` 의존 0). `beta_allowlist.py` 는 `verify_user_is_active_beta(user_id, mode)` 를 `enforce` (revoked/paused 401) / `shadow` (로그만) / `off` (bypass) 3 모드 + 60 초 TTL in-memory 캐시로 제공. `guard.py` 의 `require_auth(method, path, headers)` 는 (a) OPTIONS 프리플라이트 bypass, (b) 공개 path 4 개 (`/api/runtime/health`, `/api/runtime/auth-config`, `/api/auth/session`, `/api/auth/signout`) bypass, (c) Bearer 누락 시 401 `missing_bearer`, (d) JWT verify 실패 시 401 `auth_invalid`, (e) beta 상태 에 따라 401 `beta_revoked` / `beta_paused`, (f) **`SUPABASE_JWT_SECRET` 미설정 시 graceful downgrade (ok=True, user_id=None)** 로 로컬/CI 를 전부 유지. `routes.py` `dispatch_json` 최상단에 가드가 박혀 모든 `/api/*` 가 동일 체크를 받는다. `user_id_alias(user_id) -> "bu_" + sha256[:12]` 는 raw UUID 가 DTO/로그/UI 에 0 회 노출되도록 모든 경로가 공유하는 단일 alias 함수.
- **M2 — Login UI + SPA bootstrap**. `static/login.html` + `login.css` + `login.js` 가 (1) supabase-js v2 ESM CDN (`https://esm.sh/@supabase/supabase-js@2`) 을 module script 로 import, (2) `/api/runtime/auth-config` 로 공개 anon_key + URL 만 가져와 `createClient`, (3) `signInWithOtp({email, options:{emailRedirectTo: window.location.origin + "/login.html#callback"}})`, (4) hash `#access_token=...` 감지 시 supabase-js 가 세션 복원 → `POST /api/auth/session` 로 서버 활성화 → `location.href = "/"` 로 이동. `static/auth_bootstrap.js` 는 Product Shell 첫 렌더 **전**에 세션 체크 → 없으면 `/login.html` 리다이렉트 + 있으면 **window.fetch 전역 래핑** 으로 모든 `/api/*` 에 `Authorization: Bearer <access_token>` 자동 주입 + `window.metisEmitEvent(name, meta)` 헬퍼 발행 (localStorage 에 브라우저 UUIDv4 session 발행 + `POST /api/events` 비동기 전송). `index.html` 은 `auth_bootstrap.js` 를 `product_shell.js` 앞에 prepend. `product_shell.js` 의 `setActivePanel` / `fetchQuickAnswer` / `postFreeText` 에 `metisEmitEvent` 훅을 얹어 `session_started / page_view / research_opened / replay_opened / ask_opened / ask_quick_action_clicked / ask_free_text_submitted / ask_answer_rendered / ask_degraded_shown` 를 기록.
- **M3 — Telemetry 인제스트 서버**. `src/phase47_runtime/telemetry/event_taxonomy.py` 가 **13-event allowlist** (`session_started, page_view, research_opened, replay_opened, ask_opened, ask_quick_action_clicked, ask_free_text_submitted, ask_answer_rendered, ask_degraded_shown, sandbox_enqueue_clicked, sandbox_request_blocked, out_of_scope_shown, hero_card_focused`) + `ALLOWED_SURFACES` (7) + `ALLOWED_HORIZON_KEYS` (4) + `ALLOWED_LANGS` (2) + `MAX_METADATA_BYTES=2048` 을 불변 상수로 고정. `telemetry/ingest.py` 의 `TelemetryIngestor` 는 (1) `strip_engineering_ids` 재사용으로 metadata 에 엔지니어링 slug 유입 차단, (2) session_id UUID shape 검사 (36 자 + hyphen 4 개), (3) surface/horizon/lang allowlist 검사, (4) unknown metadata key drop + 총 크기 2KB 초과 시 drop, (5) **in-memory sliding-window rate limit 100/min/user** (deque 사용, 100 건 정확 + 101 건째 429), (6) service_role 로 `product_usage_events_v1` insert. `POST /api/events` (단건) + `POST /api/events/batch` (최대 50 건, **partial save 금지** — audit-friendly: 한 건이라도 taxonomy 위반이면 전체 reject).
- **M4 — /ops Beta Admin 탭**. 기존 `/ops` (env-gated `METIS_OPS_SHELL=1`, customer 엔 404 유지) 의 utility nav 에 "Beta Admin" 버튼 + 전용 `<section>` 추가 (`static/ops.html`). `static/ops_admin.js` 가 클릭 시 `/api/admin/beta/{users,sessions,events,trust}` 4 API 를 병렬 호출해 (a) Invited users (status 별 count + 가장 최근 활성화), (b) Recent sessions (24h, 유저 별 세션 수 + 첫/마지막 이벤트), (c) Top events (7d, SVG hand-roll 바차트, 외부 라이브러리 0), (d) Trust signals (degraded/blocked/out_of_scope 비율 게이지) 4 섹션을 렌더. `routes_admin.py` 는 `beta_users_v1.role ∈ {'admin','internal'}` 만 통과 (beta_user → 403 `admin_only`), 모든 DTO 에서 raw user_id UUID 는 `bu_<12hex>` alias, 이메일은 `{local[0..2]}***@{domain}` 로 마스킹.
- **M5 — 7 테스트 + freeze + runbook**. `src/tests/test_agh_v1_patch_12_{jwt_verify,auth_guard,beta_allowlist,event_taxonomy,telemetry_ingest,admin_surface,copy_no_leak}.py` 7 파일 × 62 케이스 all green: (1) JWT verify 는 wrong-secret / expired / malformed / wrong-aud / missing-sub / wrong-role / forged header / empty secret 를 전부 거부, (2) auth guard 는 공개 path bypass + OPTIONS bypass + missing bearer 401 + valid bearer pass + no-secret graceful + revoked 403 + bad signature reject + `user_id_alias` 결정성 확인, (3) allowlist 는 invited/active/paused/revoked 4 분기 × enforce/off/shadow 3 모드 + lookup 실패 graceful, (4) taxonomy 는 13 allow / 임의 이름 reject / unknown metadata drop / session_id shape / surface/horizon/lang 검사, (5) ingest 는 단건 성공 / rate limit 경계 (100 정확, 101 429) / batch 성공+bad-event 전체 reject / telemetry-disabled flag / metadata sanitize, (6) admin 은 admin/internal pass + beta_user 403 + DTO alias 정확성 + 미설정 Supabase graceful, (7) no-leak 은 `/login.html` + `/login.js` 에 `SUPABASE_JWT_SECRET` / `SERVICE_ROLE_KEY` substring 0 + auth DTO 에 raw user_id/email/secret 0 + admin DTO 에 raw UUID 0 + email masked. `scripts/agh_v1_patch_12_beta_freeze.py` 가 `/login.html` + `login.css` + `login.js` + `auth_bootstrap.js` + `ops_admin.js` + auth DTO 3 + admin DTO 4 + SHA256 manifest 총 12 파일을 `data/mvp/evidence/screenshots_patch_12/` 에 저장 (all_ok=true). `scripts/agh_v1_patch_12_private_beta_runbook.py` 가 S1..S7 (valid auth 통과 / revoked user 401 / valid event ingest / invalid event 400 / rate limit 429 / admin RBAC / no-leak manifest) 전부 `all_ok=true`.
- **M6 — Evidence 6 + docs 5 + .env.example 5 key**. `data/mvp/evidence/` 에 (1) `patch_12_auth_flow_evidence.json` (magic link → session → /api/auth/me 단말 + graceful 시나리오), (2) `patch_12_beta_allowlist_evidence.json` (invited/active/paused/revoked × enforce/off 분기 판정), (3) `patch_12_event_taxonomy_evidence.json` (13 allow + 5 rejected sample + unknown key drop), (4) `patch_12_telemetry_ingest_evidence.json` (100 건 성공 + 101 건째 429 경계 + batch reject), (5) `patch_12_admin_surface_evidence.json` (admin/internal/beta_user 3 role 접근), (6) `patch_12_private_beta_runbook_evidence.json` (S1..S7) 6 건 기록. 문서 5: README (최상단 Patch 12 블록), HANDOFF (이 섹션), `docs/ops/METIS_Private_Beta_Deployment_Runbook_v1.md` (Supabase 마이그레이션 → Auth UI → Railway env → 첫 invite SQL → smoke test → rollback 9 단계 copy-paste), `docs/ops/METIS_Beta_Invite_Checklist_v1.md` (invite/activate/pause/revoke SQL + 확인 쿼리 + admin UI 대조), `docs/plan/METIS_MVP_PROGRESS_VS_SPEC_KR_v1.md` §3.9 (Brain 계약 불변 명시 + 외부 경계만 추가). `.env.example` 에 `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_AUTH_REDIRECT_URL`, `METIS_BETA_ALLOWLIST_MODE`, `METIS_TELEMETRY_ENABLED` 5 키 (모두 optional, 미설정 시 graceful downgrade) 주석과 함께 추가.

**환경 변수 (Patch 12 에서 추가 5 개, 모두 optional)**

- `SUPABASE_ANON_KEY` — supabase-js 가 magic link 를 시작할 때 쓰는 공개 키 (Project Settings → API → anon).
- `SUPABASE_JWT_SECRET` — 서버 HS256 verify 용 (Project Settings → API → JWT Settings). 미설정 시 auth guard graceful bypass.
- `SUPABASE_AUTH_REDIRECT_URL` — magic link redirect (예: `https://YOUR_APP.up.railway.app/login.html#callback`).
- `METIS_BETA_ALLOWLIST_MODE` — `enforce` (production) / `shadow` (stage) / `off`. 기본: `SUPABASE_URL` + `SERVICE_ROLE_KEY` 모두 있으면 enforce, 아니면 off.
- `METIS_TELEMETRY_ENABLED` — `1` 이면 `POST /api/events` 가 DB 에 insert, `0` 이면 no-op.

**Unified Product Spec §10 대비 갭 (Patch 12 이후)**

- Q1..Q12 모두 코드 수준 불변식 + no-leak 테스트로 여전히 pin. Patch 12 는 spec §10 에 새로운 question 을 **추가하지 않았고** (인증/배포는 제품 답안 차원이 아니라 운영 레이어), 대신 Product Spec §8 의 "MVP 비범위: 공개 signup / billing / 마케팅 사이트" 경계는 그대로 유지하며 invite-only 경계만 열었다.

**다음 단계 (Patch 13 후보)**

- Beta 초대 유저 실데이터 기반 stickiness 회고 (14 일 D7/D28 cohort).
- Custom SMTP (Resend/Postmark) 도입해 Supabase default 4 emails/hour 병목 해소.
- 필요 시 Railway scale > 1 대비 Redis 기반 rate-limit 이관 (현재는 단일 web dyno 기준).

---

## 2026-04-23 — Brain Bundle v3 / Signal Quality / Long-Horizon Truth Patch 11 (plan `brain-bundle-v3-11`)

> **Patch 11 은 Brain layer 로 올라가는 패치다 — 10A/10B/10C 에서 닫은 네 고객 표면의 "제품 언어" 는 건드리지 않고, 그 아래 Brain bundle 계약을 (1) long-horizon 근거의 정직한 tier, (2) residual-score 의미의 제품 쉘까지 실전 배선, (3) brain overlay (non-quant 보정) 의 공유 focus 노출, (4) Q11/Q12 (signal quality 누적 / long-horizon honest tier) 자동 spec survey 로 봉인했다.** 가시 제품 차이: (1) Today hero / Research deep-dive / Ask AI why-confidence 가 **같은 residual freshness 문구 + 같은 overlay note + 같은 long-horizon tier 라벨** 을 말하고, (2) 장기 구간의 `long` horizon 이 실제 근거가 부족하면 "sample" 로 정직하게 표기되고 제품 쉘은 그 tier 를 문자 단위 동일하게 반복한다. 데모 장면: "AAPL, 단기" focus 에서 Today → Research → Ask AI 를 왕복해도 ribbon 지문이 유지되고, `invalidation_hint=spectrum_position_crosses_midline` 이라는 raw slug 은 어디에도 나타나지 않고 대신 "중심선 크로스 시 재검토" 한 줄로 번역된다.

**Green run 실증 (Patch 11)**

- **M0 — Residual semantics 를 제품 쉘로 배선**. `src/phase47_runtime/message_layer_v1.py` 에 `residual_score_semantics_version`, `invalidation_hint`, `recheck_cadence` 3 키를 `MESSAGE_LAYER_V1_KEYS` 에 포함. `src/phase47_runtime/product_shell/view_models_common.py` 에 `RESIDUAL_WORDING` (KO/EN × `recheck`·`invalidation` 축, 5+6=11 버킷) + `normalize_recheck_cadence`·`normalize_invalidation_hint` (raw slug → controlled key) + `residual_freshness_block` (무누수 번역 헬퍼) 를 추가하고 `build_shared_focus_block` 에서 `block["residual_freshness"]` 로 노출. `compute_coherence_signature` 는 `recheck_cadence_key` + `invalidation_hint_kind` 를 지문 입력에 흡수해 residual semantics 변경이 12-hex 지문에 반영되도록 확장. `strip_engineering_ids` 는 raw slug (`monthly_after_new_filing_or_21_trading_days`, `spectrum_position_crosses_midline`, ...) 이 DTO 에 흘러들면 스크러빙하도록 regex 를 추가.
- **M1 — Long-horizon evidence 를 정직 tier 로**. 신규 `src/metis_brain/long_horizon_evidence_v1.py` 가 (1) `LongHorizonSupportV1` Pydantic 모델 (`contract_version, tier_key, n_rows, n_symbols, coverage_ratio, as_of_utc, reason`), (2) `classify_long_horizon_tier(coverage_ratio, n_rows)` — `production` (coverage ≥ 0.8 & n_rows ≥ 30) / `limited` (coverage ≥ 0.4 & n_rows ≥ 10) / `sample` 로 분기, (3) `summarize_long_horizon_support` / `summarize_long_horizon_support_as_dicts` — forward-returns raw panel 을 horizon 별로 집계, (4) `long_horizon_support_integrity_errors` — `horizon_provenance.source=real_derived` 인데 tier=sample 이면 "거짓말" 로 flag 를 제공. `src/metis_brain/bundle.py` 의 `BrainBundleV0` 에 `long_horizon_support_by_horizon: dict | None` 를 추가하고 `validate_active_registry_integrity` 가 integrity 검사를 호출. `view_models_common.long_horizon_support_note_block` + `SHARED_WORDING.long_horizon_support.*` (KO/EN × production/limited/sample 3 bucket) 이 제품 쉘에서 같은 라벨을 문자 단위로 반복.
- **M2 — Brain overlay 공유 focus 노출**. `view_models_common.overlay_note_block` 이 `bundle.brain_overlays` (non-quant 보정: catalyst window / regime shift / liquidity caveat / invalidation warning / counter-interpretation) 에서 현재 focus horizon 에 해당하는 항목을 가중평균 우선순위로 뽑아 `{dominant_kind_key, count, counter_interpretation_present, note_ko, note_en}` 로 요약. Today hero (via shared_focus) / Research `_evidence_cards` 의 counter_or_companion 카드 / Ask AI `_quick_answer` 의 `why_confidence` + `whats_missing` 가 동일 overlay note 를 consume 하되, 어느 표면도 `ovr_*` / `pcp_*` / `persona_candidate_id` / `overlay_id` / `brain_overlay_ids` 엔지니어링 ID 를 노출하지 않도록 `strip_engineering_ids` 에 5 개 regex 를 pin. `BRAIN_OVERLAY_WORDING` 는 5 개 kind 모두 KO/EN parity.
- **M3 — Q11/Q12 자동 spec survey 확장 (Q1..Q10 불변)**. `src/metis_brain/mvp_spec_survey_v0.py` 에 (1) `_q11_signal_quality_accumulation` — short/medium horizon 의 `residual_score_semantics_version` 커버리지가 `Q11_MIN_COVERAGE_SHORT_MEDIUM=0.8` 이상일 때 `ok=True`, (2) `_q12_long_horizon_honest_tier` — `long_horizon_support_by_horizon` 가 실제 provenance 와 일관되고 integrity errors 가 0 일 때 `ok=True`. `build_mvp_spec_survey_v0` 가 기존 Q1..Q10 뒤에 Q11, Q12 를 추가해도 Q1..Q10 의 `question_id`·순서·판단 로직은 건드리지 않음을 `test_agh_v1_patch_11_q11_q12_survey.py` 로 pin.
- **M4 — Ask AI 의미적 품질 golden-set + regression score**. `data/mvp/ask_semantic_golden_set_v1.json` 에 18 엔트리 (in_scope ground / in_scope counter / low_evidence / out_of_scope advice / out_of_scope off_topic / out_of_scope foreign_ticker 6 버킷 × KO/EN + edge). `src/tests/test_agh_v1_patch_11_ask_semantic_quality.py` 가 각 엔트리에 대해 `compose_ask_product_dto` / `compose_ask_quick_dto` / `compose_ask_free_text_dto` 를 실행해 `score = 0.4*grounded + 0.3*bounded + 0.3*useful` 를 계산, `regression_score >= 0.75` 와 `bounded_strict = 1.0` (매수/매도/가격 목표가가 `claim`/`evidence` 에 단 한 글자도 유출되지 않음) 를 단언. `scripts/agh_v1_patch_11_ask_semantic_regression.py` 가 오퍼레이터용 러너로 동일한 결과를 `patch_11_ask_semantic_golden_set_evidence.json` 에 기록.
- **M5 — No-leak / Coherence / Freeze / Runbook**. `src/tests/test_agh_v1_patch_11_copy_no_leak.py` 가 (1) 10A/10B/10C 금지 패턴 계승 + Patch 11 신규 (`ovr_*`, `pcp_*`, `persona_candidate_id`, `overlay_id`, `brain_overlay_ids`, residual raw slug), (2) `SHARED_WORDING` 중첩 구조 KO/EN parity (`residual.recheck/invalidation` × 5+6 버킷, `long_horizon_support` 3 버킷, `brain_overlay` 5 버킷, 기타 10 버킷), (3) 네 표면 DTO 가 raw slug·engineering ID 를 단 1 건도 노출하지 않음을 강제. `src/tests/test_agh_v1_patch_11_coherence_with_residual.py` 가 residual cadence 변경·invalidation hint 변경·overlay dominant kind 변경 각각이 12-hex 지문을 **바꿈**, 언어 변경은 지문을 **유지**, 네 표면 fingerprint 가 문자 단위 동일함을 단언. `scripts/agh_v1_patch_11_brain_truth_freeze.py` 가 `AAPL/short` 의 12 DTO (Today / Research Deep-dive / Replay / Ask Landing / Ask Quick / Ask Free-text Out-of-Scope × KO·EN) + `brain_truth_manifest_AAPL_short.json` 을 기록해 `all_ok=true, cross_surface_ok=true, engineering_id_leaks=[]` 확인. `scripts/agh_v1_patch_11_brain_truth_runbook.py` 가 S1..S7 (residual semantics → product shell / long-horizon honest tier / brain overlay propagation / Q11/Q12 survey / Ask semantic regression / no-leak + coherence / freeze manifest) 을 전부 green.
- **M6 — Evidence 6 + docs**. `data/mvp/evidence/` 에 `patch_11_brain_bundle_v3_evidence.json` (Brain Bundle 계약이 Patch 11 확장 3 필드를 모두 포함), `patch_11_long_horizon_truth_evidence.json` (tier 분류 3 케이스 + honest/lie integrity 2 케이스), `patch_11_signal_quality_accumulation_evidence.json` (Q11 pass / fail 2 시나리오), `patch_11_ask_semantic_golden_set_evidence.json` (18 엔트리 regression_score), `patch_11_brain_truth_runbook_evidence.json` (S1..S7 all_ok), `patch_11_brain_truth_bridge_evidence.json` (네 표면 coherence + no-leak 브리지) 6 건 기록. 문서 5 갱신: README / HANDOFF (이 섹션) / MVP_PROGRESS §3.8 / Shell Spec §12 (shared_focus 하위 블록) / `METIS_Residual_Score_Semantics_v1.md` (Product-shell 연결 섹션).

**환경 변수 (Patch 11 에서 추가 0 개)**

- 10A 에서 도입한 `METIS_OPS_SHELL` 만 유효. Patch 11 은 Brain bundle 계약과 product-shell 매퍼 확장만으로 동작 (신규 sandbox kind 없음).

**Unified Product Spec §10 대비 갭 (Patch 11 이후)**

- Q1..Q10 모두 코드 수준 불변식 + no-leak 테스트로 여전히 pin. Q11 (signal quality accumulation) / Q12 (long-horizon honest tier) **신규 추가** — Patch 11 의 산출 evidence 로 초록. 남은 후보는 production 규율 (real forward-returns 파이프라인 운영 안정성) 이며 Brain 계약 자체의 구조적 갭은 없음.

**다음 단계 (Patch 12 후보)**

- Real forward-returns production 파이프라인 규율 (rolling refresh / coverage drift alert).
- Research tile sparkline / Replay timeline 의 시각적 폴리쉬 (10A Today sparkline 패턴 재사용).
- Ops Cockpit 과 Product Shell 사이 message 1급 교차 (동일 message id 를 두 표면이 서로 다른 언어로 설명).

---

## 2026-04-23 — Product Shell Coherence / Trust Closure Patch 10C (plan `product-shell-10c`)

> **Patch 10C 는 seal patch 다 — 새 페이지·새 sandbox kind 를 만들지 않고, 10A+10B 에서 펼친 네 고객 표면이 "같은 focus 에 같은 진실을 같은 제품 언어로 말한다" 를 코드 수준 불변식으로 봉인했다.** 가시 제품 차이: (1) Research/Replay/Ask AI 상단에 **공통 focus ribbon** 이 같은 grade/stance/confidence chip + 네 표면 soft-link + coherence 지문을 보여주며, (2) Today hero 아래에 **cta_more soft-link** 가 추가돼 같은 구간의 Replay·Ask AI 로 포커스 유지한 채 이동할 수 있고, (3) Ask AI 는 **3 중 grounding guard (pre-LLM scope 분류 → surfaced-context 주입 → post-LLM hallucination 스캔)** 로 매수/매도 권유·화면에 없는 종목·가격 목표가 **단 한 글자도** 고객 DTO 에 새어나가지 않도록 닫혔다. 데모 장면: "AAPL, 단기" focus 로 Today → Research → Replay → Ask AI 네 패널을 왕복하면, 리본 우하단의 12-hex 지문이 모든 패널에서 같은 값으로 유지되고, Ask AI 에 "AAPL 지금 매수 추천해 주세요" 를 쳐도 LLM 호출 없이 "노출된 근거 밖의 질문입니다" 배너로 단락된다.

**Green run 실증 (Patch 10C)**

- **A — Cross-surface coherence 계약**. `src/phase47_runtime/product_shell/view_models_common.py` 에 (1) `compute_coherence_signature` — `(asset_id, horizon_key, 양자화된 position, grade_key, stance_key, source_key, digest(what_changed), digest(rationale_summary))` 로부터 **언어 독립적** 12-hex SHA-256 지문을 만들고 `contract_version="COHERENCE_V1"` (대문자 V — 스크러버가 소문자 `_v\d+` 를 지우는 것과의 충돌 회피), (2) `build_shared_focus_block` — 네 표면 모두가 **문자 단위 동일하게** embed 하는 single-source-of-truth 블록, (3) `SHARED_WORDING` — 10 버킷 (`sample`, `preparing`, `limited_evidence`, `production`, `freshness`, `bounded_ask`, `next_step`, `what_changed`, `knowable_then`, `out_of_scope`) 의 KO/EN 공통 카피 사전을 추가. `strip_engineering_ids` 는 지문과 `COHERENCE_V1` 을 **손대지 않음** 을 테스트로 pin.
- **B — Ask AI trust closure (3 단 grounding)**. `view_models_ask.py` 에 (1) `classify_question_scope` — advice (매수/매도/목표가/추천) / off_topic (옵션·파생) / foreign_ticker (화면에 없는 티커) / in_scope 로 분류 후 out-of-scope 는 **LLM 호출 전에** 단락, (2) `surfaced_context_summary` — 화면에 보이는 focus (grade/stance/confidence + evidence 한 줄 요약) 를 scrubbed 된 한 문단으로 묶어 `copilot_context.surfaced_evidence` + `bounded_contract` 지시어와 함께 `api_conversation` 에 주입, (3) `scan_response_for_hallucinations` — 반환 body 를 advice language / foreign ticker / price target 로 스캔, 1 건이라도 걸리면 **body 자체를 폐기** 하고 `partial` 로 downgrade. `src/tests/test_agh_v1_patch_10c_ask_golden_set.py` 가 7 분기 골든셋 (in_scope/advice/off_topic/foreign_ticker/low_evidence/degraded/hallucinating) 을 전부 green 으로 통과.
- **C — 네 표면 DTO 통합 배선**. Today (`compose_today_product_dto`) 는 각 hero card 에 `shared_focus + coherence_signature + cta_more` 를 embed 하고 strongest live 카드를 `primary_focus` 로 top-level 에 끌어올림. Research deepdive / Replay / Ask-landing / Ask-quick 는 top-level 에 `shared_focus + coherence_signature + evidence_lineage_summary + shared_wording + breadcrumbs` 를 통일된 키로 노출. `src/tests/test_agh_v1_patch_10c_coherence.py` 가 동일 focus 에 대해 네 DTO 의 `coherence_signature.fingerprint` 가 KO·EN 모두 **문자 단위** 동일함과 언어만 바꾸면 지문 불변을 단언; `rationale_summary` 변경 또는 grade-tier 를 건너는 position 이동은 지문을 바꿈을 추가 단언.
- **D — Ops ↔ Product 패리티**. `src/tests/test_agh_v1_patch_10c_ops_product_parity.py` 가 synthetic `api_governance_lineage_for_registry_entry` 페이로드 (proposal/decision/applied/spectrum_refresh/validation/sandbox request+result, 30 일 gap 포함) 를 만든 뒤 (1) Product Replay DTO timeline 의 non-gap event 수가 raw chain event 수와 일치, (2) `total_applied`/`total_sandbox_requests` summary 가 일치, (3) 원본 packet id (`pkt_*`) 와 engineering regex 가 DTO 에 단 한 글자도 노출 안됨, (4) outcome 라벨은 humanized localized (예: `blocked_insufficient_inputs` → "Sandbox blocked" / "사이드 실험 보류"), (5) gap annotation 이 실제 시간 공백과 일치함을 단언. view_models_replay 의 `_event_title` 을 `_normalize_outcome_for_title` 로 보강해 `blocked_insufficient_inputs` 류 모든 에러 파생을 "blocked" 로 일관화.
- **E — Focus continuity UI + 통합 breadcrumb**. `product_shell.js` 에 (1) `renderFocusRibbon(dto, surface)` — 같은 `(asset_id, horizon_key)` 에 대해 grade/stance/confidence chip + 네 표면 soft-link 버튼 그룹 + 12-hex 지문을 보여주는 persistent strip, (2) `ps-hero-card-softlinks` — Today hero 카드 하단에 cta_more (Replay/Ask AI) chip row 추가, (3) Research deepdive / Replay / Ask breadcrumb 를 `Today / <surface> / <ticker>` 로 통일. `product_shell.css` 에 `.ps-focus-ribbon` (data-source 에 따라 좌측 accent bar 가 live/preparing/sample 로 변함) + `.ps-hero-card-softlink` 컴포넌트 + 반응형 (≤640px 에서 세로 스택) 추가.
- **F — Language contract + 신규 locale 3 패밀리**. `phase47e_user_locale.py` 에 `product_shell.continuity.*` (10 키) + `product_shell.trust.*` (5 키) + `product_shell.ask.out_of_scope.*` (3 키) = 18 쌍 KO/EN parity. `src/tests/test_agh_v1_patch_10c_language_contract.py` 가 네 표면의 `shared_wording` 블록 존재 + preparing/sample 포커스 body 가 `SHARED_WORDING` 과 문자 단위 일치 + Ask AI out-of-scope banner title 이 공유 bucket 과 동일함을 강제. `test_agh_v1_patch_10c_copy_no_leak.py` 가 10A/10B 금지 패턴 계승 + 10C 내부 헬퍼 이름 (`_quantize_position`, `_short_hash`, `classify_question_scope`, `scan_response_for_hallucinations`) 도 UI/DTO 에 노출 0 + 3 로캘 패밀리 KO/EN parity 를 함께 강제. 141 파라미터 케이스 모두 green.
- **G — Freeze + Runbook + Evidence 6 건**. `scripts/agh_v1_patch_10c_product_coherence_freeze.py` 가 동일 focus (`AAPL/short`) 의 6 DTO × 2 언어 = 12 파일 + `coherence_manifest_AAPL_short.json` 을 `data/mvp/evidence/screenshots_patch_10c/` 에 저장 (manifest invariants 에서 4 표면 지문 완전 일치 확인). `scripts/agh_v1_patch_10c_product_coherence_runbook.py` 가 S1..S6 (cross-surface coherence / Ask trust closure / focus continuity UI / DTO refinement / language contract / no-leak+fingerprint) 를 전부 green. 산출 evidence 6: `patch_10c_product_coherence_{runbook,bridge}_evidence.json`, `patch_10c_{coherence,ask_trust_golden_set,cross_surface_alignment,language_contract}_evidence.json`.

**환경 변수 (Patch 10C 에서 추가 0 개)**

- 10A 에서 도입한 `METIS_OPS_SHELL` 만 유효. 10C 는 추가 env 없이 동작.

**Unified Product Spec §10 대비 갭 (Patch 10C 이후)**

- Q1 (Today registry-only), Q2 (message 1 급), Q3 (Research lineage), Q4 (Replay lineage), Q5 (Ask AI bounded), Q6 (Honest degraded), Q7 (Product language contract) **모두 코드 수준 불변식 + no-leak 테스트로 pin 됨**. Q8/Q9 (signal quality 누적 / 장기 관점 grid) 는 brain bundle 레이어의 Patch 11 후보.

**다음 단계 (Patch 10 종료, 11 대기)**

- LLM free-text 의 retrieval-grounded quality 의미적 평가 — real golden-set 누적 후 regression score. 현재 구조적 (pre/post guard) 은 봉인 완료.
- Replay timeline 선형 시간축 시각화 + Research tile sparkline 의 polish (10A Today sparkline 패턴 재사용 가능).
- Brain Bundle v3 — long-horizon rolling forward returns + residual score semantics 결합 (이미 진행중인 `pragmatic_brain_absorption_v1` milestone E 연장).

---

## 2026-04-23 — Product Shell Rebuild Patch 10B: Research / Replay / Ask AI 정식 재설계 (plan `product-shell-10b`)

> **Patch 10B 는 10A 위에 세 표면을 제품 언어로 올리는 패치다.** 10A 에서 분리한 `/` Product Shell 에 (1) horizon 그리드 + 종목 3-rail 디프다이브의 **Research**, (2) 타임라인 + 공백 주석 + 3 시나리오의 **Replay**, (3) 컨텍스트 카드 + 6 quick-action + retrieval-grounded 자유 입력의 **Ask AI** 를 정식으로 붙였다. 모든 DTO 는 `strip_engineering_ids` 를 마지막 방어선으로 통과하고, 내부 식별자 (`art_*`, `reg_*`, `factor_*`, `job_*`, `sandbox_request_id`, `process_governed_prompt`, `counterfactual_preview_v1`, `sandbox_queue`, raw provenance enum) 는 **제품 언어로 번역되거나 제거**된다. LLM 계층이 불가피하게 응답 못할 때는 `degraded` 배너로 전환되며, 절대로 매수/매도 명령형을 쓰지 않는다.

**Green run 실증 (Patch 10B)**

- **A — Research 매퍼 + 라우트**. 신규 `src/phase47_runtime/product_shell/view_models_common.py` 가 Today/Research/Replay/Ask 가 공유하는 `HORIZON_KEYS`, `strip_engineering_ids` (10B 금지 패턴 포함), grade/stance/confidence/peer helper 를 단일 소스로 제공. 신규 `view_models_research.py` 가 (1) `compose_research_landing_dto` → `PRODUCT_RESEARCH_LANDING_V1` (horizon 4 컬럼 × top-N 타일, 각 타일에 grade/stance/confidence/한 줄 요약/deep-link), (2) `compose_research_deepdive_dto` → `PRODUCT_RESEARCH_DEEPDIVE_V1` (claim / 5 evidence cards {what_changed, strongest_support, counter_or_companion, missing_or_preparing, peer_context} / 3 action chips {open_replay, ask_ai, back_to_today}). 없는 종목·구간이면 empty_state 로 정직하게 말함. `GET /api/product/research?presentation=landing|deepdive&asset_id=&horizon_key=` 가 dispatcher 에 등록.
- **B — Replay 매퍼 + 라우트**. 신규 `view_models_replay.py` 가 `api_governance_lineage_for_registry_entry` 의 governance chain + sandbox followups 를 (1) 타임라인 이벤트 (proposal/decision/applied/spectrum_refresh/validation_evaluation/sandbox_request/sandbox_result) 로 번역, (2) 30일 이상 공백은 `kind:gap` 주석 삽입, (3) 타임라인 시작/최근 상태를 `kind:checkpoint` 로 표기, (4) `_build_scenarios` 가 baseline / weakened_evidence / stressed 3 시나리오를 baseline position 에 ±shift 해 grade/stance 재계산. `advanced_disclosure` 는 원본 payload 를 노출하지 않고 "/ops 에서 확인" 만 가리킨다 — 고객 표면 누수 0. `GET /api/product/replay?asset_id=&horizon_key=` 가 dispatcher 에 등록. 하네스 스토어가 없으면 `_try_load_lineage` 가 None 을 리턴하고 empty_state 로 폴백.
- **C — Ask AI 매퍼 + 라우트 (LLM degraded-safe)**. 신규 `view_models_ask.py` 가 (1) `_focus_context_card` — 현재 보고 있는 종목/구간/grade/stance/confidence 를 한 카드로, (2) `_quick_answer` × 6 intent (`explain_claim, show_support, show_counter, other_horizons, why_confidence, whats_missing`) — 모두 **노출된 근거 안에서만** 결정론적으로 생성, (3) `scrub_free_text_answer` — `api_conversation` 을 래핑하되 호출 실패·빈 응답이면 `_degraded_answer` 구조체로 전환 (`grounded:false`, banner 로 명시), 모든 응답은 `strip_engineering_ids` 통과, (4) `compose_request_state_dto` — sandbox followups 를 `{status_key: running|completed|blocked}` 상태 카드로 번역. 4 개 라우트 `GET /api/product/ask`, `GET /api/product/ask/quick`, `POST /api/product/ask` (free-text), `GET /api/product/requests` 가 dispatcher 에 등록.
- **D — Visual system v2 (18 새 컴포넌트)**. `static/product_shell.css` 에 `.ps-research-landing`, `.ps-research-column`, `.ps-research-tile`, `.ps-research-empty`, `.ps-research-deepdive`, `.ps-breadcrumbs`, `.ps-rails`, `.ps-claim-card`, `.ps-evidence-rail`, `.ps-evidence-card`, `.ps-missing-badge`, `.ps-peer-chip`, `.ps-action-rail`, `.ps-action-chip`, `.ps-replay`, `.ps-replay-timeline`, `.ps-timeline-event`, `.ps-timeline-gap`, `.ps-timeline-checkpoint`, `.ps-scenarios`, `.ps-scenario-card`, `.ps-ask`, `.ps-ask-main`, `.ps-ask-context-card`, `.ps-ask-quick-grid`, `.ps-ask-action-chip`, `.ps-ask-freetext`, `.ps-ask-answer`, `.ps-request-state-card`, `.ps-advanced-drawer`, `.ps-tooltip` (info/caution/trust 3 variants) 를 추가. 10A 다크 프리미엄 톤, system UI stack, 외부 차트 라이브러리·폰트 네트워크 요청 없음을 유지. 반응형 (grid 는 1100px/820px/640px 에서 fallback).
- **E — JS 확장 (STATE.focus + hash routing + 패널 렌더러)**. `static/product_shell.js` 에 `STATE.focus = {asset_id, horizon_key}` + panel-별 `{loading, error, dto}` 섹션 추가. URL hash 형식 `#research?asset=AAPL&h=short` 를 `applyHash` / `updateHashFromState` 로 왕복 동기화 (브라우저 back/forward 지원). Today hero 카드의 secondary CTA "리서치 열기" 가 disabled 해제되어 `setActivePanel("research", {horizon_key: ...})` 로 연결되고, selected_movers 카드에 "자세히 보기 →" soft-link 가 추가돼 종목 deep-dive 로 바로 점프. 신규 렌더러 `renderResearchPanel` (landing horizon 그리드 + deep-dive 3-rail), `renderReplayPanel` (타임라인 + 시나리오 3 + advanced drawer), `renderAskPanel` (context + quick chips + free-text + answer + request-state side). `fetchQuickAnswer` / `postFreeText` 가 Ask API 를 호출, `POST /api/product/ask` 응답이 degraded 이면 구조화된 `_degraded_answer` 가 그대로 답변 영역에 렌더.
- **F — 로캘 60+ 키 KO/EN parity + 10B no-leak 스캐너**. `phase47e_user_locale.py` 에 `product_shell.research.*` 21 쌍, `product_shell.replay.*` 17 쌍, `product_shell.ask.*` 24 쌍을 추가 (총 KO/EN 동일 62 쌍). 신규 `src/tests/test_agh_v1_patch_10b_copy_no_leak.py` 가 (1) Product Shell HTML/JS/CSS + (2) Research/Replay/Ask DTO (landing, deepdive, replay, ask landing, ask quick, freetext degraded, request state) 를 스캔해 `art_*`, `reg_*`, `factor_*`, `pkt_*`, `job_*`, `sandbox_request_id`, `process_governed_prompt`, `counterfactual_preview_v1`, `sandbox_queue`, raw provenance enum, "buy/sell" 명령형이 **어디에도** 없음을 강제. 118 파라미터 케이스 모두 green.
- **G — Evidence + Freeze + Runbook + 회귀 그린**. `scripts/agh_v1_patch_10b_product_shell_freeze_snapshots.py` 가 Product Shell HTML/JS/CSS + DTO 샘플 14 개 (research landing/deepdive + replay + ask landing/quick + freetext degraded + request state, 각 KO/EN) + SHA256 manifest 를 `data/mvp/evidence/screenshots_patch_10b/` 에 기록. `scripts/agh_v1_patch_10b_product_shell_runbook.py` 가 S1..S7 (research mapper / replay mapper / ask mapper / CSS 18 컴포넌트 / JS state+renderers / locale+no-leak / routes dispatch) 을 코드 수준 플래그로 검증, 결과 7 개 `*_ok` + `all_ok` 전부 green. Patch 10A+10B 계열 테스트 7 개 파일 총 306 건 green (10A 테스트 188 + 10B 테스트 118).

**환경 변수 (Patch 10B 에서 추가 0 개)**

- Patch 10A 에서 도입한 `METIS_OPS_SHELL` 만 10B 에서도 유효. 10B 는 추가 env 없이 제품 경로 확장만으로 동작.

**다음 단계 (Patch 10C 후보)**

- Research / Replay / Ask AI 의 message_snapshot_v0 통합 (lineage_signature / today_snapshot_id 를 UI 전면에 노출하지 않고 DTO 안쪽에서 링크).
- `/api/product/ask` 의 LLM 계층이 실제로 붙었을 때 retrieval-grounded 응답 품질 평가 (golden set + 회귀 스코어).
- Ops Cockpit 과 Product Shell 사이 message 1급 교차 확인 (동일 message id 를 두 표면이 서로 다른 언어로 설명).

---

## 2026-04-23 — Product Shell Rebuild Patch 10A: 하드 2-파일 분리 + Today 재설계 v1 (plan `product-shell-10a`)

> **Patch 10A 는 "데모 광택 패치가 아니다".** 이번 패치의 목적은 기존 Phase 47 Cockpit 을 그대로 보존한 채 **사용자용 Product Shell 을 별도 `/` 로 분리**하고, 그 위에 Today 한 장을 **엔지니어링 언어 누출 없이** 올려두는 것이다. Research / Replay / Ask AI 는 10B 에서 정식 재설계하며, 10A 는 스텁 카드로 남긴다. 기준은 "UI 가 더 예쁘냐" 가 아니라 **"사용자가 첫 화면에서 엔지니어링 흔적 없이 '지금 무엇을, 왜, 얼마나 믿고 볼 수 있는가' 를 읽을 수 있느냐"** 이다.

**Green run 실증 (Patch 10A)**

- **A1 — 하드 2-파일 분리 + 라우팅**. `src/phase47_runtime/static/index.html` + `app.js` 를 **git mv** 로 `ops.html` + `ops.js` 로 이동. 신규 `static/index.html` + `product_shell.js` + `product_shell.css` 가 Product Shell 을 구성. `src/phase47_runtime/app.py` 라우터는 `/` → Product Shell (`static/index.html`), `/ops` → Ops Cockpit (`static/ops.html`), **`METIS_OPS_SHELL ∈ {1, true, yes}`** 일 때만 `/ops` 가 뜨고 그 외에는 404. 같은 도메인, 같은 프로세스, **두 경로**.
- **A2 — 신규 API 접두어 `/api/product/*`**. `src/phase47_runtime/routes.py` 가 `GET /api/product/today` 를 디스패치 (`api_product_today`) — Mapper 레이어를 거쳐 나온 `PRODUCT_TODAY_V1` DTO 를 그대로 반환. 기존 `/api/*` 는 불변으로 남아 Cockpit 바인딩 유지.
- **A3 — View-model mapper 레이어 신규**. `src/phase47_runtime/product_shell/view_models.py` 가 `compose_today_product_dto` (순수, 테스트용) / `build_today_product_dto` (디스크 로더 포함, API 라우트용) / `strip_engineering_ids` (재귀 스크러버, 마지막 방어선) 를 노출. 내부 매퍼 `_spectrum_position_to_grade(..., source_key=...)` / `_spectrum_position_to_stance(...)` / `_horizon_provenance_to_confidence(...)` 가 grade (신호 강도) / stance (방향성) / confidence (데이터 품질) 를 **3 축으로 분리**해 병치하고, 샘플 소스일 때는 grade 의 상한을 제한해 "샘플이 A+ 로 찍히는 사기" 를 차단.
- **B1 — Today 레이아웃 v1**. 위→아래 순서로 `trust strip` → `today at a glance` → `hero horizon cards ×4 (시각 1순위)` → `selected movers` → `watchlist strip (subdued)` → `advanced disclosure (접힘)`. Hero 카드에는 `grade chip` + `stance label` + `confidence badge` 가 한 행에 나란히 서고, 한 줄 스토리, 포지션 바 (매도-중립-매수), **SVG hand-roll 미니 스파크라인** (외부 차트 라이브러리 없음), 그리고 CTA 주 "근거 보기" 가 붙는다. 데이터가 부족할 때 스파크라인은 degraded placeholder 로 바뀌어 **샘플임을 말로 노출** 한다.
- **B2 — Inline Evidence Drawer (정제 R1 반영)**. Hero 카드의 1순위 CTA "근거 보기" 는 **Today 내부 evidence drawer 를 확장**한다 — Research 페이지로의 하드 네비게이션은 10A 에서 **disabled**. Drawer 는 "이 확신의 근거" / "가장 강한 지지 근거" 두 블록 + 최근 변화 bullet 을 제품 톤으로 보여줌.
- **B3 — Grade/Stance 분리 (정제 R2) + Watchlist Subdued (정제 R3)**. Grade chip (A+~F, 신호 강도) 과 stance label (강한 매수 경향 / 매수 경향 / 중립 / 매도 경향 / 강한 매도 경향, 방향성) 을 병치. Watchlist strip 은 유지하되 hero 카드 아래 `selected movers` 뒤에 배치하고, 캡션 사이즈 + subdued surface + 비인터랙티브 chip 으로 **시각 우선순위를 한 단 낮춘다**.
- **B4 — Research / Replay / Ask AI 스텁 3 패널**. 각각 "곧 도착" 안내 카드 + 한 문장 약속 + "지금은 Today 근거 보기로도 충분히 답을 드립니다" 문구. 매수/매도 권유 카피 없음, 과장된 예측 확신 없음 (Product Spec §4.3, §5.1 준수). 10B 에서 정식 재설계.
- **C1 — 비주얼 시스템 v1**. 신규 `static/product_shell.css` 가 `--ps-color-*` / `--ps-sp-*` / `--ps-fz-*` / `--ps-fw-*` / `--ps-radius-*` / `--ps-elev-*` design tokens + **8 우선 컴포넌트** (`.ps-hero-card`, `.ps-grade-chip`, `.ps-stance-label`, `.ps-confidence-badge`, `.ps-change-bullet`, `.ps-mini-sparkline`, `.ps-mover-card`, `.ps-watchlist-chip`, `.ps-disclosure-drawer`) 를 제공. 외부 폰트 네트워크 요청 없음 (system UI stack), 외부 차트 라이브러리 없음 (SVG hand-roll). Ops Cockpit 의 인라인 스타일은 **그대로 보존**.
- **C2 — 로캘 `product_shell.*` 46 키 KO/EN parity**. `src/phase47_runtime/phase47e_user_locale.py` 에 nav / loading / error / footer / trust strip / glance / hero CTA+tooltip / stance / confidence / movers / watchlist / disclosure / stub title 등 46 쌍을 추가. 누수 스캐너가 KO/EN 집합 parity 를 강제.
- **C3 — Honest Degraded 언어 계약**. 내부 provenance 를 제품 `source_key` 로 번역: `real_derived` → `live` ("실시간 데이터"), `real_derived_with_degraded_challenger` → `live_with_caveat` ("실시간 데이터 (일부 제한)"), `template_fallback` → `sample` ("샘플 데이터"), `insufficient_evidence` → `preparing` ("준비 중"). **샘플일 때 샘플이라고 말한다.**
- **D1 — No-leak 스캐너 확장**. `src/tests/test_agh_v1_patch_10a_copy_no_leak.py` 가 HTML (`static/index.html`) / JS (`product_shell.js`) / CSS (`product_shell.css`) / 실 DTO (`compose_today_product_dto` 출력) **4 면 전체** 를 regex 스캔해 `art_*`, `reg_*`, `factor_*`, `pkt_*`, `pit:demo:`, `real_derived*`, `template_fallback`, `insufficient_evidence`, `horizon_provenance`, `registry_entry_id`, `..._v\d+`, "buy/sell" 명령형 등 금지 토큰 부재를 강제.
- **D2 — Hard split + Visual system 테스트**. `src/tests/test_agh_v1_patch_10a_hard_split.py` 가 파일 분리, 라우팅, env gate (`METIS_OPS_SHELL`), API 디스패치를 검증하고 `http.server` + `urllib.request` 로 `/`, `/ops`, `/api/product/today` 3 경로를 실제 HTTP probe. `src/tests/test_agh_v1_patch_10a_visual_system.py` 가 design tokens 존재, 8 컴포넌트 클래스 존재, JS 마운트 포인트 (`__PS__` debug hook / `/api/product/today` 호출 / SVG 스파크라인) 를 확인.
- **Tests — 신규 10A 계열 + 회귀 업데이트**. Patch 10A 전용 테스트 4 개 파일 (DTO/Today shape, no-leak + parity, hard split, visual system) + 기존 Patch 6~9 회귀 테스트를 `static/ops.html` / `static/ops.js` 로 경로 업데이트. 전체 회귀 1425 green (`test_phase39_hypothesis_family.py::test_phase39_orchestrator_writes_artifacts` 1 건은 본 패치 이전부터 red, 범위 밖).
- **E1 — Freeze + Runbook 스크립트**. `scripts/agh_v1_patch_10a_product_shell_freeze_snapshots.py` 가 Product Shell HTML/JS/CSS + Ops HTML/JS + DTO 샘플 (KO/EN) + SHA256 manifest 를 `data/mvp/evidence/screenshots_patch_10a/` 에 기록. `scripts/agh_v1_patch_10a_product_shell_runbook.py` 가 S1..S10 (hard split / 라우팅 / 비주얼 시스템 / 매퍼 / DTO / no-leak / 로캘 parity / degraded 카피 / inline evidence / 스텁) 을 코드 수준 플래그로 검증, 결과 10 개 `*_ok` 플래그 전부 green.
- **E2 — Evidence JSON 6 개**. `data/mvp/evidence/patch_10a_{hard_split, today_redesign, visual_system, mapper_no_leak, product_shell_bridge, product_shell_runbook}_evidence.json` 6 개 파일이 각 scope 의 계약 + 잠금 지점을 코드 경로와 함께 기록.
- **F1 — 신규 문서 2 건**. `docs/plan/METIS_Product_Shell_Rebuild_v1_Spec_KR.md` 가 아키텍처 하드 2-파일 분리 + Mapper 레이어 + Today 표면 계약 + 언어 계약 + 비주얼 시스템 + 10B 진입 계약을 단일 스펙으로 명문화. `docs/ops/METIS_Product_Shell_vs_Ops_Cockpit_Split_Runbook_v1.md` 가 "/ vs /ops", env gate, 배포 체크리스트, 트러블슈팅, 롤백 절차를 단일 copy-paste 런북으로 제공.

**환경 변수 (Patch 10A 에서 추가 1 개)**

- `METIS_OPS_SHELL` — `1` / `true` / `yes` 일 때만 `/ops` 경로가 Ops Cockpit 을 노출. 미설정 = 404 (보안 기본값).
- 이전 Patch 8/9 의 `METIS_BRAIN_BUNDLE` / `AGH_WORKER_SLEEP` / `PORT` / `METIS_UI_INVOKE_ENABLED` / `METIS_HARNESS_LLM_PROVIDER` / `METIS_TODAY_SOURCE` / Supabase 3 종 / `EDGAR_IDENTITY` 등은 그대로. `.env.example` 이 매니페스트.

**다음 단계 (Patch 10B — Research/Replay/Ask AI 정식 재설계)**

- `/api/product/research`, `/api/product/replay`, `/api/product/ask` 라우트 + 매퍼 도입.
- Today 내부 evidence drawer → 종목 전체 근거 inline expand soft-link (페이지 이동 없이) 으로 Research 확장.
- Ask AI "근거 안에서만 답한다" 계약 (Retrieval-grounded) 명문화 후 오픈.

---

## 2026-04-21 — AGH v1 Patch 9: Productionize / Self-Serve / Scale Closure (plan `agh_v1_patch_9_productionize_self_serve_scale_closure`)

> **Patch 9 도 "demo-theater 패치가 아니다".** 이 패치의 목적은 Patch 8 에서 도입한 `v2` production bundle 을 **런타임 기본 경로**로 격상하고 (env override > v2 integrity-gated > v0 fallback, 그리고 v2 가 구조적으로 깨졌을 때는 조용히 덮지 않고 health degraded reason 을 낸다), Research invoke self-serve 드로어를 **실제 제품 모양**으로 다듬으며 (humanize 된 최근 요청 드로어, queued/running 에서만 뜨는 워커 tick hint, 2-column contract grid, 운영자 게이트를 말로 드러내는 copy hardening), Patch 8 Scale Note §4.3 의 이월 병목 중 **retention / packet lookup / message snapshot IO** 세 건을 실코드로 닫는 것이다. 동시에 production-tier integrity 네 가지 검사를 opt-in 으로 추가해 graduation 스크립트가 demo fingerprint 를 production 으로 승격하지 못하게 했다. 기준은 "demo 가 더 멋있느냐" 가 아니라 **"실제 배포 가능한 MVP+ 에 한 칸 더 가까워졌느냐"**이다.

**Green run 실증 (Patch 9)**

- **A1 — `brain_bundle_path()` env>v2>v0 auto-detect + quick integrity 게이트 + health 노출**. `src/metis_brain/bundle.py::brain_bundle_path` 가 `METIS_BRAIN_BUNDLE` env override > `data/mvp/metis_brain_bundle_v2.json` (quick integrity 통과 시) > `data/mvp/metis_brain_bundle_v0.json` fallback 순으로 해석. 신규 `_quick_integrity_ok(p)` 는 JSON 파싱 + 루트 객체 + 4 개 필수 root key + schema_version 타입만 보는 **저비용 구조 게이트** (full integrity 검사는 downstream loader 에서 한 번만 수행). 신규 `brain_bundle_integrity_report_for_path(repo_root)` 가 `override_used / resolved_path / v2_exists / v2_quick_integrity_ok / v2_integrity_failed / fallback_to_v0` 6 필드를 리턴. `src/phase51_runtime/cockpit_health_surface.py` 는 이 리포트를 `/api/runtime/health` 의 `mvp_brain_gate.*` 에 그대로 싣고, `v2_integrity_failed` 가 true 이면 `degraded_reasons.append("v2_integrity_failed")` 로 **조용히 덮지 않는다**. UI 는 `app.js::hydrateBundleTierChip` 에 fallback variant 를 추가해 v2 가 깨진 상태에서는 "번들: 폴백 (v0)" / "Bundle: fallback (v0)" 라벨 + `tsr-chip--degraded` 클래스로 정직하게 표시하고 tooltip 에 `resolved_path` + `degraded_reasons` 참조를 싣는다.
- **A2 — production-tier integrity hardening (4 checks)**. `validate_active_registry_integrity(bundle, *, tier=None)` 에 `tier` 키워드 도입. `tier='production'` 일 때만 `_production_tier_integrity_checks(bundle)` 가 추가로 (1) active/challenger 일관성 (self-challenger 금지, 미등록 challenger id 탐지), (2) horizon 별 spectrum rows ≥ 1, (3) tier metadata coherence (`graduation_tier` + `validation_pointer` 가 `pit:demo:*` / `stub_feature_set` / `deterministic_kernel` 로 시작하지 않음), (4) write evidence coherence (`as_of_utc` 비어있지 않음 + `metadata.source_run_ids` + `metadata.built_at_utc`) 4 건을 검사. 기본값 `tier=None` 은 Patch 8 이전 semantic 을 그대로 유지 (demo/sample 번들은 relaxed). `BrainBundleV0` 에 `metadata: dict[str, Any] = Field(default_factory=dict)` 필드 추가로 v2 번들의 build fingerprint 를 Pydantic 이 보존. `scripts/agh_v1_patch_8_production_bundle_graduation.py` 는 `build_mode == "live"` 일 때만 `tier="production"` 으로 검증을 호출해 template fallback 빌드는 demo fingerprint 를 들고도 통과.
- **A3 — Production bundle graduation runbook**. 신규 문서 `docs/ops/METIS_Production_Bundle_Graduation_Runbook_v1.md` 가 "graduation 이 Patch 9 에서 의미하는 것" → 3-tier 어휘 → pre-flight (Supabase evidence / git status / 현재 health) → build + verify (스크립트 출력 + /api/runtime/health 기대 필드) → **rollback** (disk 복원 / env override / v2 삭제) → 실패 모드별 복구표 → 알려진 한계 → sign-off 체크리스트를 단일 copy-paste 런북으로 제공.
- **B1 — Recent sandbox requests 드로어 (humanized summary + empty state)**. `app.js::renderRecentSandboxRequestRow` 로 추출된 per-request 드로어: (kind) sandbox_kind 사람 읽는 라벨, (result) produced_refs 요약 또는 premium empty copy, (blocking) blocking_reasons 리스트, (input) target/horizon/rationale, (next) lifecycle 상태별 hint (queued → "다음 워커 tick 에 집어갑니다", completed → "Replay 에서 lineage 확인", blocked → "차단 이유 해결 후 재적재"). 기존 raw JSON audit pane 은 expandable details 안쪽으로만 제한. `.tsr-req-drawer` CSS + 12 개 로캘 키 KO/EN 양쪽에 추가. empty state 카피는 action-oriented (`research_section.recent_requests_empty`).
- **B2 — Invoke 워커 tick hint (no background worker pretence)**. `app.js::applyWorkerHint(life)` 가 lifecycle state 가 `queued` 또는 `running` 일 때만 `[data-tsr-invoke-worker-hint]` 스팬을 표시하고, `completed` / `blocked` / `unknown` 에서는 숨긴다. 카피 `research_section.invoke_worker_tick_hint` 가 워커가 주기적으로 큐를 폴링하는 사실을 정직하게 서술 (KO "워커가 주기적으로 큐를 확인합니다" / EN "a background worker polls the queue periodically"). UI 가 즉시 실행·자동 승격 환상을 주지 않는다.
- **B3 — Contract card 2-column grid**. contract card 의 4 라인 (will do / will not do / after enqueue / status after) 이 `.tsr-contract-grid` CSS grid (2×2, 좁은 화면에서 1 컬럼 fallback) 로 재배치. 각 셀은 `.tsr-contract-cell-head` + `.tsr-contract-cell-body` 2단 구성. 신규 로캘 4 개 `tsr.invoke.contract.cell_head.{will_do, will_not_do, after_enqueue, status_after}`.
- **B4 — Self-serve copy hardening**. `phase47e_user_locale.py` 의 invoke 관련 키를 운영자 게이트·큐 기반·자동 승격 없음 구조로 재작성. `invoke_enqueue_btn` = "대기열에 적재 (운영자 게이트, 자동 승격 없음)" / "Enqueue (operator-gated, no auto-promotion)", `invoke_copy_hint` 는 운영자가 복사해 실행하는 흐름을 명시. 누수 스캐너(`test_agh_v1_patch9_copy_no_leak.py`)가 이 키들에 "운영자"/"operator", "대기열"/"queue", "워커"/"worker", "degraded_reasons" 키워드가 반드시 등장하도록 강제.
- **C·A — Retention / 아카이브 (CF-8·A 해소)**. 신규 마이그레이션 `supabase/migrations/20260420000000_agentic_harness_retention_archive_v1.sql` 가 `agentic_harness_packets_v1_archive` + `agentic_harness_queue_jobs_v1_archive` 두 아카이브 테이블 (원본 + `archived_at_utc`) 과 `public.agentic_harness_count_packets_by_layer_v1()` RPC 를 생성. 신규 모듈 `src/agentic_harness/retention/archive_v1.py` 가 `ArchiveReport` + `archive_packets_older_than(client, days=, batch_size=500, dry_run=False)` + `archive_jobs_older_than(...)` 를 노출: **copy-then-delete** 순서 (아카이브 insert 성공 후에만 active delete), **dry-run 기본 지원**, **잡은 terminal status 만** (done/dlq/expired; 라이브 큐 잡은 절대 아카이브 안 함), bounded batch (기본 500). 신규 CLI `python3 -m src.main harness-retention-archive [--days N] [--batch-size N] [--dry-run] [--skip-packets] [--skip-jobs]` 가 이 둘을 한 명령으로 실행. `supabase_store.count_packets_by_layer()` 는 이제 RPC 를 먼저 시도하고 실패시 Python-side 카운트로 fallback.
- **C·B — Packet lookup JSONB 인덱스 (CF-8·B 해소)**. 신규 마이그레이션 `supabase/migrations/20260420010000_agentic_harness_packets_target_scope_index_v1.sql` 가 `agentic_harness_packets_v1_target_asset_id_idx` (on `target_scope->>'asset_id'`) 와 `..._target_horizon_idx` (on `target_scope->>'horizon'`) b-tree 인덱스를 생성. `HarnessStoreProtocol.list_packets` 시그니처에 `target_asset_id` / `target_horizon` 옵션 파라미터 추가. `supabase_store` 는 `q.eq("target_scope->>asset_id", ...)` / `q.eq("target_scope->>horizon", ...)` 로 **DB 필터로 push down**. `fixture_store` 는 동일 의미론을 in-memory 에서 미러링. `agents/layer5_orchestrator.py::_collect` 는 `asset_id` 가 있고 `allow_asset_neutral=False` 일 때 이 파라미터를 DB 에 넘겨 전체 스캔을 피한다. `allow_asset_neutral=True` (broader set 이 필요한 경우) 는 기존 Python-side 필터 유지 (JSONB 단일 `eq` 는 OR semantic 을 표현 불가하므로).
- **C·C — Message snapshot lazy generation (CF-8·C 해소)**. `src/phase47_runtime/today_spectrum.py` 의 `build_today_spectrum_payload` 는 더 이상 `persist_message_snapshots_for_spectrum_payload(repo_root, out)` 를 호출하지 않는다 (hot path 에서 N 개의 row 각각에 대해 스냅샷 upsert 를 하던 비용 제거). 대신 신규 helper `persist_message_snapshot_for_spectrum_row(repo_root, payload, row)` 를 도입하고, `build_today_object_detail_payload` 가 해당 row 진입 시 **단 한 건**만 lazy persist. 전체 스윕 helper 는 backfill / 증거 스크립트를 위해 정의는 남겨둔다. 관련 기존 테스트 `test_metis_brain_v0.py::test_today_registry_only_no_seed` / `test_today_row_message_has_contract_fields` 는 "spectrum build 후 스냅샷 파일 없어야 하고, object-detail 진입 후에만 생긴다"는 새 계약으로 업데이트.
- **D1 — Bundle tier chip product-tone + fallback variant**. `tsr.bundle_tier.{fallback, fallback_tip}` 2 키 추가 + `tsr-chip--degraded` / `tsr-tier-chip--fallback` CSS. fallback tooltip 은 반드시 "degraded_reasons" 키워드를 포함해 운영자가 `/api/runtime/health` 에서 정확히 어떤 필드를 봐야하는지 알려준다.
- **D2 — Primary nav polish (feature 제거 0)**. `.nav-primary` 버튼은 폰트 0.82rem, weight 500, padding 0.4/0.75rem 으로 프로미넌스 증가. `.nav-utility` 는 opacity 0.62 (hover 0.92), padding-top/margin-top 을 늘리고 utility button 폰트 0.7rem 으로 **한 단계 뒤로**. Journal/Advanced/Reload/bundle-tier chip 전부 그대로 남아있고, `tsr.nav.utility.note` 카피만 "운영 유틸 · 감사/원본 데이터/번들 재로드" / "Ops utilities · audit, raw data, bundle reload" 로 교체.
- **D3 — KO/EN real-user wording review + no-leak scanner 확장**. `src/tests/test_agh_v1_patch9_copy_no_leak.py` 가 Patch 6 의 forbidden token 집합을 Patch 9 신규 내부 식별자 (`brain_bundle_v2_integrity_failed`, `target_asset_id`, `target_horizon`, `agentic_harness_count_packets_by_layer_v1`, `archived_at_utc`, `persist_message_snapshot_*` 등 16 개) 로 확장. 동시에 **real-user wording 요구사항** 4 건을 파라미터 테스트로 강제 (`invoke_copy_hint` → 운영자/operator, `invoke_enqueue_btn` → 대기열/queue, `invoke_worker_tick_hint` → 워커/worker, `bundle_tier.fallback_tip` → degraded_reasons).
- **Tests — 신규 26 건 + Patch 5/6/7/8 회귀 그린**. `src/tests/test_agh_v1_patch9_production_surface.py` (A1 5건 + A2 4건 + C·A 3건 + C·B 4건 + C·C 2건 + D1/D2 2건 = 20 건) + `test_agh_v1_patch9_copy_no_leak.py` (required_keys 1 + no_leak 1 + real_user_wording 4 = 6 건). 전체 1259 + 12 (research_phase5) = 1271 green (`test_phase39_hypothesis_family.py::test_phase39_orchestrator_writes_artifacts` 1 건은 본 패치 이전부터 red 인 기존 이슈, 본 패치 범위 밖).
- **F1 — S1..S11 Patch 9 runbook script**. `scripts/agh_v1_patch_9_production_graduation_runbook.py` 가 S1 bundle auto-detect / S2 integrity report + health / S3 production tier 4 checks / S4 graduation runbook 문서 / S5 recent-request drawer / S6 worker tick hint / S7 contract card grid / S8 self-serve copy hardened / S9 retention archive / S10 JSONB lookup / S11 snapshot lazy-gen 을 전부 코드 수준 플래그로 확인. 실행 결과 11 개 top-level flag 전부 green.
- **F2 — Patch 9 freeze snapshots**. `scripts/agh_v1_patch_9_demo_freeze_snapshots.py` 가 `data/mvp/evidence/screenshots_patch_9/` 아래 SPA 셸 + Today spectrum + Today detail (KO/EN) + `/api/runtime/health` (KO/EN) + `brain_bundle_integrity_report_for_path` payload 총 7 개 HTML + SHA256 manifest 를 기록.
- **F3 — Milestone_20 evidence JSON 7 개**. `data/mvp/evidence/agentic_operating_harness_v1_milestone_20_patch_9_{production_bundle_actualization, bounded_self_serve, scale_closure, surface_polish, tests, bridge, runbook}_evidence.json` 7 개 파일이 각 scope 의 계약 + 잠금 지점을 코드 경로와 함께 기록.
- **C3 — Scale Readiness Note Patch 9 (v1)**. 신규 문서 `docs/plan/METIS_Scale_Readiness_Note_Patch9_v1.md` 가 CF-8·A / CF-8·B / CF-8·C 세 건이 **실코드로 닫힌 상태** 를 기록하고, 남은 CF-8·D (horizon_lens cache) 를 Patch 10 범위로 이월한 뒤 **500 티커 operational green verdict 조건** 을 업데이트한다.

**환경 변수 (Patch 9 에서 추가 없음 — 기존 구성 그대로)**

- `METIS_BRAIN_BUNDLE` (선택) — A1 override. 설정 시 env override 가 모든 priority 를 이긴다. 미설정이 production 운영의 기본.
- 이전 Patch 8 에서 도입한 `AGH_WORKER_SLEEP` / `PORT` / `METIS_UI_INVOKE_ENABLED` / `METIS_HARNESS_LLM_PROVIDER` / `METIS_TODAY_SOURCE` / Supabase 3 종 / `EDGAR_IDENTITY` / 선택 OPENAI / ANTHROPIC / FMP 전부 그대로. `.env.example` 이 매니페스트.

**다음 단계 (Patch 10 후보 — Scale Readiness Note Patch 9 §4.3 참조)**

- `CF-8·D` — `_horizon_lens_compare` 결과 번들 단위 캐시. Today 응답에서 horizon 4개 × asset 500개 fan-out 증폭을 없앤다.
- `CF-9·A` — `harness-retention-archive` 를 Railway cron 또는 `worker:` 사이드채널로 주기화.
- `CF-9·B` — production bundle graduation 의 Supabase r-branch 자동화 (현재는 수동 운영자 트리거).

---

## 2026-04-21 — AGH v1 Patch 8: Production graduation / UX-AI wow / Scale closure (plan `agh_v1_patch_8_production_graduation_ux_ai_wow_scale_closure`)

> **Patch 8 은 "demo-theater 패치가 아니다".** 이 패치의 목적은 (1) AI 유용성을 눈에 보이게 올리고 (Research 4-stack의 *what changed* 가 LLM 계약에 등장, Today 히어로 스택이 4줄 요약으로 바뀜), (2) 운영자 마찰을 안전하게 줄이며 (샌드박스 큐 4-state 가시화, 최근 요청 compact list, action contract state slot), (3) S&P 500 운영 병목 상위 2건을 **실코드로** 닫고 (factor validation 배치 upsert + 번들 panel cache + evaluator single-reload), (4) 프로덕션 번들 graduation 을 도입해 `demo`→`sample`→`production` 3-tier vocabulary 로 실제 R-branch 번들이 올라올 수 있게 한 것. 동시에 Railway + Supabase 로의 hosted deployment 가 원클릭으로 가능하도록 했다. 이 패치의 기준은 "demo 가 더 멋있느냐" 가 아니라 **"실제 제품이 더 빠르고, 덜 위험하며, 더 똑똑하게 느껴지느냐"** 이다.

**Green run 실증 (Patch 8)**

- **A1 — Research 4-stack (what_changed + why_it_matters)**. `src/agentic_harness/llm/contract.py::ResearchAnswerStructureV1` 에 `what_changed_bullets_ko` / `what_changed_bullets_en` (`max_length=3`, locale-consistency validator) 추가. `src/agentic_harness/llm/guardrails.py::validate_research_structured_v1` 가 두 필드의 forbidden-copy 를 스캔하고 locale 일관성을 강제. `layer5_orchestrator.py::_SYSTEM_PROMPT` 가 LLM 에 "summary_bullets 와는 별도의 **What changed** 를 채우라" 고 명시. `app.js::renderResearchStructuredSection` 이 `current_read` 클러스터 최상단에 **What changed** 섹션을 렌더하고, 기존 "current read" 라벨은 **"Why it matters"** 로 graduation (3 개 새 로캘 키).
- **A2 — Today 히어로 4-row stack**. `app.js::renderTodayWhyNowConfidenceCaveatNextHtml` 신설: Today primary panel 안에 `tsr-why-now-stack` (Why now / Confidence band / Caveat / Next step) 4 줄 블록을 hero 라인 바로 아래 렌더. `data-tsr-jump-to-invoke` affordance 로 Research invoke card 까지 즉시 스크롤 이동.
- **A3 — Replay lineage step note + 30-day+ gap annotation**. `hydrateReplayGovernanceLineageCompact` 가 현재 frontier step 에 대해 `.tsr-step-note` 배너 (`lineage.step_note.current` / `.not_started`) 를 렌더. `renderReplayTimelinePlotSvg` 는 `GAP_THRESHOLD_MS = 30 day` 를 초과한 이벤트 사이 공백에 `.plot-gap-annotation` SVG 텍스트 (`lineage.gap_30d_plus`, `lineage.gap_annotation_prefix`) 를 삽입.
- **A4 + D1 — 로캘 "demo" → "sample" graduation + legacy alias**. `phase47e_user_locale.py` 의 모든 유저 노출 `(demo)` / `(데모)` 토큰을 **sample** 로 리네임 (`home.sample.*`, `spectrum.sample_title/_meta`, `sample.route.*`). 기존 `demo.*` 키는 `LEGACY_LOCALE_ALIASES` 에서 투명하게 새 키로 라우팅돼 3 개월 유예. 신규 테스트 `test_agh_v1_patch8_locale_graduation_no_leak.py` 가 향후 누수 차단.
- **A5 — Tooltip sub 에 what_changed / confidence 합성**. `extractTooltipContextFromTsr` 헬퍼 신설 → `what_changed_one_line` + `confidence_band` 파생. rail chip / lineage step / plot event 3 곳의 `tipSub` 에 일관 주입돼 hover 한 줄에 "출력 ≠ 재진술" 밀도를 확보.
- **B2 — 샌드박스 큐 4-state lifecycle 가시화**. `routes.py::api_sandbox_requests_list` 에 `_life_state` 헬퍼 도입: `sandbox_queue` 잡 상태 + `sandbox_results` outcome 을 결합해 `queued / running / completed / blocked` 4 개 canonical lifecycle 로 환원. UI 의 `tsrInvokePollState` 는 `applyChip` 으로 invoke status 와 contract card state slot 양쪽에 동일 칩을 mirror. `humanizeProducedRefs` 헬퍼가 `produced_refs` 배열을 사람-읽는 요약으로 축약.
- **B3 — 엔트리당 recent sandbox requests 리스트**. `hydrateRecentSandboxRequests` 가 `bounded_next` 카드 아래 `tsr-recent-sandbox-requests` 블록 (`research_section.recent_requests_head/.recent_requests_empty` 2 개 로캘 키) 을 렌더. 최근 5 건, 4-state 칩 + 확장 가능 audit details, enqueue 성공 직후 1회 auto-refresh.
- **B4 — Contract card 4번째 라인 + state slot**. contract card 를 `.will_do / .will_not_do / .after_enqueue / .status_after` 4 줄로 확장 (`tsr.invoke.contract.status_after` 1 개 로캘 키). 동일 카드에 `tsr-contract-state-slot` 을 넣어 `applyChip` 이 invoke/contract 양쪽에 동일 4-state 칩을 동기화.
- **C1 — Factor validation 배치 upsert + truncation 가시화 (Scale F1 해소)**. `src/db/records.py` 에 `upsert_factor_validation_summaries` / `upsert_factor_quantile_results` / `upsert_factor_coverage_reports` 3 개 배치 헬퍼 도입 (`on_conflict`). `src/research/validation_runner.py::run_factor_validation_research` 가 팩터 루프 바깥에서 in-memory 누적 → 테이블당 upsert 1회로 flush. `summary_json` 에 `panel_truncated_at_limit` / `panel_rows_fetched` 필드 신설 (Patch 7 에서 지적한 silent truncation 위험 가시화).
- **C2 — 번들 panel cache + evaluator single-reload (Scale F3 해소)**. `bundle_full_from_validation_v1.py` 에 per-invocation `_panel_cache` + `_resolve_shared_panels` 도입, `(universe, horizon_type)` 키로 동일 panel 을 반복 fetch 하지 않음. `layer4_promotion_evaluator_v1.py::evaluate_registry_entries` 에 `reload_between_specs` 파라미터 추가: **mutation 이 발생했을 때에만** 번들을 재로드.
- **D2 — `v2` production bundle graduation 스크립트**. `scripts/agh_v1_patch_8_production_bundle_graduation.py` 가 `metis_brain_bundle_build_v2.json` 기반으로 Supabase live build (또는 template fallback) → `validate_active_registry_integrity` 통과 시 **atomic** 으로 `data/mvp/metis_brain_bundle_v2.json` 을 쓰고 `data/mvp/evidence/pragmatic_brain_absorption_v1_production_bundle_v2_evidence.json` 에 SHA256 / bytes / 모드 / 에러 를 기록.
- **D3 — 3-tier vocabulary (demo / sample / production) + health tier + UI 뱃지**. `cockpit_health_surface.py::_infer_brain_bundle_tier` 가 metadata → filename → horizon provenance 순으로 tier 를 추론해 `/api/runtime/health` 의 `mvp_brain_gate.brain_bundle_tier` 로 노출. `index.html` 에 `#tsr-bundle-tier` 배지 placeholder 추가, `app.js::hydrateBundleTierChip` 이 시작 시 1회 hydration 해 `tsr.bundle_tier.*` 4 개 로캘 키로 무광 chip 렌더. 규약 문서: `docs/plan/METIS_Production_Bundle_Graduation_Note_v1.md`.
- **E1 — `harness-tick --queue <name>` CLI 필터 + `--loop --sleep` 워커 모드**. 스케줄러는 기존 queue class map 을 알고 있지만, CLI 에서 특정 큐만 소진하는 인자가 없었음. `src/main.py` + `agentic_harness/runtime.py` + `scheduler/tick.py` 를 통해 `queue_filter` 를 threading. Unknown queue class 는 `ok:false` CLI contract error. 동시에 `harness-tick --loop --sleep 30` 워커 모드를 도입해 Railway `worker:` 프로세스가 단일 엔트리포인트로 돌아가게 한다.
- **E2 — `/api/runtime/health` degraded 200 + reasons**. `build_cockpit_runtime_health_payload` 가 5 개 sub-step (summary / bundle load / overlays / spec survey / health text) 을 개별 try/except 로 감싸고 `degraded_reasons` 에 누적, `RUNTIME_HEALTH_STATUS_VALUES = ("ok", "degraded", "down")` 를 정립. HTTP 레이어는 `down` 만 503 으로 매핑하고 `degraded` 는 200. brain bundle 부재는 `brain_bundle_missing` 이유로 200 degraded 응답 (회귀 테스트 `test_e2_degraded_returns_200_in_practice`).
- **E3 — Railway / Supabase 배포 런북**. 신규 문서 `docs/ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md` 가 topology → prerequisite → Railway 프로젝트 생성 → env var 매니페스트 → web smoke test → worker 첫 tick → rollback → observability → known limitations 를 **단일 copy-paste 가능 런북** 으로 제공.
- **E4 — `Procfile` + `railway.json` + `.env.example`**. `Procfile` 이 `web:` (phase47_runtime app with `$PORT`) + `worker:` (`harness-tick --loop --sleep 30`) 2 줄. `railway.json` 은 `healthcheckPath=/api/runtime/health` + `startCommand=python3 src/phase47_runtime/app.py --host 0.0.0.0 --port $PORT`. `src/phase47_runtime/app.py` 는 `$PORT` 가 세팅된 경우 `0.0.0.0` 로 자동 바인드, 로컬 기본은 여전히 `127.0.0.1:8765`. `.env.example` 에 Railway / METIS_UI_INVOKE_ENABLED / AGH_WORKER_SLEEP 등 블록 추가.
- **Tests — 신규 48 건 + Patch 7 회귀 그린**. `src/tests/test_agh_v1_patch8_production_graduation_surface.py` (45 surface/contract tests covering A1/A2/A3/A5 + B2/B3/B4 + C1/C2 + D2/D3 + E1/E2/E4) + `test_agh_v1_patch8_locale_graduation_no_leak.py` (3 건). `_MemQuery.upsert` 배선으로 `test_research_phase5` 회귀 복구. 전체 1245 green (pre-Patch 8 부터 red 인 `test_phase39_hypothesis_family.py::test_phase39_orchestrator_writes_artifacts` 1 건은 본 패치 범위 밖, 별도 이슈).
- **F1 — S1–S8 production graduation runbook**. `scripts/agh_v1_patch_8_production_graduation_runbook.py` 가 S1 Research 4-stack / S2 Today hero stack / S3 invoke lifecycle + recent + contract slot / S4 factor batch upsert / S5 bundle cache + single-reload / S6 production tier + UI 뱃지 / S7 healthcheck degraded / S8 harness-tick queue + Railway deploy 를 전부 코드 수준 통과 플래그로 확인. 실행 결과 8 개 top-level flag 전부 green.
- **F2 — Patch 8 freeze snapshots**. `scripts/agh_v1_patch_8_demo_freeze_snapshots.py` 가 `data/mvp/evidence/screenshots_patch_8/` 아래에 SPA 셸 + Today (KO/EN) + Replay lineage + `/api/runtime/health` (KO/EN) + `ResearchAnswerStructureV1` JSON schema 총 7 개 HTML 프리즈 + SHA256 manifest 를 기록.
- **F3 — Milestone_19 evidence JSON 7 개**. `data/mvp/evidence/` 에 `agentic_operating_harness_v1_milestone_19_patch_8_{ux_ai_wow, bounded_self_serve, scale_closure, bundle_graduation, deployment, bridge, runbook}_evidence.json` 7 개 파일을 남겨 각 scope 의 계약과 잠금 지점을 코드 경로와 함께 기록.
- **C3 — Scale Readiness Note Patch 8 (v1)**. 신규 문서 `docs/plan/METIS_Scale_Readiness_Note_Patch8_v1.md` 가 Patch 7 노트의 F1/F3 가 **실코드로 닫힌 상태** 를 기록하고, 남은 F2/F4/F5/F6 중 본 패치가 건드리지 않은 것 (CF-8·A retention / CF-8·B JSONB 인덱스 / CF-8·C message snapshot 지연 생성 / CF-8·D horizon_lens cache) 의 Patch 9 범위 추정 + **500 티커 conditional green verdict** 를 제공.

**환경 변수 (Patch 8 에서 추가 2 개 + Railway 환경)**

- `AGH_WORKER_SLEEP` (optional) — `harness-tick --loop` 인터벌 초. 기본 30. Procfile 의 `--sleep` 와 함께 조정.
- `PORT` (Railway 주입) — `src/phase47_runtime/app.py` 가 자동 인식, 0.0.0.0 바인드. 로컬에서는 여전히 `PHASE47_PORT` (기본 8765) 가 우선.
- 기타 `METIS_UI_INVOKE_ENABLED` / `METIS_HARNESS_LLM_PROVIDER` / `METIS_TODAY_SOURCE` / Supabase 3 종 / `EDGAR_IDENTITY` / 선택 OPENAI / ANTHROPIC / FMP 등은 기존 그대로. `.env.example` 이 매니페스트.

**다음 단계 (Patch 9 후보 — Scale Readiness Note Patch 8 §4.3 참조)**

- `CF-8·A` — `agentic_harness_packets_v1_archive` / `agentic_harness_queue_jobs_v1_archive` + 야간 배치 + `count_packets_by_layer` 서버측 GROUP BY.
- `CF-8·B` — `agentic_harness_packets_v1 (target_scope->>'asset_id', target_scope->>'horizon')` 인덱스 + `list_packets` 필터 인자.
- `CF-8·C` — `persist_message_snapshots_for_spectrum_payload` 를 object-detail 진입 시 지연 생성으로 전환.
- `CF-8·D` — `_horizon_lens_compare` 결과 번들 단위 캐시.

---

## 2026-04-20 — AGH v1 Patch 7: Product hardening / UX depth / scale-readiness (plan `agh_v1_patch_7_product_hardening_ux_depth_scale_readiness`)

> **Patch 7 은 "demo-theater 패치가 아니다".** 작업지시서 `docs/plan/METIS_Patch_7_Workorder_Product_Hardening_UX_Scale_2026-04-20.md` §0/§10 을 그대로 인용하면, 이 패치는 **product hardening focused on real user experience, surface clarity, and scale-readiness toward broader universe coverage** 이다. Patch 6 가 "serious system → serious product" 전환의 **표면** 을 잡았다면, Patch 7 은 그 표면의 **깊이** 와 **스케일 준비도** 를 손본다.

**단일 목표 (추가)**: Patch 6 에서 닫힌 product-grade demo surface 위에, **심각한 베타 유저가 내부 툴이 아니라 제품으로 느끼게 하는 UX depth + bounded action 의 명시적 contract + 200→S&P 500 확장을 막는 concrete bottleneck 제거** 를 더한다. 이 패치의 기준은 "미팅에서 멋있어 보이느냐" 가 아니라 "실제 제품이 더 좋아졌느냐" 이다 (workorder §10). 사용자 결정: **IA 구조 = (A) 2-tier 네비게이션** (primary row = Today/Watchlist/Research/Replay/Ask AI, utility row = Journal/Advanced/Reload bundle) + UX 독보성은 Today/Research/Replay **안에서** 복잡한 정보를 입체적으로 읽히게 만드는 방식으로 확보.

**Green run 실증 (Patch 7)**

- **A1 — Information architecture 2-tier nav**. `src/phase47_runtime/static/index.html::<nav id="nav">` 을 `.nav-row.nav-primary` (Home/Watchlist/Research/Replay/Ask AI, `role="group"` + `data-nav-tier="primary"` + `aria-label`/`data-i18n-aria-label="tsr.nav.primary.aria"`) 와 `.nav-row.nav-utility` (Journal/Advanced/Reload bundle, 0.74rem font + 0.78 opacity + 상단 점선 border + 우측 정렬 + `tsr.nav.utility.note` 설명 스팬 + `tsr.nav.utility.aria`) 의 두 row 로 분리. **기능 제거 없음** — Journal/Advanced/Reload bundle 전부 동일 `data-panel` 연결 유지, 단지 시각 톤을 demote. `showPanel` 은 primary + utility 버튼 모두에 `active` 클래스를 일관 적용해 현재 panel 하이라이트 정상. 홈 피드의 Advanced/Journal jump 버튼은 `<button>` → `<a class="feed-utility-link" data-jump="...">` 로 강등 (`preventDefault()` wiring 유지). 로캘 3 키 (`tsr.nav.primary.aria` / `tsr.nav.utility.aria` / `tsr.nav.utility.note`) 를 KO/EN 양쪽에 추가.
- **A2 — Today typography + recent-activity mini-list + consolidated audit**. `index.html` 에 `--tsr-type-hero` (1.08rem/600/−0.01em) / `--tsr-type-subhead` (0.78rem/uppercase/0.05em) / `--tsr-type-body` (0.92rem/line-height 1.55) / `--tsr-type-foot` (0.72rem muted) 4개 CSS 토큰 + `.tsr-hero/.tsr-subhead/.tsr-body/.tsr-foot` 클래스 추가. `renderTodayPrimaryPanelHtml` 이 `<h2 class="tsr-hero">${asset_id} — ${one_line_take}</h2>` 로 히어로 라인을 제시하고, "Why now" / "What changed" 는 subhead + body 의 이중 그리드로 재구성 (locale 로캘 `tsr.primary.why_now_empty` 사용). 새 렌더러 `renderTodayRecentActivityHtml` 이 `registry_surface_v1.recent_governed_applies_for_horizon` 상위 3건을 `tsr-mini-row` (time-delta chip + `tsr-chip--apply` + `tsr-mini-arrow` from→to flow) 로 그려 evidence strip 안에 삽입. 기존 `<details>` 두 개 (raw identifiers + "Show legacy MIR detail (advanced)") 는 하단 **하나의** consolidated `<details class="tsr-audit">` (`tsr.audit.head`/`tsr.audit.note`) 로 접어 `renderTodayConsolidatedAuditHtml` 로 통합. primary-UI 에서 raw snake_case id 의 가시성은 Patch 6 에서와 동일하게 audit block 안으로만 제한 (D2 누수 스캐너가 정적 잠금 유지).
- **A3 — Research 3-cluster 재그룹 + evidence humanize + 제품 톤 locale 카피**. `renderResearchStructuredSection` 의 5 섹션 (`data-tsr-sec="current_read" / "why_plausible" / "unproven" / "watch" / "bounded_next"`) 위에 **3 cluster wrapper** 를 덧대 `data-tsr-cluster="current_read"` (current_read + why_plausible) / `data-tsr-cluster="open_questions"` (unproven + watch) / `data-tsr-cluster="bounded_next"` (bounded_next) 로 묶음. 기존 DOM 구조는 그대로 (테스트 backcompat), 시각적으로만 3 클러스터로 읽힘. `evidence_cited` 칩들을 packet kind 별 (`apply`/`proposal`/`evaluation`/`message`/`other`) 로 그룹핑해 사람 친화 라벨 + hover tooltip 으로 원래 packet kind 를 드러냄. `research_section.locale_degraded_label_*` 를 "부분 응답 / Partial response" 로 제품 톤 업데이트, 빈 상태는 `.tsr-empty--premium` + Ask AI jump CTA 로 premium empty state 제공. 모든 user-facing 문자열을 inline `isKo ? '…' : '…'` 에서 `tr(key)` 로 이관해 로캘 단일 출처화.
- **A4 — Replay timeline 3-lane + lineage step count/time-delta 풍부화**. `renderReplayTimelinePlotSvg` 를 **3 레인** 구조로 재작성: 레인 0 governed apply (`tsr-apply-color`) / 레인 1 spectrum refresh (`tsr-refresh-color`) / 레인 2 sandbox followup (`tsr-sandbox-color`). 좌측 92px 에 `plot-lane-label` 로 locale 라벨 (`plot.lane_apply/spectrum/sandbox`) 을 세로 정렬, 각 레인은 점선 guide, x 축은 t0/t1 날짜 라벨. `data-tsr-timeline-plot="3lane"` 으로 버전 표시. `hydrateReplayGovernanceLineageCompact` 는 steps 각각의 `created_at_utc` 를 추출해 이전 step 대비 **time-delta** (`tsrStepDeltaLabel` 이 `Xs/Xm/Xh/Xd` 포맷, `lineage.step_after` 템플릿 `+{delta} after previous` / `이전 대비 +{delta}`) 를 tooltip sub 에 실음. 4 step 중 done 수를 세서 **step count summary** (`.tsr-step-summary`, `lineage.step_count="{done} of 4 steps complete" / "4단계 중 {done}단계 완료"`) 를 step indicator 위에 배너로 노출. lineage/plot site 의 from_active_artifact_id → to_active_artifact_id 는 여전히 `humanizeActiveArtifactLabel` 로 사람 라벨.
- **A5 — Tooltip sub-line density 보강 (SUB_SEP multi-part split)**. `window.tooltipAt(x, y, label, sub)` 이 sub 문자열을 `" · "` (SUB_SEP) 로 분할해 각 파트를 별도 `<div class="tt-sub">` 로 렌더링. 즉 호스트는 `data-tsr-tt-sub="outcome · 2d ago · ART-old → ART-new"` 라고만 쓰면 툴팁이 3 줄로 표시. rail chip / lineage steps / timeline events 3곳의 sub 를 전부 multi-part 로 업그레이드: rail chip 은 `outcome · delta · from→to`, lineage steps 는 `outcome · delta`, plot events 는 `outcome · kind · delta · from→to`. hover 에서 "라벨만 재진술" 하는 툴팁이 "한눈에 읽히는 다차원 요약" 으로 진화. backcompat: sub 에 " · " 가 없으면 단일 라인으로 기존처럼 렌더.
- **B1 — Bounded invoke tr() wiring + server cli_hint/operator_note + one-time state polling**. Sandbox enqueue 클릭 핸들러의 모든 user-facing 문자열을 `tr(key)` 로 이관 (`research_section.invoke_state_queued/completed/blocked/unknown/loading`, `research_section.invoke_error_disabled/validation/server/raw` 9 키 추가). 서버 응답의 `cli_hint` + `operator_note` 를 그대로 표시해 harness-tick 명령의 단일 출처를 서버로 확정. 새 헬퍼 `tsrInvokePollState(wrap, requestPacketId)` 가 (a) enqueue 성공 1.5s 후 **1회** 자동 폴링, (b) operator 가 "큐 상태 새로고침" 버튼을 클릭할 때만 추가 폴링, (c) **background polling 없음** 으로 operator gate 정신을 준수. `/api/sandbox/requests?limit=10&registry_entry_id=...&horizon=...` 응답의 `result.payload.outcome` 에 따라 `queued`/`completed`/`blocked` (blocking_reasons 첫 줄 추가) 칩으로 표시, 403/400/500 은 제품 톤 에러 카피 + "원본 오류 세부" `<details>` 로 degrade.
- **B2 — Bounded action contract card (will_do / will_not_do / after_enqueue)**. Research 섹션의 invoke 버튼 **바로 위** 에 contract card 를 렌더 (`tsr.invoke.contract.head/.will_do/.will_not_do/.after_enqueue` 4 키). KO 카피: "수행: 샌드박스 큐에 bounded validation_rerun 요청 1건을 적재합니다. / 수행하지 않음: 활성 레지스트리 변경·아티팩트 승격·Today 화면 갱신은 하지 않습니다. / 적재 후: 운영자가 터미널에서 `harness-tick --queue sandbox_queue` 를 실행해야 샌드박스 워커가 돌아갑니다." 즉 이 액션의 **경계** 가 로그가 아니라 **액션 지점** 에서 보이게 한다 (workorder §5.B2).
- **C1 — Scale Readiness Note v1 (6 findings + S&P 500 verdict)**. 신규 문서 `docs/plan/METIS_Scale_Readiness_Note_Patch7_v1.md` 에 현재 ~200 ticker → S&P 500 확장을 막는 **6 개 findings** (F1 factor validation cadence row-by-row insert + silent-truncation / F2 governance_scan dedupe N+1 / F3 bundle joined-fetch 중복 / F4 Today payload unbounded + _horizon_lens_compare 반복 / F5 queue/packet retention 부재 + count full-scan / F6 research structured lookup linear scan) 을 현재 동작 + 500 ticker 예측 + Patch 7 에서 무엇을 고치는지 vs 왜 이월하는지로 기술. 마지막에 **evidence-based 500-ticker verdict** 로 "이미 충분한 것 / 여전히 막는 것 / 다음 concrete patch 범위 (CF-7·1..4)" 3 블록을 명시 (workorder §6.C3).
- **C2a — governance_scan dedupe N+1 hoist**. `src/agentic_harness/agents/governance_scan_provider_v1.py::deduplicate_specs` 가 기존의 per-spec `store.list_packets(ValidationPromotionEvaluationV1, ...)` 호출 (O(K) store reads per tick) 을 제거. 새 helper `_build_existing_evaluation_index(store, limit=max(200, 2*K))` 가 루프 밖에서 **단 1회** list_packets 를 호출하고 4-tuple 을 in-memory set 에 적재 → 루프 안은 O(1) 멤버십 체크만 수행. 의미는 기존 legacy `_existing_evaluation_matches` 와 동일 (동일 4-tuple 동등성). 기존 매일 tick 이 K=수십~수백 까지 커져도 store read 는 상수. 증거: `test_c2a_dedupe_hoists_list_packets_out_of_loop` 가 `inspect.getsource(deduplicate_specs).count('store.list_packets(') == 0` 로 잠금.
- **C2b — /api/today/spectrum rows_limit + total_rows + truncated**. `src/phase47_runtime/today_spectrum.py` 에 상수 `TODAY_SPECTRUM_DEFAULT_ROWS_LIMIT=200` / `TODAY_SPECTRUM_MAX_ROWS_LIMIT=1000`. `build_today_spectrum_payload(..., rows_limit: int | None = None)` 는 rows 를 rank/quintile/movement 계산이 **모두 끝난 뒤** 에 슬라이스 (top-N 이 rank 에 거짓말하지 않음), 응답에 `total_rows` + `truncated` + `rows_limit` 노출. `/api/today/spectrum` 가 `?rows_limit=N` (또는 `?limit=N`) 를 받아 min(N, 1000) 으로 캡. `build_today_object_detail_payload` 는 자산을 찾기 위해 `rows_limit=TODAY_SPECTRUM_MAX_ROWS_LIMIT` 를 명시 요청해 correctness 우선.
- **C2c — /api/replay/governance-lineage limit cap(500)**. `src/phase47_runtime/routes.py::REPLAY_LINEAGE_DEFAULT_LIMIT=200` / `REPLAY_LINEAGE_MAX_LIMIT=500`. `api_replay_governance_lineage(..., limit: int | None = None)` 가 `?limit=N` 를 min(N, 500) 으로 캡하고 응답에 `limit` 포함.
- **C2d — perf_counter stderr JSON 로그 4곳**. `_emit_perf_log(fn, ms, extra)` 헬퍼가 stderr 로 한 줄 JSON (`{"kind":"metis_perf","fn":"...","ms":..., ...}`) 를 흘림. 설치 site: `governance_scan_provider_v1.deduplicate_specs` (specs_in/specs_out/dropped/existing_index_size) / `today_spectrum.build_today_spectrum_payload` (horizon/source/total_rows/truncated) / `today_spectrum.build_today_object_detail_payload` (asset_id/horizon/ok) / `scheduler.tick.run_one_tick` (dry_run/cadences_ran/queues). Tracing 의존성 없이 `grep metis_perf harness-tick.log` 로 "무엇이 느린가" 즉답.
- **Tests — 신규 26 + 기존 회귀 green**. 신규 `src/tests/test_agh_v1_patch7_product_hardening_surface.py` 26 건 (A1 nav 3 / A2 typography+audit 7 / A3+B2 contract 3 / A4 timeline+lineage 3 / A5 tooltip 1 / C2 guardrails 3 / C2a dedupe hoist 1 / 기타 surface). Patch 6 회귀 green (`test_agh_v1_patch6_*` 49건 모두 pass), Patch 5 회귀 green (`test_agh_v1_patch5_*` + layer3/5 + harness + today/replay 등 19건 pass).
- **F1/F2/F3 — Runbook + freeze snapshots + milestone_18 evidence**. `scripts/agh_v1_patch_7_product_hardening_runbook.py` S1–S6 (IA 2-tier / UX depth 4 surfaces / invoke contract + gate / response-size guardrails / scale-safe defaults + perf instrumentation / scale readiness note) → `data/mvp/evidence/agentic_operating_harness_v1_milestone_18_patch_7_{bridge,runbook}_evidence.json`. `scripts/agh_v1_patch_7_demo_freeze_snapshots.py` → `data/mvp/evidence/screenshots_patch_7/` 에 `freeze_spa_index_patch_7.html` + KO/EN Today detail + Replay lineage 4 HTML + `sha256_manifest.json`. F3 focused evidence 3 건: `..._patch_7_ia_evidence.json` / `..._patch_7_invoke_evidence.json` / `..._patch_7_scale_evidence.json` 각각 workorder §4/§5/§6 을 1:1 로 map.

**안전 가드 재확인 (모두 honored)**

- **No LLM writes anywhere** — Patch 6 의 operator gate (`METIS_HARNESS_UI_INVOKE_ENABLED`) + worker-not-autostart 은 그대로. B2 contract card 가 이 사실을 **액션 지점** 에서 명시. `test_c2a / c2b / c2c` + Patch 6 enqueue 회귀 테스트가 gate 를 이중 잠금.
- **No fake autonomy language** — 모든 로캘 카피는 "적재 / enqueue / operator 가 ... 실행해야" 문구만 사용, "자동 실행" / "AI 가 직접 실행" 같은 표현 금지. D2 누수 스캐너 regression 유지.
- **No demo-only shortcuts bypassing canonical truth paths** — 모든 UI 변경은 기존 registry→bundle→payload 계약 위에서 형태만 다듬음. rows_limit/limit 는 cap 일 뿐, 기본 동작 호환.
- **No breadth expansion of sandbox kinds** — `SANDBOX_KINDS=('validation_rerun',)` 유지, Patch 6 CF-6·1 는 여전히 다음 패치로 이월.
- **No investor-only theater work** — 이 패치는 실제 베타 유저의 UX 깊이 + 스케일 준비도를 개선하는 것만 포함. 외부 데모용 영상 / 마케팅 packaging 0.
- **No cosmetic replacement of real bounded workflows** — contract card / state polling 은 bounded 흐름 을 **장식** 하는 것이지 **대체** 하지 않는다.

**다음 이월 (next patch 후보 — carry-forward)**

1. **CF-7·1 · Factor validation batch RPC + silent-truncation 제거** — `run_forward_returns_long_horizons_v1` 의 row-by-row Supabase insert 를 배치 RPC 로 전환하고 panel 길이 상한/경고를 명시. 500 ticker 에서 factor_validation_runs 의 실 스루풋을 올리는 가장 큰 수.
2. **CF-7·2 · Bundle panel-fetch dedupe + cache** — `build_metis_brain_bundle_v2` 의 패널 조회를 single-flight / in-memory cache 로 묶어 동일 factor 에 대한 반복 fetch 를 제거.
3. **CF-7·3 · Research structured (asset_id, horizon) 인덱스** — `_latest_research_structured_v1_for_asset` 의 200-row linear scan 을 packet_store 의 보조 인덱스 (또는 Supabase view) 로 치환.
4. **CF-7·4 · packet_store retention + queue counter cache** — `count_packets_by_layer` full-scan 제거 + 오래된 packet/queue job 의 archival 정책 도입. 500 ticker 에서 queue 가 축적되기 시작하면 필수.
5. **CF-6·* 계속 이월** — 추가 sandbox kinds / live 녹화 / research ask → enqueue UX one-click / 실 브라우저 스크린샷 네 가지는 Patch 6 의 CF 리스트에서 그대로 이월.

**환경 변수 (Patch 7 에서 추가 없음)**

Patch 6 의 `METIS_HARNESS_UI_INVOKE_ENABLED` 를 그대로 재사용. Patch 2–5 환경변수도 동일. SPA 쉘 구조 (vanilla JS SPA / `index.html` + `app.js`) 는 React/Next 도입 없이 그대로.

## 2026-04-19 — AGH v1 Patch 6: Demo freeze / product surface renderer / live evidence closure (plan `agh_v1_patch_6_demo_freeze_surface_renderer_live_evidence`)

**단일 목표 (추가)**: Patch 5 까지 닫힌 Brain / Research / Promotion 루프 위에 **investor / early-customer 심사 를 견딜 수 있는 product-grade bilingual demo surface** 를 얹는다. 즉 Patch 4 가 상류 (validation → governance), Patch 5 가 read-path + bounded sandbox 였다면, Patch 6 는 **"serious system" → "serious product"** 전환 단계 — Today 4-block 재구성, Research 5-section 렌더러, Replay governance lineage + SVG timeline plot, 로캘 정직성, operator-gated UI invoke, demo-freeze evidence 까지. **UI 는 기존 vanilla JS SPA 만 확장** (React/Next 신규 도입 금지), 패킷 계약은 surface UI 에 꼭 필요한 optional 확장만, 새 sandbox kind / provider / registry 신규 확장 없음. 사용자 결정: **Scope A = U (run_now — Supabase probe 로 R/D 분기)**, **Scope B = E (thin_endpoint — `POST /api/sandbox/enqueue` env-gated)**, Scope C (로캘 하드닝) 은 plan 기본값.

**Green run 실증 (Patch 6)**

- **A0 — Supabase 프로브 + R/D 분기**. 신규 `scripts/agh_v1_patch_6_supabase_probe.py` 가 `factor_validation_runs.status='completed'` 행 수를 count-only 로 조회해 probe evidence `data/mvp/evidence/agentic_operating_harness_v1_milestone_17_supabase_probe.json` 을 기록. 결과: `completed_run_count=25, branch=R, sample_run_id=7023235e-d0e6-4501-8f4d-af5b25857971`. **R branch** 가 실측되어 live 경로가 도달 가능함을 확정하되, demo-freeze runbook 은 side-effect 를 피하기 위해 evaluator/sandbox 라이브 쓰기는 Patch 4/5 runbook 으로 분리.
- **D1 — `ResearchAnswerStructureV1.locale_coverage` contract + guardrail + system prompt 하드닝**. `src/agentic_harness/llm/contract.py` 에 `LOCALE_COVERAGE_KINDS=('dual','ko_only','en_only','degraded')` + `locale_coverage: Literal[...] = 'dual'` 필드 추가. Pydantic `model_validator` 가 `dual` 인데 한쪽 bullet 이 비어있으면 `locale_claim_mismatch:dual_claim_but_missing_locale` 로 reject, `ko_only`/`en_only` 는 반대쪽이 반드시 비어야 함, `degraded` 는 양쪽 모두 비어야 함을 강제. `src/agentic_harness/llm/guardrails.py::validate_research_structured_v1` 에 동일 invariant 를 Pydantic 통과 전에 raw dict 수준에서도 점검해 template fallback 경로까지 막음. `layer5_orchestrator._SYSTEM_PROMPT` 에 "You MUST set research_structured_v1.locale_coverage honestly... Do NOT claim 'dual' while one side is empty; the guardrail will reject such silently-degraded responses" 블록 추가. Patch 5 CF (dual locale silent-degrade 허용) 이 이것으로 봉인.
- **E1 — `POST /api/sandbox/enqueue` operator-gated thin endpoint**. `src/phase47_runtime/routes.py::api_sandbox_enqueue_v1` 신설 + `dispatch_json` 배선. `METIS_HARNESS_UI_INVOKE_ENABLED=1` 일 때만 활성, 기본 403 (`error='ui_invoke_disabled'` + hint). 필수 필드 (`sandbox_kind`, `registry_entry_id`, `horizon`, `target_spec`, `rationale`, `cited_evidence_packet_ids`) 검증, `sandbox_kind ∉ SANDBOX_KINDS` / `target_spec` missing / rationale 길이 (1–500) / cited 비어있음 전부 400. Happy path 는 `enqueue_sandbox_request` 로 위임해 `SandboxRequestPacketV1` + `sandbox_queue` job 생성, 200 응답에 `cli_hint='harness-tick --queue sandbox_queue'` + operator_note 포함. **worker 는 endpoint 에서 절대 자동 실행되지 않음** (evidence 로 `worker_ran_autonomously=false` 잠금). `requested_by` 기본값을 `SANDBOX_REQUEST_ACTORS=('operator','research_ask_v1')` 안의 `operator` 로 교정해 Patch 5 packet enum 과 정합.
- **B1 — Today 4-block 렌더러**. `src/phase47_runtime/static/app.js::renderTodayObjectDetailHtml` 을 **summary rail (chips) → primary panel (why now / what changed) → decision stack (progressive disclosure `<details>`) → evidence strip (active artifact + collapsible raw IDs)** 4-block 으로 재구성. 각 블록은 `renderTodaySummaryRailHtml` / `renderTodayPrimaryPanelHtml` / `renderTodayDecisionStackHtml` / `renderTodayEvidenceStripHtml` 전용 헬퍼로 분리, 기존 `mir-block` 기반 상세는 하단 `<details>` 로 수납해 legacy 호환. raw 엔지니어링 id (`active_artifact_id` / `registry_entry_id` / `message_snapshot_id`) 는 **audit-only helper** `renderTodayEvidenceRawIdsAuditHtml` 로 추출되어 primary UI 에서는 절대 노출되지 않음.
- **B2 — Research 5-section 렌더러 + E2 invoke UI**. 신규 `renderResearchStructuredSection(j, lang)` 이 `research_structured_v1` 을 읽어 **current read / why plausible / unproven / watch / bounded next step** 5 섹션을 `<div data-tsr-sec="...">` 로 렌더. `locale_coverage` 는 `tsr-research-coverage` 배지 (`dual` / `ko_only` / `en_only` / `degraded` 각각 툴팁) 로 정직하게 표기. bounded-next-step 섹션은 2-mode 조작 UI — 기본 (UI invoke 비활성) 은 `harness-sandbox-request ...` CLI 전체를 `<div class="invoke-cli">` 로 표시 + "Copy" 버튼, `?ui_invoke=1` URL 파라미터 또는 `window.__metisUiInvokeEnabled=true` 설정 시 "Enqueue via UI (operator-gated)" 버튼이 추가로 붙어 E1 endpoint 로 POST 전송. Today payload 에 `research_structured_v1` 이 들어가도록 `src/phase47_runtime/today_spectrum.py::_latest_research_structured_v1_for_asset` 헬퍼가 harness store 의 `UserQueryActionPacketV1` 최신 1건을 자산/수평선별로 best-effort 조회 (없으면 `None` 반환해 empty state 렌더).
- **B3 — Replay governance lineage compact + step indicator**. `renderReplayGovernanceLineageCompactHtml` (sync placeholder) + `hydrateReplayGovernanceLineageCompact` (async fetcher) 가 `/api/replay/governance-lineage?registry_entry_id=...&horizon=...` 를 호출해 **proposal → apply → spectrum refresh → validation eval** 4 단계를 `tsr-step-indicator` 로 그리고, 총 applies / sandbox completed / needs_db_rebuild 칩을 요약으로 제공, sandbox followups 3건을 컴팩트 리스트로 붙임. 빈 계보/로드 실패는 각각 `lineage.unavailable` / `lineage.load_failed` 로캘 메시지로 degrade.
- **B4 — Progressive disclosure CSS + premium empty state + motion guard**. `src/phase47_runtime/static/index.html` 의 embedded style block 에 `tsr-rail / tsr-chip / tsr-primary / tsr-decision / tsr-evidence / tsr-research / tsr-research-coverage / tsr-research-invoke / tsr-step-indicator / tsr-timeline-plot / tsr-tooltip / tsr-empty` 를 전부 추가. `<details>` transition + hover affordance 적용, empty/blocked/deferred 는 `.tsr-empty` 로 premium muted 스타일, `@media (prefers-reduced-motion: reduce)` 가드로 애니메이션 비활성.
- **C1 — Replay timeline SVG plot**. 새 라이브러리 의존성 없이 inline SVG (`<svg class="tsr-timeline-plot">`) 를 생성하는 `renderReplayTimelinePlotSvg(latestChain, followups, isKo)` 를 작성. governed apply 는 수직선 + `apply` 라벨, spectrum refresh 는 원형 마커, sandbox followup 은 아래쪽 tick 으로 표현하고 각 요소에 `data-tsr-tt-label` / `data-tsr-tt-sub` 가 붙어 C2 툴팁으로 날짜/outcome/전이 정보를 드러냄. `from_active_artifact_id → to_active_artifact_id` 는 `humanizeActiveArtifactLabel` 로 사람이 읽을 수 있는 라벨로 변환해 raw id 누수를 막음.
- **C2 — tooltipAt() 공용 primitive + label-not-dump 룰**. 신규 IIFE `tsrInstallTooltip()` 가 `window.tooltipAt(el, {label, sub})` / `window.tooltipHide()` 를 설치하고 delegated listener (mouseover/mousemove/mouseout) 로 `[data-tsr-tt-label]` 마크가 붙은 임의 요소에 공용 툴팁을 띄움. 라벨은 짧은 사람 친화 카피 + 선택적 서브 1줄 규칙 (raw payload 덤프 금지).
- **D2 — `tsr.*` 로캘 strings + 엔지니어링 용어 누수 스캐너**. `src/phase47_runtime/phase47e_user_locale.py::SHELL` 의 KO/EN 양쪽에 `tsr.rail.* / tsr.primary.* / tsr.decision.* / tsr.evidence.* / research_section.* / lineage.* / plot.*` 시리즈 **56 키씩** 추가 (demo-freeze evidence 로 잠금). 신규 테스트 `test_agh_v1_patch6_copy_no_leak.py` 10건이 (a) `REQUIRED_TSR_KEYS` 가 양 locale 에 전부 존재, (b) `FORBIDDEN_ENG_TOKENS` (`registry_entry_id`, `active_artifact_id`, `factor_validation_run`, `sandbox_kind`, `research_structured_v1`, `horizon_type`, `return_basis`, `message_snapshot_id` 등) 가 tsr prefix 로캘 값 + `renderTodaySummaryRailHtml` / `renderTodayPrimaryPanelHtml` / `renderTodayDecisionStackHtml` / `renderTodayEvidenceStripHtml` / `renderResearchStructuredSection` / `hydrateReplayGovernanceLineageCompact` / `renderReplayTimelinePlotSvg` 함수 **바디의 primary-UI 문자열 리터럴** (template expression `${...}` / `<details>` audit 블록 / URL 페이로드 제외) 어디에도 노출되지 않음을 정적 스캔으로 잠금.
- **Tests — 신규 44 + 기존 Patch 5 / L3 / L5 회귀 green**. 신규: `test_agh_v1_patch6_locale_coverage.py` (10 — dual/ko_only/en_only/degraded 허용·거부, guardrail, system prompt 검증), `test_agh_v1_patch6_sandbox_enqueue_endpoint.py` (7 — disabled=403, missing_fields / bad kind / empty cited / short rationale / incomplete target_spec = 400, happy path=200 + worker-not-ran), `test_agh_v1_patch6_copy_no_leak.py` (10 — locale key 존재 + 7 renderer 토큰 누수 없음), `test_agh_v1_patch6_today_research_structured_plumbing.py` (4 — empty asset / store 실패 / latest-wins / malformed packet skip), `test_agh_v1_patch6_ui_renderer_surface.py` (13 — 4-block 헬퍼·호출 순서, research 5 섹션, locale_coverage 배지, replay compact+api wiring, timeline SVG, tooltip globals, E2 data-* 속성, CSS primitive + reduced-motion). **Patch 5 회귀 green** (`test_agh_v1_patch5_*.py` 64건 + layer3/5 + harness e2e 31건 + today_spectrum / traceability / phase47 69건 전부 pass), repo 전체 **1,169 pass / 1 pre-existing failure** (`test_phase39_orchestrator_writes_artifacts` — Patch 2 이전부터 있던 Patch 6 무관 실패).
- **F1 — Demo-freeze runbook S1–S6**. `scripts/agh_v1_patch_6_demo_freeze_runbook.py` 가 다음 6 시나리오를 in-process 로 실측 → `data/mvp/evidence/agentic_operating_harness_v1_milestone_17_runbook_evidence.json` 에 기록: **S1** Supabase probe 결과 (branch=R, completed_run_count=25, sample_run_id 포함), **S2** `LOCALE_COVERAGE_KINDS` 4가지 round-trip + `silent_dual_claim_with_empty_ko_blocked=true` + `system_prompt_mentions_locale_coverage=true`, **S3** `/api/sandbox/enqueue` disabled=403 / enabled=200 + `worker_ran_autonomously=false` (operator gate 확인), **S4** `_latest_research_structured_v1_for_asset` 가 주입된 `UserQueryActionPacketV1` 을 자산별로 최신 1건 pick 해 `locale_coverage='dual'` 반환, **S5** UI 렌더러 컨트랙트 (9 renderer fn + 11 CSS primitive 모두 present, reduced-motion=true, tsr locale key 56/56), **S6** live 분기는 `branch=R, status='live_branch_reachable_dry_only'` 로 capture (sample run metadata 포함, 실제 write 는 Patch 4/5 runbook 으로 분리 — `live_write_intentionally_skipped=true`).
- **F2 — Demo-freeze HTML snapshots + sha256 manifest**. `scripts/agh_v1_patch_6_demo_freeze_snapshots.py` 가 `data/mvp/evidence/screenshots/` 에 **4개 HTML snapshot** (SPA shell 복사본 `freeze_spa_index.html`, Today object detail KO/EN `freeze_today_object_detail_*.html`, Replay governance lineage `freeze_replay_governance_lineage_demo.html`) + `sha256_manifest.json` (각 snapshot 의 sha256 + 바이트 + SPA shell source sha256) 를 생성. 라이브 브라우저 의존성 없이 canonical API 페이로드를 audit-friendly 포맷으로 고정해 demo freeze 시점의 상태를 재현 가능.
- **F3 — Milestone 17 bridge + runbook evidence**. `data/mvp/evidence/agentic_operating_harness_v1_milestone_17_bridge_evidence.json` (code-shape contracts — `locale_coverage_kinds`, `sandbox_kinds_patch_6`, `ui_invoke_env_gate`, tsr locale key count, required renderer/css present) + `...milestone_17_runbook_evidence.json` (S1–S6 실측) 2 파일 write. A0 probe evidence 는 `...milestone_17_supabase_probe.json` 로 별도 고정.

**안전 가드 재확인 (모두 honored)**

- **No LLM writes anywhere, even UI-driven** — `POST /api/sandbox/enqueue` 는 `SandboxRequestPacketV1` 만 적재하고 worker 는 여전히 `harness-tick --queue sandbox_queue` operator CLI 로만 실행 (evidence 로 `worker_ran_autonomously=false` 잠금). UI 버튼은 env-gated + 기본 비활성, 활성이어도 enqueue 만.
- **Locale honesty, no silent degrade** — Patch 5 의 dual locale silent-degrade 가 D1 contract + guardrail + prompt 로 삼중 차단. LLM 이 `dual` 을 선언하면서 한쪽 bullet 을 비우면 Pydantic + guardrail 에서 reject 되어 template fallback 으로 폴백, UI 는 `degraded` 배지로 정직하게 표기.
- **No engineering token leak in primary UI** — raw snake_case id 들은 `<details>` audit block + data-* 속성 + URL 페이로드 안에만 허용되며 D2 스캐너가 정적 차원에서 매 push 마다 잠금. 새 tsr-* 렌더러 추가 시 이 테스트가 즉시 fail 해 산업 tokenlocal leak 을 재발 방지.
- **No breadth expansion** — sandbox kinds = `('validation_rerun',)` 그대로 (CF-3 계속 이월), 새 data provider / registry slot / React 등 프레임워크 없음, 모든 UI 변경은 기존 vanilla JS SPA + embedded CSS 위에서 추가.
- **Operator gate preserved** — UI 의 "Enqueue via UI" 버튼도 결국 `SandboxRequestPacketV1` 만 만들고, 실제 실행은 운영자 터미널의 `harness-tick` 으로만 발생. `sandbox_request_enqueued_via_ui` notification 으로 enqueue 기원을 감사 추적.

**다음 이월 (next patch 후보 — carry-forward)**

1. **CF-6·1 · 추가 sandbox kinds** — Patch 5 에서 이월된 `evidence_refresh` / `residual_review` / `replay_comparison` 는 여전히 Patch 7+ 로 이월 (contract 의 `SANDBOX_KINDS` enum + `sandbox_kind_dispatcher` extension point 준비됨).
2. **CF-6·2 · Live end-to-end from evaluator to UI** — R branch 가 확보된 이상, 다음은 `governance_scan` cadence 로 실제 `ValidationPromotionEvaluationV1` 을 emit → proposal → apply → spectrum refresh 의 실측 세션을 cockpit UI 세션으로 녹화. Patch 6 은 UI 표면 + invoke path 까지 닫았고, 다음 이터레이션은 이 경로의 라이브 녹화·재현.
3. **CF-6·3 · Research ask → sandbox enqueue 연결** — 현재 UI invoke 버튼은 `research_structured_v1.proposed_sandbox_request` 를 CLI/POST 로 변환하지만, research ask LLM 응답이 실제 enqueue 를 "권유" 하는 카피 + 운영자가 one-click 으로 enqueue 승인하는 UX 는 아직 수동 JSON 필드 조합. UX polish 로 이월.
4. **CF-6·4 · Live screenshot capture (실제 브라우저)** — 현재 F2 는 자체 HTML + sha256 으로 freeze, 실제 playwright/Chromium 렌더 스크린샷은 의존성 추가라 이월.

**환경 변수 (Patch 6 에서 추가)**

- `METIS_HARNESS_UI_INVOKE_ENABLED` — 기본 미설정 (비활성). `=1` 이면 `POST /api/sandbox/enqueue` 가 enqueue 를 허용 (여전히 worker 자동 실행 없음, `harness-tick --queue sandbox_queue` 는 별도 필요). UI 프론트엔드는 URL `?ui_invoke=1` 또는 `window.__metisUiInvokeEnabled=true` 로 버튼을 표시 (실제 권한은 서버 env 로만 결정).

기존 Patch 2–5 의 환경변수는 그대로. SPA 쉘 (vanilla JS SPA / `index.html` + `app.js`) 구조는 변경되지 않음.

## 2026-04-19 — AGH v1 Patch 5: Research Ask / bounded sandbox closure (plan `agh_v1_patch_5_research_ask_sandbox`)

**단일 목표 (추가)**: 작업지시서 `METIS_Patch_5_Workorder_Research_Ask_Sandbox_Closure_2026-04-19.md` 를 받아, Patch 4 에서 닫힌 **validation → governance 상류 다리** 위에 **"완료된 validation evidence 를 operator 가 '왜 / 무엇이 미증명 / 무엇을 봐야 / 어떤 bounded sandbox 를 돌려야?' 4축으로 질의하고 replay 가능한 trace 로 남기는 최소 product-grade Research 루프"** 를 닫는다. 즉 Patch 2/3/4 가 **write-path** (proposal → decision → apply → spectrum refresh, validation → evaluator → proposal) 였다면, Patch 5 는 **read-path + operator-gated bounded action loop** 로, LLM 은 여전히 registry/번들에 한 바이트도 쓸 수 없고, bounded sandbox 는 **오직 `validation_rerun`** 1종만 closed-loop 으로 닫는다. 사용자 결정: **Sandbox scope = X (최소안, `validation_rerun` 만, `evidence_refresh`/`residual_review`/`replay_comparison` 은 Patch 6 이월)**, **Live Supabase evaluator smoke = Q (Supabase 키는 있지만 `completed factor_validation_run` 행이 없어 live smoke 는 defer, 대신 provider 코드 + idempotency 테스트 + runbook evidence 로 대체)**.

**Green run 실증 (Patch 5)**

- **A1 — `governance_scan` spec provider (Patch 4 CF-2 청산)**. 신규 `src/agentic_harness/agents/supabase_governance_scan_provider_v1.py` 가 Patch 4 의 `set_governance_scan_spec_provider` 훅을 위한 provider 를 구현. `build_supabase_governance_scan_spec_provider(client_factory, bundle_loader, lookback_minutes=1440, horizon_default='short')` 는 (1) `factor_validation_runs` 에서 최근 완료 run 을 lookback 창 안에서 조회, (2) registry entry 의 `research_factor_bindings_v1` 슬롯과 `(factor_name, universe_name, horizon_type, return_basis)` 조인, (3) bindings 가 비어 있으면 honest-skip, (4) 같은 validation_run_id 에 대해 최근 `ValidationPromotionEvaluationV1` 이 이미 존재하면 dedupe 해서 tick 간 idempotency 보장, 결과를 evaluator-compatible spec list (list of dict `{registry_entry_id, horizon, factor_name, universe_name, horizon_type, return_basis, validation_run_id, validation_pointer, evidence_refs}`) 로 반환. Supabase 쿼리 실패는 raise 대신 빈 list 로 graceful-degrade 해 cadence tick 이 DLQ 되지 않게 한다.
- **A2 — Bundle schema 확장**. `src/metis_brain/schemas_v0.py::RegistryEntryV0` 에 optional `research_factor_bindings_v1: list[dict] | None = None` 필드 추가. 각 binding 은 `{factor_name, universe_name, horizon_type, return_basis}` 의 4-튜플로, governance_scan provider 와 `sandbox_options_v1` builder 가 공용으로 읽는다. 비어있거나 누락이면 honest-skip 동작. `validate_active_registry_integrity` 는 이 필드를 해석하지 않으며 (registry 무결성 semantic 에 영향 없음), optional 이기 때문에 기존 번들 하위호환.
- **A3 — main.py 환경변수 게이트**. `src/main.py` 의 runtime boot 이 `METIS_HARNESS_GOVERNANCE_SCAN_PROVIDER=supabase_v1` 일 때만 provider 를 설치. 기본값은 미설치 (Patch 4 honest-skip 유지). Supabase client factory 가 None 을 반환하면 provider 자체가 빈 list 를 내므로 cadence tick 은 그대로 skip 으로 surface.
- **B1 — `layer5_intent_router_v1` (7 kinds, deterministic)**. 신규 `src/agentic_harness/agents/layer5_intent_router_v1.py::USER_QUESTION_KINDS = ('why_changed','what_remains_unproven','what_to_watch','deeper_rationale','sandbox_request','compare_siblings','replay_lookup')` 와 `classify_user_question(question, lang=None) -> str`. 완전히 규칙기반 (LLM 비사용) 으로, locale 별 키워드 우선순위를 고정해 `"재검증 돌려줘"` / `"rerun validation"` 는 `sandbox_request`, `"이 해석의 근거"` 는 `deeper_rationale`, `"무엇이 아직 미증명"` 는 `what_remains_unproven` 으로 안정 라우팅. 모호하거나 빈 입력은 `why_changed` 로 낙착되지만 `sandbox_request` 가 `deeper_rationale` 보다 우선. `layer5_orchestrator.founder_user_orchestrator_agent` 가 기존 ad-hoc 분기를 `classify_user_question` 으로 통합. state_reader 는 `deeper_rationale` / `what_remains_unproven` / `what_to_watch` / `sandbox_request` 프로파일에서 `ValidationPromotionEvaluationV1` + 최근 `factor_validation_summaries` refs + `research_factor_bindings_v1` 을 함께 수집.
- **B2 — `ResearchAnswerStructureV1` + LLM response 스키마 확장**. `src/agentic_harness/contracts/packets_v1.py::LLMResponseContractV1` 에 optional `research_structured_v1: ResearchAnswerStructureV1 | None = None` 필드 추가. 구조는 `{summary_bullets_ko: list[str] <=6, summary_bullets_en: list[str] <=6, residual_uncertainty_bullets: list[str] <=6, what_to_watch_bullets: list[str] <=6, evidence_cited: list[str], proposed_sandbox_request: ProposedSandboxRequestV1 | None}`. 각 bullet 은 <=280 chars. `evidence_cited` 는 top-level `cited_packet_ids` 의 **subset** 이어야 함을 cross-model Pydantic validator 가 강제. `ProposedSandboxRequestV1` 은 `{sandbox_kind: Literal['validation_rerun'], registry_entry_id, horizon, target_spec: {factor_name, universe_name, horizon_type, return_basis}, rationale}` — Patch 5 에서 `sandbox_kind` 는 `validation_rerun` 만 허용하며 다른 값은 Pydantic 차원에서 거부.
- **B3 — `_SYSTEM_PROMPT` research acceptance 블록 + `validate_research_structured_v1` 가드레일**. `layer5_orchestrator._SYSTEM_PROMPT` 에 "Research acceptance block" 을 추가: (1) `routed_kind ∈ {deeper_rationale, what_remains_unproven, what_to_watch, sandbox_request}` 일 때 `research_structured_v1` 필수 populate, (2) 모든 bullet list 바운드, (3) `evidence_cited` 는 반드시 제공된 `state_bundle` packet id 의 subset, (4) `proposed_sandbox_request` 는 **절대 자동 실행되지 않고** operator UI 에서 명시적 `harness-sandbox-request` CLI 호출을 통해야 함을 못박음, (5) proposed sandbox 를 "이미 실행됐다" 고 서술하는 것 금지. `src/agentic_harness/llm/guardrails.py::validate_research_structured_v1(research_structured, routed_kind, allowed_packet_ids)` 가 Pydantic 통과 후 추가 invariant 점검 (subset 재검증, forbidden-copy 스캔 — "buy"/"sell"/"강력 추천" 같은 매수·매도 권유 카피). 위반 시 orchestrator 가 `template_fallback_response(reason='research_structured_blocked:...')` 로 fallback.
- **C1 — `SandboxRequestPacketV1` / `SandboxResultPacketV1` + `sandbox_queue` + Supabase 마이그레이션**. 신규 패킷 2종을 `packets_v1.py` 에 추가. `SandboxRequestPacketV1` 은 `{request_id, sandbox_kind ∈ SANDBOX_KINDS=('validation_rerun',), registry_entry_id, horizon, target_spec: {factor_name, universe_name, horizon_type, return_basis}, rationale, queued_at_utc}` 전부 필수. `SandboxResultPacketV1` 은 `{result_id, cited_request_packet_id, outcome ∈ ('completed','blocked_insufficient_inputs','rejected_kind_not_allowed'), produced_refs: list[dict], blocking_reasons: list[str], completed_at_utc}` 전부 필수. cross-field validator: `outcome='blocked_insufficient_inputs'` 또는 `'rejected_kind_not_allowed'` 면 `blocking_reasons` 비어있지 않아야 함, `outcome='completed'` 면 `blocking_reasons` 비어있어야 함. `QUEUE_CLASSES` 에 `'sandbox_queue'` 추가 (동일 테스트가 이를 고정). 마이그레이션 `supabase/migrations/20260420100000_agh_v1_patch_5_sandbox_packets.sql` 이 `agentic_harness_packets_v1.packet_type` CHECK 에 `'SandboxRequestPacketV1'` / `'SandboxResultPacketV1'` 를 추가하고 `agentic_harness_queue_jobs_v1.queue_class` CHECK 에 `'sandbox_queue'` 추가. 새 테이블/컬럼/RLS 없음.
- **C2 — `layer3_sandbox_executor_v1` + runtime + `harness-sandbox-request` CLI**. 신규 `src/agentic_harness/agents/layer3_sandbox_executor_v1.py` 가 `enqueue_sandbox_request(store, ..., target_spec, rationale, now_iso=None)` 로 `SandboxRequestPacketV1` 을 upsert 하고 `sandbox_queue` job 을 enqueue. Worker `run_sandbox_queue_worker_tick(store, runner=None, client_factory=None, ...)` 는 (1) job 을 claim, (2) `sandbox_kind` 이 `SANDBOX_KINDS` 에 없으면 `SandboxResultPacketV1(outcome='rejected_kind_not_allowed')` + `blocking_reasons=['sandbox_kind_not_allowed:...']`, (3) `runner` / `client_factory` 둘 다 None 이면 `outcome='blocked_insufficient_inputs'` + `blocking_reasons=['no_sandbox_validation_rerun_runner_installed']`, (4) 정상 경로 → 기존 `src/phase47_runtime/sandbox_v1.py` + `src/research/validation_runner.py` 를 호출해 bounded `validation_rerun` 실행 → `produced_refs=[{kind:'factor_validation_run_id', id:<fvr_id>, details:{...}}]` + `outcome='completed'`, (5) idempotency: 같은 `SandboxRequestPacketV1` 에 이미 `SandboxResultPacketV1` 이 달려있으면 두 번째 run 은 skip. 번들은 **절대** mutate 하지 않음 (sandbox 는 evidence-only). `src/agentic_harness/runtime.py::build_queue_specs` 에 `sandbox_queue` 추가, `src/main.py` 에 `harness-sandbox-request` CLI 추가.
- **C3 — Replay lineage + `/api/sandbox/requests`**. `src/phase47_runtime/traceability_replay.py::api_governance_lineage_for_registry_entry` 가 `SandboxRequestPacketV1` + `SandboxResultPacketV1` 를 새로 조회해 `cited_request_packet_id` 로 pair. Chain 반환에 top-level `sandbox_followups: list[{sandbox_kind, request_packet_id, result_packet_id, result_outcome, requested_at_utc, completed_at_utc}]` (newest-first) 추가, summary 에 `total_sandbox_requests / total_sandbox_completed / total_sandbox_blocked` 추가. Pending request (result 미도착) 도 surface 해 operator 가 "enqueued but never executed" 상태를 볼 수 있게 함. 기존 Patch 3/4 의 chain (proposal/decision/applied/spectrum_refresh/validation_promotion_evaluation) backcompat 유지. `/api/replay/governance-lineage` 와 신규 `/api/sandbox/requests` 라우트가 같은 데이터를 JSON 으로 제공.
- **D1/D2 — Today object detail `sandbox_options_v1` + `research_status_badges_v1`**. `src/phase47_runtime/today_spectrum.py` 에 두 결정론적 빌더 추가. `_sandbox_options_v1_from_registry_surface(registry_surface, bundle)` 는 번들의 `research_factor_bindings_v1` 을 scan 해 해당 registry_entry 에서 operator 가 호출 가능한 `validation_rerun` 후보 리스트를 `{sandbox_kind:'validation_rerun', registry_entry_id, horizon, target_spec:{...}, cli_hint:'harness-sandbox-request ...'}` 모양으로 emit — UI 가 직접 CLI 명령에 주입 가능. bindings 가 비어있으면 빈 list. `_research_status_badges_v1_from_bundle` 는 `{has_research_factor_bindings, active_artifact_recently_applied, has_pending_governed_proposal, has_stale_spectrum_after_active_swap, no_recent_governed_apply}` 같은 결정론적 badge code set 을 emit. **어떤 badge 도 "autonomy" 나 "자동 실행" 을 함의하지 않음** (테스트 `test_research_status_badges_v1_never_claims_autonomy` 가 문자열 수준에서 잠금). `build_today_object_detail_payload` 가 두 키를 최상위에 추가. Today spectrum 자체는 건드리지 않음.
- **G — 테스트 suite (신규 8 + 기존 3 확장)**. 신규: `test_agh_v1_patch5_sandbox_packets.py` (10건 — enum / cross-field / 마이그레이션 whitelist), `test_agh_v1_patch5_intent_router.py` (5건, parameterized 20+ 케이스 — 7 kinds 분류, 우선순위 고정, locale 안정), `test_agh_v1_patch5_research_structured.py` (8건 — 필수/선택 분기, evidence_cited subset, forbidden-copy 스캔, happy path, sandbox_kind enum, cross-model validator), `test_agh_v1_patch5_governance_scan_provider.py` (5건 — recent completed run fan-out, unbound entries honest-skip, dedupe, end-to-end idempotent), `test_agh_v1_patch5_sandbox_executor.py` (6건 — enqueue, completed happy path, idempotency, 거부 (not_allowed), blocked (no runner/client), 번들 불변), `test_agh_v1_patch5_replay_lineage_sandbox.py` (3건 — pair request/result, scope by registry_entry_id, pending request surface), `test_agh_v1_patch5_today_surface_v1.py` (3건 — CLI-consumable target_spec, never_claims_autonomy, payload wiring), `test_agh_v1_patch5_today_unchanged_unless_applied.py` (1건 — AC-5 regression: sandbox path 는 active_artifact_id 와 Today payload 를 건드리지 않음). 기존: `test_agentic_packets_v1.py` (QUEUE_CLASSES 에 `sandbox_queue` 추가), `test_agentic_layer5_orchestrator_v1.py` (acceptance prompt 어휘 + state_reader profile 확장), `test_agentic_scheduler_tick_v1.py` (변경 없음 재확인). Patch 4 회귀 green.
- **H — Fixture runbook 증거**. `scripts/agh_v1_patch_5_research_ask_sandbox_runbook.py` 가 tmp store + FixtureHarnessStore 로 5 시나리오 실측 캡처 (`data/mvp/evidence/agentic_operating_harness_v1_milestone_16_research_ask_sandbox_runbook_evidence.json` + `...bridge_evidence.json`):
  - **S1 completed**: `validation_rerun` enqueue → worker → `SandboxResultPacketV1.outcome='completed'` + `produced_refs=[{kind:'factor_validation_run_id', id:'fvr_runbook_completed_1', details:{status:'completed', factors_ok:1, factors_failed:0, validation_panels_used:1, symbols_in_slice:42}}]`.
  - **S2 blocked_insufficient_inputs**: runner/client 둘 다 미설치 → `outcome='blocked_insufficient_inputs'` + `blocking_reasons=['no_sandbox_validation_rerun_runner_installed']`, 번들/registry 불변.
  - **S3 rejected_kind_not_allowed**: 저장된 request packet 의 `sandbox_kind` 를 수동으로 `'evidence_refresh'` 로 덮어쓴 뒤 worker 실행 → `outcome='rejected_kind_not_allowed'` + `blocking_reasons=["sandbox_kind_not_allowed:'evidence_refresh'"]`, 번들 불변 (Patch 6 defer 경로의 honest-block 을 증명).
  - **S4 api_governance_lineage**: `api_governance_lineage_for_registry_entry(reg_short_demo_v0, short)` summary → `total_sandbox_requests=3`, `total_sandbox_completed=1`, `total_sandbox_blocked=2`, `sandbox_followups` newest-first 로 S3 → S2 → S1 순.
  - **S5 today_surface**: `build_today_object_detail_payload` 가 `sandbox_options_v1` (count=2: raw + excess) + `research_status_badges_v1` (`has_research_factor_bindings` + `no_recent_governed_apply`) 를 포함, `active_artifact_id='art_short_demo_v0'` 시전후 동일 (sandbox worker 가 Today 에 누수되지 않음).

**안전 가드 재확인 (모두 honored)**

- **No LLM writes to registry/bundle** — `ResearchAnswerStructureV1.proposed_sandbox_request` 는 **UI surface only**. 실제 enqueue 는 operator 의 `harness-sandbox-request` CLI 만 할 수 있다. prompt 와 `validate_research_structured_v1` 가드레일이 이를 이중으로 잠근다.
- **Bounded sandbox only, one kind** — `SANDBOX_KINDS=('validation_rerun',)`. 다른 값은 (a) Pydantic 차원 거부 (proposed request), (b) worker 실행 시 `rejected_kind_not_allowed` + blocking_reasons. 사용자 결정 X (최소안) 을 코드 + 테스트 + 런북으로 삼중 잠금.
- **No active-state mutation from sandbox** — sandbox executor 는 번들을 mutate 하지 않는다. `produced_refs` 는 Supabase `factor_validation_runs` 행 id 를 가리킬 뿐, registry 에 직접 쓰지 않음. 기존 Patch 4 evaluator 가 그 run 을 다시 pick-up 해야 비로소 challenger proposal 로 변환될 수 있다 (operator gate preserved).
- **Idempotency at every tick** — governance_scan provider 는 이미 평가된 validation_run_id 를 dedupe; sandbox worker 는 같은 request packet 에 이미 result 가 있으면 skip; replay lineage 는 pair 를 newest-first 정렬.
- **Honest skip, not silent success** — governance_scan provider 의 Supabase 실패는 raise 대신 빈 list, `research_factor_bindings_v1` 미설정 entry 는 honest-skip, runner/client 부재는 `blocked_insufficient_inputs` 로 surface. replay 에 pending request 그대로 노출.
- **Today unchanged unless genuinely applied** — `test_sandbox_worker_does_not_change_today_active_artifact` (AC-5) 가 Today spectrum payload + object detail 의 `active_artifact_id` 가 sandbox 전후 동일함을 잠금.

**다음 이월 (next patch 후보 — carry-forward)**

1. **CF-3 · 추가 sandbox kinds** — `evidence_refresh` (fresh factor_validation_summaries pull), `residual_review` (factor_quantile_results 재투사), `replay_comparison` (`message_snapshot_id` + counterfactual registry_entry 평가) 는 Patch 6 으로 이월. Contract (`SandboxRequestPacketV1.sandbox_kind`) 와 executor 의 dispatch shape 은 이미 extension point 로 설계됨.
2. **CF-4 · Live Supabase evaluator smoke + sandbox smoke** — Supabase 에 실제 `completed factor_validation_run` 이 적재된 뒤 (Phase 5 research validation layer 의 real run), (a) Patch 4 evaluator 가 그 run 을 pick-up 해 proposal 을 emit 하는 end-to-end, (b) 그 run 을 target 으로 `harness-sandbox-request` 가 bounded rerun 을 실행해 `factor_validation_run_id` 를 `produced_refs` 에 담는 end-to-end 양쪽을 실측. 이번 패치는 provider/worker 코드 + idempotency unit 으로 대체.
3. **UI 렌더러** — `sandbox_options_v1` / `research_status_badges_v1` 은 현재 JSON 계약으로만 노출되고, Cockpit/Today 프론트엔드에서 해당 badge/dropdown 을 실제로 렌더하고 `harness-sandbox-request` 를 invoke 하는 조작 UI 는 Skin 단계 작업으로 이월.
4. **Research answer locale 정합** — `summary_bullets_ko` / `summary_bullets_en` dual locale 은 구조만 강제되고, 실제 LLM 출력이 한쪽 locale 만 채우는 degraded mode 를 허용. dual 모두를 강제하는 stricter guardrail + 번역 fidelity 측정은 이월.

**환경 변수 (Patch 5 에서 추가)**

- `METIS_HARNESS_GOVERNANCE_SCAN_PROVIDER` — 기본 미설정. `supabase_v1` 로 설정하면 `supabase_governance_scan_provider_v1` 를 `set_governance_scan_spec_provider` 에 설치. Supabase client factory 가 None 을 반환하면 provider 는 빈 list 를 내므로 cadence tick 은 honest-skip 으로 surface.

기존 `METIS_BRAIN_BUNDLE`, `METIS_REPO_ROOT` (Patch 2), `METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH`, `FMP_API_KEY`, `METIS_HARNESS_L1_FISCAL_TARGET` (Patch 1) 은 그대로.

## 2026-04-19 — AGH v1 Patch 4: Validation → Governance bridge closure (plan `agh_v1_patch_4_validation_to_governance_bridge`)

**단일 목표 (추가)**: 작업지시서 `METIS_Patch_4_Workorder_Validation_To_Governance_Bridge_Closure_2026-04-19.md` 를 받아, 완료된 `factor_validation_*` 증거를 **결정론적으로 governed promotion proposal 로 변환하는 상류 경로** 를 신설한다. 즉 Patch 3 가 "operator 가 승인한 artifact 스왑 을 원자적으로 apply" 하는 **하류 다리** 였다면, Patch 4 는 "완료된 validation run 하나를 받아서 `ModelArtifactPacketV0` 후보 아티팩트 + `PromotionGateRecordV0` + challenger-ready registry context + `RegistryUpdateProposalV1(target='registry_entry_artifact_promotion')` 을 결정론적으로 생성" 하는 **상류 다리** 이다. Apply 는 여전히 `harness-decide approve` + Patch 3 `registry_patch_executor` 로 게이트되며, 이번 패치로는 **active_artifact_id 를 건드리지 않는다**. 사용자 결정: **artifact_id 정책은 B (결정적 해시 `art_<factor>_<universe>_<horizon_type>_<return_basis>_<hex8(sha256(pipe-joined+validation_run_id))>`)**, **emitter 는 Y (CLI + 라이브러리 API + 신규 `governance_scan` cadence 틱)**.

**Green run 실증 (Patch 4)**

- **A — Packet contract + 마이그레이션**. `src/agentic_harness/contracts/packets_v1.py` 에 신규 `ValidationPromotionEvaluationV1` 를 추가. payload 는 `evaluation_id / factor_name / universe_name / horizon_type / return_basis / validation_run_id / validation_pointer / registry_entry_id / horizon / derived_artifact_id / artifact_action ∈ {synced_existing, added_challenger, already_active, no_change} / gate_verdict ∈ {promote, hold, reject} / gate_metrics (dict) / outcome ∈ {proposal_emitted, blocked_by_gate, blocked_same_as_active, blocked_missing_evidence, blocked_bundle_integrity} / emitted_proposal_packet_id / evidence_refs` 전부 필수. `outcome='proposal_emitted'` 는 **반드시** `gate_verdict='promote'` + `emitted_proposal_packet_id` 비어있지 않음 + `artifact_action ≠ 'already_active'` 와 동반하도록 cross-field validator 가 강제하며, 다른 outcome 은 `emitted_proposal_packet_id` 가 반드시 None/empty. `active_registry_mutation` 필드는 Pydantic 차원에서 거부 — 번들 쓰기는 evaluator 의 canonical validate + atomic write 경로로만 가능. `PACKET_TYPES` / `PACKET_TYPE_TO_CLASS` 동기화. 마이그레이션 `supabase/migrations/20260419110000_agh_v1_patch_4_promotion_evaluation.sql` 은 `agentic_harness_packets_v1.packet_type` CHECK 에 `'ValidationPromotionEvaluationV1'` 만 추가 — 새 테이블/컬럼/RLS 없음, canonical write 는 여전히 JSON 번들.
- **B — Evaluator 모듈**. 신규 `src/agentic_harness/agents/layer4_promotion_evaluator_v1.py` 가 단일 진입점. `derive_artifact_id(factor_name, universe_name, horizon_type, return_basis, validation_run_id)` 는 결정적 해시 (`hex8(sha256(...))`) 로 artifact_id 를 생성해 동일 validation_run_id 에 대해 동일 slot id 가 재현됨을 보장. `evaluate_validation_for_promotion(store, bundle_path, bundle_dict, registry_entry_id, horizon, factor_name, universe_name, horizon_type, return_basis, supabase_client=None, now_iso=None, fetch_validation_summary=None, fetch_quantiles=None, dry_run=False)` 흐름: (1) 번들에서 registry entry 조회, 없으면 `blocked_missing_evidence` + `registry_entry_missing:<id>`. (2) `fetch_validation_summary` 로 최신 `factor_validation_summaries` row 확보, 없으면 `blocked_missing_evidence` + `no_completed_factor_validation_summary:...`. (3) 요청한 `return_basis` 가 row 들에 없으면 `blocked_missing_evidence` + `return_basis_row_missing:...`. (4) `map_validation_horizon_to_bundle_horizon(horizon_type)` 결과가 요청 `horizon` 과 불일치면 `blocked_missing_evidence` + `horizon_mismatch:...` (정직한 block — artifact 를 엉뚱한 horizon 에 pin 하지 않음). (5) `build_artifact_from_validation_v1` + `factor_validation_gate_adapter_v0.build_metis_gate_summary_from_factor_summary_row` + `validation_bridge_v0.promotion_gate_from_validation_summary` 로 challenger 후보 artifact 와 gate record 구성. (6) 결정적 verdict 룰: `pit_pass=False → reject (blocking_reasons=['pit_failed', ...])`, 3-gate 모두 pass → `promote`, PIT 은 통과했지만 coverage/monotonicity 블록 → `hold`. gate_reasons 문자열은 항상 추가 block reason 으로 append 돼 replay 가 gate adapter 의 생성 이유를 그대로 본다. (7) `artifact_action` 은 `derived_artifact_id` 가 번들의 `active_artifact_id` 와 같으면 `already_active`, 기존 challenger 목록에 있거나 artifact slot 이 존재하면 `synced_existing`, 아니면 `added_challenger`. (8) 번들 mutation 은 `added_challenger && verdict='promote'` 일 때만 새 slot 을 append (artifacts[] + registry_entries[i].challenger_artifact_ids + `last_evaluator_touch_at_utc`) + `merge_promotion_gate_into_bundle_dict`, `synced_existing/already_active` 에서는 `sync_artifact_validation_pointer_for_factor_run` 으로 validation_pointer 만 새로 고치고 gate record 는 merge. `added_challenger && verdict ≠ 'promote'` 는 번들을 건드리지 않음 (정직한 rule — 블록된 아티팩트로 번들을 오염시키지 않음). 모든 mutation 은 `validate_merged_bundle_dict` 통과 후 `write_bundle_json_atomic` 로만 쓰이며 실패는 `blocked_bundle_integrity` 로 short-circuit. (9) outcome 분기: `verdict='promote' && artifact_action='already_active'` → `blocked_same_as_active` (proposal 미발행). `verdict='promote'` 일반 → `proposal_emitted` — `RegistryUpdateProposalV1(target='registry_entry_artifact_promotion', from_active=<current>, to_active=<derived>, from_challenger_ids=<post-mutation challenger list>, to_challenger_ids=<post-swap list: old active 로테이션 + new active 제거>)` 를 upsert 하고 `governance_queue` 에 job enqueue. 기타 → `blocked_by_gate`. (10) 모든 경로에서 `ValidationPromotionEvaluationV1` audit packet 을 upsert (dry_run 모드 제외). `dry_run=True` 면 packet 구조 검증은 수행하되 저장소/번들에 쓰지 않고 `dry_run_preview={'would_emit_proposal': bool, 'mutated_artifacts': bool, 'mutated_registry_entries': bool}` 를 반환. `evaluate_registry_entries(store, bundle_path, specs, ...)` 는 각 spec 마다 번들을 **디스크에서 다시 로드** 해 cross-spec challenger 추가가 결정론적으로 누적되게 한다.
- **C — `harness-evaluate-promotions` CLI**. `src/main.py` 에 신규 서브커맨드 추가. Single-slot 모드 (`--registry-entry / --horizon / --factor / --universe / --horizon-type / --return-basis`) 또는 spec-file 모드 (`--spec-file path.json` — list of dicts). `--dry-run` 은 번들/패킷을 건드리지 않고 전 pipeline 을 돌려 preview JSON 을 stdout 으로만 낸다. `--use-fixture` 는 `FixtureHarnessStore` 로 라우팅 (오프라인 runbook 용). exit-code 0/1 계약 유지.
- **D — `governance_scan` cadence**. `src/agentic_harness/scheduler/cadences.py::DEFAULT_CADENCES` 에 `layer4.governance_scan = timedelta(minutes=15)` 추가. `src/agentic_harness/runtime.py::build_layer_cadences` 가 `LayerCadenceSpec(cadence_key='layer4.governance_scan', propose_fn=propose_governance_scan_cadence)` 등록. Tick 동작: `set_governance_scan_spec_provider(None)` 인 경우 honest skip (`{'skipped': True, 'reason': 'no_governance_scan_spec_provider'}`), provider 가 설치돼 있으면 walker 호출 후 `{'scans', 'by_outcome', 'emitted_proposal_packet_ids'}` 반환. Supabase client factory 훅 (`set_governance_scan_client_factory`) 도 제공 — 프로덕션에서는 실제 client, 테스트에서는 `None` 유지.
- **E — L5 state reader + prompt 어휘**. `src/agentic_harness/agents/layer5_orchestrator.py::state_reader_agent._collect(routed_kind='why_changed')` 이 `ValidationPromotionEvaluationV1` 을 추가 수집 (asset-neutral). `_SYSTEM_PROMPT` 에 새 어휘 블록 추가 — `proposal_emitted` 와 `emitted_proposal_packet_id` 는 **여전히 제안일 뿐** 이고 Today registry 가 바뀌었다고 말하려면 매칭되는 `RegistryPatchAppliedPacketV1.outcome='applied'` 를 반드시 인용해야 함을 못박고, `blocked_by_gate / blocked_missing_evidence / blocked_same_as_active / blocked_bundle_integrity` 는 반드시 `fact_vs_interpretation_map` 에 `interpretation` 으로 라벨링 + `blocking_reasons` (e.g. `pit_failed`, `coverage_insufficient`, `monotonicity_inconclusive`) 를 있는 그대로 서술하도록 가드. 기존 Patch 3 어휘 (`registry_entry_artifact_promotion` / `SpectrumRefreshRecordV1` / `needs_db_rebuild`) 와 Patch 2 가드 ("NEVER claim..." / "signals to watch" / "promotion gate") 는 모두 유지.
- **F — Replay lineage 확장**. `src/phase47_runtime/traceability_replay.py::api_governance_lineage_for_registry_entry(store, registry_entry_id, horizon, limit=200)` 가 이제 `ValidationPromotionEvaluationV1` 도 함께 조회. Chain block 마다 `validation_promotion_evaluation` 필드가 붙어서 해당 proposal 을 생성한 evaluator audit packet 을 인용 (또는 None). Top-level `validation_promotion_evaluations` flat list 는 proposal 을 내지 않은 블록 evaluation 도 전부 newest-first 로 surface — blocked outcome 이 replay 에서 사라지지 않도록. summary 에 `total_evaluations`, `total_emitted_from_evaluator` 추가. Patch 3 의 기존 chain 필드 (proposal / decision / applied / spectrum_refresh) 와 backcompat 보장.
- **G — 테스트 suite**. 신규 2 파일 + 기존 4 파일 확장. **AGH v1 + replay_lineage + traceability 278 passed / 0 failed**, 전체 repo **1073 passed** (사전 존재 pre-existing `test_phase39_orchestrator_writes_artifacts` 제외 — Patch 2 이전부터 있던 무관한 실패). 신규: `test_layer4_promotion_evaluator_v1.py` (9건 — derive_artifact_id 결정성/거부, promote happy path (challenger + proposal + evaluation + governance_queue job), blocked_by_gate (pit_certified=False → reject, 번들/proposal 불변), blocked_missing_evidence (summary 없음), blocked_same_as_active (active == derived → validation_pointer 만 새로 고침), horizon_mismatch block, `evaluate_registry_entries` 가 specs 사이에 번들 재로드해 두 개 challenger 를 누적, dry_run 은 저장/쓰기 모두 0건), `test_harness_evaluate_promotions_cli_v1.py` (4건 — CLI dry_run, CLI 실전 path, governance_scan provider 미설치 시 honest skip, provider 설치 시 evaluator 1회 실행 + `by_outcome={'proposal_emitted':1}`). 확장: `test_agentic_layer5_orchestrator_v1.py` (system prompt 어휘 + state_reader 수집 2건), `test_agentic_scheduler_tick_v1.py` (`DEFAULT_CADENCES` 에 `layer4.governance_scan` 포함 확인), `test_traceability_governance_lineage_v1.py` (validation_promotion_evaluations flat list + per-chain 필드 + summary counts), `test_agentic_packets_v1.py` (PACKET_TYPES 어휘 유지).
- **H — Fixture runbook 증거**. `scripts/agh_v1_patch_4_validation_to_governance_runbook.py` 가 tmp 번들 5개로 다섯 시나리오 전부 실측 캡처 (`data/mvp/evidence/agentic_operating_harness_v1_milestone_15_validation_to_governance_runbook_evidence.json`):
  - **promote**: `art_active_v0` 유지 + 신규 challenger `art_demo_factor_large_cap_research_slice_demo_v0_next_month_raw_47590c4f` 가 번들에 추가, `ValidationPromotionEvaluationV1.outcome='proposal_emitted'`, `RegistryUpdateProposalV1(target='registry_entry_artifact_promotion')` 1건, `governance_queue` job 1건.
  - **blocked_by_gate**: `summary_json.pit_certified=False` → `verdict=reject` + `outcome='blocked_by_gate'` + `blocking_reasons=['pit_failed', 'gate_reasons=...']`, 번들/challenger 리스트 완전 불변, proposal 0건, job 0건, evaluation 1건 emit.
  - **blocked_missing_evidence**: summary fetcher 가 빈 row 반환 → `outcome='blocked_missing_evidence'` + `no_completed_factor_validation_summary:...`, 번들 불변, proposal 0건.
  - **blocked_same_as_active**: 번들 active 를 derive_artifact_id 결과로 seed → `artifact_action='already_active'` + `outcome='blocked_same_as_active'`, active_artifact_id 완전 불변, validation_pointer 만 `factor_validation_run:run_fvr_promote_1` 로 refresh.
  - **dry_run**: 같은 promote 입력 + `dry_run=True` → `verdict=promote` + `artifact_action=added_challenger` + `dry_run_preview.would_emit_proposal=True`, 0 packet / 0 job, 번들 디스크 불변.

**안전 가드 재확인 (모두 honored)**

- **No direct active-state mutation** — evaluator 는 `active_artifact_id` 를 절대 쓰지 않는다. 모든 경로는 (a) challenger slot 추가 + proposal emit 으로 operator 승인을 기다리거나 (b) blocked 로 기록한다. 실제 active 스왑은 여전히 `harness-decide approve` + Patch 3 `registry_patch_executor` 의 책임.
- **Canonical write path only** — 번들 쓰기는 `validate_merged_bundle_dict` → `write_bundle_json_atomic`. 정합성 실패는 `blocked_bundle_integrity` 로 short-circuit.
- **No LLM-authored registry writes** — `promotion_evaluator_v1` 은 순수 결정적 (해시 기반 artifact id, gate_record 기반 verdict, 번들 + evidence_refs 기반 proposal payload). LLM 은 path 에 전혀 없음.
- **Honest non-promotion** — 매 evaluation 이 `ValidationPromotionEvaluationV1` 을 남기고, blocked 경로는 `blocking_reasons` 로 이유를 명시 (`pit_failed`, `no_completed_factor_validation_summary:...`, `horizon_mismatch:...`, 등).
- **Operator gate preserved** — cadence 와 CLI 모두 proposal + `governance_queue` job 만 생성. 실제 active 상태 전이는 여전히 operator 가 `harness-decide approve` 를 찍어야 발생.
- **No new registry truth** — Today 는 여전히 `bundle.registry_entries` (active + challenger + recent_governed_applies) 만 읽는다. evaluator 전용 surface 필드를 만들지 않음.
- **No raw active_registry_mutation payload** — `ValidationPromotionEvaluationV1` validator 가 해당 key 를 Pydantic 차원에서 거부.

**다음 이월 (next patch 후보 — carry-forward)**

1. **CF-1 · Live Supabase evaluator 스모크** — 이번 패치는 fixture fetcher / runbook 으로 evaluator 파이프라인을 카운트했지만 실제 `factor_validation_summaries` + `factor_quantile_results` 행에 붙인 end-to-end 스모크 (DEMO_KR + AAPL 모양, Patch 1 의 FMP 스모크와 병행) 는 별도 캡처가 필요. 코드 자체는 수정 없이 client 만 주입하면 동작하도록 `_default_fetch_validation_summary` / `_default_fetch_quantiles` 이 `db.records` 헬퍼에 이미 연결돼 있다.
2. **CF-2 · `governance_scan` spec provider** — cadence 는 provider 없이 기본 honest skip. production-grade provider ("최근 완료된 `factor_validation_runs` 중 등록된 `registry_entries` 의 (factor, universe, horizon_type) 와 매칭되는 slot 을 walk" 하는 callable) 는 별도 패치로 이월. contract (`Callable[[store, now_iso], list[spec dict]]`) 는 이미 고정돼 있어 provider 만 꽂으면 됨.
3. **Multi-basis / multi-universe batched evaluation** — 현재 evaluator 는 slot 당 한 번 호출. raw + excess 동시 평가, universe 단위 fan-out 배치는 범위 밖.
4. **Evaluator retry taxonomy** — `bundle_write_failed` 는 현재 `retryable=False` 로 즉시 DLQ. Patch 1 의 retry/backoff 모양을 따른 좀 더 세분화된 taxonomy (transient fs → retryable vs. integrity → fail-fast) 는 이월.

**환경 변수 (Patch 4 에서 추가)**

이번 패치는 새 환경 변수를 도입하지 않는다. 기존 `METIS_BRAIN_BUNDLE`, `METIS_REPO_ROOT` (Patch 2), `METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH`, `FMP_API_KEY`, `METIS_HARNESS_L1_FISCAL_TARGET` (Patch 1) 이 그대로 재사용된다. `governance_scan` spec provider 는 환경 변수가 아니라 `set_governance_scan_spec_provider(fn)` 코드 훅으로 설치한다.

## 2026-04-19 — AGH v1 Patch 3: Artifact promotion bridge closure (plan `agh_v1_patch_3_artifact_promotion_bridge`)

**단일 목표 (추가)**: 작업지시서 `METIS_Patch_3_Workorder_Artifact_Promotion_Bridge_Closure_2026-04-19.md` 를 받아, Patch 2 의 `horizon_provenance` state-transition bridge 를 **진짜 artifact-promotion bridge** 로 확장한다. 한 개의 `RegistryUpdateProposalV1` 이 `target='registry_entry_artifact_promotion'` 로 올라오면 operator 가 `harness-decide approve` 를 찍은 순간부터 다음 `harness-tick` 안에서 (1) `registry_entries[...].active_artifact_id` 와 `challenger_artifact_ids` 를 원자적으로 스왑, (2) 해당 `horizon` 의 `spectrum_rows_by_horizon` 를 **canonical `build_spectrum_rows_from_validation` 풀 재계산** 하거나 (live Supabase + validation data 가 붙어있을 때) **carry-over + `stale_after_active_swap=True` 스탬프** (fixture/DB 부재 시), (3) 번들의 bounded FIFO `recent_governed_applies` (cap=20) 에 방금 apply 요약을 append 해서 Today 가 **새 worker 없이** governed-apply badge 를 렌더, (4) 신규 `SpectrumRefreshRecordV1` audit packet 이 proposal → decision → applied → refresh 4-link chain 의 마지막 고리를 닫는다. 사용자 결정: **spectrum refresh 는 A (풀 재계산 + graceful fallback)**, **surface 는 Y (새 worker 금지, 번들 필드 확장만)**.

**Green run 실증 (Patch 3)**

- **A1 — Packet contract 확장**. `src/agentic_harness/contracts/packets_v1.py` 에 `REGISTRY_PROPOSAL_TARGETS=('horizon_provenance','registry_entry_artifact_promotion')` 와 `REGISTRY_BUNDLE_HORIZONS=('short','medium','medium_long','long')` 를 도입. `RegistryUpdateProposalV1` / `RegistryPatchAppliedPacketV1` 의 `payload` validator 를 target 별 분기로 리팩터링 — 새 target 은 `registry_entry_id`, `horizon`, `from_active_artifact_id`, `to_active_artifact_id` (반드시 서로 다름), `from_challenger_artifact_ids`, `to_challenger_artifact_ids` (list[str], 중복 금지), `evidence_refs` (비어있지 않음) 을 강제. 새 `SpectrumRefreshRecordV1` 은 `outcome ∈ {recomputed, carry_over_fixture_fallback, carry_over_db_unavailable}`, `refresh_mode`, `needs_db_rebuild`, 세 cited 패킷 id, row count + asset-id sample (cap=10), `blocking_reasons` 을 강제하고 `active_registry_mutation` 필드는 Pydantic 차원에서 거부. `PACKET_TYPES` / `PACKET_TYPE_TO_CLASS` 동기화.
- **A2 — Bundle schema**. `src/metis_brain/bundle.py::BrainBundleV0` 에 `recent_governed_applies: list[dict] = []` optional 필드 추가. executor 가 outcome=applied 에서만 append 하고 FIFO cap=20 로 자르며, reject/defer/conflict_skip 은 **절대** 건드리지 않는다.
- **A3 — Supabase 마이그레이션**. `supabase/migrations/20260419100000_agh_v1_patch_3_artifact_promotion_bridge.sql` 이 `agentic_harness_packets_v1.packet_type` CHECK 에 `'SpectrumRefreshRecordV1'` 만 추가. 새 테이블/컬럼/RLS 없음. canonical registry write 는 여전히 JSON bundle 에서만 일어난다.
- **B1 — Spectrum refresh helper**. 신규 `src/agentic_harness/agents/layer4_spectrum_refresh_v1.py::refresh_spectrum_rows_for_horizon` 가 executor 와 분리된 단일 진입점. (a) `supabase_client=None` 또는 artifact spec 을 parse 못 하면 → carry-over + stale 스탬프, `outcome='carry_over_fixture_fallback'`, `needs_db_rebuild=True`. (b) `fetch_joined` 이 raise 하거나 `ok=False` 또는 빈 rows 반환 → `outcome='carry_over_db_unavailable'` (역시 stale 스탬프). (c) 정상 경로 → `build_spectrum_rows_from_validation` 으로 **전체 교체**, stale 플래그 없음, `needs_db_rebuild=False`. 이 helper 는 번들을 in-memory 로만 건드리고 절대 디스크에 쓰지 않는다 (atomic write 단일 진입점 보장).
- **B2 — Executor target dispatch + artifact promotion 경로**. `src/agentic_harness/agents/layer4_registry_patch_executor.py` 가 기존 `horizon_provenance` 로직을 `_apply_horizon_provenance` 헬퍼로 분리하고 `_apply_registry_entry_artifact_promotion` 를 추가. 새 경로는 (1) proposal payload 로부터 필수 필드 추출 → (2) registry entry 를 찾고 from-state 검증 (`active_artifact_id` / `challenger_artifact_ids` / `horizon` 모두 매칭 안 되면 `outcome='conflict_skip'` + `blocking_reasons=['active_mismatch:...']` / `['challenger_set_mismatch:...']` + proposal `deferred`, 번들 미건드림) → (3) to-state 검증 (`to_active_artifact_id` 와 `to_challenger_artifact_ids` 가 모두 `bundle.artifacts` 에 존재 + 같은 horizon, 아니면 `retryable=False` DLQ + `to_active_artifact_missing` / `horizon_mismatch:...`) → (4) deepcopy + swap + `last_governed_*` 스탬프 → (5) `refresh_spectrum_rows_for_horizon` 호출 (in-memory mutation) → (6) `_append_recent_governed_apply` 로 FIFO cap=20 관리 → (7) `validate_merged_bundle_dict` 통과 시 `write_bundle_json_atomic` → (8) `RegistryPatchAppliedPacketV1` + `SpectrumRefreshRecordV1` upsert (후자는 전자 id 를 cite) → proposal `applied`. 실패는 모두 `retryable=False` 로 DLQ 해 silent partial write 가 불가능하도록 잠가둠.
- **C — L5 pending vs applied + refresh 구분**. `src/agentic_harness/agents/layer5_orchestrator.py::state_reader_agent._collect` 의 `why_changed` 경로가 `SpectrumRefreshRecordV1` 을 추가 수집 (asset-neutral signal). `_SYSTEM_PROMPT` 에 `registry_entry_artifact_promotion` / `SpectrumRefreshRecordV1` / `needs_db_rebuild` 어휘를 주입해 LLM 이 carry-over refresh 를 "spectrum rows 는 carry-over 됐고 DB 재빌드가 대기 중" 으로 설명하게 한다. 기존 guard (`"NEVER claim..."`, `"signals to watch"`, `"promotion gate"`) 는 모두 유지.
- **D — Today surface visibility (no new worker)**. `src/phase47_runtime/today_spectrum.py` 가 `_recent_governed_applies_for_horizon(bundle, horizon)` 헬퍼로 bundle 의 `recent_governed_applies` 를 horizon 필터 + `applied_at_utc` 내림차순 정렬 + **per-horizon cap=5** 적용한 뒤 registry mode 의 Today payload `extra` 로 `recent_governed_applies_for_horizon` 키에 부착. 번들에 필드가 없으면 **missing 이 아니라 빈 리스트** 로 노출해 UI 가 "아직 governed apply 없음" placeholder 를 안정적으로 렌더 가능.
- **E — Replay lineage 4-link**. `src/phase47_runtime/traceability_replay.py::api_governance_lineage_for_registry_entry(store, registry_entry_id, horizon, limit=200)` 가 `RegistryUpdateProposalV1` + `RegistryDecisionPacketV1` + `RegistryPatchAppliedPacketV1` + `SpectrumRefreshRecordV1` 를 `cited_proposal_packet_id` / `cited_applied_packet_id` 로 조인해 `[{proposal, decision, applied, spectrum_refresh}]` chain 을 newest-first 로 반환. summary 는 `total_proposals / total_applied / total_spectrum_refreshed / latest_applied_packet_id / latest_applied_needs_db_rebuild`. 이전 Patch 2 의 `horizon_provenance` proposal 도 같은 registry_entry_id / horizon 에 속하면 chain 에 포함 (backcompat).
- **F — 테스트 suite**. 신규 5 파일 + 기존 2 파일 확장, **agentic+today+traceability+metis_brain+replay 303 passed / 0 failed**, 전체 repo **1055 passed** (pre-existing `test_phase39_hypothesis_family` 제외 — Patch 2 이전부터 있던 무관한 실패). 신규: `test_agentic_registry_artifact_promotion_packet_v1.py` (23건), `test_agentic_artifact_promotion_executor_v1.py` (8건 — 두 approve happy path / 두 conflict_skip / to-state DLQ / horizon mismatch DLQ / FIFO cap / integrity fail), `test_agentic_layer4_spectrum_refresh_v1.py` (6건 — 4-branch 의사결정 트리 + happy recompute), `test_today_spectrum_recent_governed_applies_v1.py` (3건), `test_traceability_governance_lineage_v1.py` (4건). 확장: `test_agentic_packets_v1.py` (SpectrumRefresh vocab), `test_agentic_layer5_orchestrator_v1.py` (new vocab + state reader 수집 2건).
- **G — Fixture runbook 증거**. `scripts/agh_v1_patch_3_artifact_promotion_bridge_runbook.py` 가 tmp 번들 5개로 다섯 시나리오 전부 실측 캡처 (`data/mvp/evidence/agentic_operating_harness_v1_milestone_14_artifact_promotion_bridge_runbook_evidence.json`):
  - **approve(carry-over)**: `active_artifact_id art_active_v0 → art_challenger_v0` 원자 swap, spectrum rows (`AAA/BBB/CCC`) 그대로 + 3 개 모두 `stale_after_active_swap=True`, `SpectrumRefreshRecordV1.outcome='carry_over_fixture_fallback'` + `needs_db_rebuild=True`, `recent_governed_applies` 길이 1, proposal `applied`.
  - **approve(recompute)**: 같은 swap + spectrum rows `AAA/BBB/CCC → NEW_A/NEW_B/NEW_C` 완전 교체 (stale 플래그 없음), `SpectrumRefreshRecordV1.outcome='recomputed'` + `refresh_mode='full_recompute_from_validation'` + `needs_db_rebuild=False`, proposal `applied`.
  - **reject**: 번들 불변, applied/refresh packet 0건, `recent_governed_applies` 비어있음, proposal `rejected`.
  - **defer**: 번들 불변, decision packet 에 `next_revisit_hint_utc='2026-04-26T00:00:00+00:00'`, applied/refresh packet 0건, proposal `deferred`.
  - **conflict_skip**: proposal 이 `from_active=art_unrelated_v0` 인데 번들 active 는 `art_active_v0`, applied packet `outcome='conflict_skip'` + `blocking_reasons=['active_mismatch:...']`, 번들 + spectrum 불변, `recent_governed_applies` 비어있음, proposal `deferred`.

**안전 가드 재확인 (모두 honored)**

- 번들 쓰기는 오직 `registry_patch_executor` → `validate_merged_bundle_dict` → `write_bundle_json_atomic` 경로로만. spectrum refresh helper 는 디스크에 쓰지 않는다.
- Supabase / validation data 가 붙어있지 않을 때 spectrum refresh 는 **silent skip 금지** — carry-over + `stale_after_active_swap=True` + `needs_db_rebuild=True` 를 통해 Today/L5 가 상태를 정직하게 surface.
- `recent_governed_applies` 는 executor 가 outcome=applied 에서만 append, cap=20 FIFO 유지. Today 는 per-horizon cap=5 로 다시 자른다.
- `SpectrumRefreshRecordV1` 은 outcome=applied 에서만 emit, cited applied/proposal/decision packet id 3개 모두 필수. `active_registry_mutation` payload 필드 금지 유지.
- L5 의 LLM 은 여전히 apply 를 트리거할 수 없으며, carry-over refresh 를 "rationale 이 재계산됐다" 로 확언하지 못하도록 프롬프트 가드가 잡는다.

**다음 이월 (next patch 후보)**

1. **Live Supabase recompute 증거 확정** — 이번 패치는 unit 레벨에서 mock fetch_joined + build_spectrum_rows 까지는 카운트했지만, 실제 Supabase 에 붙인 end-to-end recompute runbook 은 (Patch 1 의 FMP 이월처럼) 키/데이터 확보 이후 별도 캡처 필요.
2. **Multi-horizon batched governed apply** — 현재 executor 는 proposal 이 지시한 단일 horizon 만 refresh. cross-horizon 배치 apply 는 별도 패치.
3. **Surface action queue worker** — 여전히 unregistered. proposal 생성 시 Today 쪽으로 push-notification 을 쏘고 싶다면 별도 와이어링 필요.
4. **Replay UI 연동** — `api_governance_lineage_for_registry_entry` 는 제공되지만, 실제 Replay 뷰 컴포넌트가 이 chain 을 렌더하는 지점은 이번 패치 범위 밖.

**환경 변수 (Patch 3 에서 추가)**

이번 패치는 새 환경 변수를 도입하지 않는다. 기존 `METIS_BRAIN_BUNDLE`, `METIS_REPO_ROOT` (Patch 2), `METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH`, `FMP_API_KEY`, `METIS_HARNESS_L1_FISCAL_TARGET` (Patch 1) 이 그대로 재사용된다.

## 2026-04-18 — AGH v1 Patch 2: Promotion bridge closure (plan `agh_v1_patch_2_promotion_bridge`)

**단일 목표 (추가)**: 작업지시서 `METIS_Patch_2_Workorder_Promotion_Bridge_Closure_2026-04-18.md` 를 받아, "proposal-only governance demo" → "**operator-gated registry patch bridge**" 로 끌어올린다. 기존에는 L4 `RegistryUpdateProposalV1` 까지만 발행되고 실제 `horizon_provenance` 는 절대 움직이지 않았다. 이 패치로는 (1) L4 proposal 이 **operator 가 접근 가능한 pending** 으로 Today 에 노출되고, (2) operator 가 `harness-decide` CLI 로 `approve | reject | defer` 를 기록하면, (3) approve 에 한해 `registry_apply_queue` job 이 enqueue 되고, (4) 다음 `harness-tick` 에서 `registry_patch_executor` 가 `data/mvp/metis_brain_bundle_v0.json` 의 `horizon_provenance[horizon].source` 를 **원자적으로** 쓰고, (5) `RegistryPatchAppliedPacketV1` 이 before/after snapshot + citation 을 남겨 replay lineage 가 닫힌다. **범위는 `horizon_provenance` 전환만** (`q_apply_target=A`) — `registry_entries.active_artifact_id/challenger` 와 `spectrum_rows_by_horizon` 은 이번 패치에서 손대지 않음. Decision 파이프라인은 **2-stage** (`q_decide_pipeline=Y`) — CLI 는 decision packet 기록 + job enqueue 만, 실제 write 는 비동기 worker 가 수행.

**Green run 실증 (Patch 2)**

- **A1 — 신규 packet 2종 + 상태 어휘 확장**. `src/agentic_harness/contracts/packets_v1.py` 에 `RegistryDecisionPacketV1` (`action ∈ {approve,reject,defer}`, `actor`, `reason` [forbidden-copy scan], `cited_proposal_packet_id`, `cited_gate_packet_id?`, `next_revisit_hint_utc?`) 과 `RegistryPatchAppliedPacketV1` (`outcome ∈ {applied, conflict_skip}`, `from_state`, `to_state`, `cited_proposal_packet_id`, `cited_decision_packet_id`, `before_snapshot`, `after_snapshot`, `applied_at_utc`, `bundle_path`) 을 추가하고 `PACKET_TYPES` / `PACKET_TYPE_TO_CLASS` 동기화. 두 packet 모두 기존 `RegistryUpdateProposalV1` 과 동일하게 **raw `active_registry_mutation` payload field 를 Pydantic 차원에서 거부**. `PACKET_STATUS_VALUES` 에 `applied / rejected / deferred` 추가. `QUEUE_CLASSES` 에 `registry_apply_queue` 추가.
- **A2 — Supabase 마이그레이션**. `supabase/migrations/20260418100000_agh_v1_patch_2_promotion_bridge.sql` 가 `agentic_harness_packets_v1` 의 `packet_type` / `status` CHECK, `agentic_harness_queue_jobs_v1` 의 `queue_class` CHECK 를 확장. 새 테이블/컬럼/RLS 없음. Canonical registry write 는 여전히 JSON bundle 에서 일어남 (SQL 영역 밖).
- **B1 — `record_registry_decision` + `harness-decide` CLI**. `src/agentic_harness/agents/layer4_governance.py::record_registry_decision` 이 proposal fetch → type / status 검증 (`proposed` 또는 `escalated` 만 허용, 터미널 상태면 `DecisionError`) → 동일 proposal 에 대한 기존 decision 존재 시 **first-decision-wins** 거부 → `RegistryDecisionPacketV1` upsert → action 별 분기: (a) `approve` 는 `registry_apply_queue` 에 job enqueue 하고 proposal 상태는 **`escalated` 유지** (실제 상태 전이는 worker 책임), (b) `reject` 는 proposal 을 `rejected` 로 set, (c) `defer` 는 proposal 을 `deferred` 로 set 하고 decision packet 에 `next_revisit_hint_utc` 보존. `src/agentic_harness/runtime.py::perform_decision` 은 error 를 `{ok:false, error}` JSON 으로 직렬화하고 `ValueError` (forbidden-copy 등) 를 그대로 surface. `src/main.py` 에 `harness-decide --proposal-id/--action/--actor/--reason/--next-revisit-hint-utc/--use-fixture` 서브커맨드 추가, exit-code 0/1 계약.
- **B2 — `registry_patch_executor` worker**. 신규 `src/agentic_harness/agents/layer4_registry_patch_executor.py` 가 `registry_apply_queue` consumer. 각 job 에 대해: (1) proposal 이 `escalated` 아닌 상태면 **idempotent skip**, (2) 매칭되는 approve `RegistryDecisionPacketV1` 없으면 `retryable=False` → DLQ, (3) `payload.target != 'horizon_provenance'` 면 `retryable=False` → DLQ (이번 패치 범위 밖), (4) `load_bundle_json` 으로 현재 번들 읽고 `horizon_provenance[horizon].source != from_state` 면 **`conflict_skip`** packet 남기고 proposal 을 `deferred` 로 (번들 미건드림, honest fallback), (5) 정합하면 `deepcopy` → in-memory mutate (`.source=to_state`, `last_governed_update_at_utc`, `last_governed_proposal_packet_id`, `last_governed_decision_packet_id` 스탬프) → `validate_merged_bundle_dict` 통과 확인 → `write_bundle_json_atomic` (tempfile + `os.replace`) 로 **원자 write**, (6) `RegistryPatchAppliedPacketV1.outcome='applied'` upsert (before/after 스냅샷 포함) 후 proposal 을 `applied` 로. 실패 모두 `retryable=False` 로 DLQ 해 재시도 예산 소모 없이 문제를 surface.
- **B3 — Atomic bundle write helper**. `src/metis_brain/bundle_promotion_merge_v0.py::write_bundle_json_atomic` 추가 — `path.with_suffix('.json.tmp')` 에 쓴 뒤 `os.replace` 로 원자 치환. Today 읽기 주체가 절반 쓰인 번들을 관찰할 위험을 제거. `runtime.build_queue_specs()` 에 `QueueSpec('registry_apply_queue', registry_patch_executor)` 등록.
- **C — L5 pending vs applied 구분**. `src/agentic_harness/agents/layer5_orchestrator.py::_collect` 에 `status_in` 필터 추가. `why_changed` 경로가 `RegistryUpdateProposalV1` 을 `status ∈ {proposed, escalated, deferred}` 만 수집 (이미 `applied` / `rejected` 로 넘어간 proposal 은 pending 뷰에서 숨겨짐), 그리고 `RegistryDecisionPacketV1` + `RegistryPatchAppliedPacketV1` 을 함께 수집해 실제 change lineage 를 LLM 에 제공. `_SYSTEM_PROMPT` 에 proposal 상태 용어집 (`pending/escalated/applied/rejected/deferred`) + "Today active state 단정은 cited packet 이 `RegistryPatchAppliedPacketV1.outcome=='applied'` 일 때만 허용" 가드 추가. 기존 guard 문구 (`"NEVER claim..."`, `"signals to watch"`, `"promotion gate"`) 는 모두 유지.
- **D — 테스트 suite**. 신규 4 개 + 기존 3 개 확장, `193 passed / 0 failed`. 신규: `test_agentic_registry_decision_packet_v1.py` (14건 — vocab / invariants / forbidden-copy / mutation 필드 거절 / before-after 구조), `test_agentic_registry_patch_executor_v1.py` (6건 — approve happy path / from_state mismatch conflict_skip / idempotent skip / missing decision DLQ / missing horizon conflict_skip / missing bundle DLQ, 실제 tmp bundle write 검증), `test_agentic_harness_decide_cli_v1.py` (9건 — approve enqueue, reject / defer 터미널, 중복 decision 차단, 터미널 proposal 차단, forbidden-copy reason 차단, perform_decision 오류 JSON, CLI subprocess smoke), `test_agentic_layer5_applied_distinction_v1.py` (4건 — decision + applied packet 수집 / applied proposal hide / escalated pending 유지 / 프롬프트 어휘). 확장: `test_agentic_packets_v1.py` (`registry_apply_queue` 어휘), `test_agentic_packet_store_v1.py` (신규 packet_type filter), `test_agentic_harness_e2e_v1.py` (`test_agentic_harness_e2e_patch2_promotion_bridge` — L4 proposal → `perform_decision(approve)` → `perform_tick` → bundle 실제 mutate → L5 why_changed 에서 applied packet 노출 + applied proposal pending 뷰에서 숨김 end-to-end).
- **E — Fixture runbook 증거**. `scripts/agh_v1_patch_2_promotion_bridge_runbook.py` 를 tmp bundle 로 실행 → 4 시나리오 전부 실측 캡처 (`data/mvp/evidence/agentic_operating_harness_v1_milestone_13_promotion_bridge_runbook_evidence.json`):
  - **approve**: `horizon_provenance.short.source` `template_fallback → real_derived` 원자 write, `last_governed_proposal_packet_id` + `last_governed_decision_packet_id` 스탬프, proposal `escalated → applied`, `RegistryPatchAppliedPacketV1.outcome='applied'` with 정확한 before/after 스냅샷.
  - **reject**: 번들 불변, proposal `escalated → rejected`, `registry_apply_queue` job 0, applied packet 0.
  - **defer**: 번들 불변, proposal `escalated → deferred`, decision packet 에 `next_revisit_hint_utc='2026-04-20T00:00:00+00:00'` + `expiry_or_recheck_rule='next_revisit:2026-04-20T00:00:00+00:00'` 보존.
  - **conflict_skip**: 번들 이미 `real_derived` 인 상태에서 proposal 이 `from=template_fallback` 으로 approve 되면, executor 가 **번들 미건드림**, `RegistryPatchAppliedPacketV1.outcome='conflict_skip'` + `blocking_reasons=["from_state_mismatch:expected=template_fallback actual=real_derived"]` + `after_snapshot={}`, proposal 은 `deferred`.

**안전 가드 재확인 (모두 honored)**

- 번들 쓰기는 오직 `registry_patch_executor` → `validate_merged_bundle_dict` → `write_bundle_json_atomic` 경로로만. LLM 는 apply 를 트리거할 수 없음.
- `from_state` 불일치는 **절대 silent overwrite 하지 않음** — `conflict_skip` 로 honest fallback.
- Today active state 단정 금지 가드는 유지되며, 새 어휘 ("applied", "pending operator-approved patches") 를 통해 실제 change 가 발생한 경우에만 확언 가능.
- Supabase 는 audit sink 역할만. canonical registry = JSON bundle 단일 원천.

**환경 변수 (Patch 2 에서 추가)**

| 변수 | 의미 | 기본값 | 비고 |
| --- | --- | --- | --- |
| `METIS_BRAIN_BUNDLE` | executor 가 쓸 번들 경로 override | `data/mvp/metis_brain_bundle_v0.json` | 테스트 / runbook 이 tmp 번들을 주입할 때 사용. |
| `METIS_REPO_ROOT` | repo root override | auto-detect (src parent) | `brain_bundle_path` 계산에 사용. 프로덕션에서는 보통 설정 불필요. |

**다음 이월 (next patch 후보)**

1. **registry_entries active↔challenger swap** — 이번 패치는 `horizon_provenance` 전환만. `RegistryUpdateProposalV1` payload 를 artifact-swap 용으로 확장하고 executor 에 두번째 write target 을 추가하면 Stage 3 autonomy 의 마지막 퍼즐.
2. **spectrum_rows_by_horizon 재계산 트리거** — `real_derived` 로 승격된 horizon 에 대해 별도 build 파이프라인 호출이 필요. 지금은 수동 재빌드 의존.
3. **surface_action_queue worker 등록** — 현재 proposal 노출은 L5 read path 로만 이뤄짐. proposal 생성 시 surface 쪽 알림/배지를 push 하고 싶다면 wire 필요.
4. **Live smoke 증거 확정 (Patch 1 이월)** — `FMP_API_KEY` 확보 즉시 Patch 1 runbook 실행 후 evidence 확장.

## 2026-04-18 — AGH v1 Patch 1: Layer 1 live ingest closure (plan `agh_v1_patch_1_live_ingest`)

**단일 목표 (추가)**: 작업지시서 `METIS_Patch_1_Workorder_Live_Ingest_Closure_2026-04-18.md` 를 받아, Layer 1 을 "stale detection visible loop" 에서 "실제 live source ingest 가 product-visible autonomy 루프를 닫는" 단계로 끌어올린다. 직전 patch 2 까지는 stale 후보 → `IngestAlertPacketV1` 까지만 발행되고 worker 는 의도적으로 DLQ 로 떨어지는 구조였으나, 이 patch 로는 **두 env flag (`METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH` + `FMP_API_KEY`)** 가 둘 다 켜진 환경에서만 실제 FMP earning-call API 까지 호출하고, 결과를 `transcript_ingest_runs` + `raw_transcript_payloads_fmp` + `SourceArtifactPacketV1` 에 정직하게 기록한다. Brain bundle / registry / factor_validation_* 는 **한 줄도** 쓰지 않는다 (§2 Out of Scope 준수, §3.1 Safety).

**Green run 실증 (Patch 1)**

- **A1 — Live FMP fetcher adapter**. 신규 `src/agentic_harness/adapters/layer1_transcript_fetcher.py` 가 `run_fmp_sample_ingest` 를 얇게 감싸 `TranscriptFetcher` 계약을 구현한다. `_infer_target_fiscal_quarter(now)` 가 월별로 직전 완료·공개 분기를 추정하고 (Jan–Mar → prev-year Q4, Apr–Jun → Q1, Jul–Sep → Q2, Oct–Dec → Q3), `METIS_HARNESS_L1_FISCAL_TARGET=YYYY-Q<n>` 또는 job_meta 의 `_force_target` 으로 override 가능. `classify_fmp_result(http_status, probe_status, payload)` 는 FMP 결과를 6 가지 `FetchClassification` 으로 쪼갠다: HTTP 200 + content → `ok`, 200 + 빈 리스트/이상 shape → `empty (honest)`, 404 → `empty (transcript_not_available_for_quarter)`, 401/402/403 또는 200+error-body → **fail-fast** (`fmp_auth_failed:*`, `retryable=False`), 429 / 5xx / `RuntimeError('fmp_network_error:...')` → **retryable** (`retryable=True`). 성공/empty 경로 모두 `supabase://transcript_ingest_runs/<id>`, `supabase://raw_transcript_payloads_fmp/<id>` (있을 때), `fmp://earning_call_transcript/<SYM>/<Y>/Q<Q>`, `packet:<alert_packet_id>` 4종 provenance ref 를 붙인다.
- **A2 — Worker fetch_outcome pass-through**. `src/agentic_harness/agents/layer1_ingest.py::ingest_queue_worker` 가 fetcher 반환값의 `fetch_outcome in {ok, empty}` 을 그대로 받아 `SourceArtifactPacketV1.payload.fetch_outcome` 에 전달한다. `empty` 도 packet schema 차원에서 유효 — **정직한 부재 기록**. 패킷 payload 에 `http_status` + `probe_status` 가 추가돼 L5 가 "왜 empty 인지" 재호출 없이 설명 가능. fetcher 가 `retryable` 을 주면 worker result 에 그대로 포함되고, 미지정 시 legacy-compat 으로 `retryable=True` 가 기본. `ok=True` 인데 `fetch_outcome` 이 `ok/empty` 가 아니면 `retryable=False` 로 **즉시 DLQ** (fabricated 경로 차단).
- **A3 — Scheduler retryable-aware + exponential backoff**. `src/agentic_harness/scheduler/tick.py::run_one_tick` 이 worker 실패 시 `result.get('retryable', True)` 를 본다. `retryable=False` 또는 `attempts_so_far >= max_attempts` → `status=dlq`. 그렇지 않으면 `status=enqueued` 로 되돌리되, `next_not_before_utc = now + min(3600, 300 * 2^(attempts_so_far - 1))` 로 **지수 백오프** (5m → 10m → 20m → 40m → cap 1h). 새 헬퍼 `_compute_next_not_before(now_iso, backoff_s)` 가 timezone 을 normalize. `status != 'enqueued'` 일 때 `next_not_before_utc` 는 무시된다 (DLQ 가 미래 시각을 설정하는 일 없음).
- **A4 — Store `next_not_before_utc` 지원**. `HarnessStoreProtocol.mark_job_result(..., next_not_before_utc: Optional[str] = None)` 인자 추가. `FixtureHarnessStore` 와 `SupabaseHarnessStore` 둘 다 `status=='enqueued'` 일 때만 `not_before_utc` 컬럼/필드를 업데이트 — backward compatible (기존 호출은 그대로 작동). Supabase 스키마는 이미 `not_before_utc timestamptz not null default now()` 로 존재했고 write 경로만 확장됨.
- **A5 — Runtime env-gated live bootstrap**. `src/agentic_harness/runtime.py::_maybe_bootstrap_layer1_live_fetch` 가 **두 조건** (`METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH ∈ {1,true,yes}` AND `FMP_API_KEY` 실제 설정됨) 이 모두 충족돼야 `set_transcript_fetcher(build_transcript_fetcher(...))` 를 호출. flag 가 켜졌는데 key 가 비면 `WARNING` 로그만 남기고 fallback 을 유지해 **config 문제를 은폐하지 않음**. fixture store 는 항상 skip, 한 프로세스당 1회 (idempotent). `perform_tick` 에서 `_maybe_bootstrap_layer1_production` 과 나란히 호출되어 두 bootstrap 이 각자 독립적으로 켜질 수 있다.
- **회귀 확인 (B)**. `PYTHONPATH=src python3 -m pytest src/tests/test_agentic_*.py -q` → **158 passed** (이전 102 + 신규 fetcher/backoff/bootstrap/store 56건). 새 테스트 파일 2종: `src/tests/test_agentic_layer1_transcript_fetcher_v1.py` (21건 — 12개월 fiscal 테이블 + classify 브랜치 + success/empty/auth/rate/server/network/no-key + force-target override + missing asset_id), `src/tests/test_agentic_layer1_live_fetch_bootstrap_v1.py` (4건 — flag off / fixture skip / key missing warning / key+flag 성공 & idempotent). 기존 `test_agentic_layer1_ingest_v1.py` 에 empty-outcome 유지 + retryable-False 전파 + unexpected-outcome 거절 3건 추가. `test_agentic_scheduler_tick_v1.py` 에 retryable-false 즉시 DLQ + exp backoff 2 단계 + 1h cap 3건 추가 (기존 retry 테스트는 명시적 `now` 주입 + 6분 advance 패턴으로 업데이트). `test_agentic_packet_store_v1.py` 에 `next_not_before_utc` enqueued-only 반영 + 비-enqueued 무시 2건 추가.

**환경 변수 (Patch 1 에서 추가)**

| 변수 | 의미 | 기본값 | 비고 |
| --- | --- | --- | --- |
| `METIS_HARNESS_L1_LIVE_TRANSCRIPT_FETCH` | 실제 FMP earning-call fetch ON | (없음 = OFF) | `1 / true / yes` 만 활성. Fixture store 는 언제나 무시. |
| `FMP_API_KEY` | FMP 키 | (없음) | flag=ON + 키 비어있으면 bootstrap 이 WARNING 남기고 fallback 유지. |
| `METIS_HARNESS_L1_FISCAL_TARGET` | fiscal 분기 강제 override | (없음 = auto) | `YYYY-Q<n>` 형식. AAPL/2025 Q2 같은 out-of-band 스모크 용. |

**Retry 정책 스냅샷**

| attempts_so_far 후 실패 | 재시도 간격 | 누적 대기 |
| --- | --- | --- |
| 1 | 300s (5m) | 5m |
| 2 | 600s (10m) | 15m |
| 3 | 1200s (20m) | 35m |
| 4 | 2400s (40m) | 1h 15m |
| 5+ | **3600s cap (1h)** | 선형 증가 |

auth/config 오류 (`fmp_auth_failed:*`, `fmp_api_key_missing`, `transcripts_provider_not_fmp`) 는 backoff 없이 **첫 실패에 DLQ**.

**라이브 스모크 (이월)**

- 현재 실행 환경에 `FMP_API_KEY` 가 프로비저닝돼 있지 않아, "DEMO_KR_{A,B,C} honest-empty 3건 + AAPL/2025 Q2 out-of-band positive 1건 + harness-ask 재확인" 정식 증거는 키 확보 후 실행. Unit test 가 `run_fmp_sample_ingest` 를 mock 하여 fetcher/bootstrap/scheduler 경로는 전부 커버됐고, live HTTP 라운드 트립만 대기 중.
- 운영 시 절차는 `data/mvp/evidence/agentic_operating_harness_v1_milestone_12_layer1_live_fetch_evidence.json` 의 `live_smoke.runbook_when_key_available` 에 step-by-step 기록.

**다음 이월 (next patch 후보)**

1. **Promotion Bridge Closure** — Layer 4 governance_queue 가 `RegistryUpdateProposalV1` 을 발행하지만 실제 registry_entries 를 mutate 하는 코드 경로가 아직 없음. proposal-only 거버넌스를 유지하면서 "승인 → patch" 다리를 제품 안에 닫으면 Stage 3 autonomy 에 가까워짐.
2. **Live smoke 증거 확정** — FMP_API_KEY 확보 즉시 runbook 실행 후 evidence 확장. (Brain bundle universe 는 건드리지 않음 — DEMO_KR 3건 + AAPL 1건 out-of-band)
3. **Event-anchored freshness** — earnings calendar 앵커가 추가되면 `90d 기본 × 이벤트 ±72h 수축` 하이브리드로 freshness 기준을 진화.

## 2026-04-17 (patch 2) — AGH v1 Layer 1 stale wiring + L5 scope (plan `agh_v1_b+c_—_l1_real_stale_wiring_+_l5_scope`)

**단일 목표 (추가)**: 사용자 진행 권고 (A smoke gate 1회 → 메인 패치 B+C) 를 그대로 집행해, Stage 2.5+ 로의 실질적 전진을 닫는다. **B** 는 Layer 1 의 `StaleAssetProvider` 를 실제 Brain bundle universe × 실제 transcript ingest 기록에 연결하지만 **live FMP fetch 는 의도적으로 이월** (worker-side fallback 유지), **C** 는 L5 state_reader 가 asset-neutral research/overlay 까지 bundle 에 담도록 범위를 넓히고 system prompt 에 "Today active state 단정 금지" 가드를 추가해 `why_changed` 흐름의 surface 신뢰를 닫는다.

**Green run 실증 (B+C)**

- **B — Layer 1 production wiring (stale detection only)**. 신규 `src/agentic_harness/adapters/layer1_brain_adapter.py` 가 `data/mvp/metis_brain_bundle_v0.json` (또는 `METIS_BRAIN_BUNDLE` override) 의 `spectrum_rows_by_horizon` 에서 unique `asset_id` 집합을 읽고, `raw_transcript_payloads_fmp` (primary, `symbol + fetched_at`) + `transcript_ingest_runs` (fallback, `detail_json->>symbol`, `status='success'`) 로 `last_fetched_at_utc` 를 합성해 `StaleAssetProvider` 를 만든다. `runtime._maybe_bootstrap_layer1_production` 은 env flag `METIS_HARNESS_L1_WIRE_PRODUCTION ∈ {1,true,yes}` 에서만 **한 번** 켜지고 fixture store 경로에서는 절대 켜지지 않아 테스트는 여전히 hermetic. 기본 freshness 는 `METIS_HARNESS_L1_FRESHNESS_HOURS=2160` (90d × 24h), 기본 universe source 는 `brain_bundle`. **Worker fetcher 는 건드리지 않음** — `_fallback_transcript_fetcher` 가 `transcript_fetcher_not_configured` 를 반환해, 생성된 ingest_queue job 은 의도대로 DLQ 로 떨어진다 (alert packet 자체는 DB 에 남음). Direct registry / Brain bundle write = **0**. 증거: `data/mvp/evidence/agentic_operating_harness_v1_milestone_10_layer1_stale_wiring_evidence.json`.
- **C — L5 state_reader scope + system prompt 보강**. `state_reader_agent._collect` 이 routed_kind 별로 `allow_asset_neutral` 을 받도록 바뀌었다. `why_changed` 는 per-asset evidence (`IngestAlert / SourceArtifact`) 는 asset-scoped 만, 레지스트리·유니버스급 신호 (`OverlayProposal / RegistryUpdateProposal / ReplayLearning`) 는 asset-neutral 도 포함. `research_pending` 은 `ResearchCandidate / Evaluation / PromotionGate` 전부 asset-neutral 포함 — 그 결과 사용자가 특정 티커를 지정해도 universe-scoped persona 후보가 "pending research" 응답에 비지 않음. `_SYSTEM_PROMPT` 에는 Spec §4.3·§11 준수 3문장을 추가: "NEVER claim that the Today registry has changed its active model family/band/horizon surface", "describe them as *signals to watch* or *proposals*, never as accomplished facts", "Today active state is only updated by the promotion gate + registry patch, which is outside this response scope." 증거: `data/mvp/evidence/agentic_operating_harness_v1_milestone_11_state_reader_scope_evidence.json`.
- **Live smoke (실제 Supabase + 실제 OpenAI)**. `METIS_HARNESS_L1_WIRE_PRODUCTION=1` 로 `propose_layer1_cadence` 를 실행 → Brain bundle universe 3종 (`DEMO_KR_A/B/C`) 전부 stale 판정 → 3 `IngestAlertPacketV1` + 3 ingest_queue job 이 `agentic_harness_packets_v1` / `agentic_harness_queue_jobs_v1` 에 실제로 기록됨 (응답: `{"stale_asset_count":3,"triggered":3,"enqueued":3}`). 직후 `harness-ask --asset DEMO_KR_A --provider openai` → OpenAI `HTTP/1.1 200 OK`, `guardrail_passed=true`, `llm_fallback=false`, `cited_packet_ids=["pkt_47500e6f160f582b2d996f"]` 이 **방금 L1 이 기록한 DEMO_KR_A 용 alert packet_id 와 정확히 일치** (환각/오염 0), `fact_vs_interpretation_map={"pkt_47500e6f160f582b2d996f":"fact"}`, 응답 텍스트는 "Today active state 변경" 단정 없이 "transcript 신호 / freshness stale" 언어로 서술.

**환경 변수 (새로 추가된 스위치)**

| 변수 | 의미 | 기본값 | 비고 |
| --- | --- | --- | --- |
| `METIS_HARNESS_L1_WIRE_PRODUCTION` | L1 production wiring ON | (없음 = OFF) | `1 / true / yes` 만 활성. Fixture store 는 언제나 무시. |
| `METIS_HARNESS_L1_FRESHNESS_HOURS` | stale 판정 기준 시간 | `2160` (90d) | 72h 은 earnings-calendar anchor 가 생긴 뒤 검토. |
| `METIS_HARNESS_L1_UNIVERSE_SOURCE` | universe source | `brain_bundle` | 현재는 `brain_bundle` 만 허용. |
| `METIS_BRAIN_BUNDLE` | Brain bundle JSON 경로 | `data/mvp/metis_brain_bundle_v0.json` | 기존 `metis_brain.bundle` 와 동일한 override. |

**회귀 확인 (B+C)**

- `PYTHONPATH=src python3 -m pytest src/tests/test_agentic_*.py -q` → **102 passed** (이전 93 + 신규 adapter 6 + L5 scope/prompt 3). 이전부터 green 이었던 93 건은 전부 그대로 green.
- Fixture 경로 (`--use-fixture`) 는 adapter bootstrap 이 강제로 skip 되어 hermetic — 네트워크 0.

**다음 이월 (next patch 후보)**

1. **Live FMP transcript fetcher 배선** — `set_transcript_fetcher` 에 conservative retry / rate-limit 을 붙여 DLQ 대신 실제 `SourceArtifactPacketV1` 까지 닫기.
2. **Event-anchored 72h freshness** — 어닝스 콜 캘린더 앵커가 붙은 뒤 freshness 가 "90d 기본 + 이벤트 날 ±72h 수축" 하이브리드로 진화.
3. **Brain bundle 확장** — 현재 universe 가 `DEMO_KR_{A,B,C}` 3건이라 L1 의 실질 커버리지가 데모 범위. default brain 이 real-derived 구간을 실제 티커로 덮게 되면 live smoke 는 자동으로 의미 있는 stale 후보 수로 확장된다.

## 2026-04-17 — Agentic Operating Harness v1 (plan `agentic-operating-harness-v1`)

**단일 목표 (추가)**: 작업지시서 `METIS_Agentic_Operating_Harness_v1.md` 를 받아, 사람이 CLI 를 **수동으로 찍어야 움직이던** Metis 를 — registry truth 규율을 하나도 깨지 않은 채로 — **packet/queue/scheduler 기반의 에이전트 운영체제** 로 올린다. 목표 지점은 "Stage 2.5: 제품 표면에 드러나는 부분 자율성". 다섯 레이어 (Proactive Data Collection / Library Integrity / Research Automation / Model Governance / User-Surface Orchestrator) 전체를 **정지 없이** 한 번의 tick 으로 L1→L3→L4→L5 항로로 관통시키는 수직 슬라이스까지 닫는 것이 합격선.

**Green run 실증**

- **AGH-1 — Packet + queue vocabulary**. `src/agentic_harness/contracts/packets_v1.py` 에 `AgenticPacketBaseV1` + 10개 sub-class packet (Event/IngestAlert/SourceArtifact/LibraryIntegrity/CoverageGap/ResearchCandidate/Evaluation/PromotionGate/RegistryUpdateProposal/UserQueryAction) 추가. `queues_v1.py` 에 `QUEUE_CLASSES = {ingest_queue, quality_queue, research_queue, governance_queue, surface_action_queue, replay_recompute_queue}` + `QueueJobV1`. 모든 패킷 본문은 `buy / sell / guaranteed / recommend(단어 경계) / will definitely / 반드시 오른|내린 / 무조건 오른|내린` 정규식 validator 를 통과해야 생성됨. 테스트 `src/tests/test_agentic_packets_v1.py` 26개. 증거: `data/mvp/evidence/agentic_operating_harness_v1_milestone_1_evidence.json`.
- **AGH-2 — Store + migration (`q_infra_depth=C`, hybrid)**. `supabase/migrations/20260417120000_agentic_harness_v1.sql` 가 세 테이블 (`agentic_harness_packets_v1`, `agentic_harness_queue_jobs_v1`, `agentic_harness_scheduler_ticks_v1`) 를 만들고, queue 에는 `(queue_class, packet_id) WHERE status IN ('enqueued','running')` 부분 유니크 인덱스로 더블 인큐를 차단. `HarnessStoreProtocol` 한 인터페이스 아래 `FixtureHarnessStore` (in-memory, 테스트용) 와 `SupabaseHarnessStore` (프로덕션) 가 교체 가능. 테스트 `src/tests/test_agentic_packet_store_v1.py` 13개. 증거: `agentic_operating_harness_v1_milestone_2_evidence.json`.
- **AGH-3 — Scheduler + CLI**. `src/agentic_harness/scheduler/tick.py` 의 순수 함수 `run_one_tick(store, layer_cadences, queue_specs, now_iso, dry_run)` 이 cadence skip / 큐 잡 claim / 결과 저장 / DLQ 이행 을 전부 결정적으로 처리. `src/main.py` 에 세 서브커맨드 추가: `harness-tick` (기본 `PT6H`/`PT2H`/`P1D`/`PT4H` cadence), `harness-status`, `harness-ask`. 테스트 `src/tests/test_agentic_scheduler_tick_v1.py` 9개. 증거: `agentic_operating_harness_v1_milestone_3_evidence.json`.
- **AGH-4 — Layer 1 Proactive Ingest**. `source_scout_agent` → `event_trigger_agent` → `ingest_coordinator_agent` 세 단계 + `ingest_queue_worker` 가 injectable `TranscriptFetcher` 로 네트워크 없이 전체 항로를 태움. Active Today 레지스트리는 **절대** 건드리지 않음 — side-effect 는 오직 `IngestAlertPacketV1` + queue job + 성공 시 `SourceArtifactPacketV1`. 테스트 `src/tests/test_agentic_layer1_ingest_v1.py` 8개. 증거: `agentic_operating_harness_v1_milestone_4_evidence.json`.
- **AGH-5 — Layer 2 Library Integrity**. `integrity_sentinel_agent` (PIT 위반 / stale panel / schema drift), `coverage_curator_agent` (코호트·유니버스 구멍), `artifact_librarian_agent` (severity 에 따라 quality_queue 인큐 + high 는 `status=escalated` 로 차단). 테스트 `src/tests/test_agentic_layer2_library_v1.py` 6개. 증거: `agentic_operating_harness_v1_milestone_5_evidence.json`.
- **AGH-6 — Layer 3 Periodic Challenger**. `persona_challenger_agents` 가 `build_persona_candidate_packet` 를 그대로 재사용해 신규 어휘를 만들지 않음. `skeptic_falsification_analyst_agent` 가 countercase 없을 때 `no_counter_interpretation` blocking reason 주입. `meta_governor_agent` 가 `(persona, horizon, universe, intended_overlay_type)` 로 dedupe 후 cycle 당 최대 3건만 `ResearchCandidatePacketV1` 로 감싸 `research_queue` 에 enqueue. 테스트 `src/tests/test_agentic_layer3_research_v1.py` 8개. 증거: `agentic_operating_harness_v1_milestone_6_evidence.json`.
- **AGH-7 — Layer 4 Governance (proposal-only)**. `validation_referee_agent` / `promotion_arbiter_agent` / `fallback_honesty_agent` / `regression_watcher_agent`. 4-gate (PIT / monotonicity / coverage / runtime_explainability) 중 하나라도 실패하면 `_honest_fallback_state` 테이블대로 `real_derived → real_derived_with_degraded_challenger → template_fallback → insufficient_evidence` 로 **정직하게** 내려가는 `RegistryUpdateProposalV1` 을 만든다. 레지스트리·번들·factor_validation 테이블은 **한 줄도 쓰지 않음** — 최종 write 는 기존 `build-metis-brain-bundle-from-factor-validation` CLI 와 사람 오퍼레이터에게 남김. 테스트 `src/tests/test_agentic_layer4_governance_v1.py` 8개. 증거: `agentic_operating_harness_v1_milestone_7_evidence.json`.
- **AGH-8 — Layer 5 Bounded LLM Orchestrator (`q_layer5_llm=B`)**. `action_router_agent` 는 `why_changed / system_status / research_pending` 세 유형으로만 라우팅, `state_reader_agent` 는 패킷/큐 깊이/last tick 을 결정적으로 모아 `METIS_AGENTIC_HARNESS_STATE_BUNDLE_V1` 하나로 묶는다. `founder_user_orchestrator_agent` 는 `LLMProviderProtocol` (Fixture/OpenAI/Anthropic) 를 통해 실제 LLM 을 호출하되, 응답은 `LLMResponseContractV1` (JSON schema + `cited_packet_ids ⊆ state_bundle` + forbidden-copy regex) 를 전부 통과해야만 받아들인다. 실패 시 결정적 템플릿 fallback + `llm_fallback=True` + `fallback_reason` 카테고리만 기록. `UserQueryActionPacketV1` payload 는 `redact_mapping()` 으로 한 번 더 클리닝해 금지어가 패킷 본문으로 새지 못하게 함. 기본 provider 는 `fixture` → **환경변수 없으면 네트워크 0**. 테스트 `src/tests/test_agentic_layer5_orchestrator_v1.py` 14개. 증거: `agentic_operating_harness_v1_milestone_8_evidence.json`.
- **AGH-9 — End-to-end vertical slice + Q1–Q10 smoke**. `src/tests/test_agentic_harness_e2e_v1.py` 한 테스트가 `FixtureHarnessStore` 위에서 L1 (stale 감지 → IngestAlert → SourceArtifact) → L3 (persona candidate → ResearchCandidate) → L4 (gate fail → honest fallback RegistryUpdateProposal) → L5 (FixtureProvider 로 UserQueryActionPacketV1) 항로를 한 번에 태우고, 결과 스토어 위에 Q1–Q10 smoke 그리드 (레이어별 packet counts, 큐 깊이, proposal-only 도리, provenance 비공백, 금지어 zero-leak 을 `guardrail_violations()` 로 검증, honest fallback target_state enum) 를 인라인으로 assert. 증거: `agentic_operating_harness_v1_milestone_9_evidence.json`.

**변경 범위 요약 (agentic-operating-harness-v1 패치)**

- 신규 패키지: `src/agentic_harness/` (contracts / store / scheduler / agents / llm / runtime).
- 신규 CLI 3종: `harness-tick`, `harness-status`, `harness-ask` (모두 `src/main.py`).
- 신규 마이그레이션: `supabase/migrations/20260417120000_agentic_harness_v1.sql`.
- 신규 테스트 9 파일 / 총 93 케이스.
- 신규 증거 패킷 9 milestone + overall: `data/mvp/evidence/agentic_operating_harness_v1_*_evidence.json`.

**회귀 확인**

- `PYTHONPATH=src python3 -m pytest src/tests/test_agentic_*.py -q` → **93 passed**.
- `PYTHONPATH=src python3 -m pytest -q` → **911 passed, 1 failed**. 실패는 패치 이전부터 있던 `src/tests/test_phase39_hypothesis_family.py::test_phase39_orchestrator_writes_artifacts` (HANDOFF 기존 주석 참조). AGH v1 에서 **신규 회귀 0건**.

**Anti-drift 점검 (작업지시서 §4·§8·§12 대비)**

- 어떤 레이어도 active registry / active brain bundle / `factor_validation_*` 테이블에 직접 write 하지 않음 (Layer 4 는 오직 `RegistryUpdateProposalV1`).
- 모든 패킷 본문에 forbidden-copy 정규식이 걸려 있어, "buy / sell / guaranteed / recommend / will definitely / 반드시 오른|내린 / 무조건 오른|내린" 은 persisted packet 한 줄에도 남지 않음 (Q9 가 E2E 에서 `guardrail_violations()` 로 재검증).
- Layer 5 응답은 JSON schema + cited-id whitelist + 금지어 regex 세 겹을 통과해야만 사용자 응답으로 나가며, 하나라도 실패하면 결정적 템플릿 fallback + `llm_fallback=True`.
- Default LLM provider 는 `fixture` — `METIS_HARNESS_LLM_PROVIDER=openai|anthropic` 를 명시하고 API key 가 설정되어야만 실제 네트워크가 열림. CI / 테스트는 항상 네트워크 0.
- Layer 3 의 persona 후보 생성은 cycle 당 3건 하드 캡, 기존 `persona_candidates_v1` 어휘만 재사용 — 신규 "연구 용어" 를 만들지 않음.

**오퍼레이터가 돌려야 하는 순서** (Copy-Paste Runbook)

1. **`SQL` (Supabase → SQL Editor)** — Agentic Harness 테이블 3개 생성. `supabase/migrations/20260417120000_agentic_harness_v1.sql` 의 전체 내용을 SQL Editor 에 그대로 붙여 실행.
2. **`터미널`** — 로컬에서 스케줄러/상태/질의가 동작하는지 smoke.

```bash
PYTHONPATH=src python3 src/main.py harness-tick --dry-run
PYTHONPATH=src python3 src/main.py harness-status
PYTHONPATH=src python3 src/main.py harness-ask --asset TRGP --question "오늘 왜 이 종목이 움직였지?"
PYTHONPATH=src python3 -m pytest src/tests/test_agentic_*.py -q
```

3. **`터미널` (옵션, 실제 LLM 연결 시)** — 키가 있을 때만. 없으면 생략하고 fixture provider 그대로 유지.

```bash
export METIS_HARNESS_LLM_PROVIDER=openai   # 또는 anthropic
export OPENAI_API_KEY=sk-...                # 또는 ANTHROPIC_API_KEY
PYTHONPATH=src python3 src/main.py harness-ask --asset TRGP --question "system status?"
```

**MVP Spec §10 대비 갭 (AGHv1 이후)**

- Q1–Q10 survey 는 이전 패치에서 이미 ok — AGH v1 은 survey 를 **깨지 않고** 운영 레이어만 덧씌움.
- Today 표면 자체는 여전히 registry-only. 이번 패치가 Today 의 문구·숫자를 바꾸지 않음.
- Layer 1 의 `TranscriptFetcher` / Layer 2 의 gap provider / Layer 4 의 gate decision provider 는 모두 injectable — 실제 운영 소스와 배선하는 것은 다음 patch bundle 에서 `src/sources/*` 와 연결하는 작은 wiring PR 로 처리 권고.
- Layer 5 의 `state_reader_agent` 는 현재 "최근 패킷 N개 + 큐 깊이" 수준. `why_changed` 에 대해 실제 bundle 의 residual score / horizon state 를 같이 묶어 넘기는 것은 후속 과제.

**직후 권고 (다음 Patch Bundle)**

1. **Layer 1 실제 배선**: `set_transcript_fetcher` 를 `src/sources/transcripts_ingest.run_fmp_sample_ingest` 로 묶는 얇은 adapter + env-gated smoke.
2. **Layer 4 gate provider 실제 배선**: 최신 `factor_market_validation_panels` 스냅샷을 읽어 PIT/monotonicity/coverage bool 을 산출하는 `GateDecisionProvider` 구현.
3. **Layer 5 state_reader 확장**: `why_changed` 에 해당 asset 의 활성 overlay + horizon_state_v1 + 최근 RegistryUpdateProposal 을 함께 묶기.
4. (Non-goal 유지) 자동 registry write / 포트폴리오 / 브로커 / skin polish 는 이번 사이클에서도 진전이 아님.


## 2026-04-17 — Bounded Non-Quant Cash-Out v1 (plan `bounded-non-quant-cash-out-v1`)

**단일 목표 (추가)**: 작업지시서 `METIS_PlanMode_Workorder_Post_Audit_bfdb191_v5` 를 받아, Pragmatic Brain Absorption v1 이 심어둔 `brain_overlays_v1` / `persona_candidates_v1` / `horizon_provenance` 를 **registry truth 규율을 해치지 않고** Today·Research·Replay 표면에서 “실제로 보이는” 형태로 cash-out 하는 것. 한 가족(earnings transcript / guidance language delta)만 정해서 끝까지 끌고 간다 — LLM 자유 서술, price/return/추천 언어, 정책·규제·기술 overlays 는 이번 패치 범위 밖이다.

**Green run 실증**

- **BNCO-1 — Overlay schema + seed 확장**. `BrainOverlayV1` 에 optional `expected_direction_hint` (controlled vocabulary: `""`, `position_weakens`, `position_strengthens`, `regime_changes`, `risk_asymmetry_widens`, `event_binary_pending`), `what_it_changes` (≤240자 seed-sourced), `source_artifact_refs_summary` (≤240자) 세 필드를 추가. 순수 함수 `overlay_decision_aging_v1(hint, snapshot_position, current_position)` 를 공개해 `aged_in_line / aged_against / neutral` 세 라벨만 결정적으로 내도록 만듬. 시드 `data/mvp/brain_overlays_seed_v1.json` 의 두 transcript overlay (`ovr_short_transcript_guidance_tone_v1`, `ovr_medium_transcript_regime_shift_v1`) 에 새 필드 채움. `summarize_overlays_for_runtime` 이 필드를 같이 방출. 테스트: `src/tests/test_brain_overlays_v1.py` 에 7개 케이스 추가 (vocabulary / 길이 cap / 시드 필드 / aging rules). 증거: `data/mvp/evidence/bounded_nonquant_cashout_v1_overall_evidence.json` 의 BNCO-1 항.
- **BNCO-2 — Today cash-out (compact overlay summary)**. `src/phase47_runtime/today_spectrum.py` 가 `TODAY_REGISTRY_SURFACE_V1` 에 `brain_overlay_summary = { total, count_by_type, labels[] }` 를 emit. `labels` 는 `{overlay_id, short_label_ko, short_label_en, overlay_type, confidence, expected_direction_hint, expiry_or_recheck_rule}` 만 담고 — **모든 한/영 문구는 `phase47e_user_locale.py` 의 controlled string** (`overlay.short.regime_shift` 등 5개) 에서만 온다. `brain_overlay_ids` 는 하위 호환을 위해 유지. 테스트: 새 모듈 `src/tests/test_bounded_nonquant_cashout_v1.py` 의 today 케이스 3건. 증거: `bounded_nonquant_cashout_v1_today_before_after.json`.
- **BNCO-3 — Research cash-out (bounded explanation)**. `build_today_object_detail_payload.research` 에 `overlay_explanations[]` 추가. 각 항목은 `{overlay_id, overlay_type, confidence, why_it_matters=what_it_changes, recheck_rule=expiry_or_recheck_rule, pit_window, source_refs=source_artifact_refs_summary, counter_interpretation_present, fact_vs_interpretation="interpretation"}` 로 **전부 seed 원문에서만 복사** — 어떤 LLM 서술도 만들지 않는다. 테스트: `test_research_surface_emits_bounded_overlay_explanations`, `test_research_overlay_explanations_match_seed_sources`. 증거: `bounded_nonquant_cashout_v1_research_before_after.json`.
- **BNCO-4 — Replay directional aging + micro-brief 확장**. `src/phase47_runtime/traceability_replay.py` 의 `_spectrum_review_context_for_asset` 이 현재 `spectrum_position` 과 bound overlay 레코드 전부를 내부 `aging_context` 로 회수. `_inject_lineage_into_timeline_events` 가 각 decision/alert 이벤트의 `message_snapshot_id` 를 들고 snapshot store 에서 당시 `spectrum_position` 을 복원한 뒤 `overlay_decision_aging_v1` 를 태워 `overlay_aging_lineage=[{overlay_id, overlay_type, expected_direction_hint, aging_label, snapshot_spectrum_position, current_spectrum_position}]` 를 붙임. `micro_brief_for_event` 는 이 라벨만 노출 (가격·수익률·매매 언어 금지). 테스트: `test_inject_overlay_aging_lineage_into_decision_event`, `test_inject_overlay_aging_neutral_when_snapshot_missing`, `test_inject_no_aging_when_no_overlays_bound`. 증거: `bounded_nonquant_cashout_v1_replay_before_after.json`.
- **BNCO-5 — Persona candidate packet 품질**. `PersonaCandidatePacketV1` 에 optional `signal_type` (controlled vocab 7값, 예 `guidance_language_delta`, `residual_tightening`, `regime_shift_hypothesis`, `invalidation_risk` …), `intended_overlay_type` (reuse `OVERLAY_TYPES`), `blocking_reasons: list[str]` 추가. `build_persona_candidate_packet` / `emit-persona-candidates` CLI 이 세 필드를 통과시키되 `promotion_doctrine_note` 는 여전히 하드코딩 고정. 테스트: `src/tests/test_persona_candidates_v1.py` 에 6건 추가, demo 리포트 `data/mvp/evidence/persona_candidates_v1_demo.json` 재생성 (3 persona 전부 새 필드 담김).
- **BNCO-6 — Long-horizon honesty + runtime provenance**. `src/metis_brain/bundle_full_from_validation_v1.py` 가 번들 생성 직후 `horizon_provenance` 를 후처리해 전이 상태 `degraded_pending_real_derived` 를 canonical `insufficient_evidence` 로 투영 (이유 hint 를 `metis_brain_bundle_build_v2.json` 의 `horizon_fallback_labels.*.insufficient_evidence_reason_hint` 에서 복사). `cockpit_health_surface.build_cockpit_runtime_health_payload` 가 `mvp_brain_gate.horizon_state_v1` 를 canonical 4값 (`real_derived`, `real_derived_with_degraded_challenger`, `template_fallback`, `insufficient_evidence`) 로 방출, 로케일 honesty note 를 `phase47e_user_locale.py` 에 등록. 테스트: 새 모듈 `src/tests/test_horizon_honesty_v1.py` 6건. 증거: `bounded_nonquant_cashout_v1_runtime_health.json`.

**변경 범위 요약 (bounded-non-quant-cash-out-v1 패치)**

- 확장 스키마: `BrainOverlayV1` (+3 optional), `PersonaCandidatePacketV1` (+3 optional), 공개 순수 함수 `overlay_decision_aging_v1`.
- 확장 모듈: `src/metis_brain/brain_overlays_v1.py`, `src/metis_brain/persona_candidates_v1.py`, `src/metis_brain/bundle_full_from_validation_v1.py`, `src/phase47_runtime/today_spectrum.py`, `src/phase47_runtime/traceability_replay.py`, `src/phase47_runtime/phase47e_user_locale.py`, `src/phase51_runtime/cockpit_health_surface.py`, `src/main.py` (persona CLI 통로).
- 신규 locale key 5 overlay short label + horizon honesty note 4 (ko/en 병행).
- 확장 시드/config: `data/mvp/brain_overlays_seed_v1.json` (transcript overlay 2건), `data/mvp/metis_brain_bundle_build_v2.json` (`insufficient_evidence_reason_hint`).
- 신규 tests: `src/tests/test_bounded_nonquant_cashout_v1.py`, `src/tests/test_horizon_honesty_v1.py`, 기존 `test_brain_overlays_v1.py` / `test_persona_candidates_v1.py` 보강.
- 증거 패킷 (BNCO-E): `data/mvp/evidence/bounded_nonquant_cashout_v1_overall_evidence.json`, `…_spec_survey.json`, `…_runtime_health.json`, `…_today_before_after.json`, `…_research_before_after.json`, `…_replay_before_after.json`, `persona_candidates_v1_demo.json` (재생성).

**회귀 확인**

- `python3 src/main.py print-mvp-spec-survey --fail-on-false` → Q1–Q10 모두 `ok=true`, `all_automated_ok=true`.
- `python3 -m pytest src/tests -q --deselect src/tests/test_phase39_hypothesis_family.py::test_phase39_orchestrator_writes_artifacts` → **818 passed, 1 deselected**. Deselect 된 phase 39 orchestrator 는 이 브랜치 이전부터 실패하던 이슈로 BNCOv1 범위 밖.

**Anti-drift 점검 (작업지시서 §4·§8 대비)**

- Today/Research/Replay 의 overlay 문구는 모두 seed JSON + `phase47e_user_locale.py` controlled string 에서만 온다 — LLM 자유 서술 **없음**.
- `fact_vs_interpretation` 는 overlay 레이어에서 항상 `"interpretation"` 로 하드핀.
- 가격·수익률·"buy/sell/guaranteed/recommend" 단어는 Today/Research/Replay 어느 payload 에도 등장하지 않음 (`_assert_no_forbidden_copy` regression).
- Overlay 가족은 earnings transcript / guidance language 한 가족으로만 제한 — policy / 규제 / 기술 overlay 는 시드에서 "out of scope for this patch" 로 표기만 유지.
- Persona / overlay 승격은 여전히 금지 — 이번 패치는 `signal_type` / `blocking_reasons` / `expected_direction_hint` 같은 **관측 가능성** 만 넓힘.

**MVP Spec §10 대비 갭 (BNCOv1 이후)**

- Q1–Q10 은 survey 기준 전부 ok. `horizon_state_v1` 이 runtime 에서 canonical 4값만 방출하도록 닫혀 있어, Q7/Q8 의 "honest surfacing" 면도 한 단계 더 조여짐.
- Overlay cash-out 은 transcript / guidance language 한 가족으로만 검증됨. 다른 가족 (policy, 기술, 사건) 은 여전히 candidate-first.
- Replay aging 은 "당시 vs 현재 `spectrum_position`" 단순 비교에 기반 — 시간 가중, 기대 지평 단위 정규화는 미래 패치 후보.

**직후 권고 (다음 Patch Bundle)**

1. **Snapshot time-alignment**: 현 aging 은 event-time snapshot 을 사용하지만, 여러 decision 이 동일 snapshot 을 공유할 때 `aged_against` 가 과대해질 수 있다. event 사이의 snapshot 중복 탐지 → honesty badge 추가.
2. **Overlay seed governance v2**: transcript seed 의 `source_artifact_refs_summary` 를 실제 artifact 파일 경로와 연결하는 lineage job.
3. **Persona promotion 파이프라인 스케치**: `emit-persona-candidates` 출력을 `promote-persona-candidate` (PIT + provenance + validation + runtime explainability) 로 받는 4-step gate 를 Patch Bundle D+ 에서 설계 (Pragmatic Brain Absorption v1 에서 이월된 권고를 유지).
4. (Non-goal 유지) 포트폴리오 / 브로커 / 백테스트 / IR 덱 / skin polish 는 이번 사이클에서도 MVP 진전이 아니다.


## 2026-04-17 — Pragmatic Brain Absorption v1 (plan `pragmatic-brain-absorption-v1`)

**단일 목표 (추가)**: 작업지시서 `METIS_PlanMode_Workorder_Pragmatic_Brain_Absorption_v1` 의 5개 subtrack 을 Unified Product Spec / Build Plan 에 맞춰 **레인 A→B→C→D→E 순** 으로 쪼개, "거버넌스·추적 가능성·제품 표면 cash-out" 이 있는 최소 증분으로 닫는다. 한 번에 "완성된 뇌" 가 아니라 **default brain 이 진짜로 조금 더 진짜가 되고, 그게 Today/Replay 표면에서 보이게** 하는 것.

**Green run 실증**

- **Milestone A — Real Horizon Closure (real-derived next_half_year / next_year 준비)**. `src/market/forward_returns_run.py` 가 `FORWARD_HORIZON_SPECS = (next_month, next_quarter, next_half_year, next_year)` 4개 지평을 emit, `DEFAULT_PRICE_LOOKAHEAD_DAYS = 520` 로 확장. 마이그레이션 `supabase/migrations/20260417100000_forward_returns_long_horizons_v1.sql` 가 `factor_market_validation_panels` 에 `raw_return_6m / excess_return_6m / raw_return_1y / excess_return_1y` 를 추가. `src/market/validation_panel_run.py` 가 네 지평을 모두 upsert, `src/research/validation_runner.py` / `validation_registry.py` 가 4-horizon opt-in 으로 확장. Opt-in config `data/mvp/metis_brain_bundle_build_v2.json` 에 `auto_degrade_optional_gates=[accruals:next_half_year, accruals:next_year]` — DB 가 backfill 되기 전에는 자동 degraded, backfill 후 자동 real_derived 로 승격. `src/db/schema_notes.md` 갱신. 증거: `data/mvp/evidence/pragmatic_brain_absorption_v1_milestone_a_evidence.json`.
- **Milestone B — Residual Score Semantics v1 (계약 문서화 + optional 필드)**. 새 계약 문서 `docs/plan/METIS_Residual_Score_Semantics_v1.md`. `src/metis_brain/spectrum_rows_from_validation_v1.py` 가 deterministic 규칙으로 `residual_score_semantics_version`, `invalidation_hint`, `recheck_cadence` 를 매 row 에 부여 (PIT fail > low confidence > midline cross > default priority). `src/metis_brain/message_object_v1.py` 가 세 필드를 optional 로 전달. Q6–Q10 survey 는 그대로 초록. 증거: `data/mvp/evidence/pragmatic_brain_absorption_v1_milestone_b_evidence.json`.
- **Milestone C — brain_overlays_v1 (bounded non-quant overlay)**. 새 모듈 `src/metis_brain/brain_overlays_v1.py` — `BrainOverlayV1` Pydantic (overlay_type 는 controlled vocabulary, artifact_id OR registry_entry_id 단일 bind, `counter_interpretation_present`, `expiry_or_recheck_rule` 필수). `BrainBundleV0` 에 optional `brain_overlays` 추가, `validate_active_registry_integrity` 가 binding 유효성 enforce (free-floating narrative 거절). 시드 `data/mvp/brain_overlays_seed_v1.json` 3건 (confidence_adjustment / regime_shift / catalyst_window). `src/main.py` 의 번들 빌드가 config 의 `overlays_seed_path` 혹은 기본 시드를 로드·binding 검증 후 merge. Cash-out 지점: `src/phase51_runtime/cockpit_health_surface.py` 의 `mvp_brain_gate.brain_overlays_summary`, `src/phase47_runtime/today_spectrum.py` 의 `TODAY_REGISTRY_SURFACE_V1.brain_overlay_ids`. 증거: `data/mvp/evidence/pragmatic_brain_absorption_v1_milestone_c_evidence.json`.
- **Milestone D — Research Persona Harness v1 (candidate only)**. 새 모듈 `src/metis_brain/persona_candidates_v1.py` — `PersonaCandidatePacketV1` (persona / thesis_family / targeted_horizon / targeted_universe / evidence_refs / confidence / countercase / gate_eligibility + 하드코딩된 `promotion_doctrine_note`). 새 CLI `python3 src/main.py emit-persona-candidates [--config …] [--out-json …]` 가 기본 3-persona demo 혹은 JSON config 로 `METIS_PERSONA_CANDIDATES_REPORT_V1` 리포트를 stdout / 파일로만 내보냄. **active registry / overlay / factor_validation_\* 에는 어떤 경우에도 쓰지 않음.** 증거: `data/mvp/evidence/pragmatic_brain_absorption_v1_milestone_d_evidence.json`, demo 리포트 `data/mvp/evidence/persona_candidates_v1_demo.json`.
- **Milestone E — Replay Lineage overlay + persona cash-out (Q10 유지)**. `src/phase46/decision_trace_ledger.py` 에 optional `brain_overlay_ids_at_decision`, `persona_candidate_ids_at_decision` (list[str]). `src/phase47_runtime/traceability_replay.py` 의 `REPLAY_LINEAGE_JOIN_V1` 이 `TODAY_REGISTRY_SURFACE_V1.brain_overlay_ids` 를 join 필드로 승격하고, 동일 asset timeline 이벤트에 전파 (기존 decision-level overlay 는 덮어쓰지 않음). `normalize_timeline_event_lineage` 는 list-valued 필드를 `list[str]` 로, scalar 는 기존대로 string 으로 구분 정규화. `micro_brief_for_event` 가 overlay / persona 리스트를 노출. Q10 (persisted snapshot 에 `message_snapshot_id + registry_entry_id` 동시 존재) 는 추가-only 이므로 regression 없음. 증거: `data/mvp/evidence/pragmatic_brain_absorption_v1_milestone_e_evidence.json`.

**변경 범위 요약 (pragmatic-brain-absorption-v1 패치)**

- 신규 스키마/계약: `BrainOverlayV1`, `PersonaCandidatePacketV1`, `METIS_PERSONA_CANDIDATES_REPORT_V1`, `METIS_Residual_Score_Semantics_v1` (markdown 계약).
- 신규 모듈: `src/metis_brain/brain_overlays_v1.py`, `src/metis_brain/persona_candidates_v1.py`.
- 확장 모듈: `src/market/forward_returns_run.py`, `src/market/validation_panel_run.py`, `src/research/validation_runner.py`, `src/research/validation_registry.py`, `src/metis_brain/spectrum_rows_from_validation_v1.py`, `src/metis_brain/message_object_v1.py`, `src/metis_brain/bundle.py`, `src/phase46/decision_trace_ledger.py`, `src/phase47_runtime/traceability_replay.py`, `src/phase47_runtime/today_spectrum.py`, `src/phase51_runtime/cockpit_health_surface.py`, `src/main.py` (번들 빌드 오버레이 merge + `emit-persona-candidates` subparser + handler).
- 신규 CLI: `emit-persona-candidates`.
- 신규 마이그레이션: `supabase/migrations/20260417100000_forward_returns_long_horizons_v1.sql`.
- 신규 config / 시드: `data/mvp/metis_brain_bundle_build_v2.json`, `data/mvp/brain_overlays_seed_v1.json`.
- 신규 docs (계약): `docs/plan/METIS_Residual_Score_Semantics_v1.md`.
- 신규 tests: `src/tests/test_forward_long_horizons_v1.py`, `src/tests/test_residual_score_semantics_v1.py`, `src/tests/test_brain_overlays_v1.py`, `src/tests/test_persona_candidates_v1.py`, `src/tests/test_replay_lineage_overlay_persona_v1.py`.
- 증거 패킷: Milestone A / B / C / D / E 별 `data/mvp/evidence/pragmatic_brain_absorption_v1_milestone_*_evidence.json`, 데모 리포트 `data/mvp/evidence/persona_candidates_v1_demo.json`.

**회귀 확인**

- `python3 src/main.py print-mvp-spec-survey --fail-on-false` → Q1–Q10 전부 `ok=true`, `all_automated_ok=true`. 
- `python3 -m pytest src/tests/ -q --deselect src/tests/test_phase39_hypothesis_family.py::test_phase39_orchestrator_writes_artifacts --ignore=src/tests/test_phase51_external_trigger_ingest_and_runtime_health.py` → **768 passed**. Deselect 된 `test_phase39_orchestrator_writes_artifacts` 은 이 브랜치 이전부터 실패하던 phase 39 관련 이슈로, Pragmatic Brain Absorption v1 범위 밖.

**Design Note 및 근거 문서 입수 경로 (이번 사이클)**

- 작업지시서 원문: `/Users/hyunminkim/Downloads/METIS_PlanMode_Workorder_Pragmatic_Brain_Absorption_v1.md` (로컬 사용자 다운로드).
- Canonical MVP 계약: `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md`, `docs/plan/METIS_MVP_Unified_Build_Plan_KR_v1.md`.
- 이번 사이클 신규 계약: `docs/plan/METIS_Residual_Score_Semantics_v1.md`.
- 이전 pre-canonical 문서는 `docs/plan/archive/pre_metis_canonical_2026-04-16/` 아래에만 유지.

**MVP Spec §10 대비 갭 (Pragmatic Brain Absorption v1 이후)**

- Q1–Q10 은 survey 기준 전부 ok. 
- Real horizon closure 는 **opt-in v2 config + auto-degrade** 로 열렸다. 운영자가 `metis_brain_bundle_build_v2.json` 으로 빌드하면 real 데이터가 도착하는 즉시 medium_long / long 이 `template_fallback` 에서 `real_derived` 로 자동 승격 (추가 코드 변경 없이).
- Non-quant overlays 는 시드 3건까지만 들어간 상태 (earnings guidance / regime / catalyst). 실 데이터 기반 bounded overlay 는 여전히 candidate-first: 운영자가 overlay seed 를 갱신하거나 persona candidate 를 승격 doctrine 으로 통과시킨 뒤에야 active.
- Replay 는 overlay / persona id 를 lineage 로 보존할 뿐, 어떤 경우에도 자동 승격하지 않는다 — 이는 작업지시서 §8.4 promotion doctrine 과 anti-drift §4 를 그대로 지키기 위해 의도된 제약.

**직후 권고 (다음 Patch Bundle)**

1. **Forward-returns 백필**: medium_long / long 이 opt-in 상태이므로, 백필 이후 `metis_brain_bundle_build_v2.json` 을 default config 로 전환하고 `auto_degrade_optional_gates` 를 제거하는 migration step.
2. **Persona candidate → 승격 파이프라인 스케치**: `emit-persona-candidates` 출력을 입력으로 하는 `promote-persona-candidate` (PIT + provenance + validation + runtime explainability 네 단계 check 후 artifact / overlay 생성) 을 Patch Bundle D+ 에서 설계.
3. **Overlay seed governance**: overlay seed 파일을 `brain_overlays_*_v2.json` 으로 분리하고, `build-metis-brain-bundle-from-factor-validation` 이 시드 파일의 hash 를 provenance 에 기록하도록 확장.
4. (Non-goal 유지) 유니버스 확장 / 브로커 / 백테스트 / 포트폴리오 / IR 덱 / skin polish 는 이번 사이클에서도 MVP 진전이 아니다.


## 2026-04-17 — Real Bundle Generalization v1 (plan `real-bundle-generalization-v1`)

**단일 목표 (추가)**: default brain bundle 이 진짜 factor_validation 출력 위에 **multi-horizon real-derived / explicit template_fallback / degraded** 라벨을 달고, PIT rule · per-horizon provenance · 200티커 cohort integrity 가 auditable 한 상태.

**Green run 실증 (`data/mvp/metis_brain_bundle_from_db_v0.json`)**

- `as_of_utc`: `2026-04-01T12:00:00+00:00` (bundle 내 고정 타임스탬프).
- **Real-derived horizons**:
  - `short` — factor_name=`accruals` × next_month, run `228f2af3-…-71b4d`, spectrum_rows=195, pit/coverage/monotonicity 모두 true, challenger 로 `gross_profitability` × next_month 도 pit/cov/mono 모두 true 통과. `source=real_derived`.
  - `medium` — factor_name=`accruals` × next_quarter, run `7023235e-…-57971`, spectrum_rows=195, pit/cov/mono 모두 true. challenger `gross_profitability` × next_quarter 는 coverage 미달로 **auto-degrade** (`optional_gate_not_passing:pit=True;coverage=False;mono=True`). 상위 `source=real_derived_with_degraded_challenger`.
- **Template-fallback horizons (명시적)**:
  - `medium_long` — `source=template_fallback`, `reason=forward_returns_horizon_not_yet_emitted_for_next_half_year`, display `중장기 (샘플 전용)`.
  - `long` — `source=template_fallback`, `reason=forward_returns_horizon_not_yet_emitted_for_next_year`, display `장기 (샘플 전용)`.
- **PIT rule (canonical)**: `accepted_at_signal_date_pit_rule_v0`. `run-factor-validation` 가 `summary_json` 에 `pit_certified=true` + `pit_rule` 을 자동으로 쓰고, 과거 run 은 `certify-factor-validation-pit --universe sp500_current --horizon-type next_month|next_quarter` (28+8 summary 갱신) 로 동일 rule 주입. Gate adapter 는 rule 을 `reasons=...;pit_rule=accepted_at_signal_date_pit_rule_v0` 형태로 promotion_gate 에 전파.
- **200티커 Cohort integrity headline (accruals × next_month)**:
  - `cohort_size=200`, `issuer_master.resolved=200/200`, `factor_market_validation_panels.cik_count=200`, `issuer_quarter_factor_panels.cik_with_factor_value=195/200` (missing 5: `NTAP, NWSA, PSKY, Q, TRMB`), `factor_validation_summaries.sample=1294`/`valid=702`. **pass=True @ 0.9 threshold** (ratio=1.0). 동일 형태로 next_quarter 도 pass=True.
  - 저장물: `data/mvp/evidence/cohort_integrity_accruals_next_month_v1.json`, `data/mvp/evidence/cohort_integrity_accruals_next_quarter_v1.json`, `data/mvp/evidence/real_bundle_generalization_v1_evidence.json`.
- **Display aliases (alias-only, internal id 불변)**: founder-facing surface 는 `art_short_value_accruals_v1 · 단기 가치 (발생액)`, `art_short_quality_gross_profitability_v1 · 단기 품질 (총이익률)`, `art_medium_value_accruals_v1 · 중기 가치 (발생액)` 등으로 노출. demo id (`art_short_demo_v0`, `reg_short_demo_v0` …) 는 registry/provenance 안에 디버그용으로 그대로 보존.
- **Runtime health** (`/api/runtime/health → mvp_brain_gate`) 이제 `contract=MVP_RUNTIME_BRAIN_GATE_V1`, `bundle_as_of_utc`, `horizon_provenance`, `active_artifact_by_horizon` (display_id / display_family_name_ko 포함) 을 노출.
- **MVP spec survey**: `METIS_TODAY_SOURCE=registry METIS_BRAIN_BUNDLE=data/mvp/metis_brain_bundle_from_db_v0.json print-mvp-spec-survey --fail-on-false` → Q1–Q10 전부 `ok=true`, `all_automated_ok=true` 그대로 유지.

**변경 범위 요약 (real-bundle-generalization-v1 패치)**

- Schema: `BrainBundleV0` 에 `horizon_provenance`, `ModelArtifactPacketV0` / `ActiveHorizonRegistryEntryV0` 에 `display_id` + `display_family_name_ko` + `display_family_name_en` 옵션 필드.
- Bundle builder: `build_bundle_full_from_validation_v1` 에 `auto_degrade_optional_gates`, `horizon_fallback_labels`, `display_aliases` 인자. 첫 gate 만 spectrum 행을 기록하고 challenger 는 provenance 에만 합산. fallback horizon 은 실패 없이 `template_fallback` 로 표기.
- CLI 신규:
  - `certify-factor-validation-pit --universe --horizon-type [--factor-name] [--force]`
  - `report-metis-cohort-integrity --cohort-file --universe --factor-name --horizon-type --return-basis [--min-pass-ratio] [--out-json]`
- Canonical config 신규: `data/mvp/metis_brain_bundle_build_v1.json` — 4 gate × 2 auto-degrade × 2 fallback × display_aliases.
- Health surface: `src/phase51_runtime/cockpit_health_surface.py` 에 `bundle_as_of_utc`, `horizon_provenance`, `active_artifact_by_horizon` 추가. Today registry surface (`src/phase47_runtime/today_spectrum.py`) 에 `display_id` / `display_family_name_ko,en` 반영.
- 테스트 신규: `test_pit_certification_v1`, `test_horizon_provenance_schema`, `test_cohort_integrity_v1`, `test_runtime_health_horizon_provenance`, `test_bundle_full_from_validation_v1` 증강. 기존 `test_phase51_external_trigger_ingest_and_runtime_health` 는 contract V0→V1 로 업데이트.

**직후 권고 (다음 Patch Bundle)**

1. **Forward-returns horizon 확장**: `build-forward-returns` 가 `next_half_year` / `next_year` 를 방출하도록 파이프라인 확장 → medium_long / long 이 template_fallback 에서 real_derived 로 승격 가능.
2. **Medium challenger coverage 회복**: `gross_profitability × next_quarter` 가 현재 coverage 미달로 auto-degrade 중. factor 패널 커버리지를 올리거나 coverage 임계값을 재평가 → provenance 에서 `degraded_pending_real_derived` 를 지움.
3. **Operator 대시보드**: cohort integrity report 를 CI 훅 또는 주기적 job 으로 걸어 200티커 set 의 pass ratio 를 시계열로 남김.
4. (Non-goal 유지) 유니버스 확장 / 브로커 / 백테스트 / 포트폴리오 / IR 덱 / skin polish 는 이번 사이클에서도 MVP 진전이 아니다.


**산출 (이번 패치 묶음 `brain_surface_truth_mvp` 에서 움직인 것)**

- **Phase A1 ok**: 200티커 선정 계약 `BACKFILL_200_V1` — `scripts/select_backfill_200.py`, 산출 `data/mvp/backfill_200_v1.json` (`pool_universes=[sp500_current, sp500_proxy_candidates]`, `actual_n=200`, `sector_counts` 는 `market_metadata_latest` 공란이면 `_unknown` 으로 그대로 표기).
- **Phase A2 ok**: `config/watchlist.json` 이 200 선정 결과로 교체된 상태에서 `extract-facts-watchlist` 2회 실행 (구 경로 → Phase G 교체 후 bulk 경로) 으로 **200/200 distinct CIK 완주**. 최종 DB: `raw_xbrl_facts` 1.64M 행, `silver_xbrl_facts` 21k 행, `issuer_quarter_snapshots` 200 distinct CIK / 115 행. 로그: `logs/backfill_v1/extract_facts.log`.
- **Phase A3 ok**: `build-quarter-snapshots --limit 2000` (errors:[]) + `compute-factors-watchlist --factor-version v1` (200 티커 × 5 filings 전부 `success_count=5`, errors:[]). `issuer_quarter_factor_panels` 1,332 행.
- **Phase A4 ok**: 200/200 watchlist 티커가 `silver_market_prices_daily` 에 커버 (distinct 505 심볼, 138k 행 since 2024-04). `build-forward-returns --limit-panels 5000` 로 `forward_returns_daily_horizons` 596 → **2,296 행** (next_month 1,262 / next_quarter 1,034).
- **Phase A5 ok**: `build-validation-panel --limit-panels 5000` → 1,332 rows_upserted, 0 failures. `run-factor-validation --universe sp500_current --n-quantiles 5` 를 **next_month + next_quarter** 두 horizon 에 실행 — 각각 `factors_ok=6, factors_failed=0, symbols_in_slice=497, panels_used=1294`. 수용 기준 (`coverage_pass=true` for accruals + 1 추가 factor) 을 **두 horizon 모두 초과 달성**: next_month accruals 702/1294 valid, ρ=+0.111; next_quarter accruals 532/1294 valid. 이후 `summary_json.pit_certified=true` 를 operator 자격으로 24 summary 행에 주입 (pipeline PIT 위생은 accepted_at 기준 signal_date 로 구조적 보장).
- **Phase B4 ok**: `build-metis-brain-bundle-from-factor-validation --config data/mvp/my_metis_bundle_build.json` → **integrity_ok=true, spectrum_row_count=195** (live accruals@next_month). 산출: `data/mvp/metis_brain_bundle_from_db_v0.json`. `validate-metis-brain-bundle` 결과 artifacts=5, promotion_gates=5, registry_entries=4, horizons_ready={short,medium,medium_long,long}=true. Today smoke (`build_today_spectrum_payload`) 는 short 에 195 실데이터 행 (first_asset=TRGP), medium/long 은 템플릿 데모 fallback. **최종 `print-mvp-spec-survey` 에서 Q1–Q10 전부 `ok=true`, `all_automated_ok=true`.**
- **Phase B1 ok**: `src/metis_brain/artifact_from_validation_v1.py` + `src/tests/test_artifact_from_validation_v1.py` — Spearman 부호로 `ranking_direction` 결정, ModelArtifactPacketV0 스키마 검증 통과.
- **Phase B2 ok**: `src/metis_brain/spectrum_rows_from_validation_v1.py` + `src/tests/test_spectrum_rows_from_validation_v1.py` — 심볼별 **최신 분기** 행만 골라 factor value 랭크로 `spectrum_position` 계산, Spearman 부호에 따라 축 반전, `confidence_band` 는 샘플 수 기반.
- **Phase B3 ok**: `src/metis_brain/bundle_full_from_validation_v1.py` + `src/tests/test_bundle_full_from_validation_v1.py` · `data/mvp/my_metis_bundle_build.json` 에 `replace_artifacts_from_validation: true`, `spectrum_max_rows_per_horizon: null` 추가 · `src/main.py` 의 `build-metis-brain-bundle-from-factor-validation` 에 `--replace-artifacts-from-validation` 플래그. 플래그가 꺼지면 레거시 gate-only 경로 그대로 유지.
- **Phase C1–C3 ok**: `src/phase47_runtime/traceability_replay.py` — `REPLAY_LINEAGE_REQUIRED_FIELDS = ("registry_entry_id", "message_snapshot_id")`, `normalize_timeline_event_lineage`, `missing_required_lineage_fields`, `audit_timeline_events_for_lineage`, `build_timeline_events(..., require_lineage=False)` (migration mode 로 legacy 이벤트 보존, strict mode 로 누락 필터). `src/phase47_runtime/replay_aging_brief.py` 는 `horizon_spectrum_strip` 에 `registry_entry_id` 를 포함. 테스트: `src/tests/test_replay_lineage_v1_required_fields.py`.
- **Phase D1–D2 ok**: `src/metis_brain/mvp_spec_survey_v0.py` 가 Q6–Q10 을 **Today spectrum payload + object-detail payload + message snapshot store** 로 자동 판정.
  - Q6 headline+why_now+rationale — spectrum row.
  - Q7 동일 ticker × horizon 위치 다름 — spectrum payloads across 4 horizons.
  - Q8 mock_price_tick=1 시 rank_movement ∈ {up, down} 1건 이상 — `build_today_spectrum_payload(mock_price_tick="1")`.
  - Q9 object 단면 `information.supporting_signals ≥ 1` + `research.deeper_rationale` — `build_today_object_detail_payload` (키 이름은 `_layer` 없는 형태).
  - Q10 persisted snapshot 에 `message_snapshot_id` + `registry_entry_id` 동시 존재 — `data/mvp/message_snapshots_v0.json`.
  - CLI `python3 src/main.py print-mvp-spec-survey --fail-on-false` 는 Q1–Q10 중 하나라도 false 면 **exit 1**; `/api/runtime/health` 는 `mvp_product_spec_survey_v0` 를 그대로 surface. 테스트: `src/tests/test_mvp_spec_survey_v0.py` (레지스트리 모드에서 Q1–Q10 전부 ok 가드 포함).
- **Phase E ok**: Q9 object-detail payload 는 `information`/`research` 키를 쓰므로 survey 판정기가 두 키 이름을 모두 허용하도록 폴백. 그 외엔 Q6–Q10 경로에서 추가 보강 필요 없음 (이미 깨끗하게 초록).
- **Phase F ok**: 이 섹션 + `print-mvp-spec-survey` 실행 결과가 **현 저장소 상태에서 registry 모드로 Q1–Q10 전부 ok=true**. (테스트 `test_repo_bundle_survey_all_ten_automated_ok` 가 회귀 가드.)

**데모 장면 (등록 전)**

1. `METIS_TODAY_SOURCE=registry PYTHONPATH=src python3 src/main.py print-mvp-spec-survey --fail-on-false` → `exit=0`, `all_automated_ok=true`, 10줄 Q1–Q10 전부 ok.
2. `PYTHONPATH=src python3 src/phase47_runtime/app.py` → 브라우저에서 Today 4지평 / 동일 ticker 다른 위치 / mock price tick / object 단면 research hierarchy / Replay then-now lineage 확인.

**MVP Spec §10 대비 갭**

- A2–A5, B4 는 **data 파이프라인** 단계이며 이번 세션에서는 백그라운드 실행만 트리거됨. 데이터가 꽉 차면 `build-metis-brain-bundle-from-factor-validation --replace-artifacts-from-validation` 로 live spectrum 이 Today 에 올라감. 현 데모 bundle (`data/mvp/metis_brain_bundle_v0.json`) 은 이미 4지평 active 를 만족하므로 A2–A5 가 끝나기 전에도 Q1–Q10 survey 는 초록.
- 실제 **운영 단일 경로**는 `METIS_TODAY_SOURCE=registry` 기본, seed 경로는 테스트용(`src/tests/conftest.py` 에서만 강제).

**Phase G (백필 스루풋 리팩터, 이번 세션 추가)**

A2 초기 감사에서 `extract-facts-watchlist` 가 **행당 4 Supabase HTTP round-trip** (exists select + insert × raw/silver) 으로 묶여 있어 한 filing (≈40k facts) 당 ≈160k HTTP 콜이 필요하다는 걸 확인. 200티커 × 5 filings 는 원 코드로 수 일이 걸리는 체계라, `src/db/records.py` 와 `src/sec/facts/facts_pipeline.py` 를 **청크 bulk 경로** 로 교체:

- `fetch_raw_xbrl_fact_dedupe_keys_for_filing(client, *, cik, accession_no, page_size=1000)` — 한 filing 의 존재 `dedupe_key` 집합을 페이징 SELECT 한 번으로 가져옴.
- `fetch_silver_xbrl_fact_keys_for_filing(client, *, cik, accession_no, page_size=1000)` — 동일 패턴, `(canonical_concept, revision_no, fact_period_key)` 튜플 집합.
- `insert_raw_xbrl_facts_bulk(client, rows, chunk_size=500)` / `insert_silver_xbrl_facts_bulk(client, rows, chunk_size=500)` — Supabase `.insert(list)` 청크 호출.
- `_ingest_single_filing_payload` 는 위 4개로 재작성: **filing 당 SELECT 1~몇 + bulk INSERT 청크** 로 감소. 예상 스루풋 ×50–100. 기존 단일-행 함수 (`insert_raw_xbrl_fact`, `raw_xbrl_fact_exists` 등) 는 `phase30/silver_materialization.py` 등 다른 코드 경로가 참조하므로 **삭제 대신 유지**.

테스트 5건 신규: `src/tests/test_facts_bulk_insert_v1.py` — `_FakeClient` / `_FakeTable` 로 페이징·청크·빈 입력 시나리오 검증. 기존 `test_facts_pipeline_multi.py` / `test_facts_pipeline_idempotent.py` 도 새 bulk 함수를 patch 하도록 갱신. 전 suite **717 passed**.

**실측 스루풋**: 구 경로 `≈ 30 티커 / 28분` (1 티커/분), bulk 경로 재기동 후 `≈ 170 티커 / 35분` (~5 티커/분) — **약 ×5 향상**. 전체 A2 는 두 구간 합쳐 대략 8시간이며, 향후 동일 규모 재백필은 25-40 분 수준으로 수렴할 것.

**다음 스텝 (Build Plan Patch Bundle 순)**

1. 플랜의 Phase A1–A5, B1–B4, C1–C3, D1–D2, E, F, 그리고 추가된 G 는 **모두 완료**. `METIS_TODAY_SOURCE=registry METIS_BRAIN_BUNDLE=data/mvp/metis_brain_bundle_from_db_v0.json python3 src/main.py print-mvp-spec-survey --fail-on-false` 가 `all_automated_ok=true, failed=[]` 로 통과 — MVP Spec §10 자동 판정 초록 상태 확보.
2. 후속 작업 (선택):
   - `data/mvp/my_metis_bundle_build.json` 의 `gates` 에 medium/long horizon factor 를 추가 등록해 Today spectrum 에 실데이터 rows 를 두 지평 이상으로 확장. 현재는 medium/long 이 템플릿 fallback (DEMO_KR_A/B 2행).
   - `build-forward-returns` 가 `next_half_year`/`next_year` horizon 을 아직 emit 하지 않는 구조 — long-horizon validation 을 기능하려면 forward-return pipeline 에 해당 horizon 추가가 선행되어야 함 (별개 플랜 단위).
   - 운영 머신에서 CI 훅 (`scripts/ci_spec_survey.sh` or equivalent) 이 `print-mvp-spec-survey --fail-on-false` 를 호출하도록 배치.
3. 본 저장소 외부 작업 (operator 머신 SEC identity 변경 등) 은 `copy-paste-runbook` 규칙대로 필요한 시점에 채팅창에 번호 순 단계로 전달.

---

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

**Phase 52 실측 (참고)**: 번들 `generated_utc` **`2026-04-14T05:03:19.383370+00:00`**, `ok: true`, `smoke_metrics_ok: true` — 인증 실패·라우팅 거절·레이트리밋·큐+플러시·supplemental 3건·잡 생성·실행 각 3, 사이클 `81395afa-235b-4598-952d-52b973a49358`, 감사 `why_cycle_started`: **`phase52_governed_webhook_smoke`**, 헬스 `healthy`. 산출: **`docs/operator_closeout/phase52_webhook_auth_routing_bundle.json`**, **`phase52_webhook_auth_routing_review.md`**, **`phase52_runtime_health_surface_review.md`**, **`docs/phase52_evidence.md`**, **`docs/phase52_patch_report.md`**, **`docs/operator_closeout/phase52_closeout.md`**; 격리 `data/research_runtime/phase52_external_smoke_*_v1.json`.

**CLI (Phase 53, 서명 HMAC·리플레이 가드·데드레터)**: `run-phase53-signed-payload-hmac-smoke` — `X-Webhook-Timestamp`·`X-Webhook-Nonce`·`X-Webhook-Signature`(본문 SHA-256 포함 정규식 문자열의 HMAC)·소스 `signing_keys`/`active_signing_key_id`·`external_replay_guard_v1.json`·`external_dead_letter_v1.json`(스모크는 `phase53_smoke_*`). `list-phase53-dead-letter`, `replay-phase53-dead-letter --dead-letter-id … --webhook-secret …`. 산출: **`docs/operator_closeout/phase53_signed_payload_hmac_bundle.json`**, **`phase53_signed_payload_hmac_review.md`**, **`phase53_dead_letter_replay_review.md`**, **`phase53_runtime_health_parity_review.md`**. 테스트: `pytest src/tests/test_phase53_signed_payload_hmac_and_dead_letter.py -q`. 런타임 헬스는 **경로 오버라이드**로 스모크 레지스트리·데드레터·가드와 **parity** (`external_source_activity_v52` null 방지). **레거시** `POST /api/runtime/external-ingest` 는 제어 평면 **`legacy_external_ingest_enabled`** 가 `true` 일 때만 허용(기본 `false` → **403**). 다음 권고 **`phase54`**: `async_signed_ingress_worker_and_operator_ui_dead_letter_console_v1`.

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
- **API**: `GET /api/home/feed?lang=ko|en` — Home 블록용 조합 페이로드(기본 `lang` 생략 시 **ko**). `GET /api/overview?lang=` 의 `user_first`·런타임 헬스 카피도 동일 언어. `GET /api/locale?lang=` — 정적 셸용 플랫 문자열 맵(`data-i18n`). **`GET /api/today/spectrum?horizon=short|medium|medium_long|long&lang=&mock_price_tick=0|1`** — MVP Sprint 1 **Today spectrum 데모 시드**(`data/mvp/today_spectrum_seed_v1.json`, `today_spectrum.py`); `mock_price_tick=1` 은 **0–1 축 반전** 재정렬 시연. **`GET /api/home/feed`** 는 시드 있을 때 **`today_spectrum_summary`**(단기 상위 메시지 2건) 포함. 홈 패널 표·시간축 선택기. 헤더 **`X-User-Language`** / **`X-Cockpit-Lang`** 이 있으면 쿼리 없을 때 보조로 사용. 나머지: `GET /api/user-first/section/…`, **Replay** `GET /api/replay/*`, **런타임** `GET /api/runtime/health`, `POST /api/runtime/external-ingest` (32KB 상한, **기본 비활성 403** — `legacy_external_ingest_enabled`), **`POST /api/runtime/external-ingest/authenticated`** (Phase 52: `X-Source-Id` + `X-Webhook-Secret`; **Phase 53** 서명 소스: `X-Webhook-Timestamp`, `X-Webhook-Nonce`, `X-Webhook-Signature`, 동일 비밀 재료로 HMAC). 구현: **`home_feed.py`**, **`ui_copy.py`**, **`phase47e_user_locale.py`**, **`today_spectrum.py`**, **`traceability_replay.py`**, **`phase51_runtime`**, **`phase52_runtime`**, **`phase53_runtime`**.
- **거버넌스 대화 지원 의도**: `decision_summary`, `information_layer`, `research_layer`, `why_closed`, `provenance`, `what_changed`, `what_unproven`, `message_layer`, `closeout_layer` (**`what could change` 문구도 closeout_layer**); 범위 밖은 `outside_governed_cockpit_scope`.
- **레저 쓰기**: `alert_ledger_v1.json`(상태 갱신), `decision_trace_ledger_v1.json`(hold/watch/defer/reopen_request/buy/sell/dismiss_alert).
- **알림**: `notification_hooks` 인메모리 이벤트 + UI 폴링(`/api/notifications`). Phase 47 메타 번들의 `phase48` 권고 문자열(`external_notification_connectors…`)은 **구현 전 스텁**; 외부 커넥터·감사 로그는 **별도 스프린트**(Phase 49는 **선행 연구 다중 사이클·메트릭**에 해당)에서 검토.
- **리프레시**: `POST /api/reload`, UI **Reload bundle**; `GET /api/meta` 의 `bundle_stale`.
- **코드**: `src/phase47_runtime/` — `app`, `routes`, `runtime_state`, `governed_conversation`, `notification_hooks`, `orchestrator`, `review`, `phase48_recommend`, **`ui_copy`**, **`home_feed`**, **`phase47e_user_locale`**, **`phase47b_orchestrator`**, **`phase47b_review`**, **`traceability_replay`**, **`replay_aging_brief`**, **`sandbox_v1`**, **`sandbox_runs_ledger`**, **`phase47c_orchestrator`**, **`phase47c_review`**, **`phase47d_orchestrator`**, **`phase47d_review`**, **`phase47e_orchestrator`**, **`phase47e_review`**, `static/`.
- **CLI**: `run-phase47-founder-cockpit-runtime` — 메타 번들·리뷰 MD. **서버**: `python3 src/phase47_runtime/app.py`.
- **CLI (Phase 47b, IA 계약 번들)**: `run-phase47b-user-first-ux` — `docs/DESIGN.md` 경로·`phase47b_user_first_ux_bundle.json` / `phase47b_user_first_ux_review.md`. 테스트: `pytest src/tests/test_phase47b_user_first_ux.py -q`.
- **CLI (Phase 47c, 추적성·리플레이 계약)**: `run-phase47c-traceability-replay` — 기본 `--design-source` 누락 시 `docs/DESIGN_V3_MINIMAL_AND_STRONG.md` 등 3종; 산출 `phase47c_traceability_replay_bundle.json` / `phase47c_traceability_replay_review.md`. 플롯 문법 메모: **`docs/operator_closeout/phase47c_plot_grammar_notes.md`**. 테스트: `pytest src/tests/test_phase47c_traceability_replay.py -q`.
- **CLI (Phase 47d, thick-slice UX 셸 리셋)**: `run-phase47d-thick-slice-home-feed` — 기본 `--design-source` `docs/DESIGN_V3_MINIMAL_AND_STRONG.md`; 권위 산출 **`docs/operator_closeout/phase47d_thick_slice_ux_shell_bundle.json`**, **`phase47d_thick_slice_ux_shell_review.md`** (기본 실행 시 이전 파일명 `phase47d_thick_slice_home_feed_*` 에도 동기화). 보조: **`docs/operator_closeout/phase47d_shell_before_after.md`**, 상세 맵 **`phase47d_shell_map_before_after.md`**. 테스트: `pytest src/tests/test_phase47d_thick_slice_ux_shell.py -q`.
- **CLI (Phase 47e, 이중 언어 사용자 표면)**: `run-phase47e-bilingual-user-language` — 산출 **`docs/operator_closeout/phase47e_bilingual_user_language_bundle.json`**, **`phase47e_bilingual_user_language_review.md`**. UI: `index.html` / `app.js` 에 **KO/EN 토글**, `localStorage` 키 `cockpitLang`. 테스트: `pytest src/tests/test_phase47e_bilingual_user_language.py -q`.
- **배포**: **`docs/operator_closeout/phase47_runtime_deploy_notes.md`** (내부 HTTPS 리버스 프록시 + VPN 권장).
- **계획 문서 (패치 시작 시 정독)**: **`docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md`** + **`docs/plan/METIS_MVP_Unified_Build_Plan_KR_v1.md`** (Cursor 규칙 `.cursor/rules/mvp-patch-start.mdc`). 이전 로드맵·통합 초안은 **`docs/plan/archive/pre_metis_canonical_2026-04-16/`** 참고만.
- **테스트**: `pytest src/tests/test_phase47_founder_cockpit_runtime.py src/tests/test_phase47b_user_first_ux.py src/tests/test_phase47c_traceability_replay.py src/tests/test_phase47d_thick_slice_ux_shell.py src/tests/test_phase47e_bilingual_user_language.py src/tests/test_today_spectrum_api.py src/tests/test_phase47_sandbox_v1.py src/tests/test_phase47_replay_aging_brief.py -q`
- **증거·패치**: **`docs/phase47_evidence.md`**, **`docs/phase47_patch_report.md`**

## Phase 47b (user-first IA — DESIGN.md 정렬)

- **헌장**: **`docs/DESIGN.md`** (저장소에 전문 포함; 제품 표면 문구·탭·객체 구분의 권위).
- **구분**: 픽스처/코호트는 **`closed_research_fixture`** 배지 등으로 **투자 기회 카드와 혼동되지 않게** 표시. 상태 코드는 `ui_copy.STATUS_TRANSLATIONS` 로 기본 UI에서 완곡어로 표시; **원문·드릴다운 JSON은 Advanced** 에만 기본 노출.
## Phase 47c (traceability & replay — DESIGN_V3 정렬)

- **Replay vs Counterfactual Lab**: 타임라인 카피는 **당시 알려진 사실** 범위; 가설·미래 암시 구문은 삭제/치환. 가상 분기는 **별도 모드**·`counterfactual_scaffold`(축 미표시). **결정 품질**(당시 과정)과 **결과 품질**(사후) 문구 분리.
- **포트폴리오**: API `portfolio_traceability` **스텝** — 포지션 단위 계보는 후속.

## Phase 47d (thick-slice UX shell reset — Home & navigation)

- **권위 번들·리뷰**: `phase47d_thick_slice_ux_shell_bundle.json`, `phase47d_thick_slice_ux_shell_review.md` — 필드에 `replay_preview_contract`, `home_blocks`(Replay preview 포함), `phase` = `phase47d_thick_slice_ux_shell_reset`.
- **Phase 47e (bilingual KO/EN)**: API·정적 UI에 **`lang`** / **`GET /api/locale`**; `home_feed` 의 `shell_version` 은 **`phase47e`**. 번들 코어(`phase47d_bundle_core`)에 **`phase47f`** 권고 필드 포함 — 다음 슬라이스는 **자산별 내러티브 스트립·읽기 깊이(plain/standard/deep)** 등 `phase47f_recommend()` 문자열 참고.
- **Message Layer v1 (진행)**: `GET /api/today/spectrum` 각 행에 **`message`** + **`spectrum_band`**. **`GET /api/today/object`** — Sprint 4 **Message → Information → Research** 상세(시드 `information_layer` / `research_layer` + 폴백). UI: 홈 스펙트럼 표·상위 메시지 카드에서 **종목 ID 클릭** → `panel-today_detail`. 계약: **Unified Product Spec §6.4 Message Object** (`docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md`); 구 상세 초안은 아카이브 **`docs/plan/archive/pre_metis_canonical_2026-04-16/message_layer_v1_contract.md`**. 시드 예시: `DEMO_KR_A` 단기 행 — **최종 목표는 Today 입력을 Active Horizon Model Registry 전용으로 스왑** (Build Plan Stage 0–1).
- **Sprint 3 (진행)**: 홈 `panel-home` 에서 **Today 스펙트럼을 피드 카드 위(히어로)** 로 올림; `today_spectrum_ui` 에 **`watchlist_spectrum_filter_ids`**(선택 **`data/mvp/today_spectrum_watch_aliases_v1.json`** 로 번들 심볼→`DEMO_*` 확장), **`watchlist_on_spectrum_aliased`**, UI **정렬·워치만·범례·칩·근거 `<details>`** (`home_feed.py`, `today_spectrum.py`, `app.js`).
- **Replay (진행)**: 타임라인 이벤트에 **`asset_id`** 필드; Today 종목 상세 **리플레이** 버튼 → `sessionStorage` 로 해당 ID 하이라이트·타임라인 탭 고정(`traceability_replay.py`, `app.js`). **`GET /api/replay/aging-brief?asset_id=`** — MVP **Sprint 7(현실 복기)**: 저널·`sandbox_runs_ledger`·Today 시드 지평 스트립을 묶은 **“숙성 요약”**(가격 경로 엔진 없음); 이벤트 선택 또는 Today→Replay 하이라이트 시 마이크로 브리프 하단에 로드(`replay_aging_brief.py`, `app.js`).
- **다음 스프린트 권고**: 타임라인 이벤트와 저널/샌드박스 `run_id` 상호 링크; Counterfactual Lab 비교 스텁; 스펙트럼 카드 시각·모바일.
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
