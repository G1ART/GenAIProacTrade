# PLAN_MODE_ROADMAP_CURSOR_CONTINUOUS_BUILD
# 2026-04-14
# Purpose: a Cursor-facing, continuously executable roadmap based on the current locked product north star.
# This is not a generic backlog. It is a plan-mode implementation roadmap for building the MVP/Alpha
# as fast as possible without drifting back into a non-actionable research tool.

---

## 0. Product North Star (LOCKED)

The product is **not** a generic AI investing assistant, stock picker, or research dashboard.

It is a:

**public-data-first, point-in-time, research-governed investment operating system**

with a product surface organized around:

- **Today**
- **Research**
- **Replay**

The product must deliver:
1. what matters now
2. why it matters now
3. how to investigate deeper
4. how to review the decision later

The core user flow is:

**Data → Information → Message → Decision → Replay**

Important:
- the user-facing surface must be **message-first**
- the research engine is not the hero
- “watch / wait / no action” is not the headline product
- the product must feel like a premium investment operating surface, not an internal research admin tool

---

## 1. Most Important Product Truths (LOCKED)

### 1.1 Today is the primary product
The most important screen is **Today**.

Today must show, by time horizon:
- short-term
- medium-term
- medium-long-term
- long-term

For each horizon, Today must display a **relative undervaluation ↔ overvaluation spectrum**
driven by that horizon's **active model family**.

This is critical:
- different horizon buttons may use different active model families
- the same stock should not be assumed to have the same relative position at all horizons
- users must be able to feel that “this stock can be short-term overheated but long-term undervalued,” etc.

### 1.2 Today is not a recommendation screen
Do not write the product as “buy / sell.”
Instead, Today should communicate:
- where attention should go now
- relative asymmetry
- what is overheated vs compressed
- why the current placement exists
- what changed
- what would move the view

### 1.3 Message-first, not research-first
For each surfaced stock/object:
- first show the message
- then the information
- then deeper rationale / research substrate

### 1.4 Replay is a signature feature
Replay is not decorative.
It must include:
- reality replay
- counterfactual replay
- decision trace
- what the system said then
- what changed after

### 1.5 Custom Research Sandbox must be real enough to excite
Sandbox is not a placeholder.
It must be usable enough that a serious user thinks:
“if this becomes fully mature, this is extremely powerful.”

---

## 2. Absolute Build Priorities

Cursor must evaluate every patch against one question:

**Does this move Today / Research / Replay toward demo-grade Alpha readiness?**

If no, it is likely not a current priority.

### Priority order
1. Today Spectrum Engine
2. Message Layer v1
3. Today UI / shell integration
4. Detail page (message → information → research)
5. Ask AI copilot
6. Custom Research Sandbox v1
7. Reality Replay v1
8. Counterfactual Replay v1
9. KO/EN language and copy polish
10. Ingest / runtime trust layer hardening
11. Design/polish/animation/quality improvements
12. Expansion hooks only after the above are real

---

## 3. Execution Philosophy

### 3.1 Avoid these failure modes
Do not drift into:
- internal research object viewer
- beautiful but non-actionable research dashboard
- generic chatbot center-stage
- backend-heavy progress that users cannot feel
- excessive architecture work that does not improve the visible product

### 3.2 Prefer these behaviors
Do:
- build product surfaces users can actually react to
- build with frozen/snapshot data if needed, as long as the final interaction is clear
- keep the narrative honest: if some data is snapshot and some is pseudo-real-time, say so clearly
- optimize for “this already feels like a real product”
- make each sprint produce a more convincing user-visible experience

### 3.3 Demo honesty principle
It is acceptable for parts of the Alpha to be snapshot/frozen,
as long as:
- the product interaction is real
- the story is honest
- the user can clearly infer what the fully live version will become

---

## 4. Sprint Structure

This roadmap is organized into executable sprint blocks.
Cursor should treat each block as a mini-program, not a vague theme.

---

# SPRINT 1 — TODAY SPECTRUM ENGINE (FOUNDATIONAL PRODUCT CORE)

## Goal
Build the engine that powers Today:
- horizon selection
- active model family per horizon
- stock ranking on undervaluation ↔ overvaluation spectrum
- rationale summary
- pseudo-real-time re-ranking logic

## Why this sprint matters
Without this, the product will continue drifting toward a non-actionable research tool.

