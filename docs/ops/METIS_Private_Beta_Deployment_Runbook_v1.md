# METIS Private Beta — Deployment Runbook v1

**Patch 12 (2026-04-23).** This runbook is the **only** document you need
to put METIS online for invited beta users. Follow each step in order.
Each block marks its **type** — `SQL` (Supabase → SQL Editor) vs `터미널`
(local shell / Railway CLI).

Scope:
- 5–10 명 초대 유저가 실제로 로그인 → Product Shell 사용
- 서버는 account-level telemetry 를 bounded taxonomy 로 적재
- Ops Cockpit (`/ops`) 은 customer 에게 계속 404 (env-gated)

Non-goals (이번 패치 밖): public signup, billing, full entitlement.

---

## 0. 준비물

- Supabase 프로젝트 1개 (Free 플랜으로 충분)
- Railway 계정 + 이 저장소에 연결된 서비스 2개 (`web`, `worker`)
- 로컬에서 `git pull`, `python3 -V >= 3.11`, `psql` (optional)
- 프로덕트 URL (예시: `https://metis-<something>.up.railway.app`)

---

## 1. Supabase — 마이그레이션 적용

### 1-a. (`SQL`) `beta_users_v1` / `profiles_v1` / `product_usage_events_v1` 생성 + RLS + 4 admin view

Supabase 대시보드 → **SQL Editor** 에서 이 저장소의 다음 파일을 그대로
복붙해 실행하세요:

```
supabase/migrations/20260423100000_patch_12_private_beta_auth_tracking_v1.sql
```

파일 안의 모든 블록이 `begin;` … `commit;` 하나로 감싸져 있어 재실행이 안전
합니다 (idempotent — `create table if not exists` + `drop policy if exists` +
`create or replace view`).

### 1-b. (`SQL`) 마이그레이션 확인

아래 쿼리를 실행해 기대 숫자와 일치하는지 확인하세요.

```sql
select count(*) as table_count
  from information_schema.tables
 where table_schema = 'public'
   and table_name in ('beta_users_v1', 'profiles_v1', 'product_usage_events_v1');
-- 기대: 3

select count(*) as view_count
  from information_schema.views
 where table_schema = 'public'
   and table_name in ('v_beta_users_active_v1', 'v_beta_sessions_recent_v1',
                      'v_beta_top_events_v1', 'v_beta_trust_signals_v1');
-- 기대: 4

select count(*) as policy_count
  from pg_policies
 where schemaname = 'public'
   and tablename in ('beta_users_v1', 'profiles_v1', 'product_usage_events_v1');
-- 기대: ≥ 6 (테이블별 2~3 정책)
```

### 1-c. (`SQL`) RLS 동작 확인

사용자는 자기 row 만 읽을 수 있는지, anon 은 events 테이블을 못 읽는지
확인합니다.

```sql
-- 1) anon 으로는 events 가 빈 결과
set local role anon;
select count(*) from public.product_usage_events_v1;
-- 기대: 0 (RLS 가 차단)
reset role;

-- 2) service_role 로는 읽을 수 있음
select count(*) from public.product_usage_events_v1;
-- 기대: 0 이거나 현재 적재량
```

---

## 2. Supabase — Auth 설정

### 2-a. (`UI`) Magic link / OTP 활성화

Supabase 대시보드 → **Authentication** → **Providers** → **Email**:
- `Enable Email provider` = on
- `Confirm email` = off (매직 링크 발송이 곧 인증)
- `Secure email change` = on

### 2-b. (`UI`) Redirect URL 등록

Supabase 대시보드 → **Authentication** → **URL Configuration**:
- `Site URL` = `https://YOUR_APP.up.railway.app`
- `Redirect URLs` 에 추가:
  - `https://YOUR_APP.up.railway.app/login.html#callback`
  - `http://localhost:8765/login.html#callback` (로컬 smoke test 용)

### 2-c. (선택) Custom SMTP

Supabase **기본 SMTP 는 4 emails/hour** 제한이 있습니다. 10명 이상 초대
한다면 **Resend / Postmark / AWS SES** 중 하나로 custom SMTP 를 설정하
세요. **Authentication → SMTP Settings** 에서 입력합니다.

---

## 3. Railway — 환경변수 (5 + 3 기존)

Railway 대시보드 → `web` 서비스 → **Variables** 에 아래를 채워 넣으세요.
`worker` 서비스에도 동일 값을 넣거나 **Shared Variables** 를 사용하세요.

