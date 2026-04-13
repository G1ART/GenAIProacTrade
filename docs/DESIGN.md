# DESIGN.md
# Founder-Facing Decision Product Design Constitution
# 2026-04-12
# Purpose: govern the user-facing product surface for the investment intelligence platform.
# This document defines how truth becomes usable product experience.

## 1. Product identity

This product is **not**:
- a generic AI stock picker
- a hype trading terminal
- a raw research artifact viewer
- a black-box quant recommendation engine

This product **is**:
- a research-governed investment decision operating surface
- a place where evidence becomes information, information becomes message, and message supports decisions
- a system that preserves traceability, uncertainty, and reopening discipline

## 2. Core product promise

For the founder or user, the product should answer:

1. What is this?
2. Why am I seeing it now?
3. What is the system actually saying?
4. What do I need to do, if anything?
5. What is still uncertain?
6. What would change the current stance?

If the UI does not answer those six questions quickly, it is failing.

## 3. Product object hierarchy

The UI must clearly distinguish these object types:

### A. Opportunity
A surfaced candidate where the system believes there is enough evidence to justify serious user attention.
This is not necessarily “buy now,” but it is above generic monitoring.

### B. Watchlist item
A tracked object with meaningful signals or uncertainty worth continued observation.
Not decision-ready.

### C. Closed research fixture or closed case
A research object whose current status is closed, deferred, or claim-narrowed.
Important for learning and provenance, but not an opportunity card.

### D. Alert
A time-based or state-based notification about a change, conflict, threshold, reopen condition, or operator action.

### E. Decision log entry
A record of what the founder or operator decided, why, and based on which message or evidence.

These objects must never be visually conflated.

## 4. Information hierarchy

The default surface should present information in this order:

### 1. Brief
The one-screen answer.
Must include:
- object type
- current stance
- one-line explanation
- what to do now
- evidence state

### 2. Why now
Why this object is on screen now.
Examples:
- new evidence
- status change
- reopened condition
- watchpoint hit
- surfaced by research runtime

### 3. What could change
What conditions would change the stance.
Examples:
- new named source
- exact_public_ts_available gain
- sector_available gain
- management signal confirmation
- premium escalation resolution

### 4. Evidence
Human-readable summary of supporting and limiting evidence.
Must include:
- what changed
- what did not change
- what remains unproven
- what is unsupported

### 5. History
Alerts, decision log entries, prior messages, and key transitions.

### 6. Ask AI
A governed discussion surface that helps the founder understand the object.
Not a generic chat toy.

### 7. Advanced
Raw provenance, technical codes, file paths, debug/state details, internal labels.

The default user flow must not begin with Advanced.

## 5. Top-level navigation principles

Main navigation must be user-question-centric, not internal-architecture-centric.

Preferred section labels:
- Brief
- Why now
- What could change
- Evidence
- History
- Ask AI
- Advanced

Avoid exposing raw internal layer names such as:
- provenance
- closeout
- research
- information
as the main top-level tabs unless translated into user meaning.

These internal layers may still exist underneath.

## 6. Action framing rules

Every primary object card must tell the user the current action framing.

Allowed examples:
- No action
- Keep watching
- Review new evidence
- Research closed
- Decision-ready
- Consider reopen request

This is not the same as:
- buy
- sell
- long
- short

The UI should frame decision state first, not force a trade posture prematurely.

## 7. Language translation layer

Internal system language must be translated before reaching the default UI.

Examples:
- `deferred_due_to_proxy_limited_falsifier_substrate`
  -> `Evidence is still too limited for a stronger claim`
- `closed_pending_new_evidence`
  -> `Closed until new evidence arrives`
- `material_falsifier_improvement: false`
  -> `The latest pass did not materially improve decision-quality evidence`
- `optimistic_sector_relabel_only`
  -> `Diagnosis improved, but the decision state did not materially improve`
- `narrow_claims_document_proxy_limits_operator_closeout_v1`
  -> `Keep claims narrow and hold until stronger evidence appears`

The default UI should never require the user to decode internal machine language.

## 8. Visual hierarchy

Default card order on a detail page:

1. Status or stance header
2. Brief summary
3. Why now
4. What could change
5. Key evidence
6. History
7. Ask AI
8. Advanced or raw or provenance drawer