## Required output
A system that can, for a fixed as-of date and current/latest price layer:
- choose horizon
- choose current active model family for that horizon
- score/rank a stock universe
- place stocks on a relative spectrum
- generate per-stock rationale payloads

## Required product concepts
- `horizon`
- `active_model_family`
- `spectrum_position`
- `valuation_tension`
- `rationale_summary`
- `confidence_band`
- `what_changed`
- `next_watch_item`

## Deliverables
- model registry structure
- horizon-to-model mapping
- scoring output schema
- ranking pipeline
- per-stock message payload contract
- bundle/review docs
- browser-visible Today payload support

## Acceptance criteria
- switching horizon visibly changes the ranked board
- different horizons may produce different orderings and color positions
- each stock has a short rationale
- output is understandable without reading raw research internals

## Anti-goals
- no fully generalized model marketplace
- no infinite optimization loop
- no “best model ever” language
- no overclaiming predictive certainty

---

# SPRINT 2 — MESSAGE LAYER V1 (CORE USER VALUE)

## Goal
Turn research outputs into first-class message objects.

## Why this sprint matters
The current biggest product gap is that the system still often stops at information,
instead of producing a message that a user can actually consume.

## Required message object
Each surfaced stock/object should have:
- `message_id`
- `asset_id`
- `horizon`
- `headline`
- `one_line_take`
- `why_now`
- `what_changed`
- `what_remains_unproven`
- `what_to_watch`
- `confidence_band`
- `linked_model_family`
- `linked_evidence_summary`

## Required UX effect
The user should immediately understand:
- what this means
- why now
- what changed
- whether this is improving or deteriorating
- what to monitor next

## Deliverables
- message object schema
- message generation layer
- message payload tests
- integration into Today and Detail
- bundle/review docs

## Acceptance criteria
- Today cards no longer feel like research fragments
- cards feel like real product messages
- a user could screenshot a card and understand it
- “watch / wait / no action” is no longer the main message

---

# SPRINT 3 — TODAY PAGE PRODUCTIZATION (VISIBLE HOME EXPERIENCE)

## Goal
Turn the Today board into the dominant homepage experience.

## What must appear
- horizon toggle
- spectrum board
- color system
- stock rows/cards
- rationale snippets
- watchlist filter
- sort/priority controls
- “what changed” mini-signals
- optional explain / expand affordance

## Required UX behavior
The page must feel:
- decisive
- legible
- premium
- useful immediately

The page must not feel:
- like an admin grid
- like a static research dump
- like a watch/wait holding page

## Deliverables
- Today-first home shell
- cards/list modules
- watchlist projection
- status legend
- empty states
- responsive layout
- bundle/review docs

## Acceptance criteria
- a first-time user sees where attention should go
- the board feels like the core product
- the page is understandable in 10 seconds

---

# SPRINT 4 — DETAIL PAGE (MESSAGE → INFORMATION → RESEARCH)

## Goal
Build the stock/object detail page in the correct order.

## Mandatory structure
1. Message
2. Information
3. Research

## Message section
- current stance by horizon
- headline
- why now
- what changed
- what to watch
- confidence / uncertainty

## Information section
- selected supporting signals
- selected opposing signals
- compact evidence summary
- premium/data-layer note where relevant

## Research section
- deeper rationale
- model family context
- additional drilldowns
- links into sandbox / replay / Ask AI

## Acceptance criteria
- the user gets the takeaway before the evidence
- the evidence comes before the deep substrate
- the page does not feel like a research log first

---

# SPRINT 5 — ASK AI COPILOT (PRODUCTIVE, NOT GIMMICK)

## Goal
Add a real Ask AI layer that helps users interrogate Today/Detail/Replay.

## Must support
- why now?
- what changed?
- why is this still ranked here?
- what would change this view?
- compare short-term vs long-term
- show replay for this item
- explain this more simply
- summarize the core rationale

## Rules
- this is not a generic chatbot playground
- suggested prompts must reflect real user intent
- answers should be grounded in the visible product objects

## Acceptance criteria
- Ask AI clarifies the product
- Ask AI deepens understanding
- Ask AI feels like a decision copilot

---

# SPRINT 6 — CUSTOM RESEARCH SANDBOX V1

## Goal
Make Sandbox compelling enough for real excitement.

## Required capabilities
User can:
- enter a hypothesis / question
- choose universe or asset scope
- choose horizon
- choose current snapshot vs past PIT mode
- run a bounded analysis
- see a structured result
- compare multiple horizon outcomes
- save the result as a research object

