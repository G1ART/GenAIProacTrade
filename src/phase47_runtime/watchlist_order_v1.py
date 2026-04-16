"""User watchlist display order — MVP Build Plan Stage 1 (spectrum: model order fixed; watch ids reorderable)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 1
_MAX_IDS = 80
_ID_RE = re.compile(r"^[A-Za-z0-9_.:\-]+$")


def watchlist_order_path(repo_root: Path) -> Path:
    return repo_root / "data" / "mvp" / "watchlist_order_v1.json"


def load_watchlist_order(repo_root: Path) -> list[str]:
    p = watchlist_order_path(repo_root)
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, dict):
        return []
    ids = raw.get("ordered_asset_ids")
    if not isinstance(ids, list):
        return []
    out: list[str] = []
    for x in ids:
        s = str(x).strip()
        if s and s not in out and _ID_RE.match(s) and len(s) <= 200:
            out.append(s)
        if len(out) >= _MAX_IDS:
            break
    return out


def save_watchlist_order(repo_root: Path, ordered_asset_ids: list[str]) -> None:
    p = watchlist_order_path(repo_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {"schema_version": _SCHEMA_VERSION, "ordered_asset_ids": ordered_asset_ids},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def merge_watchlist_display_order(bundle_ids: list[str], stored: list[str]) -> list[str]:
    """Apply saved order for ids still in bundle; append new bundle ids in bundle order."""
    if not stored:
        return list(bundle_ids)
    bundle_set = set(bundle_ids)
    front = [x for x in stored if x in bundle_set]
    tail = [x for x in bundle_ids if x not in front]
    return front + tail


def validate_full_reorder_payload(
    raw: Any,
    *,
    allowed_ordered: list[str],
) -> tuple[list[str] | None, str | None]:
    """POST must be an exact permutation of the current bundle-derived watch ids."""
    if not isinstance(raw, list):
        return None, "ordered_asset_ids_must_be_list"
    allowed_set = set(allowed_ordered)
    if not allowed_set:
        return None, "no_tracked_assets_in_bundle"
    if len(raw) != len(allowed_ordered):
        return None, "ordered_asset_ids_length_mismatch"
    seen: set[str] = set()
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if not s or not _ID_RE.match(s) or len(s) > 200:
            return None, "invalid_asset_id"
        if s not in allowed_set:
            return None, f"unknown_asset_id:{s}"
        if s in seen:
            return None, f"duplicate:{s}"
        seen.add(s)
        out.append(s)
    if seen != allowed_set:
        return None, "ordered_asset_ids_set_mismatch"
    return out, None
