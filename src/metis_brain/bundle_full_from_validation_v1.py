"""Slice B — build a Metis brain bundle with artifacts + spectrum rows **synthesized**
from live factor_validation results (no longer stub template data).

Pipeline per gate spec:
    1. Export promotion_gate from DB (existing `factor_validation_gate_export_v0`).
    2. Synthesize ``ModelArtifactPacketV0`` from the summary + quantiles (B1).
    3. Synthesize ``spectrum_rows_by_horizon[bundle_horizon]`` from the joined
       validation + factor panel rows (B2).
    4. Replace the corresponding artifact in the bundle, merge the gate (legacy
       merge), set spectrum rows, sync validation_pointer.
    5. Validate bundle integrity (same contract as ``today_spectrum.py`` reads).

The caller provides two DB-adapter callables so this module stays pure and testable.

Real Bundle Generalization v1 extensions:
    * ``auto_degrade_optional_gates`` — list of ``"factor:horizon"`` keys whose
      failures (gate_export / joined_fetch / empty spectrum rows / non-passing
      gate) are tolerated; the spec is skipped instead of aborting the build,
      and provenance records a ``degraded`` entry.
    * ``horizon_fallback_labels`` — explicit label map for bundle horizons that
      have no real-derived input yet (e.g. ``medium_long``/``long``). Those
      horizons are recorded as ``template_fallback`` in ``horizon_provenance``.
    * ``display_aliases`` — founder-facing alias layer keyed by ``artifact_id``
      or ``registry_entry_id``. Canonical display names are written into
      artifact / registry entry fields and surfaced in ``horizon_provenance``.
    * ``horizon_provenance`` — top-level bundle field populated here so Today /
      Research / Replay and runtime health can distinguish real-derived
      artifacts from template fallbacks without silent carryover.
"""

from __future__ import annotations

import json
import sys
from time import perf_counter
from typing import Any, Callable

from metis_brain.artifact_from_validation_v1 import (
    build_artifact_from_validation_v1,
    map_validation_horizon_to_bundle_horizon,
)
from metis_brain.bundle_promotion_merge_v0 import (
    merge_promotion_gate_into_bundle_dict,
    sync_artifact_validation_pointer_for_factor_run,
    validate_merged_bundle_dict,
)
from metis_brain.spectrum_rows_from_validation_v1 import (
    build_spectrum_rows_from_validation,
)

GateFetchFn = Callable[[Any, dict[str, Any]], dict[str, Any]]
JoinedFetchFn = Callable[[Any, dict[str, Any]], dict[str, Any]]


def _emit_perf_log(*, fn: str, ms: float, extra: dict[str, Any] | None = None) -> None:
    """AGH v1 Patch 8 C2a — bundle-builder stderr perf log."""
    try:
        rec = {"kind": "metis_perf", "fn": fn, "ms": round(float(ms), 3)}
        if extra:
            rec.update(extra)
        sys.stderr.write(json.dumps(rec, sort_keys=True) + "\n")
    except Exception:  # pragma: no cover - defensive
        pass


