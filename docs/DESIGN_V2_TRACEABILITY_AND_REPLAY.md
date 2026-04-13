# DESIGN_V2_TRACEABILITY_AND_REPLAY.md
# Companion to DESIGN.md for Phase 47c
# 2026-04-13

## Modes

- **Replay**: actual sequence, evidence-bounded copy per event time.
- **Counterfactual Lab**: alternative branches (scaffold); not mixed into replay axis as facts.

## Event types (grammar)

`research_event`, `ai_message_event`, `decision_event`, `portfolio_event`, `market_event`, `outcome_checkpoint` — each with distinct visual token (color/shape/opacity).

## See also

- `docs/DESIGN.md` — product constitution
- `docs/DESIGN_V3_MINIMAL_AND_STRONG.md` — Phase 47c strict rules
- `docs/operator_closeout/phase47c_plot_grammar_notes.md` — implementation notes