## Important
This does not need full maturity.
It DOES need enough realness that:
- a serious user feels the power
- a serious investor sees monetizable depth
- it is clearly beyond a toy prompt box

## Deliverables
- sandbox input schema
- bounded run orchestration
- result page structure
- saved object support
- links into replay
- bundle/review docs

## Acceptance criteria
- user can run at least one non-trivial custom investigation
- result is interpretable
- result feels meaningfully different from generic chatbot output

---

# SPRINT 7 — REALITY REPLAY V1

## Goal
Show what the system said, what the user did, and what happened.

## Core requirements
- decision log input or imported decision record
- link to prior message snapshot
- subsequent price/path evolution
- simple “how it aged” framing
- ability to review by horizon

## Acceptance criteria
- the replay feels useful
- the user can see whether a prior view improved or deteriorated
- the product starts to feel like a decision memory system

---

# SPRINT 8 — COUNTERFACTUAL REPLAY V1

## Goal
Let the user ask “what if” against past PIT conditions.

## Required questions
- what if I waited?
- what if I bought later?
- what if I held longer?
- what if I used a different horizon?
- what if I ignored the signal?

## Acceptance criteria
- counterfactual is real enough to be compelling
- the user can compare alternate paths
- this becomes obviously premium-worthy

---

# SPRINT 9 — BILINGUAL USER LANGUAGE + COPY SYSTEM

## Goal
Make the product natural and premium in both Korean and English.

## Required
- visible KO/EN toggle
- major shell localized
- user-language dictionary layer
- no awkward literal translation
- no internal status codes in primary UI

## Acceptance criteria
- Korean reads naturally
- English reads naturally
- first-time readability is dramatically improved

---

# SPRINT 10 — TRUST LAYER / INGEST HARDENING

## Goal
Ensure the visible product is backed by trustworthy runtime ingress.

## Includes
- signed payload ingress
- key rotation
- dead-letter replay
- runtime health parity
- legacy ingest tightening

## Why it matters
This is not the product face, but it supports the credibility of the live/dynamic system.

---

## 5. Cross-Cutting Requirements

These apply to all sprints.

### 5.1 Everything should ladder into investor demo scenes
Every sprint should improve at least one demo scene:
- Today board
- stock detail
- Ask AI interaction
- sandbox run
- replay session

### 5.2 Keep narrative alignment
If the build starts to look like:
- research admin surface
- data exhaust viewer
- generic AI assistant
then correct immediately.

### 5.3 Track user-facing proof, not only technical proof
For every sprint, record:
- what the user can now do
- what the user can now understand
- what the investor can now see
- what premium value is now visible

---

## 6. Recommended Immediate Execution Order (Fast Track)

If speed is the priority, Cursor should bias toward this sequence:

### Phase A
- Sprint 1 — Today Spectrum Engine
- Sprint 2 — Message Layer v1
- Sprint 3 — Today Page Productization

### Phase B
- Sprint 4 — Detail Page
- Sprint 5 — Ask AI
- Sprint 6 — Sandbox v1

### Phase C
- Sprint 7 — Reality Replay
- Sprint 8 — Counterfactual Replay

### Phase D
- Sprint 9 — KO/EN language rewrite
- Sprint 10 — Trust layer hardening

This order is preferred because it gets visible product value fastest.

---

## 7. Hard Rules for Cursor

Cursor must not:
- optimize internal elegance while visible product scenes remain weak
- overbuild data plumbing that users cannot feel
- hide behind research terminology instead of product clarity
- ship “watch / wait / no action” as the primary product message
- present one universal model across horizons if the product core is horizon-specific model families
- use overconfident language like “most accurate model”

Cursor must:
- build toward the locked product shape
- preserve PIT/public-data-first discipline
- keep message-first UX
- maintain replayability
- keep work auditable and handoff-friendly

---

## 8. Required Handoff Update Discipline

At the end of each patch or sprint:
1. update `HANDOFF.md`
2. state what changed in visible product terms
3. state what investor-demo scene improved
4. state what remains missing for Today / Research / Replay
5. recommend the exact next sprint

---

## 9. Final Operational Principle

From now on, this project should not be treated as:
- “building an engine and figuring out the product later”

It must be treated as:
- **building the already-defined product as fast as possible**

The standard for every new patch is:

**Does this make Today / Research / Replay more real, more legible, more valuable, and more demoable?**

If yes, keep going.
If no, cut scope and refocus.
