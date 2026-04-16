"""Replay lineage join v1 — message snapshot id + seed-side lineage stub (Patch Bundle C / Product Spec §5.3, §6.3)."""

from __future__ import annotations

import hashlib

# Today 시드·미연결 결정이 레지스트리 lineage 없이도 스키마를 깨지 않도록 하는 스텁.
SEED_REPLAY_LINEAGE_POINTER = "seed:replay_lineage_v0"


def message_snapshot_id_v1(
    *,
    message_id: str,
    registry_entry_id: str,
    artifact_id: str,
    horizon: str,
    asset_id: str,
    as_of_utc: str,
) -> str:
    """Deterministic id for a message row at a point in time (pointer, not full blob storage)."""
    parts = [
        str(message_id or "").strip(),
        str(registry_entry_id or "").strip(),
        str(artifact_id or "").strip(),
        str(horizon or "").strip(),
        str(asset_id or "").strip(),
        str(as_of_utc or "").strip(),
    ]
    payload = "\n".join(parts)
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"msg_snap:v1:{h}"
