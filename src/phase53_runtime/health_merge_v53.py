"""Phase 53: extend runtime health summary with dead-letter, replay guard, signed-ingress flags."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase53_runtime.dead_letter_registry import dead_letter_counts_by_stage, default_dead_letter_path, load_dead_letter
from phase53_runtime.replay_guard import default_replay_guard_path, replay_guard_count


def merge_phase53_into_summary(
    summary: dict[str, Any],
    repo_root: Path,
    *,
    source_registry_path: Path | None = None,
    dead_letter_path: Path | None = None,
    replay_guard_path: Path | None = None,
) -> None:
    from phase52_runtime.source_registry import default_external_source_registry_path, load_source_registry

    reg_p = source_registry_path or default_external_source_registry_path(repo_root)
    dlp = dead_letter_path or default_dead_letter_path(repo_root)
    rgp = replay_guard_path or default_replay_guard_path(repo_root)

    reg = load_source_registry(reg_p) if reg_p.is_file() else {"sources": []}
    signed_any = False
    rotation_sources = 0
    for s in reg.get("sources") or []:
        if bool(s.get("signed_ingress_required")) or bool(s.get("signing_keys")):
            signed_any = True
        if s.get("signing_keys"):
            rotation_sources += 1

    dl_total = len(load_dead_letter(dlp).get("entries") or [])
    dl_by_stage = dead_letter_counts_by_stage(dlp)
    replay_entries = replay_guard_count(rgp)

    summary["external_ingress_phase53"] = {
        "signed_ingress_configured": signed_any,
        "sources_with_rotation_keys": rotation_sources,
        "dead_letter_total_entries": dl_total,
        "dead_letter_by_failure_stage": dl_by_stage,
        "replay_guard_active_entries": replay_entries,
        "registry_path_used": str(reg_p),
    }
