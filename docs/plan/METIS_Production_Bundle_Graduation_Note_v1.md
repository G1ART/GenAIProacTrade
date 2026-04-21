# METIS Production Bundle Graduation Note v1

**Patch:** AGH v1 Patch 8 (D1 + D2 + D3)
**Status:** authoritative for all bundle-tier copy / health / UI

## 1. Why we graduated "demo" to "sample" and introduced "production"

Up to Patch 7 the product surfaced a single user-facing label — "demo" —
for the frozen investor seed pack at
`data/mvp/metis_brain_bundle_v0.json`. Two problems emerged:

1. The word *demo* implied the artifact is throw-away UI, when in
   practice the bundle carries real research-branch shape (artifacts,
   registry entries, spectrum rows, horizon provenance).
2. There was no path to describe a **production** tier that graduates
   from the R-branch Supabase live validation runs without renaming the
   existing frozen seed pack.

Patch 8 therefore introduces a stable **3-tier vocabulary**:

| Tier         | Source                                                                 | Bundle path                                 |
| ------------ | ---------------------------------------------------------------------- | ------------------------------------------- |
| `demo`       | Built-in fallback artifacts; no DB-derived evidence.                   | (no file; fallback-only path)               |
| `sample`     | Frozen investor seed pack. Real bundle shape, frozen provenance.       | `data/mvp/metis_brain_bundle_v0.json`       |
| `production` | Graduated from R-branch Supabase completed runs via D2 build script.   | `data/mvp/metis_brain_bundle_v2.json`       |

The old `demo`-prefixed locale keys (`home.demo.*`, `spectrum.demo_*`,
`demo.route.*`) are still resolvable for a **3-month grace window** via
`LEGACY_LOCALE_ALIASES` in `src/phase47_runtime/phase47e_user_locale.py`.
All new code MUST use the `sample` / `production` prefixes.

## 2. Building the production bundle

```
python scripts/agh_v1_patch_8_production_bundle_graduation.py
```

The script is deterministic and safe to run offline:

* With `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` in the environment it
  pulls the live research-branch rows and runs
  `build_bundle_full_from_validation_v1` over the canonical
  `data/mvp/metis_brain_bundle_build_v2.json` gate set.
* Without credentials it falls back to a template-only build and stamps
  `metadata.graduation_tier = "production"` on the output bundle. The
  evidence JSON records `build_mode = "template"` so operators can tell
  the two modes apart.

Output:

* `data/mvp/metis_brain_bundle_v2.json` — atomic write (`.tmp` → `os.replace`).
* `data/mvp/evidence/pragmatic_brain_absorption_v1_production_bundle_v2_evidence.json`
  — sha256, byte size, integrity errors (must be `[]`), gate count, build mode.

The script refuses to write the bundle if
`validate_active_registry_integrity` returns any errors — the v2 bundle
is only promoted when the registry invariants hold.

## 3. How the tier is inferred at runtime

`src/phase51_runtime/cockpit_health_surface.py::_infer_brain_bundle_tier`
is the single source of truth. Precedence:

1. `bundle.metadata.graduation_tier` ∈ {demo, sample, production} — wins
   immediately (the D2 script always writes `production` into this
   field).
2. Filename suffix: `metis_brain_bundle_v2.json` → `production`,
   `metis_brain_bundle_v0.json` → `sample`.
3. Horizon-provenance fallback: if every horizon is `real_derived*` and
   no horizon is missing provenance → `production`; if any horizon is
   `real_derived*` → `sample`; otherwise `demo`.

The inferred tier is exposed on `/api/runtime/health` under
`mvp_brain_gate.brain_bundle_tier`. The UI renders it as a **muted
chip in the utility row** (`#tsr-bundle-tier`) so the operator can tell
at a glance what tier the server is serving without opening Advanced.

## 4. Non-goals and explicit limits

* The tier badge never appears above the fold on Today. Today must
  remain registry-only regardless of tier (Product Spec §5.1).
* Tier graduation does not silently refresh active registry entries on
  a running server. The operator must still:
  1. Run the D2 script,
  2. Reload the bundle (utility-row "Reload bundle" button or restart
     the worker),
  3. Confirm `/api/runtime/health` reports the new tier.
* No automatic promotion from `sample` → `production`. A human or the
  D2 runbook must invoke the graduation script explicitly.