Important rules:
- the first screen must explain the object in plain language
- the first screen must not look like a debug panel
- JSON-like structures must not dominate default cards
- raw details must be collapsed by default

## 9. AI interaction model

The AI surface should behave like:
- a chief of staff
- a research lead
- a bounded decision copilot

It should not behave like:
- a generic chatbot
- a verbose assistant
- a hypey idea generator

The AI must:
- speak from authoritative artifacts
- preserve claim narrowing
- explicitly note uncertainty
- support drill-down
- never overrun unsupported scope

The AI should provide quick action prompts such as:
- Explain this briefly
- Show key evidence
- Why is this closed?
- What changed?
- What could change?
- Show history
- Log my decision

## 10. Trust and safety rules for product copy

The UI must always distinguish:
- known
- suspected
- unsupported
- blocked
- closed
- reopened
- watch-only

The UI must not:
- imply certainty that the engine does not have
- surface unsupported scope as actionable recommendation
- use research fixture language as if it were an opportunity pitch
- hide the reason something is blocked or closed

## 11. Object-specific presentation rules

### Opportunity cards
Must show:
- why it surfaced
- current stance
- key evidence summary
- what still needs confirmation
- decision logging action

### Watchlist items
Must show:
- what is being watched
- what trigger or event matters
- why it is not yet an opportunity

### Closed research fixtures
Must show:
- that they are closed
- why they are closed
- what would reopen them
- what they taught the system
- that they are not current actionable opportunities

### Alerts
Must show:
- why the alert fired
- whether it needs attention
- which object it belongs to
- what action is available

### Decision log entries
Must show:
- what was decided
- why
- on which message or evidence
- when
- linked follow-up or outcome field

## 12. Empty-state design rules

Every empty state must explain:
- what belongs here
- why it is empty right now
- what event would populate it later

Examples:
- no opportunities yet
- no active alerts
- no decision log entries yet

Empty states must feel informative, not broken.

## 13. Benchmarking doctrine

Benchmark aggressively from the earliest stage.

Study at minimum:
- Koyfin for workspace composition and research overview
- FinChat or similar financial copilots for research IA and ask-AI framing
- TradingView for watchlist and alert and feed behavior
- Shadcn dashboard patterns for clean operator and admin information layout

Do not copy visual style blindly.
Borrow:
- hierarchy
- framing
- density decisions
- alert and feed patterns
- navigation logic
- empty-state treatment

## 14. DESIGN.md operational role

Cursor should treat this file as:
- a governing design constitution
- a reference for page generation
- a conflict resolver for UI wording and navigation
- a long-lived design source across 47b / 47c / 47d / 47e

When generating pages, Cursor should read this file first.

## 15. What the founder should not have to do

The founder should not need to:
- manually explain the same IA principles every patch
- decode raw machine states in the default UI
- specify basic dashboard structure from scratch each time

The founder may still provide:
- taste feedback
- screenshot feedback
- prioritization feedback
- benchmark references

But the baseline UI logic should already come from this file.

## 16. What the founder will still likely do later

The founder will probably still want to:
- react to screenshots or live runtime
- say which framing feels more useful
- choose between a few UI options
- refine the tone of the representative agent
- decide how aggressively opportunities should be surfaced

That is expected.
But it is refinement, not basic scaffolding.

## 17. Immediate implementation guidance for 47-series

### Phase 47b
Focus:
- user-first IA
- object separation
- tab or section rewrite
- translation layer
- action framing

### Phase 47c
Focus:
- visual system
- spacing and typography and emphasis
- dashboard clarity
- empty states and badges and card rhythm

### Phase 47d
Focus:
- Ask AI interaction quality
- governed conversation affordances
- quick actions
- history-aware assistant framing

### Phase 47e
Focus:
- opportunities vs watchlist vs fixtures separation
- alert center maturity
- decision workflow polish

## 18. Final principle

The product wins when:
- the research engine remains rigorous underneath
- the default surface becomes radically easier to understand
- the founder can move from message to evidence to decision without friction
- the system feels alive, trustworthy, and decision-oriented

The product loses when:
- the surface feels like a debug console
- the user cannot tell what matters now
- the AI sounds clever but ungrounded
- the UI makes internal architecture more visible than user meaning
