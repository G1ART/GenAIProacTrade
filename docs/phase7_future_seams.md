# Phase 7 — Future seams (explicitly out of scope in implementation)

- **Research lab / formula discovery**: `hypothesis_registry`, `research_formula_candidates`, `leakage_check_result`, `promotion_gate_status` — table stubs exist; no scoring wiring.
- **Walk-forward evaluation**: `strict_ex_ante_simulation`, `benchmark_comparison`, `shadow_mode` — not implemented; no performance claims.
- **Horizon / regime packs**: `short_horizon_pack`, `medium_horizon_pack`, `long_horizon_pack`, `regime_pack` — documentation hooks only.
- **Cross-domain adapters**: equities (current), crypto, property — philosophy: sibling platforms if one DB boundary is too tight; no ingestion expansion in Phase 7.

COS_ONLY / INTERNAL_SUPPORT / EXTERNAL_EXECUTION routing for *business ops text* is a **message-layer product** concern; this repo’s Phase 7 patch focuses on **deterministic candidate → memo overlay** only.
