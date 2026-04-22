# METIS Production Bundle Graduation Runbook v1

**Audience**: the single operator responsible for promoting `data/mvp/metis_brain_bundle_v2.json` from a newly-built candidate to the authoritative production bundle that Today / Research / Replay read at runtime.

**Scope**: covers the *repeatable* path (not the one-time bootstrap Patch 8 shipped). The graduation script, integrity hardening, tier exposure, and rollback target are all under test. This document is the operator-side view of what to do and what to expect.

**Companion docs**
- Contract: [docs/plan/METIS_Production_Bundle_Graduation_Note_v1.md](../plan/METIS_Production_Bundle_Graduation_Note_v1.md)
- Scale: [docs/plan/METIS_Scale_Readiness_Note_Patch9_v1.md](../plan/METIS_Scale_Readiness_Note_Patch9_v1.md)
- Runtime: [docs/ops/METIS_Railway_Supabase_Deployment_Runbook_v1.md](./METIS_Railway_Supabase_Deployment_Runbook_v1.md)

---

## 0. What "graduation" means in Patch 9

Patch 9 makes `v2` the **default production reality**, with auto-detection:

```
brain_bundle_path() priority, top first:
  1. METIS_BRAIN_BUNDLE env override     (operator-explicit path)
  2. data/mvp/metis_brain_bundle_v2.json (if quick-integrity OK)
  3. data/mvp/metis_brain_bundle_v0.json (sample fallback — never removed)
```

`GET /api/runtime/health` always reports the **actually resolved** bundle path and its quick-integrity state. If v2 exists on disk but is structurally broken, the runtime silently falls back to v0 **and** health emits `degraded_reasons: ["v2_integrity_failed"]` so the operator sees the fallback without surprise.

Tier vocabulary (unchanged from Patch 8):
- `demo` — built-in fallback artifacts only.
- `sample` — frozen investor seed pack (`v0`). Real bundle shape, frozen provenance.
- `production` — graduated from R-branch Supabase (`v2`). Live validation evidence.

---

## 1. Pre-flight

Before every graduation attempt:

### 1.1 Supabase evidence check

`SQL` — Supabase SQL Editor, from a read-only connection:

```sql
select count(*)
from factor_validation_runs
where status = 'completed'
  and as_of_utc >= now() - interval '180 days';
```

Expect: ≥ 1 row per horizon you intend to graduate. If you get zero rows, **stop**. The graduation script will silently fall back to template mode and refuse to claim `production` tier (Patch 9 behaviour).

### 1.2 Git state is clean

`터미널`:

```bash
cd /Users/hyunminkim/GenAIProacTrade
git status --short
```

Expect: empty output. Uncommitted local changes make rollback noisy. Commit or stash first.

### 1.3 Current health baseline

`터미널`:

```bash
cd /Users/hyunminkim/GenAIProacTrade
PHASE47_PORT=8765 python3 src/phase47_runtime/app.py --host 127.0.0.1 --port 8765 &
sleep 3
curl -s http://127.0.0.1:8765/api/runtime/health | python3 -m json.tool | head -40
kill %1
```

Expect: `health_status` is `ok` or `degraded`. Note the current `brain_bundle_path_resolved` and `brain_bundle_tier` so you have a rollback baseline.

---

## 2. Graduate v2

### 2.1 Build the candidate

`터미널`:

```bash
cd /Users/hyunminkim/GenAIProacTrade
python3 scripts/agh_v1_patch_8_production_bundle_graduation.py
```

The script will:
1. Probe Supabase for completed validation runs.
2. Attempt a live build. On failure, fall back to a template build (and refuse to claim production tier).
3. Run `validate_active_registry_integrity(parsed_bundle, tier="production")` (Patch 9 A2 hardening):
   - active/challenger id consistency, no self-promotion loops.
   - spectrum rows exist for every horizon that has an active registry entry.
   - artifact fingerprints are not demo/stub (`validation_pointer` must not start with `pit:demo:`; `created_by` must not be `deterministic_kernel`; `feature_set` must not be `stub_feature_set`).
   - `metadata.source_run_ids` non-empty and `metadata.built_at_utc` present when tier is claimed.
4. Atomic-write `data/mvp/metis_brain_bundle_v2.json` and evidence JSON. No partial writes.

### 2.2 Read the evidence

`터미널`:

```bash
cat data/mvp/evidence/pragmatic_brain_absorption_v1_production_bundle_v2_evidence.json \
  | python3 -m json.tool
```

Expect (for a real graduation):
- `"build_mode": "live"`
- `"graduation_tier": "production"`
- `"integrity_errors": []`
- `"output_sha256"` present, `"output_bytes"` > 0

If `"build_mode": "template"`, the graduation **did not** reach production tier. The v2 file on disk is still usable as a sample bundle, but you must not claim production in downstream reporting. Go back to 1.1.

### 2.3 Verify runtime sees v2

`터미널`:

