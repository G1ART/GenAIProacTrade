# Phase 47d — Thick-slice UX shell reset (Home & navigation)

- **Phase**: `phase47d_thick_slice_ux_shell_reset`
- **Generated**: `2026-04-14T05:08:18.514350+00:00`
- **Design source**: `/Users/hyunminkim/GenAIProacTrade/docs/DESIGN_V3_MINIMAL_AND_STRONG.md`

## DESIGN_V3 alignment

- Home-first blocks (Today, Watchlist, Research in progress, Alerts, Decision journal, Ask AI brief, **Replay preview**, portfolio stub).
- Top nav matches user mental model: Home, Watchlist, Research, Replay, Journal, Ask AI, Advanced.
- Raw JSON and full alert tooling are confined to **Research → Advanced** cohort tab and **Advanced** top-level panel.
- Closed research fixtures are de-prioritized on Home: Today explains archive context and points to Watchlist / Research / Alerts.

## Blockers / deviations

_None recorded._ If a future change conflicts with `docs/DESIGN_V3_MINIMAL_AND_STRONG.md`, list it here.

## Home blocks (catalog)

```json
[
  {
    "id": "today",
    "label": "Today",
    "purpose": "What deserves attention now and whether action is needed"
  },
  {
    "id": "watchlist",
    "label": "Watchlist",
    "purpose": "Tracked cohorts / names and why not yet opportunity"
  },
  {
    "id": "research_in_progress",
    "label": "Research in progress",
    "purpose": "Active or recent threads — activity feed, not a job table"
  },
  {
    "id": "alerts",
    "label": "Alerts",
    "purpose": "Signals that need review"
  },
  {
    "id": "decision_journal",
    "label": "Decision journal",
    "purpose": "Recent decisions with replay link"
  },
  {
    "id": "ask_ai_brief",
    "label": "Ask AI brief",
    "purpose": "Copilot shortcuts — not a generic chat center"
  },
  {
    "id": "replay_preview",
    "label": "Replay preview",
    "purpose": "Signature capability on Home — teaser, not full timeline"
  },
  {
    "id": "portfolio_snapshot",
    "label": "Portfolio snapshot",
    "purpose": "Placeholder — lineage in later phase"
  }
]
```

## Navigation shell

```json
[
  {
    "id": "home",
    "label": "Home",
    "user_question": "What matters now across my surface?"
  },
  {
    "id": "watchlist",
    "label": "Watchlist",
    "user_question": "What am I tracking and how is it moving?"
  },
  {
    "id": "research",
    "label": "Research",
    "user_question": "What is being worked on and archived context?"
  },
  {
    "id": "replay",
    "label": "Replay",
    "user_question": "What happened, knowable then?"
  },
  {
    "id": "journal",
    "label": "Journal",
    "user_question": "What did I decide and why?"
  },
  {
    "id": "ask_ai",
    "label": "Ask AI",
    "user_question": "Copilot — bounded, bundle-grounded"
  },
  {
    "id": "advanced",
    "label": "Advanced",
    "user_question": "Alerts manager, raw references"
  }
]
```

## Closed fixture repositioning

- Closed research fixtures are no longer the dominant Home hero.
- They remain reachable under Research → cohort detail and Advanced (archive-style context).
- Home 'Today' explains when the loadout is fixture-first and points to Watchlist / Research / Alerts instead.

## Ask AI brief contract

```json
[
  {
    "id": "matters_now",
    "label": "What matters now?",
    "prompt_text": "decision summary"
  },
  {
    "id": "what_changed",
    "label": "What changed?",
    "prompt_text": "what changed"
  },
  {
    "id": "active_research",
    "label": "Show my active research",
    "prompt_text": "research layer"
  },
  {
    "id": "review_next",
    "label": "What should I review next?",
    "prompt_text": "what remains unproven"
  },
  {
    "id": "last_decisions",
    "label": "Show my last decisions",
    "prompt_text": "decision summary"
  },
  {
    "id": "open_replay",
    "label": "Open Replay for this item",
    "prompt_text": "what changed",
    "opens_panel": "replay"
  }
]
```

## Replay preview contract

```json
{
  "surface": "home_feed_card",
  "includes": [
    "last_decision_teaser_when_available",
    "time_axis_snippet_label_illustrative",
    "what_changed_since_teaser",
    "jump_to_replay_panel"
  ],
  "design_v3": "Teasers use bundle-time summaries and known-then framing; full truth on Replay panel."
}
```

## Empty-state rules

- Each Home block ships copy for: what belongs here, why it can be empty, what will populate it later.
- No raw JSON as the default block body on Home — summaries and plain lines only.
- Advanced is the only top-level area where full alert tooling and raw drilldown appear by default.

## Phase 47e recommendation

- **`live_watchlist_multi_asset_and_portfolio_attribution_v1`**
- Multi-row watchlist, live symbol hooks (still governed), portfolio card data — no substrate repair.

## Runtime API

- `GET /api/home/feed` — composed Home blocks for UI + tests.
- `GET /api/overview` — includes `user_first.navigation` with Phase 47d primary nav.

## UI

- `src/phase47_runtime/static/index.html`, `app.js` — Home grid, Replay preview card, relocated alerts manager, Journal cards.
