"""Load Phase 46 bundle + ledger paths; reload and staleness."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_artifact_path(stored: str, repo_root: Path) -> Path | None:
    p = Path(stored)
    if p.is_file():
        return p
    cand = repo_root / "docs" / "operator_closeout" / p.name
    if cand.is_file():
        return cand
    return None


@dataclass
class CockpitRuntimeState:
    repo_root: Path
    phase46_bundle_path: Path
    alert_ledger_path: Path
    decision_ledger_path: Path
    bundle: dict[str, Any] = field(default_factory=dict)
    source_mtime_at_load: float = 0.0
    loaded_at_utc: str = ""

    @classmethod
    def from_paths(
        cls,
        *,
        repo_root: Path,
        phase46_bundle_path: Path,
        alert_ledger_path: Path | None = None,
        decision_ledger_path: Path | None = None,
    ) -> CockpitRuntimeState:
        ap = alert_ledger_path or (repo_root / "data" / "product_surface" / "alert_ledger_v1.json")
        dp = decision_ledger_path or (repo_root / "data" / "product_surface" / "decision_trace_ledger_v1.json")
        st = cls(
            repo_root=repo_root,
            phase46_bundle_path=phase46_bundle_path,
            alert_ledger_path=ap,
            decision_ledger_path=dp,
        )
        st.reload_bundle()
        return st

    def reload_bundle(self) -> dict[str, Any]:
        raw = self.phase46_bundle_path.read_text(encoding="utf-8")
        self.bundle = dict(json.loads(raw))
        self.source_mtime_at_load = self.phase46_bundle_path.stat().st_mtime
        self.loaded_at_utc = datetime.now(timezone.utc).isoformat()
        p = self.bundle.get("alert_ledger_path")
        d = self.bundle.get("decision_trace_ledger_path")
        if isinstance(p, str):
            rp = resolve_artifact_path(p, self.repo_root)
            if rp:
                self.alert_ledger_path = rp
        if isinstance(d, str):
            rd = resolve_artifact_path(d, self.repo_root)
            if rd:
                self.decision_ledger_path = rd
        return self.bundle

    def is_bundle_stale(self) -> bool:
        if not self.phase46_bundle_path.is_file():
            return True
        return self.phase46_bundle_path.stat().st_mtime > self.source_mtime_at_load + 1e-6

    def meta(self) -> dict[str, Any]:
        b = self.bundle
        return {
            "phase46_generated_utc": b.get("generated_utc"),
            "runtime_loaded_at_utc": self.loaded_at_utc,
            "bundle_stale": self.is_bundle_stale(),
            "phase46_bundle_path": str(self.phase46_bundle_path.resolve()),
            "alert_ledger_path": str(self.alert_ledger_path.resolve()),
            "decision_ledger_path": str(self.decision_ledger_path.resolve()),
            "phase": b.get("phase"),
            "bundle_ok": b.get("ok"),
        }
