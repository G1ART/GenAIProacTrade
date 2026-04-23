"""AGH v1 Patch 9 — production / self-serve / scale closure surface tests.

This file covers the Patch 9 deliverables that are not already covered
by ``test_agh_v1_patch9_copy_no_leak.py``:

* A1 — ``brain_bundle_path()`` env>v2>v0 auto-detect with quick
  integrity gate, and ``brain_bundle_integrity_report_for_path`` fields.
* A2 — ``validate_active_registry_integrity(..., tier='production')``
  raises the four production checks (active/challenger consistency,
  spectrum rows per horizon, tier-metadata coherence, write-evidence
  coherence) that the sample/demo tier is allowed to relax.
* C·A — ``archive_packets_older_than`` / ``archive_jobs_older_than``
  copy-then-delete behaviour including dry-run and terminal-state
  gating for jobs. Uses a minimal in-memory stand-in for the Supabase
  client so the test runs offline.
* C·B — ``FixtureHarnessStore.list_packets`` new
  ``target_asset_id`` / ``target_horizon`` filters.
* C·C — spectrum build no longer pre-persists message snapshots; they
  are written only when the object-detail path is exercised.
* D1 — the bundle-tier chip has a degraded ``--fallback`` variant.
* D2 — primary vs. utility nav tier structural grouping.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _write_bundle(dst: Path, data: dict[str, Any]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data), encoding="utf-8")


_VALID_V2_SKELETON: dict[str, Any] = {
    "schema_version": 1,
    "artifacts": [],
    "promotion_gates": [],
    "registry_entries": [],
    "spectrum_rows_by_horizon": {},
}


# ---------------------------------------------------------------------------
# A1 — brain_bundle_path + integrity report
# ---------------------------------------------------------------------------


def test_a1_brain_bundle_path_env_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from metis_brain.bundle import brain_bundle_path

    override = tmp_path / "override_bundle.json"
    override.write_text("{}", encoding="utf-8")
    # Even when v2 exists with a valid structure, env override wins.
    _write_bundle(tmp_path / "data" / "mvp" / "metis_brain_bundle_v2.json", _VALID_V2_SKELETON)
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(override))

    resolved = brain_bundle_path(tmp_path)

    assert resolved == override


def test_a1_brain_bundle_path_picks_v2_when_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from metis_brain.bundle import brain_bundle_path

    monkeypatch.delenv("METIS_BRAIN_BUNDLE", raising=False)
    _write_bundle(tmp_path / "data" / "mvp" / "metis_brain_bundle_v2.json", _VALID_V2_SKELETON)

    resolved = brain_bundle_path(tmp_path)

    assert resolved.name == "metis_brain_bundle_v2.json"


def test_a1_brain_bundle_path_falls_back_when_v2_corrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metis_brain.bundle import brain_bundle_path

    monkeypatch.delenv("METIS_BRAIN_BUNDLE", raising=False)
    (tmp_path / "data" / "mvp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "mvp" / "metis_brain_bundle_v2.json").write_text(
        "{not: valid json", encoding="utf-8"
    )

    resolved = brain_bundle_path(tmp_path)

    # Must fall back to v0 — we never silently serve a structurally
    # broken v2 bundle.
    assert resolved.name == "metis_brain_bundle_v0.json"


def test_a1_brain_bundle_integrity_report_flags_v2_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metis_brain.bundle import brain_bundle_integrity_report_for_path

    monkeypatch.delenv("METIS_BRAIN_BUNDLE", raising=False)
    (tmp_path / "data" / "mvp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "mvp" / "metis_brain_bundle_v2.json").write_text(
        "not even json", encoding="utf-8"
    )

    rep = brain_bundle_integrity_report_for_path(tmp_path)

    assert rep["v2_exists"] is True
    assert rep["v2_quick_integrity_ok"] is False
    assert rep["v2_integrity_failed"] is True
    assert rep["fallback_to_v0"] is True
    assert rep["override_used"] is False


def test_a1_brain_bundle_integrity_report_clean_v2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metis_brain.bundle import brain_bundle_integrity_report_for_path

    monkeypatch.delenv("METIS_BRAIN_BUNDLE", raising=False)
    _write_bundle(tmp_path / "data" / "mvp" / "metis_brain_bundle_v2.json", _VALID_V2_SKELETON)

    rep = brain_bundle_integrity_report_for_path(tmp_path)

    assert rep["v2_integrity_failed"] is False
    assert rep["v2_quick_integrity_ok"] is True
    assert rep["fallback_to_v0"] is False


# ---------------------------------------------------------------------------
# A2 — production-tier integrity checks
# ---------------------------------------------------------------------------


def _load_current_sample_bundle() -> dict[str, Any]:
    """Reuse the in-repo sample bundle for schema-safe mutation in tests."""
    p = REPO_ROOT / "data" / "mvp" / "metis_brain_bundle_from_db_v0.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _minimal_active_bundle(*, production_shaped: bool) -> Any:
    """Build a BrainBundleV0 derived from the sample bundle, stamping the
    artifact fingerprints + metadata either production-shaped or
    demo-shaped so the ``tier='production'`` checks can tell them apart.
    """
    from metis_brain.bundle import BrainBundleV0

    raw = _load_current_sample_bundle()
    # Harmonise the minimum fields Patch 9 A2 inspects.
    raw["as_of_utc"] = "2026-04-20T00:00:00Z" if production_shaped else ""
    for art in raw.get("artifacts") or []:
        if production_shaped:
            art["validation_pointer"] = "pit:prod:run_abc"
            art["created_by"] = "supabase_r_branch_builder"
            art["feature_set"] = "prod_feature_set_v1"
        else:
            art["validation_pointer"] = "pit:demo:x"
            art["created_by"] = "deterministic_kernel"
            art["feature_set"] = "stub_feature_set"
    raw["metadata"] = (
        {
            "graduation_tier": "production",
            "graduated_at_utc": "2026-04-20T00:00:00Z",
            "built_at_utc": "2026-04-20T00:00:00Z",
            "source_run_ids": ["run_abc"],
        }
        if production_shaped
        else {}
    )
    return BrainBundleV0.model_validate(raw)


def test_a2_production_tier_clean_bundle_has_no_errors() -> None:
    from metis_brain.bundle import validate_active_registry_integrity

    bundle = _minimal_active_bundle(production_shaped=True)
    errs = validate_active_registry_integrity(bundle, tier="production")

    assert errs == [], errs


def test_a2_production_tier_rejects_demo_fingerprints() -> None:
    from metis_brain.bundle import validate_active_registry_integrity

    bundle = _minimal_active_bundle(production_shaped=False)
    errs = validate_active_registry_integrity(bundle, tier="production")

    # Demo-shaped artifacts should trip the "validation_pointer /
    # created_by / feature_set look like demo" production check.
    joined = "\n".join(errs)
    assert "pit:demo" in joined or "non-production" in joined
    # And as_of_utc was left empty on demo-shaped bundle — another
    # production hint we should have surfaced.
    assert any("as_of_utc" in e for e in errs)


def test_a2_sample_tier_does_not_raise_production_errors() -> None:
    from metis_brain.bundle import validate_active_registry_integrity

    # Same shape as the failing "production" case, but called without tier:
    # sample/demo tier must stay lenient (Patch 8 baseline semantics).
    bundle = _minimal_active_bundle(production_shaped=False)
    errs = validate_active_registry_integrity(bundle)

    joined = "\n".join(errs)
    assert "pit:demo" not in joined
    assert "production:" not in joined


def test_a2_production_rejects_self_challenger() -> None:
    from metis_brain.bundle import BrainBundleV0, validate_active_registry_integrity

    bundle = _minimal_active_bundle(production_shaped=True)
    # Mutate one active entry to challenge itself.
    raw = bundle.model_dump()
    raw["registry_entries"][0]["challenger_artifact_ids"] = [
        raw["registry_entries"][0]["active_artifact_id"]
    ]
    mutated = BrainBundleV0.model_validate(raw)

    errs = validate_active_registry_integrity(mutated, tier="production")

    assert any(
        "challenger_artifact_id equals active_artifact_id" in e for e in errs
    ), errs


# ---------------------------------------------------------------------------
# C·A — retention archive (packets + jobs)
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = list(data)


class _FakeTable:
    def __init__(self, client: "_FakeClient", name: str) -> None:
        self._client = client
        self._name = name
        self._mode = "select"
        self._rows_to_insert: list[dict[str, Any]] = []
        self._filters: list[tuple[str, str, Any]] = []
        self._limit: int | None = None

    def select(self, _cols: str = "*") -> "_FakeTable":
        self._mode = "select"
        return self

    def upsert(self, rows: Any, on_conflict: str = "") -> "_FakeTable":
        self._mode = "upsert"
        self._rows_to_insert = list(rows)
        self._on_conflict = on_conflict
        return self

    def delete(self) -> "_FakeTable":
        self._mode = "delete"
        return self

    def lt(self, col: str, value: Any) -> "_FakeTable":
        self._filters.append(("lt", col, value))
        return self

    def in_(self, col: str, values: Any) -> "_FakeTable":
        self._filters.append(("in", col, list(values)))
        return self

    def order(self, col: str, desc: bool = True) -> "_FakeTable":
        return self

    def limit(self, n: int) -> "_FakeTable":
        self._limit = int(n)
        return self

    def _apply_filters(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = rows
        for op, col, val in self._filters:
            if op == "lt":
                out = [r for r in out if str(r.get(col) or "") < str(val)]
            elif op == "in":
                s = set(str(v) for v in val)
                out = [r for r in out if str(r.get(col) or "") in s]
        return out

    def execute(self) -> _FakeResult:
        store = self._client.tables.setdefault(self._name, [])
        if self._mode == "select":
            out = self._apply_filters(store)
            out.sort(key=lambda r: str(r.get("created_at_utc") or r.get("enqueued_at_utc") or ""))
            if self._limit is not None:
                out = out[: self._limit]
            return _FakeResult(out)
        if self._mode == "upsert":
            key = self._on_conflict or "packet_id"
            by_id = {str(r.get(key) or ""): r for r in store}
            for row in self._rows_to_insert:
                by_id[str(row.get(key) or "")] = row
            self._client.tables[self._name] = list(by_id.values())
            return _FakeResult(list(self._rows_to_insert))
        if self._mode == "delete":
            keep = self._apply_filters(store)
            to_drop = {id(r) for r in keep}
            self._client.tables[self._name] = [r for r in store if id(r) not in to_drop]
            return _FakeResult(keep)
        raise AssertionError(f"unknown mode {self._mode}")


class _FakeClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(self, name)


def test_ca_archive_packets_copy_then_delete() -> None:
    from agentic_harness.retention.archive_v1 import archive_packets_older_than

    client = _FakeClient()
    client.tables["agentic_harness_packets_v1"] = [
        {"packet_id": "p_old", "created_at_utc": "2020-01-01T00:00:00Z", "status": "done"},
        {"packet_id": "p_new", "created_at_utc": "2099-01-01T00:00:00Z", "status": "done"},
    ]

    rep = archive_packets_older_than(client, days=30)

    assert rep.selected == 1
    assert rep.archived == 1
    assert rep.deleted == 1
    active_ids = [r["packet_id"] for r in client.tables["agentic_harness_packets_v1"]]
    archive_ids = [
        r["packet_id"] for r in client.tables.get("agentic_harness_packets_v1_archive", [])
    ]
    assert "p_old" not in active_ids
    assert "p_new" in active_ids
    assert "p_old" in archive_ids


def test_ca_archive_packets_dry_run_does_not_write() -> None:
    from agentic_harness.retention.archive_v1 import archive_packets_older_than

    client = _FakeClient()
    client.tables["agentic_harness_packets_v1"] = [
        {"packet_id": "p_old", "created_at_utc": "2020-01-01T00:00:00Z", "status": "done"},
    ]

    rep = archive_packets_older_than(client, days=30, dry_run=True)

    assert rep.dry_run is True
    assert rep.selected == 1
    assert rep.archived == 0
    assert rep.deleted == 0
    assert "agentic_harness_packets_v1_archive" not in client.tables


def test_ca_archive_jobs_only_terminal_statuses() -> None:
    from agentic_harness.retention.archive_v1 import archive_jobs_older_than

    client = _FakeClient()
    client.tables["agentic_harness_queue_jobs_v1"] = [
        {"job_id": "j1", "status": "done", "enqueued_at_utc": "2020-01-01T00:00:00Z"},
        {"job_id": "j2", "status": "enqueued", "enqueued_at_utc": "2020-01-01T00:00:00Z"},
        {"job_id": "j3", "status": "running", "enqueued_at_utc": "2020-01-01T00:00:00Z"},
        {"job_id": "j4", "status": "dlq", "enqueued_at_utc": "2020-01-01T00:00:00Z"},
    ]

    rep = archive_jobs_older_than(client, days=7)

    # Only terminal-status rows should have been archived; live jobs
    # (enqueued/running) stay in the active table.
    active_ids = sorted(r["job_id"] for r in client.tables["agentic_harness_queue_jobs_v1"])
    assert active_ids == ["j2", "j3"]
    archive_ids = sorted(
        r["job_id"] for r in client.tables.get("agentic_harness_queue_jobs_v1_archive", [])
    )
    assert archive_ids == ["j1", "j4"]
    assert rep.archived == 2
    assert rep.deleted == 2


# ---------------------------------------------------------------------------
# C·B — list_packets JSONB filters
# ---------------------------------------------------------------------------


@pytest.fixture
def _seeded_fixture_store() -> Iterator[Any]:
    from agentic_harness.store.fixture_store import FixtureHarnessStore

    store = FixtureHarnessStore()
    for i, row in enumerate(
        [
            {"asset_id": "AAPL", "horizon": "short"},
            {"asset_id": "AAPL", "horizon": "long"},
            {"asset_id": "MSFT", "horizon": "short"},
            {"asset_id": None, "horizon": "short"},
        ]
    ):
        store.upsert_packet(
            {
                "packet_id": f"p_{i}",
                "packet_type": "research_answer_v1",
                "packet_schema_version": 1,
                "target_layer": "layer5_orchestrator",
                "target_scope": row,
                "status": "done",
                "created_at_utc": f"2026-04-2{i}T00:00:00Z",
            }
        )
    yield store


def test_cb_list_packets_filters_by_target_asset_id(_seeded_fixture_store: Any) -> None:
    out = _seeded_fixture_store.list_packets(target_asset_id="AAPL")
    assert {str(r["packet_id"]) for r in out} == {"p_0", "p_1"}


def test_cb_list_packets_filters_by_target_horizon(_seeded_fixture_store: Any) -> None:
    out = _seeded_fixture_store.list_packets(target_horizon="short")
    assert {str(r["packet_id"]) for r in out} == {"p_0", "p_2", "p_3"}


def test_cb_list_packets_combined_filter(_seeded_fixture_store: Any) -> None:
    out = _seeded_fixture_store.list_packets(target_asset_id="AAPL", target_horizon="short")
    assert [r["packet_id"] for r in out] == ["p_0"]


def test_cb_list_packets_no_filter_returns_all(_seeded_fixture_store: Any) -> None:
    out = _seeded_fixture_store.list_packets()
    assert len(out) == 4


# ---------------------------------------------------------------------------
# C·C — snapshot lazy generation
# ---------------------------------------------------------------------------


def test_cc_spectrum_build_does_not_persist_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Today spectrum path must NOT write message snapshots — that work is
    deferred until an object detail is opened.
    """
    from phase47_runtime import today_spectrum as ts

    calls: list[tuple[str, dict[str, Any]]] = []

    def _fake_upsert(repo_root: Path, sid: str, rec: dict[str, Any]) -> None:
        calls.append((sid, rec))

    monkeypatch.setattr(ts, "upsert_message_snapshot", _fake_upsert)

    out = ts.build_today_spectrum_payload(
        repo_root=REPO_ROOT,
        horizon="short",
        lang="en",
    )

    assert out.get("ok") is True, out
    # Spectrum build should be snapshot-IO free in Patch 9.
    assert calls == []


