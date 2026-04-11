"""Phase 35 클로즈아웃 번들에서 Phase 34 동기화 후 joined 확정 23행 키 추출."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_validation.metrics import norm_cik, norm_signal_date


def load_phase35_bundle(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def natural_key_from_reference(ref: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        norm_cik(ref.get("cik")),
        str(ref.get("accession_no") or ""),
        str(ref.get("factor_version") or ""),
        norm_signal_date(ref.get("signal_available_date")),
    )


def newly_joined_references_from_phase35(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    fin = bundle.get("forward_validation_join_displacement_final") or {}
    rows = list(fin.get("rows") or [])
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for r in rows:
        if str(r.get("displacement_bucket") or "") != "included_in_joined_recipe_substrate":
            continue
        ref = r.get("reference_from_phase34")
        if not isinstance(ref, dict):
            continue
        k = natural_key_from_reference(ref)
        if not (k[0] and k[1] and k[2] and k[3]) or k in seen:
            continue
        seen.add(k)
        out.append(dict(ref))
    return out
