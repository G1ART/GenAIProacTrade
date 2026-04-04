# Founder surface contract (Phase 7 minimum)

## What the operator gets

- **Deterministic spine** remains source of truth: Phase 0–6 tables are **not** overwritten by the harness.
- **Investigation memos** are overlays: thesis + **mandatory** counter-argument + synthesis that **preserves disagreement**.
- **Uncertainty taxonomy** on claims: `confirmed` | `plausible_hypothesis` | `unverifiable`.
- **Review queue** rows: `pending` | `reviewed` | `needs_followup` | `blocked_insufficient_data`.

## What the operator does not get (by design)

- No buy/sell, portfolio, execution, or alpha-promotion language in generated memos (RefereeGate blocks common patterns).
- No LLM-invented numeric overrides of `state_change_score_v1` or factor truth.
- No use of forward-return columns as **model features** in state change (unchanged from Phase 6); validation context is **summary-only** in harness inputs.

## Commands

See `HANDOFF.md` — `smoke-harness`, `build-ai-harness-inputs`, `generate-investigation-memos`, `report-review-queue`.
