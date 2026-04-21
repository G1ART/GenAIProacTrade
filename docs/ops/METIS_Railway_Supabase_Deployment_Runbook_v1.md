# METIS Railway + Supabase Deployment Runbook v1

**Patch:** AGH v1 Patch 8 (E3 + E4)
**Audience:** single founder operator.
**Status:** authoritative for first hosted deployment.
**Scope:** deploy the Phase 47 cockpit (`web:`) + harness scheduler
(`worker:`) on Railway with Supabase as the sole state backend.

This is the **single, copy-pasteable** runbook; do not fan out to
per-subsystem guides. Stages 1–8 below are linear; re-running any stage
is idempotent.

## 0. Topology

```
                     +-------------------------+
                     |        Operator         |
                     +-----------+-------------+
                                 |
                                 v  HTTPS
                 +-------------------------------+
                 |  Railway Service: web          |
                 |  python3 src/phase47_runtime/  |
                 |   app.py --host 0.0.0.0 \      |
                 |         --port $PORT           |
                 |                                |
                 |  Healthcheck: /api/runtime/    |
                 |   health  (200 ok|degraded,    |
                 |             503 down)          |
                 +-------------+------------------+
                               |  supabase-py (service role)
                               v
                 +-------------------------------+
                 |        Supabase Project        |
                 |  (DB + auth + storage; single  |
                 |   source of truth for packets, |
                 |   jobs, validation runs, brain |
                 |   bundle promotions)           |
                 +-------------+------------------+
                               ^
                               |  supabase-py (service role)
                 +-------------+------------------+
                 |  Railway Service: worker       |
                 |  python3 src/main.py           |
                 |    harness-tick --loop         |
                 |    --sleep 30                  |
                 +-------------------------------+
```

Both services run the same Python image. The difference is only the
`Procfile` command (`web:` vs `worker:`). They share the same env var
set (Supabase, LLM, cockpit defaults).

## 1. Prerequisites

1. Supabase project with migrations applied up to
   `supabase/migrations/20260417100000_forward_returns_long_horizons_v1.sql`.
   The brain bundle (`data/mvp/metis_brain_bundle_v0.json`, and
   optionally `..._v2.json` from the D2 graduation script) is committed
   to the repo — Railway ships it with the image.
2. Railway account + CLI (`npm i -g @railway/cli`). The CLI is optional
   — Stages 2–7 below can be performed entirely from the Railway UI.
3. A `SUPABASE_SERVICE_ROLE_KEY` (Project Settings → API) and
   `SUPABASE_URL`.

## 2. Create the Railway project

1. Railway → New Project → Deploy from GitHub → choose the
   `GenAIProacTrade` repo.
2. Railway reads `railway.json` and `Procfile` automatically:
   * `web:` becomes the default service (start command from
     `railway.json.deploy.startCommand`).
   * To create the `worker:` you must explicitly add a second service
     in the same project (New Service → From Repo → same repo) and
     override its start command to
     `python3 src/main.py harness-tick --loop --sleep 30`.

## 3. Configure env vars (both services, identical values)

Paste these in Railway → Service → Variables. `.env.example` is the
master manifest; it always matches this list. Do **not** put the
service role key anywhere else.

| Key                              | Required  | Notes                                              |
| -------------------------------- | --------- | -------------------------------------------------- |
| `SUPABASE_URL`                   | yes       | `https://<ref>.supabase.co`                        |
| `SUPABASE_SERVICE_ROLE_KEY`      | yes       | Project Settings → API → service_role              |
| `EDGAR_IDENTITY`                 | yes       | SEC-compliant name + email                         |
| `METIS_HARNESS_LLM_PROVIDER`     | yes       | `fixture` (cold start) or `openai` / `anthropic`    |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | if using that provider |                                              |
| `METIS_TODAY_SOURCE`             | yes       | `registry` (MVP default; do not change)            |
| `METIS_UI_INVOKE_ENABLED`        | optional  | `0` unless you want UI-originated sandbox enqueues |
| `PHASE47_PHASE46_BUNDLE`         | no        | Defaults to the committed bundle path              |
| `FMP_API_KEY`                    | optional  | Only if using FMP transcripts                      |

