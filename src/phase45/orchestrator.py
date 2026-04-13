"""Assemble Phase 45 canonical closeout bundle (no DB, no substrate work)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase45.authoritative_resolver import resolve_authoritative_recommendation
from phase45.closeout_package import build_canonical_closeout
from phase45.phase46_recommend import recommend_phase46
from phase45.reopen_protocol import build_current_closeout_status, build_future_reopen_protocol


def _read_json(path: str) -> dict[str, Any]:
    import json

    return dict(json.loads(Path(path).read_text(encoding="utf-8")))


def run_phase45_operator_closeout_and_reopen_protocol(
    *,
    phase44_bundle_in: str,
    phase43_bundle_in: str,
    operator_registered_new_named_source: bool = False,
) -> dict[str, Any]:
    p44 = _read_json(phase44_bundle_in)
    p43 = _read_json(phase43_bundle_in)

    authoritative_resolution = resolve_authoritative_recommendation(
        phase43_bundle=p43,
        phase44_bundle=p44,
    )
    future_reopen_protocol = build_future_reopen_protocol(phase44_bundle=p44)
    current_closeout_status = build_current_closeout_status(
        authoritative_resolution=authoritative_resolution
    )
    canonical_closeout = build_canonical_closeout(
        phase43_bundle=p43,
        phase44_bundle=p44,
        authoritative_resolution=authoritative_resolution,
        future_reopen_protocol=future_reopen_protocol,
    )
    phase46 = recommend_phase46(
        operator_registered_new_named_source=operator_registered_new_named_source
    )

    gen = datetime.now(timezone.utc).isoformat()

    return {
        "ok": True,
        "phase": "phase45_operator_closeout_and_reopen_protocol",
        "generated_utc": gen,
        "input_phase44_bundle_path": str(Path(phase44_bundle_in).resolve()),
        "input_phase43_bundle_path": str(Path(phase43_bundle_in).resolve()),
        "authoritative_resolution": authoritative_resolution,
        "canonical_closeout": canonical_closeout,
        "future_reopen_protocol": future_reopen_protocol,
        "current_closeout_status": current_closeout_status,
        "phase46": phase46,
    }
