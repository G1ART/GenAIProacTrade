# Phase 47c — Plot grammar (operator notes)

- **X-axis**: UTC time (`plot_grammar.x_axis` = `time_utc_iso`). The browser draws normalized positions (`x_norm` in `[0,1]`) from bundle anchor span; labels remain ISO strings in event rows.
- **Series roles**: `illustrative_reference` — dashed, low opacity, **not** live OHLC; `stance_posture_index` — ordinal mapping from decision-type / stance tokens, **not** a return series.
- **Style dimensions**: color, opacity, stroke (solid vs dashed), marker shape (event grammar), optional band fill (reserved).
- **Event markers**: See `event_grammar` in `phase47c_traceability_replay_bundle.json` — replay markers only; counterfactual branches are listed in **Counterfactual Lab** UI, not as timeline facts.
