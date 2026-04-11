"""GIS raw_present_no_silver_facts: deterministic concept-map inspection only."""

from __future__ import annotations

from typing import Any

from phase31.silver_seam_repair import report_raw_present_no_silver_targets
from sec.facts.concept_map import map_source_concept, normalize_concept_key_for_mapping


def inspect_gis_raw_present_no_silver_deterministic(
    client: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    max_concepts_sample: int = 120,
) -> dict[str, Any]:
    prep = report_raw_present_no_silver_targets(
        client, universe_name=universe_name, panel_limit=panel_limit
    )
    targets = [
        t
        for t in (prep.get("targets") or [])
        if str(t.get("symbol") or "").upper() == "GIS"
    ]
    if not targets:
        return {
            "ok": True,
            "outcome": "no_gis_in_raw_present_no_silver_bucket",
            "blocked_reason": None,
        }
    row = dict(targets[0])
    cik = str(row.get("cik") or "").strip()
    if not cik:
        return {
            "ok": True,
            "outcome": "blocked",
            "blocked_reason": "empty_cik_on_target_row",
        }
    r = (
        client.table("raw_xbrl_facts")
        .select("concept")
        .eq("cik", cik)
        .limit(2000)
        .execute()
    )
    concepts = sorted(
        {str(x.get("concept") or "").strip() for x in (r.data or []) if x.get("concept")}
    )[:max_concepts_sample]

    unmapped_after_normalize: list[dict[str, Any]] = []
    for c in concepts:
        norm_k = normalize_concept_key_for_mapping(c)
        mapped, reason = map_source_concept(c)
        if mapped is None:
            unmapped_after_normalize.append(
                {"source_concept": c, "normalized_key": norm_k, "map_reason": reason}
            )

    if not unmapped_after_normalize:
        return {
            "ok": True,
            "cik": cik,
            "symbol": "GIS",
            "outcome": "all_sampled_concepts_map_or_empty_raw",
            "concepts_sampled": len(concepts),
            "blocked_reason": None,
            "note": "If classification stays raw_present_no_silver, check non-concept pipeline factors.",
        }

    return {
        "ok": True,
        "cik": cik,
        "symbol": "GIS",
        "outcome": "blocked_unmapped_concepts_remain_in_sample",
        "blocked_reason": "concept_map_misses_for_sampled_raw_concepts",
        "concepts_sampled": len(concepts),
        "unmapped_sample": unmapped_after_normalize[:40],
        "unmapped_count": len(unmapped_after_normalize),
    }
