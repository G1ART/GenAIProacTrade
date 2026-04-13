# Phase 47c — Traceability & decision replay

- **Phase**: `phase47c_traceability_replay`
- **Generated**: `2026-04-13T06:05:37.863207+00:00`
- **Design sources**: ['/Users/hyunminkim/GenAIProacTrade/docs/DESIGN_V3_MINIMAL_AND_STRONG.md', '/Users/hyunminkim/GenAIProacTrade/docs/DESIGN_V2_TRACEABILITY_AND_REPLAY.md', '/Users/hyunminkim/GenAIProacTrade/docs/DESIGN.md']

## Traceability views

```json
[
  {
    "id": "replay_timeline",
    "label": "Replay",
    "description": "What happened, knowable then, on a time axis."
  },
  {
    "id": "counterfactual_lab",
    "label": "Counterfactual Lab",
    "description": "Hypothetical branches — not historical replay."
  }
]
```

## Plot grammar (contract)

```json
{
  "x_axis": "time_utc_iso",
  "series_style_dimensions": [
    "color",
    "opacity",
    "stroke_style",
    "marker_shape",
    "band_fill"
  ],
  "default_series": [
    {
      "series_id": "illustrative_reference",
      "role": "market_event",
      "stroke_style": "dashed",
      "opacity": 0.35,
      "disclaimer": "Illustrative only — not live OHLC; shows temporal rhythm for review."
    },
    {
      "series_id": "stance_posture_index",
      "role": "decision_quality_proxy",
      "stroke_style": "solid",
      "opacity": 0.85,
      "disclaimer": "Ordinal index from stance codes — not a market return."
    }
  ]
}
```

## Event grammar (markers)

```json
[
  {
    "type": "research_event",
    "label": "Research / bundle",
    "marker": "square",
    "color": "#6b8cce",
    "opacity": 1.0,
    "stroke": "solid"
  },
  {
    "type": "ai_message_event",
    "label": "AI / alert signal",
    "marker": "diamond",
    "color": "#c9a227",
    "opacity": 0.95,
    "stroke": "solid"
  },
  {
    "type": "decision_event",
    "label": "Decision",
    "marker": "circle",
    "color": "#3d9a6e",
    "opacity": 1.0,
    "stroke": "solid"
  },
  {
    "type": "portfolio_event",
    "label": "Portfolio (stub)",
    "marker": "triangle",
    "color": "#a78bfa",
    "opacity": 0.7,
    "stroke": "dashed"
  },
  {
    "type": "market_event",
    "label": "Market reference",
    "marker": "none",
    "color": "#5b8cff",
    "opacity": 0.35,
    "stroke": "dashed"
  },
  {
    "type": "outcome_checkpoint",
    "label": "Outcome frame",
    "marker": "cross",
    "color": "#8b9bb4",
    "opacity": 0.85,
    "stroke": "solid"
  }
]
```

## Replay vs counterfactual

### Replay rules

- Replay lists only events at or before each point’s timestamp; copy is generated from ledger/bundle fields available for that event.
- No counterfactual or hypothetical language in replay event titles or micro-briefs.
- Outcome checkpoints labeled as review-time framing, not as if known historically.

### Counterfactual rules

- Counterfactual Lab is a separate mode; branches are not drawn as factual timeline markers.
- Numeric simulation may be added later; UI grammar reserves branches only.
- Copy avoids ‘you would have been rich’ or implied certainty.

## Decision quality vs outcome quality

- Decision quality: process and evidence fit at decision time.
- Outcome quality: ex-post result — may diverge from decision quality.
- UI surfaces both labels; does not conflate them.

## Counterfactual scaffold

```json
{
  "mode": "counterfactual_lab",
  "branches": [
    {
      "id": "actual",
      "label": "Actual path",
      "state": "active_in_replay"
    },
    {
      "id": "if_not_sold",
      "label": "If not sold",
      "state": "stub"
    },
    {
      "id": "if_held_longer",
      "label": "If held longer",
      "state": "stub"
    },
    {
      "id": "if_size_differed",
      "label": "If size differed",
      "state": "stub"
    },
    {
      "id": "if_watch_only",
      "label": "If watch-only",
      "state": "stub"
    },
    {
      "id": "if_followed_ai_guidance",
      "label": "If AI guidance followed",
      "state": "stub"
    }
  ],
  "rules": [
    "Counterfactual Lab is a separate mode; branches are not drawn as factual timeline markers.",
    "Numeric simulation may be added later; UI grammar reserves branches only.",
    "Copy avoids ‘you would have been rich’ or implied certainty."
  ],
  "disclaimer": "Hypothetical branches — no numeric engine in MVP; not shown on Replay axis."
}
```

## Phase 47d recommendation

- **`counterfactual_numeric_engine_and_live_price_attribution_v1`**
- Numeric simulation for branches, live/benchmark series, attribution wiring — still governance-bound.

## Runtime API

- `GET /api/replay/timeline` — events + synthetic series + portfolio stub.
- `GET /api/replay/micro-brief?event_id=…` — hover/select payload.
- `GET /api/replay/contract` — views + counterfactual scaffold summary.

## UI

- Top nav **Replay** (not under Advanced); sub-mode **Replay** vs **Counterfactual Lab**.
- Implementation: `src/phase47_runtime/static/`, logic: `traceability_replay.py`.
