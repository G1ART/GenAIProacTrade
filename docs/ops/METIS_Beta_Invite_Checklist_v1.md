# METIS Beta — Invite Checklist v1

**Patch 12 (2026-04-23).** Short SQL-first checklist for every invite state
transition. Pair with `METIS_Private_Beta_Deployment_Runbook_v1.md` — this
doc assumes Supabase + Railway 는 이미 설정되어 있음.

상태 머신:

```
   (Auth user 생성)
          │
          ▼
      invited ──────► active ───────► paused
                         │               │
                         ▼               ▼
                     revoked         revoked
```

## 1. Invite — 새 유저 추가 (`SQL`)

1. Supabase 대시보드 → **Authentication** → **Users** → **Add user**
   → **Create new user (passwordless)** 로 이메일만 입력해 UUID 발급.
2. SQL Editor 에서 아래 실행:

```sql
insert into public.beta_users_v1 (user_id, email, status, role, notes)
values (
  '<PASTE-AUTH-UUID-HERE>',
  'user-email@example.com',
  'invited',
  'beta_user',
  'YYYY-MM-DD invite wave <n>'
)
on conflict (user_id) do update
set email  = excluded.email,
    status = 'invited',
    role   = excluded.role,
    notes  = excluded.notes;
```

3. 사용자에게 `https://YOUR_APP.up.railway.app/login.html` URL 공유 →
   사용자가 매직 링크로 로그인.

## 2. Activate — 첫 로그인 후 승격 (`SQL`)

대부분은 자동입니다. `POST /api/auth/session` 가 첫 호출되는 순간 서버가
`profiles_v1.last_seen_at` 를 upsert 하고, `beta_users_v1.status = 'invited'`
는 그대로 유지됩니다. 관리자가 명시적으로 **active** 로 올리려면:

```sql
update public.beta_users_v1
   set status = 'active',
       activated_at = coalesce(activated_at, now())
 where email = 'user-email@example.com';
```

## 3. Pause — 임시 접근 차단 (`SQL`)

유저의 세션은 즉시 끊기지 않지만 (JWT 는 1h 유효), 다음 API 호출부터
`beta_paused` 로 401 이 발생합니다.

```sql
update public.beta_users_v1
   set status = 'paused'
 where email = 'user-email@example.com';
```

재개:

```sql
update public.beta_users_v1
   set status = 'active'
 where email = 'user-email@example.com';
```

## 4. Revoke — 완전 차단 (`SQL`)

```sql
update public.beta_users_v1
   set status = 'revoked'
 where email = 'user-email@example.com';
```

Revoked 유저는 `/api/auth/session` 을 포함한 **모든** API 경로에서 401 을
받습니다 (`beta_revoked`). `/login.html` 자체는 열리지만 세션 활성화가
실패합니다.

완전 삭제가 필요하면 Supabase 대시보드 → **Authentication** → **Users**
에서 해당 row 를 삭제하세요. `auth.users(id)` 가 삭제되면 `on delete
cascade` 로 `beta_users_v1`, `profiles_v1`, `product_usage_events_v1` 의
관련 row 가 함께 정리됩니다.

## 5. 확인 쿼리 (`SQL`)

```sql
-- 현재 초대 상태 요약
select status, count(*) from public.beta_users_v1 group by status;

-- 최근 7일 활동한 유저 상위 10명
select p.display_name,
       bu.email,
       count(e.id) as events_7d,
       max(e.occurred_at) as last_event_at
  from public.beta_users_v1 bu
  left join public.profiles_v1 p using (user_id)
  left join public.product_usage_events_v1 e
         on e.user_id = bu.user_id
        and e.occurred_at >= now() - interval '7 days'
 group by p.display_name, bu.email
 order by events_7d desc
 limit 10;

-- 상위 event_name
select event_name, count(*) from public.product_usage_events_v1
 where occurred_at >= now() - interval '7 days'
 group by event_name
 order by count(*) desc;
```

## 6. Admin UI 에서 확인

admin/internal role 로 `/ops` 로그인 → **Beta Admin** 탭 → **Refresh**.
4 섹션 (Invited users / Sessions / Top events / Trust signals) 가
위 SQL 과 동일한 숫자를 보여야 합니다.
