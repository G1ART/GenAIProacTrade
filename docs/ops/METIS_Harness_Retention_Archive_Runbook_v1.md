# METIS Harness Retention · Archive Runbook (v1)

**작성 근거**: AGH v1 Patch 9 §C·A (CF-8·A 해소). `agentic_harness_packets_v1` / `agentic_harness_queue_jobs_v1` 가 장기 운영에서 무한 증가하지 않도록 **copy-then-delete** 아카이브 정책을 운영자에게 제공한다.

**스펙 권위**: `docs/plan/METIS_MVP_Unified_Product_Spec_KR_v1.md` §8 (MVP 포함/제외 경계), `docs/plan/METIS_MVP_Unified_Build_Plan_KR_v1.md` §12 (항상 지킬 문장 — Replay needs lineage: **아카이브는 감사 기록을 보존해야 한다**).

**전제 환경**: Supabase 원본 schema + Patch 9 migration 2 건 (`20260420000000_agentic_harness_retention_archive_v1.sql`, `20260420010000_agentic_harness_packets_target_scope_index_v1.sql`) 적용 완료.

---

## 1. 이 런북이 주는 것

- `harness-retention-archive` CLI 의 **정확한 운영 호출 순서**.
- **dry-run → 실제 실행** 2 단 보호 프로토콜.
- **rollback** (아카이브 되돌리기) 절차.
- **자주 발생하는 실패 모드** 와 복구.
- 운영 **주기 추천값** (Patch 10 에서 Railway cron 화 예정).

## 2. 무엇을 아카이브하고 무엇을 아카이브하지 않는가

| 대상 | 아카이브 기준 | 비고 |
|------|---------------|------|
| `agentic_harness_packets_v1` (모든 패킷) | `created_at_utc < now() - interval 'N days'` | layer 구분 없이 일괄. 감사 기록이므로 **삭제 전 아카이브** 필수. |
| `agentic_harness_queue_jobs_v1` (잡) | `updated_at_utc < now() - interval 'N days'` **AND** `status in ('done', 'dlq', 'expired')` | **terminal status 만**. `queued` / `running` / `retry_pending` 잡은 절대 건드리지 않음. |

**중요**: 아카이브는 `_archive` suffix 테이블로 **copy-then-delete** 이다. 원본 감사 기록은 항상 Supabase 에 보존된다 (다만 active 테이블이 아닌 archive 테이블에).

## 3. Pre-flight (SQL · 4 분)

운영 Supabase SQL Editor 에서 한 줄씩 실행:

1. **현재 active table 크기 확인** (`SQL`):

```sql
select 'packets_active' as t, count(*) as n from public.agentic_harness_packets_v1
union all
select 'packets_archive', count(*) from public.agentic_harness_packets_v1_archive
union all
select 'jobs_active', count(*) from public.agentic_harness_queue_jobs_v1
union all
select 'jobs_archive', count(*) from public.agentic_harness_queue_jobs_v1_archive;
```

2. **어느 시점까지 자를지 후보 확인** (예: 90일) (`SQL`):

```sql
select count(*) as would_archive_packets
  from public.agentic_harness_packets_v1
 where created_at_utc < now() - interval '90 days';

select count(*) as would_archive_jobs
  from public.agentic_harness_queue_jobs_v1
 where updated_at_utc < now() - interval '90 days'
   and status in ('done', 'dlq', 'expired');
```

3. **살아있는 큐 잡 (절대 아카이브 되면 안 되는 것) 확인** (`SQL`):

```sql
select status, count(*) from public.agentic_harness_queue_jobs_v1
 where status in ('queued', 'running', 'retry_pending')
 group by status order by status;
```

4. **git status 가 clean 인지 확인** (`터미널`):

```bash
cd /Users/hyunminkim/GenAIProacTrade && git status --short
```

## 4. Dry-run (운영자 첫 호출)

`--dry-run` 은 copy/delete 를 실행하지 않고 **무엇이 이동될 것인지** 만 리포트한다. 첫 실행 때는 반드시 dry-run 부터.

`터미널`:

```bash
cd /Users/hyunminkim/GenAIProacTrade && python3 -m src.main harness-retention-archive --days 90 --batch-size 500 --dry-run
```

기대 출력 (JSON):

- `ok: true`
- `packets.scanned = <§3·2 의 would_archive_packets 와 동일>`
- `packets.copied = 0` (dry-run 이므로)
- `packets.deleted = 0`
- `packets.dry_run = true`
- `jobs.*` 도 같은 패턴.

만약 `scanned` 가 예상치와 현저히 다르면 **즉시 중단** 하고 §7 의 실패 모드표를 참조.

## 5. 실제 실행

Dry-run 결과가 기대와 일치할 때만:

`터미널`:

```bash
cd /Users/hyunminkim/GenAIProacTrade && python3 -m src.main harness-retention-archive --days 90 --batch-size 500
```

기대 출력:

- `ok: true`
- `packets.copied == packets.scanned`
- `packets.deleted == packets.copied`
- `jobs.copied == jobs.scanned` + `jobs.deleted == jobs.copied`.
- `packets.batches` 와 `jobs.batches` 는 `ceil(scanned / batch_size)`.

**사후 검증** (`SQL`):

