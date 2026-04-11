"""Phase 31 클로즈아웃 번들에서 터치된 CIK·심볼 집합 로드."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_validation.metrics import norm_cik


def load_phase31_bundle(path: str) -> dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def phase31_downstream_unblocked_ciks(bundle: dict[str, Any]) -> list[str]:
    """검증 패널 빌드가 스킵되지 않은 하류 재시도 CIK(Phase 31 validation-unlock 근거)."""
    out: list[str] = []
    for pc in (bundle.get("downstream_substrate_retry") or {}).get("per_cik") or []:
        vp = pc.get("validation_panel") or {}
        if vp.get("skipped"):
            continue
        cik = str(pc.get("cik") or "").strip()
        if cik:
            out.append(cik)
    return out


def phase31_repaired_raw_ciks(bundle: dict[str, Any]) -> list[str]:
    """raw facts bridge에서 raw_present로 복구된 CIK."""
    out: list[str] = []
    seen: set[str] = set()
    for e in (bundle.get("raw_facts_backfill_repair") or {}).get(
        "repaired_to_raw_present"
    ) or []:
        cik = str(e.get("cik") or "").strip()
        nk = norm_cik(cik) if cik else ""
        if not nk or nk in seen:
            continue
        seen.add(nk)
        out.append(cik)
    return out


def phase31_touched_cik_list(bundle: dict[str, Any]) -> list[str]:
    """Phase 31에서 우선적으로 forward 타깃으로 삼을 CIK 순서(하류 성공 → raw 복구)."""
    primary = phase31_downstream_unblocked_ciks(bundle)
    if primary:
        return primary
    return phase31_repaired_raw_ciks(bundle)


def phase31_touched_norm_ciks(bundle: dict[str, Any]) -> set[str]:
    return {norm_cik(c) for c in phase31_touched_cik_list(bundle) if c}