def test_cc_persist_row_helper_writes_exactly_one_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from phase47_runtime import today_spectrum as ts

    calls: list[str] = []

    def _fake_upsert(repo_root: Path, sid: str, rec: dict[str, Any]) -> None:
        calls.append(sid)

    monkeypatch.setattr(ts, "upsert_message_snapshot", _fake_upsert)

    payload = ts.build_today_spectrum_payload(
        repo_root=REPO_ROOT,
        horizon="short",
        lang="en",
    )
    assert payload.get("ok") is True, payload
    rows = payload.get("rows") or []
    if not rows:
        pytest.skip("no spectrum rows in test environment; lazy-gen contract still holds")

    sid = ts.persist_message_snapshot_for_spectrum_row(REPO_ROOT, payload, rows[0])

    if sid is None:
        pytest.skip("row did not produce a snapshot pair (optional branch)")
    assert calls == [sid]


# ---------------------------------------------------------------------------
# D1 / D2 — structural nav + chip classes
# ---------------------------------------------------------------------------


INDEX_HTML = REPO_ROOT / "src" / "phase47_runtime" / "static" / "ops.html"


def test_d1_bundle_tier_chip_has_fallback_css_variant() -> None:
    src = INDEX_HTML.read_text(encoding="utf-8")
    assert ".tsr-chip--degraded" in src
    assert ".tsr-tier-chip--fallback" in src


def test_d2_nav_keeps_primary_and_utility_rows_with_all_features() -> None:
    src = INDEX_HTML.read_text(encoding="utf-8")
    # Primary tier must still expose the 5 canonical actions.
    for dp in ("home", "watchlist", "research", "replay", "ask_ai"):
        assert f'data-panel="{dp}"' in src
    # Utility tier must still expose Journal, Advanced, Reload — no
    # Patch 9 feature removal.
    assert 'data-panel="journal"' in src
    assert 'data-panel="advanced"' in src
    assert 'id="btn-reload"' in src
    # Utility row is structurally nested under the push-back CSS class.
    assert 'class="nav-row nav-utility"' in src
