# Phase 53 — Dead-letter registry & bounded replay

Failed governed ingress events are appended to `data/research_runtime/external_dead_letter_v1.json` (smoke uses `phase53_smoke_dead_letter_v1.json`).

- **Stages**: `signature`, `replay_guard`, `auth`, `routing`, `budget`, `normalize`, `queue`.
- **Replay**: `replay-phase53-dead-letter --dead-letter-id …` re-submits excerpt through `process_governed_external_ingest` — still subject to signing, replay guard, budgets, and routing.
- **Lineage**: audit rows may include `operator_replay_dead_letter_id` when replay succeeds.

```json
{
  "cli_replay": "replay-phase53-dead-letter",
  "note": "Replays re-enter governed ingress with current rules; use CLI with corrected secret/signature material."
}
```