Railway injects `$PORT` automatically for `web:` — `phase47_runtime/app.py`
detects it and binds `0.0.0.0:$PORT`. Locally it still defaults to
`127.0.0.1:8765`.

## 4. First deploy + smoke test (web)

1. Deploy → wait for the build to finish.
2. `curl https://<your-railway-domain>/api/runtime/health?lang=ko`
   — expect:
   ```
   HTTP/1.1 200 OK
   { "ok": true,
     "health_status": "ok" | "degraded",
     "degraded_reasons": [...],
     "mvp_brain_gate": { ..., "brain_bundle_tier": "sample" }, ... }
   ```
   * `ok` = all subsystems green.
   * `degraded` = the service is up but one of bundle/overlay/summary
     steps failed — the payload still renders. `degraded_reasons`
     lists the failing step.
   * `down` (503) = catastrophic, only the process-level exception path.
3. `curl https://<your-railway-domain>/api/locale?lang=ko | jq '.strings["home.sample.card_title"]'`
   — should return the new **sample** copy (not `(데모)`).
4. Open the cockpit in a browser; the utility nav row should show the
   bundle-tier chip (`Production` if the v2 bundle is committed and
   wins the inference rule; otherwise `Sample`).

## 5. First worker tick (worker)

1. Railway → worker service → Logs.
2. Verify you see one `{"ok": true, "summary": ...}` line per 30s.
3. Trigger a one-shot sandbox enqueue from the UI (or the
   `/api/sandbox/requests` POST endpoint). Watch the worker drain it
   within one cycle — the request should move through
   `queued → running → completed` and show up in the per-entry "Recent
   sandbox requests" list.
4. If the worker is **idle but queues have depth**, the most common
   cause is env-var drift between `web` and `worker`. Pin both services
   to the same env var template.

## 6. Rollback procedure

Railway keeps each deployment as a rollback target.

1. If `/api/runtime/health` returns `down` or the worker Logs show
   repeated `tick_loop_exception`:
   * Railway → Deployments → previous green deploy → **Rollback**.
   * The worker rolls back independently; rollback order is not
     critical because state lives in Supabase.
2. If Supabase is the problem (migration broken, extension disabled),
   pause the worker (Railway → worker → Settings → Stop), fix
   Supabase, then resume. The `web` service will degrade (200 +
   `degraded`) but stay reachable during the outage.
3. If the v2 bundle regresses, roll back `data/mvp/metis_brain_bundle_v2.json`
   in git and redeploy. The `_infer_brain_bundle_tier` rule will then
   re-classify the active bundle back to `sample` — no service
   intervention needed.

## 7. Observability (built-in, no external SaaS)

* **Railway Logs** — `{json}` lines; filter by `"event"` field.
* **`/api/runtime/health`** — always 200 unless `down`. Look at
  `degraded_reasons` before opening a deep debug session.
* **`/api/runtime/health` → `advanced.perf_metrics`** — factor-validation
  and bundle-build timings (C1 / C2 instrumentation). Use this to
  confirm the scale-closure bottlenecks stay closed.
* **`mvp_brain_gate.brain_bundle_tier`** — never toggles from
  `production` to `sample` without a deploy; if it does, investigate
  the bundle file committed to git.
* **`recent_skips_plain`** — 5 most recent scheduler skip reasons.

## 8. Known limitations (intentional)

* **No auto-scaling**. Single web + single worker. S&P 500 coverage
  has been rehearsed in C3 (Scale Readiness Note Patch 8) but the
  hosted footprint stays 1-web + 1-worker until a second operator is
  onboarded.
* **No LLM direct writes**. The hosted worker never writes registry
  bundles or Today rows straight from an LLM — only the human
  promotion path via `harness-decide` + `harness-tick` mutates the
  bundle.
* **No `buy/sell` copy**. All operator-facing strings graduate from
  `phase47e_user_locale.py`; the no-leak test
  (`test_agh_v1_patch8_locale_graduation_no_leak.py`) must stay green
  in CI before any deploy.
* **No `demo` UI copy in production**. D1 graduated the locale to
  `sample` / `production`; legacy `demo` keys still resolve via
  `LEGACY_LOCALE_ALIASES` for a 3-month grace window only.
