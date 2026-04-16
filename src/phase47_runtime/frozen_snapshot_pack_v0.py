"""Stage 5 stub — frozen snapshot pack manifest (Build Plan §8.2 item 4, Product Spec §8.1 item 14)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def frozen_snapshot_pack_path(repo_root: Path) -> Path:
    return repo_root / "data" / "mvp" / "frozen_snapshot_pack_v0.json"


def load_frozen_snapshot_pack_v0(repo_root: Path, *, lang: str) -> dict[str, Any]:
    """Load demo freeze manifest; resolve investor step labels for current locale."""
    from phase47_runtime.phase47e_user_locale import normalize_lang, t

    lg = normalize_lang(lang)
    p = frozen_snapshot_pack_path(repo_root)
    if not p.is_file():
        return {
            "ok": False,
            "error": "frozen_snapshot_pack_missing",
            "hint": str(p),
            "contract": "FROZEN_SNAPSHOT_PACK_V0",
        }
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "error": "frozen_snapshot_pack_invalid_json", "contract": "FROZEN_SNAPSHOT_PACK_V0"}
    if not isinstance(raw, dict):
        return {"ok": False, "error": "frozen_snapshot_pack_not_object", "contract": "FROZEN_SNAPSHOT_PACK_V0"}
    if int(raw.get("schema_version") or 0) < 1:
        return {"ok": False, "error": "frozen_snapshot_pack_bad_schema", "contract": "FROZEN_SNAPSHOT_PACK_V0"}

    steps_in = raw.get("investor_demo_steps") or []
    steps_out: list[dict[str, Any]] = []
    if isinstance(steps_in, list):
        for i, s in enumerate(steps_in):
            if not isinstance(s, dict):
                continue
            lk = str(s.get("label_key") or "").strip()
            steps_out.append(
                {
                    "id": str(s.get("id") or f"step_{i}"),
                    "order": i + 1,
                    "label": t(lg, lk) if lk else "",
                }
            )

    pod = raw.get("price_overlay_demo")
    price_overlay = pod if isinstance(pod, dict) else {}

    return {
        "ok": True,
        "contract": "FROZEN_SNAPSHOT_PACK_V0",
        "lang": lg,
        "pack": raw,
        "investor_demo_steps_resolved": steps_out,
        "price_overlay_demo": price_overlay,
    }