def _resolve_shared_panels(
    client: Any,
    *,
    universe_name: str,
    limit: int,
    cache: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    """Return ``(symbols, vpanels, fp_map)`` for ``(universe_name, limit)``.

    AGH v1 Patch 8 C2a — during ``build_bundle_full_from_validation_v1`` the
    same universe / panel limit is fetched once per ``(universe, limit)`` and
    reused across every gate spec that targets that universe. This removes
    the Patch 7 F3 bottleneck where each factor·horizon·basis spec fetched
    the full panel slice independently (~N× cost at 200 specs).

    The cache is per builder invocation (instantiated inside
    ``build_bundle_full_from_validation_v1``) so we never leak panel snapshots
    across batch boundaries / runs.
    """

    key = (str(universe_name).strip(), int(limit))
    cached = cache.get(key)
    if cached is not None:
        cached["cache_hit"] = True
        return cached

    from db.records import (
        fetch_factor_market_validation_panels_for_symbols,
        fetch_issuer_quarter_factor_panels_for_accessions,
    )
    from research.universe_slices import resolve_slice_symbols

    t0 = perf_counter()
    symbols = resolve_slice_symbols(client, key[0])
    vpanels = fetch_factor_market_validation_panels_for_symbols(
        client, symbols=symbols, limit=key[1]
    )
    accessions = sorted(
        {str(p.get("accession_no")) for p in vpanels if p.get("accession_no")}
    )
    fp_map = fetch_issuer_quarter_factor_panels_for_accessions(
        client, accession_nos=accessions, limit_per_batch=key[1]
    )
    entry = {
        "symbols": symbols,
        "vpanels": vpanels,
        "fp_map": fp_map,
        "cache_hit": False,
    }
    cache[key] = entry
    _emit_perf_log(
        fn="bundle_full_from_validation_v1._resolve_shared_panels",
        ms=(perf_counter() - t0) * 1000.0,
        extra={
            "universe_name": key[0],
            "limit": key[1],
            "symbol_count": len(symbols),
            "vpanel_count": len(vpanels),
            "fp_map_size": len(fp_map),
        },
    )
    return entry


def _replace_artifact_in_bundle(
    bundle_dict: dict[str, Any], artifact_dict: dict[str, Any]
) -> dict[str, Any]:
    aid = str(artifact_dict.get("artifact_id") or "").strip()
    if not aid:
        raise ValueError("artifact_dict.artifact_id required")
    out = json.loads(json.dumps(bundle_dict, default=str))
    arts = list(out.get("artifacts") or [])
    arts = [a for a in arts if str((a or {}).get("artifact_id") or "") != aid]
    arts.append(dict(artifact_dict))
    out["artifacts"] = arts
    return out


def _set_spectrum_rows_for_horizon(
    bundle_dict: dict[str, Any],
    *,
    bundle_horizon: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    out = json.loads(json.dumps(bundle_dict, default=str))
    srh = dict(out.get("spectrum_rows_by_horizon") or {})
    srh[bundle_horizon] = [dict(r) for r in rows]
    out["spectrum_rows_by_horizon"] = srh
    return out


def _auto_degrade_key(spec: dict[str, Any]) -> str:
    return f"{str(spec.get('factor_name') or '').strip()}:{str(spec.get('horizon_type') or '').strip()}"


def _alias_for_artifact(
    aliases: dict[str, Any], *, artifact_id: str
) -> dict[str, str]:
    bucket = aliases.get("artifacts") if isinstance(aliases, dict) else None
    if not isinstance(bucket, dict):
        return {}
    row = bucket.get(artifact_id) or {}
    if not isinstance(row, dict):
        return {}
    return {
        "display_id": str(row.get("display_id") or "").strip(),
        "display_family_name_ko": str(row.get("display_family_name_ko") or "").strip(),
        "display_family_name_en": str(row.get("display_family_name_en") or "").strip(),
    }


def _alias_for_registry(
    aliases: dict[str, Any], *, registry_entry_id: str
) -> dict[str, str]:
    bucket = aliases.get("registry_entries") if isinstance(aliases, dict) else None
    if not isinstance(bucket, dict):
        return {}
    row = bucket.get(registry_entry_id) or {}
    if not isinstance(row, dict):
        return {}
    return {
        "display_id": str(row.get("display_id") or "").strip(),
        "display_family_name_ko": str(row.get("display_family_name_ko") or "").strip(),
        "display_family_name_en": str(row.get("display_family_name_en") or "").strip(),
    }


def _apply_alias_to_dict(target: dict[str, Any], alias: dict[str, str]) -> dict[str, Any]:
    if not alias:
        return target
    if alias.get("display_id"):
        target["display_id"] = alias["display_id"]
    if alias.get("display_family_name_ko"):
        target["display_family_name_ko"] = alias["display_family_name_ko"]
    if alias.get("display_family_name_en"):
        target["display_family_name_en"] = alias["display_family_name_en"]
    return target


def _inject_artifact_alias(
    bundle_dict: dict[str, Any],
    *,
    artifact_id: str,
    aliases: dict[str, Any],
) -> dict[str, Any]:
    alias = _alias_for_artifact(aliases, artifact_id=artifact_id)
    if not alias:
        return bundle_dict
    out = json.loads(json.dumps(bundle_dict, default=str))
    arts = list(out.get("artifacts") or [])
    for i, a in enumerate(arts):
        if str((a or {}).get("artifact_id") or "") == artifact_id:
            arts[i] = _apply_alias_to_dict(dict(a), alias)
    out["artifacts"] = arts
    return out


def _inject_registry_aliases(
    bundle_dict: dict[str, Any], *, aliases: dict[str, Any]
) -> dict[str, Any]:
    out = json.loads(json.dumps(bundle_dict, default=str))
    entries = list(out.get("registry_entries") or [])
    for i, e in enumerate(entries):
        rid = str((e or {}).get("registry_entry_id") or "")
        if not rid:
            continue
        alias = _alias_for_registry(aliases, registry_entry_id=rid)
        if alias:
            entries[i] = _apply_alias_to_dict(dict(e), alias)
    out["registry_entries"] = entries
    return out


def _registry_entry_for_artifact(
    bundle_dict: dict[str, Any], *, artifact_id: str
) -> dict[str, Any] | None:
    for e in bundle_dict.get("registry_entries") or []:
        if str((e or {}).get("active_artifact_id") or "") == artifact_id:
            return dict(e)
        chs = (e or {}).get("challenger_artifact_ids") or []
        if isinstance(chs, list) and artifact_id in chs:
            return dict(e)
    return None


def _gate_passes(gate: dict[str, Any]) -> bool:
    return bool(
        gate.get("pit_pass")
        and gate.get("coverage_pass")
        and gate.get("monotonicity_pass")
    )


def _extract_pit_rule(gate: dict[str, Any]) -> str:
    reasons = str(gate.get("reasons") or "")
    for token in reasons.split(";"):
        t = token.strip()
        if t.startswith("pit_rule="):
            return t.split("=", 1)[1].strip()
    return ""


def _initial_spectrum_rows_present(
    bundle_dict: dict[str, Any], *, bundle_horizon: str
) -> bool:
    srh = (bundle_dict.get("spectrum_rows_by_horizon") or {}).get(bundle_horizon) or []
    return isinstance(srh, list) and len(srh) > 0


def build_bundle_full_from_validation_v1(
    *,
    template_bundle: dict[str, Any],
    gate_specs: list[dict[str, Any]],
    fetch_gate: GateFetchFn,
    fetch_joined: JoinedFetchFn,
    client: Any,
    sync_artifact_validation_pointer: bool,
    spectrum_max_rows_per_horizon: int | None = None,
    auto_degrade_optional_gates: list[str] | None = None,
    horizon_fallback_labels: dict[str, dict[str, Any]] | None = None,
    display_aliases: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return (bundle_dict, report). ``bundle_dict`` is None on any hard failure.

    ``fetch_joined(client, spec)`` must return a dict with keys:
        - ``ok`` (bool)
        - ``summary_row`` (dict)
        - ``quantile_rows`` (list)
        - ``joined_rows`` (list)
        - ``run_id`` (str)
    """
    _build_t0 = perf_counter()
    merged: dict[str, Any] = json.loads(json.dumps(template_bundle, default=str))
    steps: list[dict[str, Any]] = []

    optional_set = {str(k).strip() for k in (auto_degrade_optional_gates or [])}
    aliases = display_aliases or {}
    fallbacks = dict(horizon_fallback_labels or {})

    # AGH v1 Patch 8 C2a — shared panel cache per builder invocation. If
    # ``fetch_joined`` is our canonical DB adapter (accepts ``panel_cache``),
    # we wrap it so all specs on the same universe share one fetch. If the
    # caller injected a legacy fixture-style callable without that kwarg,
    # the wrapper quietly falls back to the original semantics. The cache
    # is in-process only and dies with this call.
    _panel_cache: dict[tuple[str, int], dict[str, Any]] = {}
    _panel_cache_hits = 0
    _panel_cache_misses = 0
    _original_fetch_joined = fetch_joined

    def _cached_fetch_joined(c: Any, s: dict[str, Any]) -> dict[str, Any]:
        nonlocal _panel_cache_hits, _panel_cache_misses
        try:
            before = len(_panel_cache)
            res = _original_fetch_joined(c, s, panel_cache=_panel_cache)  # type: ignore[call-arg]
            after = len(_panel_cache)
            if after > before:
                _panel_cache_misses += 1
            else:
                _panel_cache_hits += 1
            return res
        except TypeError:
            # Legacy / test fixture fetch_joined without panel_cache kwarg.
            return _original_fetch_joined(c, s)

    fetch_joined = _cached_fetch_joined

    # horizon_provenance entries aggregated per bundle_horizon.
    provenance: dict[str, dict[str, Any]] = {}
    horizon_has_spectrum_rows: dict[str, bool] = {}

    def _record_real_derived(
        *,
        bundle_horizon: str,
        spec: dict[str, Any],
        gate: dict[str, Any],
        run_id: str,
        spectrum_row_count: int,
        artifact_alias: dict[str, str],
        registry_entry_id: str,
    ) -> None:
        entry_core = {
            "factor_name": spec.get("factor_name"),
            "validation_horizon_type": spec.get("horizon_type"),
            "return_basis": spec.get("return_basis") or "raw",
            "run_id": run_id,
            "artifact_id": spec.get("artifact_id"),
            "registry_entry_id": registry_entry_id,
            "pit_pass": bool(gate.get("pit_pass")),
            "coverage_pass": bool(gate.get("coverage_pass")),
            "monotonicity_pass": bool(gate.get("monotonicity_pass")),
            "pit_rule": _extract_pit_rule(gate),
            "spectrum_row_count": int(spectrum_row_count),
            "display_id": artifact_alias.get("display_id") or "",
            "display_family_name_ko": artifact_alias.get("display_family_name_ko") or "",
            "display_family_name_en": artifact_alias.get("display_family_name_en") or "",
            "degraded": False,
        }
        cur = provenance.get(bundle_horizon)
        if cur is None:
            provenance[bundle_horizon] = {
                "source": "real_derived",
                **entry_core,
                "contributing_gates": [dict(entry_core)],
            }
        else:
            # Subsequent gates for same horizon become contributing entries.
            cur["contributing_gates"].append(dict(entry_core))
            # Keep top-level reflecting any degraded state in contributors.
            if any(g.get("degraded") for g in cur["contributing_gates"]):
                cur["source"] = "real_derived_with_degraded_challenger"

    def _record_degraded(
        *,
        bundle_horizon: str | None,
        spec: dict[str, Any],
        reason: str,
    ) -> None:
        key = bundle_horizon or map_validation_horizon_to_bundle_horizon(
            str(spec.get("horizon_type") or "")
        )
        entry = {
            "factor_name": spec.get("factor_name"),
            "validation_horizon_type": spec.get("horizon_type"),
            "return_basis": spec.get("return_basis") or "raw",
            "artifact_id": spec.get("artifact_id"),
            "degraded": True,
            "degraded_reason": reason,
        }
        cur = provenance.get(key)
        if cur is None:
            provenance[key] = {
                "source": "degraded_pending_real_derived",
                "contributing_gates": [entry],
                "display_id": "",
                "display_family_name_ko": "",
                "display_family_name_en": "",
            }
        else:
            cur["contributing_gates"].append(entry)
            if cur.get("source") == "real_derived":
                cur["source"] = "real_derived_with_degraded_challenger"

    for spec_in in gate_specs:
        spec = {
            k: str(v).strip()
            for k, v in spec_in.items()
            if k
            in {
                "factor_name",
                "universe_name",
                "horizon_type",
                "return_basis",
                "artifact_id",
            }
        }
        is_optional = _auto_degrade_key(spec) in optional_set
        step: dict[str, Any] = {
            "spec": spec,
            "optional": is_optional,
            "gate_export_ok": False,
            "joined_fetch_ok": False,
            "spectrum_row_count": 0,
            "merged": False,
            "degraded": False,
        }
        steps.append(step)

        try:
            bundle_horizon_preview = map_validation_horizon_to_bundle_horizon(
                spec.get("horizon_type") or ""
            )
        except ValueError:
            bundle_horizon_preview = None
        step["bundle_horizon"] = bundle_horizon_preview

        ex = fetch_gate(client, spec)
        step["gate_export_ok"] = bool(ex.get("ok"))
        if not ex.get("ok"):
            reason = f"gate_export_failed:{ex.get('error')}"
            if is_optional:
                step["degraded"] = True
                step["degraded_reason"] = reason
                _record_degraded(
                    bundle_horizon=bundle_horizon_preview, spec=spec, reason=reason
                )
                continue
            return None, {
                "integrity_ok": False,
                "errors": [reason],
                "steps": steps,
                "aborted_reason": "gate_export_failed",
            }
        gate = ex.get("promotion_gate")
        if not isinstance(gate, dict):
            reason = "promotion_gate_missing_in_export"
            if is_optional:
                step["degraded"] = True
                step["degraded_reason"] = reason
                _record_degraded(
                    bundle_horizon=bundle_horizon_preview, spec=spec, reason=reason
                )
                continue
            return None, {
                "integrity_ok": False,
                "errors": [reason],
                "steps": steps,
                "aborted_reason": "invalid_gate_export",
            }

        step["gate_pass"] = _gate_passes(gate)
        if is_optional and not step["gate_pass"]:
            reason = (
                f"optional_gate_not_passing:pit={bool(gate.get('pit_pass'))};"
                f"coverage={bool(gate.get('coverage_pass'))};"
                f"mono={bool(gate.get('monotonicity_pass'))}"
            )
            step["degraded"] = True
            step["degraded_reason"] = reason
            _record_degraded(
                bundle_horizon=bundle_horizon_preview, spec=spec, reason=reason
            )
            continue

        jx = fetch_joined(client, spec)
        step["joined_fetch_ok"] = bool(jx.get("ok"))
        if not jx.get("ok"):
            reason = f"joined_fetch_failed:{jx.get('error')}"
            if is_optional:
                step["degraded"] = True
                step["degraded_reason"] = reason
                _record_degraded(
                    bundle_horizon=bundle_horizon_preview, spec=spec, reason=reason
                )
                continue
            return None, {
                "integrity_ok": False,
                "errors": [reason],
                "steps": steps,
                "aborted_reason": "joined_fetch_failed",
            }
        summary_row = jx.get("summary_row") or {}
        quantile_rows = jx.get("quantile_rows") or []
        joined_rows = jx.get("joined_rows") or []
        run_id = str(jx.get("run_id") or "").strip()
        if not run_id:
            reason = "joined_fetch_missing_run_id"
            if is_optional:
                step["degraded"] = True
                step["degraded_reason"] = reason
                _record_degraded(
                    bundle_horizon=bundle_horizon_preview, spec=spec, reason=reason
                )
                continue
            return None, {
                "integrity_ok": False,
                "errors": [reason],
                "steps": steps,
                "aborted_reason": "joined_fetch_failed",
            }

        artifact = build_artifact_from_validation_v1(
            factor_name=spec["factor_name"],
            universe_name=spec["universe_name"],
            horizon_type=spec["horizon_type"],
            return_basis=spec.get("return_basis") or "raw",
            artifact_id=spec["artifact_id"],
            run_id=run_id,
            summary_row=summary_row,
            quantile_rows=quantile_rows,
        )
        artifact_alias = _alias_for_artifact(
            aliases, artifact_id=str(artifact.get("artifact_id") or "")
        )
        artifact = _apply_alias_to_dict(dict(artifact), artifact_alias)

        bundle_horizon, spectrum_rows = build_spectrum_rows_from_validation(
            factor_name=spec["factor_name"],
            horizon_type=spec["horizon_type"],
            summary_row=summary_row,
            joined_rows=joined_rows,
            max_rows=spectrum_max_rows_per_horizon,
        )
        step["bundle_horizon"] = bundle_horizon
        step["spectrum_row_count"] = len(spectrum_rows)
        step["artifact_id"] = artifact.get("artifact_id")

        if not spectrum_rows:
            reason = (
                f"no_spectrum_rows_synthesized:factor={spec['factor_name']}"
                f";horizon={bundle_horizon};universe={spec['universe_name']}"
            )
            if is_optional:
                step["degraded"] = True
                step["degraded_reason"] = reason
                _record_degraded(
                    bundle_horizon=bundle_horizon, spec=spec, reason=reason
                )
                continue
            return None, {
                "integrity_ok": False,
                "errors": [reason],
                "steps": steps,
                "aborted_reason": "no_spectrum_rows",
            }

        try:
            merged = _replace_artifact_in_bundle(merged, artifact)
            merged = merge_promotion_gate_into_bundle_dict(merged, gate)
            # Only the first successful spec per horizon writes spectrum rows;
            # subsequent challenger gates keep their gate + artifact but do not
            # overwrite the active spectrum rows for that horizon.
            if not horizon_has_spectrum_rows.get(bundle_horizon):
                merged = _set_spectrum_rows_for_horizon(
                    merged, bundle_horizon=bundle_horizon, rows=spectrum_rows
                )
                horizon_has_spectrum_rows[bundle_horizon] = True
            if sync_artifact_validation_pointer:
                merged = sync_artifact_validation_pointer_for_factor_run(
                    merged,
                    artifact_id=str(gate.get("artifact_id") or ""),
                    evaluation_run_id=str(gate.get("evaluation_run_id") or ""),
                )
        except ValueError as e:
            reason = f"merge_failed:{e}"
            if is_optional:
                step["degraded"] = True
                step["degraded_reason"] = reason
                _record_degraded(
                    bundle_horizon=bundle_horizon, spec=spec, reason=reason
                )
                continue
            return None, {
                "integrity_ok": False,
                "errors": [reason],
                "steps": steps,
                "aborted_reason": "merge_failed",
            }

        step["merged"] = True
        reg = _registry_entry_for_artifact(merged, artifact_id=spec["artifact_id"])
        _record_real_derived(
            bundle_horizon=bundle_horizon,
            spec=spec,
            gate=gate,
            run_id=run_id,
            spectrum_row_count=len(spectrum_rows),
            artifact_alias=artifact_alias,
            registry_entry_id=str((reg or {}).get("registry_entry_id") or ""),
        )

    # After all specs: overlay registry aliases (for any registry entries named
    # explicitly in display_aliases.registry_entries) so founder-facing
    # surfaces see canonical names regardless of which gates ran.
    merged = _inject_registry_aliases(merged, aliases=aliases)

    # Fallback horizons — horizons explicitly labelled as template-only by the
    # build config (e.g. ``medium_long``, ``long`` until the forward-returns
    # pipeline emits those targets).
    for hz, meta in fallbacks.items():
        if hz in provenance:
            continue  # real-derived takes precedence
        meta = meta or {}
        # Attempt to surface the active registry's artifact_id for visibility.
        reg = next(
            (
                e
                for e in merged.get("registry_entries") or []
                if str((e or {}).get("horizon") or "") == hz
            ),
            None,
        )
        active_aid = str((reg or {}).get("active_artifact_id") or "")
        registry_alias = _alias_for_registry(
            aliases, registry_entry_id=str((reg or {}).get("registry_entry_id") or "")
        )
        artifact_alias = _alias_for_artifact(aliases, artifact_id=active_aid)
        provenance[hz] = {
            "source": "template_fallback",
            "reason": str(
                meta.get("reason")
                or "horizon_real_derived_not_available_in_this_build"
            ),
            "artifact_id": active_aid,
            "registry_entry_id": str((reg or {}).get("registry_entry_id") or ""),
            "display_id": (
                artifact_alias.get("display_id")
                or registry_alias.get("display_id")
                or str(meta.get("display_id") or "")
            ),
            "display_family_name_ko": (
                artifact_alias.get("display_family_name_ko")
                or registry_alias.get("display_family_name_ko")
                or str(meta.get("display_family_name_ko") or "")
            ),
            "display_family_name_en": (
                artifact_alias.get("display_family_name_en")
                or registry_alias.get("display_family_name_en")
                or str(meta.get("display_family_name_en") or "")
            ),
            "contributing_gates": [],
        }

    # Bounded Non-Quant Cash-Out v1 — BNCO-6. Canonicalize horizon_provenance.source
    # to one of the 4 canonical values required by runtime honesty surfaces:
    #   real_derived / real_derived_with_degraded_challenger /
    #   template_fallback / insufficient_evidence.
    # The transient label ``degraded_pending_real_derived`` means no real gate
    # landed AND no template fallback is configured — we project it to
    # ``insufficient_evidence`` so runtime / health surfaces never imply
    # confidence that does not exist.
    for hz_key, prov in list(provenance.items()):
        if not isinstance(prov, dict):
            continue
        src = str(prov.get("source") or "")
        if src == "degraded_pending_real_derived":
            prov["source"] = "insufficient_evidence"
            if "reason" not in prov:
                prov["reason"] = "no_real_derived_gate_landed_and_no_template_fallback_configured"
    merged["horizon_provenance"] = provenance

    # Patch 11 — aggregate long-horizon evidence support per horizon so
    # the Product Shell confidence badge on medium_long/long can show an
    # honest tier (production / limited / sample) rather than a binary
    # provenance label.
    from metis_brain.long_horizon_evidence_v1 import (
        summarize_long_horizon_support_as_dicts,
    )

    merged["long_horizon_support_by_horizon"] = summarize_long_horizon_support_as_dicts(
        spectrum_rows_by_horizon=dict(merged.get("spectrum_rows_by_horizon") or {}),
        as_of_utc=str(merged.get("as_of_utc") or ""),
        horizons=("medium_long", "long"),
    )

    integrity_ok, errs = validate_merged_bundle_dict(merged)
    report: dict[str, Any] = {
        "integrity_ok": integrity_ok,
        "errors": errs,
        "steps": steps,
        "horizon_provenance": provenance,
        # AGH v1 Patch 8 C2a — surface panel cache metrics so the runbook /
        # evidence JSON can quantify the before-after improvement.
        "panel_cache": {
            "distinct_universes": len(_panel_cache),
            "hits": _panel_cache_hits,
            "misses": _panel_cache_misses,
            "spec_count": len(gate_specs),
        },
    }
    _emit_perf_log(
        fn="bundle_full_from_validation_v1.build_bundle_full_from_validation_v1",
        ms=(perf_counter() - _build_t0) * 1000.0,
        extra={
            "spec_count": len(gate_specs),
            "panel_cache_hits": _panel_cache_hits,
            "panel_cache_misses": _panel_cache_misses,
            "distinct_universes": len(_panel_cache),
            "integrity_ok": bool(integrity_ok),
        },
    )
    if not integrity_ok:
        report["aborted_reason"] = "integrity_failed"
        return None, report
    report["aborted_reason"] = None
    return merged, report


def fetch_joined_rows_for_factor_db(
    client: Any,
    spec: dict[str, Any],
    *,
    panel_cache: dict[tuple[str, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """DB adapter: fetches summary_row + quantile_rows + joined_rows for one gate spec.

    AGH v1 Patch 8 C2a — ``panel_cache`` is an optional, caller-owned dict
    keyed by ``(universe_name, panel_limit)``. When provided, panel / factor
    fetches are cached so multiple specs on the same universe reuse one fetch
    instead of re-hitting the DB. Passing ``None`` preserves legacy
    standalone-call semantics for any outside caller that's not the bundle
    builder.

    Reuses the primitives in ``research.validation_runner``:
      * ``resolve_slice_symbols(client, universe_name)``
      * ``fetch_factor_market_validation_panels_for_symbols(...)``
      * ``fetch_issuer_quarter_factor_panels_for_accessions(...)``
    """
    from db.records import (
        fetch_factor_quantiles_for_run,
        fetch_latest_factor_validation_summaries,
        issuer_quarter_factor_panel_join_key,
    )

    factor = str(spec.get("factor_name") or "").strip()
    universe = str(spec.get("universe_name") or "").strip()
    horizon = str(spec.get("horizon_type") or "").strip()
    basis = str(spec.get("return_basis") or "raw").strip()

    run_id, rows = fetch_latest_factor_validation_summaries(
        client,
        factor_name=factor,
        universe_name=universe,
        horizon_type=horizon,
    )
    if not run_id or not rows:
        return {"ok": False, "error": "no_completed_validation_summary"}
    summary = next((r for r in rows if str(r.get("return_basis")) == basis), None)
    if summary is None:
        return {
            "ok": False,
            "error": "return_basis_row_missing",
            "available_return_basis": sorted({str(r.get("return_basis")) for r in rows}),
        }

    quantile_rows = fetch_factor_quantiles_for_run(
        client,
        run_id=run_id,
        factor_name=factor,
        universe_name=universe,
        horizon_type=horizon,
        return_basis=basis,
    ) or []

    if panel_cache is None:
        panel_cache = {}
    panels = _resolve_shared_panels(
        client, universe_name=universe, limit=8000, cache=panel_cache
    )
    vpanels = panels["vpanels"]
    fp_map = panels["fp_map"]

    joined: list[dict[str, Any]] = []
    for vp in vpanels:
        key = issuer_quarter_factor_panel_join_key(
            vp.get("cik"),
            vp.get("accession_no"),
            vp.get("factor_version"),
            default_factor_version="v1",
        )
        fp = fp_map.get(key)
        if fp is None:
            continue
        factor_value = fp.get(factor)
        if factor_value is None:
            continue
        joined.append({
            "symbol": vp.get("symbol"),
            "cik": vp.get("cik"),
            "accession_no": vp.get("accession_no"),
            "fiscal_year": fp.get("fiscal_year"),
            "fiscal_period": fp.get("fiscal_period"),
            factor: factor_value,
        })

    return {
        "ok": True,
        "run_id": run_id,
        "summary_row": dict(summary),
        "quantile_rows": [dict(q) for q in quantile_rows],
        "joined_rows": joined,
    }
