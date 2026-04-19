"""AGH v1 Patch 3 — per-horizon spectrum refresh helper.

Called by ``registry_patch_executor`` **after** a governed
``registry_entry_artifact_promotion`` active/challenger swap has been mutated
into the in-memory bundle dict, but **before** the atomic bundle JSON write.

Scope lock (work-order METIS_Patch_3 §5.C, Q1=A):
  * Full recompute path uses the canonical
    ``bundle_full_from_validation_v1.fetch_joined`` adapter +
    ``spectrum_rows_from_validation_v1.build_spectrum_rows_from_validation``.
    No shadow spectrum writer is permitted; the helper mutates
    ``bundle_dict['spectrum_rows_by_horizon'][horizon]`` in-place and the
    executor performs the single atomic write.
  * When ``supabase_client`` is missing (fixture / DB-less runs) the helper
    does **not** silently skip. It carries over the prior rows but marks each
    row with ``stale_after_active_swap=True`` + ``stale_since_utc`` and
    returns an ``outcome='carry_over_fixture_fallback'`` result with
    ``needs_db_rebuild=True``. Today / L5 surface the stale flag explicitly.
  * When ``fetch_joined`` raises or returns ``ok=False`` on the live path, the
    same carry-over + stale-flag path kicks in but with
    ``outcome='carry_over_db_unavailable'`` and a ``blocking_reasons`` entry.

This helper never writes the bundle to disk and never persists any packet.
Those side effects belong to the executor so that all bundle mutation flows
through a single canonical atomic write.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from metis_brain.artifact_from_validation_v1 import (
    VALIDATION_HORIZON_TO_BUNDLE,
)
from metis_brain.spectrum_rows_from_validation_v1 import (
    build_spectrum_rows_from_validation,
)


__all__ = [
    "SpectrumRefreshResult",
    "refresh_spectrum_rows_for_horizon",
]


SpectrumRefreshResult = dict[str, Any]


_BUNDLE_HORIZON_TO_VALIDATION = {
    v: k for k, v in VALIDATION_HORIZON_TO_BUNDLE.items()
}


def _row_asset_ids(rows: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for r in rows or []:
        aid = str((r or {}).get("asset_id") or "").strip()
        if aid:
            out.append(aid)
    return out


def _mark_rows_stale(
    rows: list[dict[str, Any]], *, now_iso: str
) -> list[dict[str, Any]]:
    """Mutate each row in-place with the honest 'needs db rebuild' marker."""

    for r in rows or []:
        if not isinstance(r, dict):
            continue
        r["stale_after_active_swap"] = True
        r["stale_since_utc"] = now_iso
    return rows


def _lookup_artifact(
    bundle_dict: dict[str, Any], *, artifact_id: str
) -> dict[str, Any] | None:
    for a in bundle_dict.get("artifacts") or []:
        if str((a or {}).get("artifact_id") or "") == artifact_id:
            return dict(a)
    return None


def _parse_spec_from_artifact(
    artifact: dict[str, Any],
) -> tuple[str, str, str, str] | None:
    """Return (factor_name, universe_name, horizon_type, return_basis) or None.

    Artifacts minted by ``build_artifact_from_validation_v1`` encode factor
    name inside ``feature_set`` as ``factor:<name>``. The
    ``validation_pointer`` field carries
    ``factor_validation_run:<run_id>:<factor>:<return_basis>`` so we can
    recover ``return_basis`` deterministically. ``universe`` is the artifact's
    top-level field. ``horizon`` (bundle-level) reverses the validation
    horizon type used by the panel fetcher.
    """

    feature_set = str(artifact.get("feature_set") or "").strip()
    if not feature_set.startswith("factor:"):
        return None
    factor_name = feature_set.split(":", 1)[1].strip()
    if not factor_name:
        return None
    universe_name = str(artifact.get("universe") or "").strip()
    if not universe_name:
        return None
    bundle_horizon = str(artifact.get("horizon") or "").strip()
    horizon_type = _BUNDLE_HORIZON_TO_VALIDATION.get(bundle_horizon)
    if not horizon_type:
        return None
    return_basis = "raw"
    vp = str(artifact.get("validation_pointer") or "")
    parts = vp.split(":")
    if len(parts) >= 5 and parts[0] == "factor_validation_run":
        return_basis = parts[4] or "raw"
    return factor_name, universe_name, horizon_type, return_basis


def refresh_spectrum_rows_for_horizon(
    bundle_dict: dict[str, Any],
    *,
    horizon: str,
    new_active_artifact_id: str,
    registry_entry_id: str,
    now_iso: str,
    bundle_path: str,
    cited_proposal_packet_id: str,
    cited_decision_packet_id: str,
    supabase_client: Optional[Any] = None,
    fetch_joined: Optional[Callable[[Any, dict[str, Any]], dict[str, Any]]] = None,
    build_spectrum_rows: Optional[
        Callable[..., tuple[str, list[dict[str, Any]]]]
    ] = None,
    max_rows: int | None = None,
) -> SpectrumRefreshResult:
    """Refresh ``bundle_dict['spectrum_rows_by_horizon'][horizon]`` in-place.

    Parameters
    ----------
    bundle_dict
        In-memory brain bundle dict. Already mutated by the executor to reflect
        the active/challenger swap prior to calling this helper.
    horizon
        Bundle horizon key (``short|medium|medium_long|long``).
    new_active_artifact_id
        The artifact that just became ``registry_entries[...].active_artifact_id``.
    registry_entry_id / cited_*_packet_id
        Audit identifiers copied into the result so the executor can emit the
        ``SpectrumRefreshRecordV1`` with a full lineage chain.
    now_iso
        Caller-provided UTC ISO timestamp (keeps the helper deterministic).
    bundle_path
        Path (stringified) the executor is going to ``os.replace`` into; the
        helper simply echoes this back into the result for the audit packet.
    supabase_client
        Live Supabase client. When ``None`` the helper takes the
        ``carry_over_fixture_fallback`` path.
    fetch_joined / build_spectrum_rows
        Injection hooks for tests. Defaults fall back to the canonical
        ``bundle_full_from_validation_v1.fetch_joined_rows_for_factor_db`` and
        ``spectrum_rows_from_validation_v1.build_spectrum_rows_from_validation``.
    """

    srh = dict(bundle_dict.get("spectrum_rows_by_horizon") or {})
    before_rows: list[dict[str, Any]] = list(srh.get(horizon) or [])
    before_row_count = len(before_rows)
    before_sample = _row_asset_ids(before_rows)[:10]

    result_common: dict[str, Any] = {
        "horizon": horizon,
        "registry_entry_id": registry_entry_id,
        "cited_applied_packet_id": "",  # executor fills this in after upsert
        "cited_proposal_packet_id": cited_proposal_packet_id,
        "cited_decision_packet_id": cited_decision_packet_id,
        "refreshed_at_utc": now_iso,
        "bundle_path": bundle_path,
        "before_row_count": before_row_count,
        "before_row_asset_ids_sample": before_sample,
    }

    artifact = _lookup_artifact(bundle_dict, artifact_id=new_active_artifact_id)
    spec_tuple = (
        _parse_spec_from_artifact(artifact) if isinstance(artifact, dict) else None
    )

    if supabase_client is None or spec_tuple is None:
        blocking: list[str] = []
        if supabase_client is None:
            blocking.append("supabase_client_missing_or_fixture_mode")
        if spec_tuple is None:
            blocking.append(
                "artifact_spec_unparseable_for_refresh:"
                f"{new_active_artifact_id}"
            )
        carry_rows = _mark_rows_stale(list(before_rows), now_iso=now_iso)
        srh[horizon] = carry_rows
        bundle_dict["spectrum_rows_by_horizon"] = srh
        return {
            **result_common,
            "outcome": "carry_over_fixture_fallback",
            "refresh_mode": "fixture_fallback",
            "needs_db_rebuild": True,
            "after_row_count": len(carry_rows),
            "after_row_asset_ids_sample": _row_asset_ids(carry_rows)[:10],
            "blocking_reasons": blocking,
        }

    factor_name, universe_name, horizon_type, return_basis = spec_tuple

    if fetch_joined is None:
        from metis_brain.bundle_full_from_validation_v1 import (
            fetch_joined_rows_for_factor_db,
        )

        fetch_joined = fetch_joined_rows_for_factor_db
    if build_spectrum_rows is None:
        build_spectrum_rows = build_spectrum_rows_from_validation

    spec = {
        "factor_name": factor_name,
        "universe_name": universe_name,
        "horizon_type": horizon_type,
        "return_basis": return_basis,
        "artifact_id": new_active_artifact_id,
    }

    try:
        jx = fetch_joined(supabase_client, spec)
    except Exception as exc:  # noqa: BLE001
        carry_rows = _mark_rows_stale(list(before_rows), now_iso=now_iso)
        srh[horizon] = carry_rows
        bundle_dict["spectrum_rows_by_horizon"] = srh
        return {
            **result_common,
            "outcome": "carry_over_db_unavailable",
            "refresh_mode": "fixture_fallback",
            "needs_db_rebuild": True,
            "after_row_count": len(carry_rows),
            "after_row_asset_ids_sample": _row_asset_ids(carry_rows)[:10],
            "blocking_reasons": [f"fetch_joined_raised:{type(exc).__name__}:{exc}"],
        }

    if not isinstance(jx, dict) or not jx.get("ok"):
        err = (
            str((jx or {}).get("error"))
            if isinstance(jx, dict)
            else "fetch_joined_returned_non_dict"
        )
        carry_rows = _mark_rows_stale(list(before_rows), now_iso=now_iso)
        srh[horizon] = carry_rows
        bundle_dict["spectrum_rows_by_horizon"] = srh
        return {
            **result_common,
            "outcome": "carry_over_db_unavailable",
            "refresh_mode": "fixture_fallback",
            "needs_db_rebuild": True,
            "after_row_count": len(carry_rows),
            "after_row_asset_ids_sample": _row_asset_ids(carry_rows)[:10],
            "blocking_reasons": [f"fetch_joined_failed:{err}"],
        }

    summary_row = dict(jx.get("summary_row") or {})
    joined_rows = list(jx.get("joined_rows") or [])
    _, new_rows = build_spectrum_rows(
        factor_name=factor_name,
        horizon_type=horizon_type,
        summary_row=summary_row,
        joined_rows=joined_rows,
        max_rows=max_rows,
    )

    if not new_rows:
        carry_rows = _mark_rows_stale(list(before_rows), now_iso=now_iso)
        srh[horizon] = carry_rows
        bundle_dict["spectrum_rows_by_horizon"] = srh
        return {
            **result_common,
            "outcome": "carry_over_db_unavailable",
            "refresh_mode": "fixture_fallback",
            "needs_db_rebuild": True,
            "after_row_count": len(carry_rows),
            "after_row_asset_ids_sample": _row_asset_ids(carry_rows)[:10],
            "blocking_reasons": ["fetch_joined_ok_but_zero_rows_synthesized"],
        }

    srh[horizon] = [dict(r) for r in new_rows]
    bundle_dict["spectrum_rows_by_horizon"] = srh

    return {
        **result_common,
        "outcome": "recomputed",
        "refresh_mode": "full_recompute_from_validation",
        "needs_db_rebuild": False,
        "after_row_count": len(new_rows),
        "after_row_asset_ids_sample": _row_asset_ids(new_rows)[:10],
        "blocking_reasons": [],
    }