```bash
cd /Users/hyunminkim/GenAIProacTrade
PHASE47_PORT=8765 python3 src/phase47_runtime/app.py --host 127.0.0.1 --port 8765 &
sleep 3
curl -s http://127.0.0.1:8765/api/runtime/health \
  | python3 -c "import json,sys; d=json.load(sys.stdin); g=d.get('mvp_brain_gate',{}); print('tier:', g.get('brain_bundle_tier')); print('path:', g.get('brain_bundle_path_resolved')); print('integrity_ok:', g.get('brain_bundle_integrity_ok')); print('degraded:', d.get('degraded_reasons'))"
kill %1
```

Expect:
- `tier: production`
- `path:` ends with `metis_brain_bundle_v2.json`
- `integrity_ok: True`
- `degraded:` does not contain `v2_integrity_failed`

### 2.4 UI check (optional)

Visit `http://127.0.0.1:8765/` in a browser. The utility nav tier chip should read **"운영 번들 / Production bundle"** (not "샘플 번들 / Sample bundle"). Hover title shows the real resolved path.

---

## 3. Rollback

Rollback is **non-destructive** — `v0` is never removed by graduation, so the fallback path always exists.

### 3.1 Rollback option A — disk restore

`터미널`:

```bash
cd /Users/hyunminkim/GenAIProacTrade
git restore data/mvp/metis_brain_bundle_v2.json
```

After restore:
- If the prior `v2` was a good production build, the auto-detect returns to that bundle.
- If the prior `v2` is missing from git (first-time bootstrap), remove the broken file:

  ```bash
  rm data/mvp/metis_brain_bundle_v2.json
  ```

  Auto-detect will now fall back to `v0` (sample), which is safe.

### 3.2 Rollback option B — env override

`터미널` (for the web process; on Railway set the env var in the dashboard):

```bash
export METIS_BRAIN_BUNDLE=data/mvp/metis_brain_bundle_v0.json
python3 src/phase47_runtime/app.py --host 0.0.0.0 --port 8765
```

This pins the runtime to `v0` regardless of what's in `v2`. Use when you want to rollback without touching disk (e.g. investigating the v2 failure at the same time).

### 3.3 Verify rollback

Repeat step 2.3. Expect:
- `tier: sample` (or `demo`, depending on v0 provenance).
- `degraded:` may include `v2_integrity_failed` if you kept a broken v2 on disk — that is intentional and the health surface is telling you the truth.

---

## 4. Failure modes + recovery

| Symptom                                                             | Diagnosis                                           | Fix                                                              |
| ------------------------------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------------------- |
| Script exits 2, "missing config"                                    | `data/mvp/metis_brain_bundle_build_v2.json` absent  | Commit the config; Patch 8 D2 ships a working one.               |
| Script exits 3, "bundle schema validation failed"                   | Supabase payload shape drift                        | Re-run 1.1; inspect the offending artifact JSON manually.        |
| Script exits 3, "validate_active_registry_integrity FAILED"         | Integrity hardening (Patch 9 A2) rejected the build | Read the lines; common culprit is `pit:demo:*` still in v2.      |
| Script exits 0 but `build_mode: "template"`                         | Live build had zero usable runs                     | Re-run 1.1; the graduation refuses to lie about production tier. |
| Health returns 200 but `degraded_reasons: ["v2_integrity_failed"]`  | v2 physically exists but fails quick-integrity gate | Run 2.1 again, OR run 3.1 (disk restore).                        |
| Health returns 200 but `brain_bundle_tier: sample` post-graduation  | Auto-detect fell back to v0                         | Inspect evidence JSON (2.2). Likely template-mode build.         |

---

## 5. Known limitations

- Patch 9 does not auto-schedule graduation. The operator runs 2.1 manually or via Railway cron (see deployment runbook §retention archive for the same cron plumbing).
- `v2` ships in git for reproducibility. For orgs that don't want bundle JSON in source control, swap step 3.1 for a Supabase Storage restore path — schema is the same.
- Integrity hardening is tier-gated. `validate_active_registry_integrity(bundle)` without `tier="production"` still uses the Patch 8 minimum checks for backwards compatibility; the strict path only fires when the caller explicitly opts in.

---

## 6. Sign-off checklist

Before you close a graduation ticket:

- [ ] Evidence JSON shows `build_mode: live` and `integrity_errors: []`.
- [ ] Runtime health shows `brain_bundle_tier: production`.
- [ ] `degraded_reasons` does not include `v2_integrity_failed`.
- [ ] UI tier chip reads "Production bundle" / "운영 번들".
- [ ] Git commit includes both `data/mvp/metis_brain_bundle_v2.json` and `data/mvp/evidence/pragmatic_brain_absorption_v1_production_bundle_v2_evidence.json`.
- [ ] Commit message references the graduation run (e.g. SHA256).
- [ ] Rollback plan noted in the ticket (disk restore vs env override).