```sql
select 'packets_active' as t, count(*) as n from public.agentic_harness_packets_v1
union all
select 'packets_archive', count(*) from public.agentic_harness_packets_v1_archive
union all
select 'jobs_active', count(*) from public.agentic_harness_queue_jobs_v1
union all
select 'jobs_archive', count(*) from public.agentic_harness_queue_jobs_v1_archive;
```

`_archive` 쪽이 §3·1 시점 대비 증가했고, active 쪽이 감소했어야 한다.

## 6. 파트 별 옵션 (packets only / jobs only)

패킷만 아카이브:

```bash
python3 -m src.main harness-retention-archive --days 90 --batch-size 500 --skip-jobs
```

잡만 아카이브:

```bash
python3 -m src.main harness-retention-archive --days 90 --batch-size 500 --skip-packets
```

권장: **패킷과 잡을 동일 days 로 함께** 돌리는 것. 둘을 다르게 두면 lineage 조인이 깨질 수 있다.

## 7. 실패 모드와 복구

| 증상 | 원인 | 조치 |
|------|------|------|
| dry-run `scanned` 가 예상보다 **수 배 많음** | `days` 를 너무 작게 줌 (`--days 9` 등 오타) | `--days` 를 재확인. **실행하지 말 것**. |
| `jobs.scanned > 0` 인데 terminal 상태 잡이 없어야 하는 시점 | 오래된 `queued` 잡이 장기 정체 | 아카이브 대신 **운영자가 수동 expire** 처리 먼저. CLI 는 자동으로 `done/dlq/expired` 만 보지만, 정체된 queued 는 본 런북의 대상이 아님. |
| `ok: false` + `message: "supabase client not ready"` | Supabase env 미설정 | `.env` 에 `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` 확인. |
| copy 는 성공했는데 delete 가 일부 실패 | 네트워크 중단 / rate limit | 같은 명령을 **한 번 더** 실행. `copy` 는 idempotent (primary key 동일 시 skip), `delete` 는 이번에 마저 진행. active=0 확인까지 반복 안전. |
| active delete 완료 후 아카이브 조회 시 행이 **없음** | archive 마이그레이션 미적용 | §1 의 migration 2 건 (`20260420000000_*.sql`) 재적용. |

## 8. Rollback — 아카이브 되돌리기

만약 "방금 아카이브 한 것을 active 로 되돌려야 한다" 면:

`SQL` (트랜잭션 안에서):

```sql
begin;

insert into public.agentic_harness_packets_v1
select column1, column2, column3  -- 원본 컬럼만, archived_at_utc 제외
  from public.agentic_harness_packets_v1_archive
 where archived_at_utc >= now() - interval '1 hour'
on conflict (packet_id) do nothing;

-- 검증 후
commit;
```

(실제 컬럼 목록은 `supabase/migrations/20260420000000_*.sql` 을 참조.)

**주의**: rollback 은 **예외 상황용** 이다. Patch 9 의 copy-then-delete 는 이미 감사 기록을 보존하므로, 일반적으로 rollback 없이 archive 테이블에서 바로 조회하면 된다.

## 9. 주기 추천값 (Patch 10 이전)

| 운영 규모 | 추천 `--days` | 추천 cron |
|-----------|---------------|-----------|
| 개발 / 스테이징 | 30 | 수동 주 1회 |
| 200 티커 라이브 | 90 | 일 1회, UTC 03:00 |
| 500 티커 라이브 | 60 | 일 1회, UTC 03:00 |

Patch 10 (CF-10·B) 에서 Railway scheduled job 으로 등록할 예정. 그 전까지는 운영자가 수동 또는 로컬 cron 으로 호출.

## 10. 알려진 한계

- **라이브 큐 잡은 절대 건드리지 않음**: 이는 안전 보장이자 한계이다. 장기 정체된 `queued` 잡은 본 런북이 자동 정리하지 않는다 (운영자가 별도 판단).
- **아카이브 테이블 자체의 retention 은 본 패치 범위 밖**: `_archive` 테이블이 수 년 쌓이면 역시 bounded 하지 않다. Patch 10+ 에서 **이중 retention** (archive → cold storage) 을 별도로 도입할 예정.
- **Supabase RLS / service role**: 본 CLI 는 service role key 로 동작한다 (운영자 권한). RLS 를 뚫는 경로이므로 로컬에서 실행 시 키 노출에 주의.

## 11. Sign-off 체크리스트

- [ ] `harness-retention-archive --dry-run` 실행 결과 `ok:true` 이고 scanned 가 §3·2 와 일치.
- [ ] 실제 실행 후 `copied == scanned` 그리고 `deleted == copied`.
- [ ] 사후 SQL 에서 active 감소 + archive 증가 확인.
- [ ] `/api/runtime/health.health_status` 가 여전히 `ok`.
- [ ] 아카이브 주기를 운영 가이드 (§9) 에 등록.

---

## 12. 참고

- 본 런북은 `docs/plan/METIS_Scale_Readiness_Note_Patch9_v1.md` §2 Finding 5 와 짝이다.
- 구현 코드: `src/agentic_harness/retention/archive_v1.py`, `src/main.py::_cmd_harness_retention_archive`.
- 테스트: `src/tests/test_agh_v1_patch9_production_surface.py` 의 C·A 블록.
