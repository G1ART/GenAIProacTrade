"""Phase 27.5: 수리 연쇄 후 리뷰·번들 재생성(review-only 명령과 구분)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from targeted_backfill.market_metadata_gaps import run_market_metadata_hydration_repair
from targeted_backfill.review import build_phase27_evidence_bundle, write_phase27_targeted_backfill_review_md
from targeted_backfill.validation_registry import run_validation_registry_repair


def run_targeted_backfill_repair_and_review(
    settings: Any,
    *,
    universe_name: str,
    panel_limit: int = 8000,
    program_id_raw: str | None = None,
    review_out: str = "docs/operator_closeout/phase27_targeted_backfill_review.md",
    bundle_out: str | None = None,
    repair_forward: bool = False,
    price_lookahead_days: int = 400,
) -> dict[str, Any]:
    """
    1) registry repair → 2) metadata hydration → 3) 선택 forward backfill → 4) 리뷰·번들.
    """
    from db.client import get_supabase_client
    from substrate_closure.repair import run_forward_return_backfill_repair

    reg_out = run_validation_registry_repair(
        settings, universe_name=universe_name, panel_limit=panel_limit
    )
    meta_out = run_market_metadata_hydration_repair(
        settings,
        universe_name=universe_name,
        panel_limit=panel_limit,
        price_lookahead_days=price_lookahead_days,
    )
    fwd_out: dict[str, Any] = {"skipped": True, "reason": "repair_forward_false"}
    if repair_forward:
        fwd_out = run_forward_return_backfill_repair(
            settings,
            universe_name=universe_name,
            panel_limit=panel_limit,
        )

    client = get_supabase_client(settings)
    bundle = build_phase27_evidence_bundle(
        client,
        universe_name=universe_name,
        panel_limit=panel_limit,
        program_id_raw=program_id_raw,
    )
    bundle["repair_closeout"] = {
        "validation_registry_repair": reg_out,
        "market_metadata_hydration": meta_out,
        "forward_backfill": fwd_out,
    }
    outp = write_phase27_targeted_backfill_review_md(path=review_out, bundle=bundle)
    bundle_path = None
    bo = (bundle_out or "").strip()
    if bo:
        import json

        bp = Path(bo).expanduser()
        bp.parent.mkdir(parents=True, exist_ok=True)
        bp.write_text(
            json.dumps(bundle, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        bundle_path = str(bp)

    return {
        "ok": True,
        "command": "run_targeted_backfill_repair_and_review",
        "review_md": str(outp),
        "bundle_out": bundle_path,
        "repair_closeout": bundle["repair_closeout"],
        "phase28": bundle.get("phase28"),
    }
