"""AGH v1 Patch 4 — ``harness-evaluate-promotions`` CLI + governance_scan cadence tests.

We exercise only the fixture-store paths so the tests stay hermetic:

    * CLI --dry-run: full pipeline runs but no packets are persisted and the
      brain bundle is not mutated. Stdout contains a single JSON blob with
      ``dry_run=True`` and ``result.outcome='proposal_emitted'``.
    * CLI normal: evaluator emits a RegistryUpdateProposalV1 +
      ValidationPromotionEvaluationV1 and a governance_queue job is enqueued.
    * governance_scan cadence: without a spec provider -> honest skip. With
      a provider returning one spec -> evaluator is invoked exactly once and
      the tick summary carries ``by_outcome={'proposal_emitted': 1}``.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from agentic_harness.agents.layer4_promotion_evaluator_v1 import (
    derive_artifact_id,
    propose_governance_scan_cadence,
    set_governance_scan_client_factory,
    set_governance_scan_spec_provider,
)
from agentic_harness.store import FixtureHarnessStore

# Reuse bundle-building helpers from the evaluator test module.
from tests.test_layer4_promotion_evaluator_v1 import (  # type: ignore[import-not-found]
    _promote_summary_row,
    _quantiles_promote,
    _write_bundle,
)


@pytest.fixture(autouse=True)
def _reset_governance_scan_providers():
    set_governance_scan_spec_provider(None)
    set_governance_scan_client_factory(None)
    yield
    set_governance_scan_spec_provider(None)
    set_governance_scan_client_factory(None)


@pytest.fixture
def bundle_env(tmp_path, monkeypatch):
    p = tmp_path / "metis_brain_bundle_v0.json"
    _write_bundle(p)
    monkeypatch.setenv("METIS_BRAIN_BUNDLE", str(p))
    monkeypatch.setenv("METIS_REPO_ROOT", str(tmp_path))
    return p


def _spec() -> dict:
    return {
        "registry_entry_id": "reg_short_demo_v0",
        "horizon": "short",
        "factor_name": "demo_factor",
        "universe_name": "large_cap_research_slice_demo_v0",
        "horizon_type": "next_month",
        "return_basis": "raw",
    }


def _install_promote_fetchers(monkeypatch):
    """Patch the evaluator's default fetchers with promote-shaped data."""
    import agentic_harness.agents.layer4_promotion_evaluator_v1 as ev

    def _fetch_summary(client, spec):
        return "run_cli_1", [
            _promote_summary_row(run_id="run_cli_1", basis=spec.get("return_basis") or "raw"),
        ]

    def _fetch_quant(client, spec):
        return _quantiles_promote()

    monkeypatch.setattr(ev, "_default_fetch_validation_summary", _fetch_summary)
    monkeypatch.setattr(ev, "_default_fetch_quantiles", _fetch_quant)


def test_cli_dry_run_does_not_persist(bundle_env, monkeypatch):
    _install_promote_fetchers(monkeypatch)

    from agentic_harness.store import FixtureHarnessStore
    import agentic_harness.runtime as rt

    store = FixtureHarnessStore()
    monkeypatch.setattr(rt, "build_store", lambda use_fixture=False: store)

    import main as cli  # noqa: WPS433

    class _Args:
        registry_entry = "reg_short_demo_v0"
        horizon = "short"
        factor = "demo_factor"
        universe = "large_cap_research_slice_demo_v0"
        horizon_type = "next_month"
        return_basis = "raw"
        spec_file = ""
        dry_run = True
        use_fixture = True

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli._cmd_harness_evaluate_promotions(_Args())
    assert rc == 0
    out = json.loads(buf.getvalue())
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["result"]["outcome"] == "proposal_emitted"
    # No packets persisted in dry run.
    assert store.list_packets(packet_type="RegistryUpdateProposalV1") == []
    assert store.list_packets(packet_type="ValidationPromotionEvaluationV1") == []


def test_cli_emits_proposal_and_evaluation(bundle_env, monkeypatch):
    _install_promote_fetchers(monkeypatch)

    from agentic_harness.store import FixtureHarnessStore
    import agentic_harness.runtime as rt

    store = FixtureHarnessStore()
    monkeypatch.setattr(rt, "build_store", lambda use_fixture=False: store)

    import main as cli  # noqa: WPS433

    class _Args:
        registry_entry = "reg_short_demo_v0"
        horizon = "short"
        factor = "demo_factor"
        universe = "large_cap_research_slice_demo_v0"
        horizon_type = "next_month"
        return_basis = "raw"
        spec_file = ""
        dry_run = False
        use_fixture = True

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli._cmd_harness_evaluate_promotions(_Args())
    assert rc == 0
    out = json.loads(buf.getvalue())
    assert out["ok"] is True
    assert out["dry_run"] is False
    assert out["result"]["outcome"] == "proposal_emitted"

    proposals = store.list_packets(packet_type="RegistryUpdateProposalV1")
    assert len(proposals) == 1
    evals = store.list_packets(packet_type="ValidationPromotionEvaluationV1")
    assert len(evals) == 1

    jobs = store.list_jobs(queue_class="governance_queue")
    assert any(
        str(j.get("packet_id") or "") == proposals[0]["packet_id"] for j in jobs
    )


def test_governance_scan_tick_honest_skip_without_provider(bundle_env):
    store = FixtureHarnessStore()
    res = propose_governance_scan_cadence(store, "2026-04-19T10:00:00+00:00")
    assert res["skipped"] is True
    assert res["reason"] == "no_governance_scan_spec_provider"
    assert store.list_packets(packet_type="ValidationPromotionEvaluationV1") == []


def test_governance_scan_tick_runs_evaluator_once_per_spec(bundle_env, monkeypatch):
    _install_promote_fetchers(monkeypatch)

    store = FixtureHarnessStore()

    def _provider(store_, now_iso):
        return [_spec()]

    set_governance_scan_spec_provider(_provider)

    res = propose_governance_scan_cadence(store, "2026-04-19T10:00:00+00:00")

    assert res["scans"] == 1
    assert res["by_outcome"].get("proposal_emitted") == 1
    assert len(res["emitted_proposal_packet_ids"]) == 1
    # Evaluator side effects are visible in the store.
    assert store.list_packets(packet_type="RegistryUpdateProposalV1")
    assert store.list_packets(packet_type="ValidationPromotionEvaluationV1")
