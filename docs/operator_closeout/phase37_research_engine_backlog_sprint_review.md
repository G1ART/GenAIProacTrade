# Phase 37 — Research engine backlog sprint 1

_Generated (UTC): `2026-04-10T16:46:00.733222+00:00`_
_Bundle generated (UTC): `2026-04-10T16:46:00.732862+00:00`_

## Ground truth (Phase 36.1)

- `joined_recipe_substrate_row_count`: `266`
- `joined_market_metadata_flagged_count`: `0`
- `no_state_change_join`: `8`
- `missing_excess_return_1q`: `78`
- `missing_validation_symbol_count`: `151`

## Research engine constitution

Pillars mapped to modules + JSON artifacts — see `docs/research_engine_constitution.md` and bundle `research_engine_constitution`.

## Executable vs still conceptual

### Executable now
- JSON hypothesis objects (hypotheses_v1.json)
- JSON casebook entries (casebook_v1.json)
- PIT experiment scaffold record (pit_experiments_v1.json) — inputs/alternates only
- Adversarial review records (adversarial_reviews_v1.json)
- Explanation prototype markdown (phase37_explanation_prototype.md)

### Conceptual (Phase 38+)

- DB-bound PIT replay comparing alternate as_of / run specs
- Promotion gate checklist persistence and enforcement hooks
- User-facing app surface wiring (API/UI) beyond static MD

## Hypothesis registry v1

- Count: **1**
- `hyp_pit_join_key_mismatch_as_of_boundary_v1` — **under_test** — Residual no_state_change_join (join_key_mismatch) reflects score-run as-of vs signal-date ordering, not missing SC build

## PIT experiment scaffold

- Experiments recorded: **1** (scaffold; no DB replay in Sprint 1)
- Fixture rows: **8** (`join_key_mismatch`)

## Casebook

- Entries: **4**
- `case_pit_no_sc_join_key_mismatch_8` — no_state_change_join — state_change_built_but_join_key_mismatch (8 symbols)
- `case_gis_unmapped_concept_seam` — GIS deterministic inspect — blocked_unmapped_concepts_remain_in_sample
- `case_maturity_immature_nq_7` — Immature next-quarter forward window — 7 symbols (Phase 34/35 schedule)
- `case_registry_tail_151` — missing_validation_symbol_count — registry / upstream pipeline tail

## Adversarial reviews

- Records: **1**

## Explanation prototype

- Path: `/Users/hyunminkim/GenAIProacTrade/docs/operator_closeout/phase37_explanation_prototype.md`
- Hypothesis: `hyp_pit_join_key_mismatch_as_of_boundary_v1`
- Signal symbol: `BBY`

## Phase 38 recommendation

- **`bind_pit_experiment_runner_to_db_and_execute_alternate_as_of_specs`**
- Hypothesis registry, casebook, and scaffold experiments exist; the next increment is a deterministic DB-bound PIT runner that replays join logic under alternate specs, persists results, and feeds adversarial review resolution — without broad substrate repair campaigns.
