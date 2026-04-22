-- AGH v1 Patch 9 C·B1 — target_scope JSONB indexes.
--
-- Closes CF-8·B from the Patch 8 Scale Readiness Note. The packet list
-- API filters by ``target_scope->>'asset_id'`` and
-- ``target_scope->>'horizon'`` (e.g. Today / Research packet lookups
-- for a single asset + horizon). Without indexes this is a sequential
-- scan + JSONB traversal per row, which is the worst-case shape for
-- 500-ticker coverage.
--
-- Both indexes are b-tree on the extracted text, because the queries
-- are equality filters ("where asset_id = 'TRGP'"). A GIN index on the
-- full JSONB would also work but the b-tree expression index is both
-- smaller and faster for the equality patterns we actually use.
--
-- Both statements are idempotent.

create index if not exists agentic_harness_packets_v1_target_asset_id_idx
    on public.agentic_harness_packets_v1 ((target_scope->>'asset_id'))
    where target_scope ? 'asset_id';

create index if not exists agentic_harness_packets_v1_target_horizon_idx
    on public.agentic_harness_packets_v1 ((target_scope->>'horizon'))
    where target_scope ? 'horizon';

comment on index public.agentic_harness_packets_v1_target_asset_id_idx is
    'AGH v1 Patch 9 C·B1 — per-asset packet lookup (target_scope->>asset_id).';
comment on index public.agentic_harness_packets_v1_target_horizon_idx is
    'AGH v1 Patch 9 C·B1 — per-horizon packet lookup (target_scope->>horizon).';