| 키                              | 값 소스                                           |
|---------------------------------|--------------------------------------------------|
| `SUPABASE_URL`                  | Project Settings → API → Project URL             |
| `SUPABASE_SERVICE_ROLE_KEY`     | Project Settings → API → service_role key        |
| `SUPABASE_ANON_KEY`             | Project Settings → API → anon key                |
| `SUPABASE_JWT_SECRET`           | Project Settings → API → JWT Settings → JWT Secret |
| `SUPABASE_AUTH_REDIRECT_URL`    | `https://YOUR_APP.up.railway.app/login.html#callback` |
| `METIS_BETA_ALLOWLIST_MODE`     | `enforce` (production) / `shadow` (stage) / `off` |
| `METIS_TELEMETRY_ENABLED`       | `1`                                              |
| `EDGAR_IDENTITY`                | 이미 설정되어 있어야 함 (`.env.example` 참고)     |

**중요**: `SUPABASE_JWT_SECRET` 과 `SUPABASE_SERVICE_ROLE_KEY` 는 **절대**
브라우저에 노출되지 않습니다. `/api/runtime/auth-config` 가 클라이언트
부트스트랩용으로 **anon_key 만** 반환합니다.

---

## 4. Railway — 배포

### 4-a. (`터미널`) 최신 main 을 푸시

```bash
git push origin main
```

### 4-b. (`UI`) 서비스가 healthy 인지 확인

Railway 대시보드 → `web` → **Deployments** 에서 최신 빌드가 녹색인지 확
인. 건강체크는 기본 `GET /api/runtime/health` (200 혹은 503) 입니다.

### 4-c. (`터미널`) healthcheck 확인

```bash
curl -fsS https://YOUR_APP.up.railway.app/api/runtime/health | python3 -m json.tool
```

---

## 5. 첫 초대 유저 (`SQL`)

### 5-a. Supabase Auth 에 유저 생성

Supabase 대시보드 → **Authentication** → **Users** → **Add user** →
**Send magic link** 혹은 **Create new user (passwordless)** 를 눌러
유저 1명을 만듭니다. 이 때 `auth.users(id)` 에 UUID 가 발급됩니다.

### 5-b. 초대 row 등록

SQL Editor 에서 UUID 를 복붙한 뒤 아래를 실행:

```sql
insert into public.beta_users_v1 (user_id, email, status, role, notes)
values (
  '<PASTE-AUTH-UUID-HERE>',
  'user-email@example.com',
  'invited',
  'beta_user',
  'First beta invite — Patch 12 rollout'
)
on conflict (user_id) do update
set email = excluded.email, status = 'invited', role = excluded.role, notes = excluded.notes;
```

### 5-c. 사용자에게 로그인 링크 공유

- 사용자에게 `https://YOUR_APP.up.railway.app/login.html` URL 을 공유
- 사용자가 이메일 입력 → "Send secure sign-in link" → 메일박스에서 링크 클릭
- 클릭 후 브라우저가 자동으로 `/login.html#callback` → 서버 `/api/auth/session` → `/` 로 이동

---

## 6. Admin — 첫 admin 지정 (`SQL`)

```sql
update public.beta_users_v1
   set role = 'admin', status = 'active'
 where email = 'you@your-company.com';
```

그 뒤 admin 유저로 로그인 → `https://YOUR_APP.up.railway.app/ops`
(Ops Cockpit 은 `METIS_OPS_SHELL=1` 이 설정된 경우에만 열립니다) →
**Beta Admin** 탭 클릭 → **Refresh**.

Customer 유저 (beta_user role) 가 `/api/admin/*` 를 호출하면 403 입니다.

---

## 7. Smoke test 체크리스트

- [ ] `https://YOUR_APP.up.railway.app/login.html` 이 열린다
- [ ] 초대된 이메일로 "Send secure sign-in link" 를 누르면 메일이 온다
- [ ] 메일 링크 클릭 → 자동으로 `/` 로 이동 → Today hero 가 로딩된다
- [ ] DevTools Network 탭에서 `/api/events` 호출이 200 으로 들어간다
- [ ] 초대 안 된 이메일로 로그인 시도 → "not on allowlist" 안내
- [ ] admin 유저로 `/ops` → **Beta Admin** → 4 섹션 모두 렌더
- [ ] SQL: `select count(*) from product_usage_events_v1;` 가 증가한다

---

## 8. 롤백

만약 Auth 를 일시적으로 끄고 싶다면 Railway 에서 `SUPABASE_JWT_SECRET`
을 비우고 redeploy 하면 서버가 graceful downgrade (auth guard no-op) 로
돌아갑니다. 유저는 `/login.html` 에서 "not configured" 안내를 봅니다.
Customer 는 `/` 로 직접 접근 가능 — 이 상태는 public demo 모드 입니다.

## 9. 참고 문서

- `docs/ops/METIS_Beta_Invite_Checklist_v1.md` — invite / activate / revoke 단위 SQL
- `docs/plan/METIS_MVP_PROGRESS_VS_SPEC_KR_v1.md` — §3.9 Patch 12 범위
- `HANDOFF.md` — 최신 작업 요약
