# Phase 44 — Claim narrowing & audit truthfulness

- Bundle phase: `phase44_claim_narrowing_truthfulness`
- Generated: `2026-04-12T06:44:44.839337+00:00`
- Phase 43 input: `/Users/hyunminkim/GenAIProacTrade/docs/operator_closeout/phase43_targeted_substrate_backfill_bundle.json`
- Phase 42 Supabase input: `/Users/hyunminkim/GenAIProacTrade/docs/operator_closeout/phase42_evidence_accumulation_bundle_supabase.json`

## Truthfulness assessment

- **material_falsifier_improvement**: `False`
- **optimistic_sector_relabel_only**: `True`
- **falsifier_usability_improved**: `False`
- **gate_materially_improved**: `False`
- **discrimination_rollups_improved**: `False`

### Notes

- Sector scorecard moved no_market_metadata_row_for_symbol → sector_field_blank_on_metadata_row without sector_available increase; treated as diagnostic relabel, not falsifier upgrade.
- No increase in exact_public_ts_available, sector_available, or filed-date-only path.

## Retry eligibility

- **filing_retry_eligible**: `False`
- **sector_retry_eligible**: `False`
- **reason**: No named alternative filing ingestion path declared; cannot authorize another bounded filing pass. No named alternative sector fill path declared; cannot authorize another bounded sector pass. Phase 44 truthfulness: no material falsifier usability / gate / discrimination improvement.

## Claim narrowing (cohort)

- **claim_status**: `narrowed`
- **bounded_retry_eligibility**: `not_eligible_without_named_new_path`

## Phase 45

- **recommendation**: `narrow_claims_document_proxy_limits_operator_closeout_v1`
- **rationale**: No material falsifier upgrade under Phase 44 rules; do not reopen broad substrate. Narrow claims, document proxy limits, and close out unless new evidence appears.

## Provenance audit

See `phase44_provenance_audit.md` (input bundle vs runtime snapshots, separated).
