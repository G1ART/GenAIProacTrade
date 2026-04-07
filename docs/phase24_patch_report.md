# Phase 24 — Public-first empirical layer (census, plateau review, alternating cycle)

**Date:** 2026-04-07

## Intent

Phase 23 removed operator UUID friction. Phase 24 adds a **compact empirical layer**: branch/signal/improvement distributions across **recent compatible** iteration series, a **three-way plateau review** conclusion (review-only for premium), and an **alternating-cycle coordinator** that formalizes repair versus depth rhythm when evidence supports it.

## New CLI

| Command | Role |
|---------|------|
| `report-public-first-branch-census` | JSON census: aggregated branches, signals, classifications, included/excluded counts, exclusions audit |
| `export-public-first-branch-census-brief` | JSON + Markdown (`census_to_markdown`) |
| `export-public-first-plateau-review-brief` | Census + plateau conclusion to `public_first_plateau_review.json` + `latest_public_first_review.md` |
| `run-public-first-plateau-review` | Same artifacts as export (alias) |
| `advance-public-first-cycle` | Census, plateau review, coordinator, optional advance, refresh `latest_public_first_review.md` |

Shared flags: `--program-id`, `--universe`, `--include-closed-series`, `--series-scan-limit`.

## Plateau review conclusions (deterministic)

- `premium_discovery_review_preparable` — active series **current** escalation is `open_targeted_premium_discovery` (human review prep only; not live integration).
- `public_first_still_improving` — at least two deduped depth classifications and more than half are `meaningful_progress` or `marginal_progress`.
- `mixed_or_insufficient_evidence` — default.

## Coordinator logic

1. Premium preparable conclusion: `hold_for_plateau_review`, no advance.
2. Still improving: alternate from last member kind (`public_depth` then repair, else depth).
3. Mixed: Phase 23 `choose_post_patch_next_action` on resolved active series.

## Evidence

1. **Branch census** — `report-public-first-branch-census` JSON fields listed in `docs/phase24_evidence.md`.
2. **Plateau review** — `export-public-first-plateau-review-brief` writes `public_first_plateau_review.json` and `latest_public_first_review.md`.
3. **Alternating cycle** — `advance-public-first-cycle` stdout + updated review MD.
4. **Premium** — With 2026-04-07 `sp500_current` closeout (hold_and_repeat + repeat repair), premium review is **not** preparable until escalation is `open_targeted_premium_discovery`. No auto-open.
5. **Tests** — `src/tests/test_phase24_public_first.py`; full suite **309 passed**.
6. **Production scoring** — `test_runner_still_no_public_repair_iteration_reference` in that file.

## Docs / handoff

- `HANDOFF.md` (Phase 24)
- `docs/phase24_evidence.md`
- `docs/OPERATOR_POST_PATCH.md` (appendix D)
