"""Single JSON snapshot: substrate metrics + exclusions + rerun gates (Phase 25)."""

from __future__ import annotations

from typing import Any

from public_buildout.revalidation import build_revalidation_trigger
from public_depth.diagnostics import compute_substrate_coverage
from public_repair_iteration.resolver import resolve_program_id


def build_substrate_closure_snapshot(
    client: Any,
    *,
    universe_name: str,
    program_id: str | None = None,
    panel_limit: int = 8000,
) -> dict[str, Any]:
    metrics, exclusion_distribution = compute_substrate_coverage(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    trig: dict[str, Any]
    if program_id:
        trig = build_revalidation_trigger(client, program_id=program_id)
    else:
        trig = {"ok": False, "skipped": True, "reason": "program_id_not_provided"}

    return {
        "ok": True,
        "universe_name": universe_name,
        "program_id": program_id,
        "metrics": metrics,
        "exclusion_distribution": exclusion_distribution,
        "rerun_readiness": trig,
    }


def dominant_exclusion_counts(exclusion_distribution: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for k, v in (exclusion_distribution or {}).items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def resolve_program_id_for_universe(client: Any, *, universe_name: str) -> str | None:
    out = resolve_program_id(
        client, "latest", universe_name=universe_name.strip() or None
    )
    if not out.get("ok"):
        return None
    return str(out["program_id"])
