# Phase 47b — User-first information architecture & UX

- **Phase**: `phase47b_user_first_ux`
- **Generated**: `2026-04-13T02:44:44.251024+00:00`
- **Design source**: `/Users/hyunminkim/GenAIProacTrade/docs/DESIGN.md`

## Primary navigation (user-first)

```json
[
  {
    "id": "brief",
    "label": "Brief",
    "user_question": "What is this? What should I do?"
  },
  {
    "id": "object",
    "label": "This object",
    "user_question": "Drill into one cohort or symbol"
  },
  {
    "id": "alerts",
    "label": "Alerts",
    "user_question": "What needs attention?"
  },
  {
    "id": "history",
    "label": "History",
    "user_question": "Decisions and trail"
  },
  {
    "id": "ask_ai",
    "label": "Ask AI",
    "user_question": "Bounded decision copilot"
  }
]
```

## Object detail sections (replaces internal tabs in default view)

```json
[
  {
    "id": "brief",
    "label": "Brief",
    "maps_internal": "decision + message (summary)"
  },
  {
    "id": "why_now",
    "label": "Why now",
    "maps_internal": "message + headline / what_changed"
  },
  {
    "id": "what_could_change",
    "label": "What could change",
    "maps_internal": "next_watchpoints + closeout card"
  },
  {
    "id": "evidence",
    "label": "Evidence",
    "maps_internal": "information + research layers"
  },
  {
    "id": "history",
    "label": "History",
    "maps_internal": "alerts + decisions (links)"
  },
  {
    "id": "ask_ai",
    "label": "Ask AI",
    "maps_internal": "governed_conversation"
  },
  {
    "id": "advanced",
    "label": "Advanced",
    "maps_internal": "provenance + closeout + raw drilldown JSON"
  }
]
```

## Object hierarchy

```json
[
  {
    "kind": "opportunity",
    "label": "Opportunity",
    "hint": "Enough evidence to deserve serious attention (not necessarily buy)."
  },
  {
    "kind": "watchlist_item",
    "label": "Watchlist item",
    "hint": "Worth watching; not decision-ready."
  },
  {
    "kind": "closed_research_fixture",
    "label": "Closed research fixture",
    "hint": "Closed / deferred / claim-narrowed — not an actionable pitch."
  },
  {
    "kind": "alert",
    "label": "Alert",
    "hint": "Time- or state-based signal."
  },
  {
    "kind": "decision_log_entry",
    "label": "Decision log entry",
    "hint": "Recorded founder/operator decision."
  }
]
```

## Status translation (sample)

```json
[
  {
    "from": "claim_narrowed_closed",
    "to": "Claims are narrowed; case treated as closed under current evidence"
  },
  {
    "from": "closed_pending_new_evidence",
    "to": "Closed until new evidence arrives"
  },
  {
    "from": "deferred",
    "to": "Deferred — waiting on stronger substrate or evidence"
  },
  {
    "from": "deferred_due_to_proxy_limited_falsifier_substrate",
    "to": "Evidence is still too limited for a stronger claim"
  },
  {
    "from": "hold_closeout_until_named_new_source_or_new_evidence_v1",
    "to": "Hold the closeout until a new named source or new evidence is registered"
  },
  {
    "from": "material_falsifier_improvement: false",
    "to": "The latest pass did not materially improve decision-quality evidence"
  }
]
```

## Advanced boundary rules

- Raw JSON, internal layer keys, and file paths appear only under Advanced.
- Default cards use plain language from the translation layer.
- Gate codes and stance tokens are summarized first; verbatim codes are optional in Advanced.

## Phase 47c recommendation

- **`visual_system_spacing_typography_empty_states_and_card_rhythm_v1`**
- Phase 47c: visual system, spacing, typography, dashboard clarity, badges, empty states

## Section naming map (old → new)

| Internal (retired from top tabs) | User-first section |
|-----------------------------------|----------------------|
| decision / message (split) | **Brief** |
| message / what_changed | **Why now** |
| closeout / next_watchpoints | **What could change** |
| information / research | **Evidence** |
| (scattered) | **History** (alerts + decisions panels) |
| governed prompts | **Ask AI** |
| provenance / closeout / raw | **Advanced** |

## Runtime

- UI: `src/phase47_runtime/static/` — Brief-first layout, object badge, detail tabs, copilot shortcuts.
- API: `GET /api/overview` includes `user_first`; `GET /api/user-first/section/{id}`.
- Copy layer: `src/phase47_runtime/ui_copy.py`.
