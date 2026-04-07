-- Phase 22: public-depth iterations as first-class iteration members (alongside repair campaigns).

alter table public.public_repair_iteration_members
  add column if not exists member_kind text not null default 'repair_campaign';

alter table public.public_repair_iteration_members
  drop constraint if exists public_repair_iteration_members_member_kind_chk;

alter table public.public_repair_iteration_members
  add constraint public_repair_iteration_members_member_kind_chk
  check (member_kind in ('repair_campaign', 'public_depth'));

alter table public.public_repair_iteration_members
  alter column repair_campaign_run_id drop not null;

alter table public.public_repair_iteration_members
  add column if not exists public_depth_run_id uuid references public.public_depth_runs (id) on delete cascade;

alter table public.public_repair_iteration_members
  drop constraint if exists public_repair_iteration_members_repair_campaign_run_id_key;

create unique index if not exists public_repair_iteration_members_repair_run_unique
  on public.public_repair_iteration_members (repair_campaign_run_id)
  where repair_campaign_run_id is not null;

create unique index if not exists public_repair_iteration_members_depth_run_unique
  on public.public_repair_iteration_members (public_depth_run_id)
  where public_depth_run_id is not null;

alter table public.public_repair_iteration_members
  drop constraint if exists public_repair_iteration_members_kind_fk_xor_chk;

alter table public.public_repair_iteration_members
  add constraint public_repair_iteration_members_kind_fk_xor_chk
  check (
    (
      member_kind = 'repair_campaign'
      and repair_campaign_run_id is not null
      and public_depth_run_id is null
    )
    or (
      member_kind = 'public_depth'
      and public_depth_run_id is not null
      and repair_campaign_run_id is null
    )
  );

comment on column public.public_repair_iteration_members.member_kind is
  'Phase 22: repair_campaign (Phase 19 run) vs public_depth bounded expansion row.';
comment on column public.public_repair_iteration_members.public_depth_run_id is
  'Phase 22: links iteration member to public_depth_runs when member_kind = public_depth.';
