"""Phase 53: signed HMAC, replay guard, dead-letter, health parity, legacy ingest gate."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState

from phase51_runtime.runtime_health import build_runtime_health_summary
from phase52_runtime.governed_ingress import process_governed_external_ingest
from phase52_runtime.source_registry import save_source_registry
from phase52_runtime.webhook_auth import hash_shared_secret

from phase53_runtime.key_rotation import signing_keys_for_verification, source_requires_signed_ingress
from phase53_runtime.orchestrator import run_phase53_signed_payload_hmac_smoke
from phase53_runtime.replay_guard import try_register_nonce
from phase53_runtime.signed_auth import canonical_signing_string, compute_hmac_hex, verify_signed_request


def _bundle() -> dict:
    return {
        "ok": True,
        "phase": "phase46_founder_decision_cockpit",
        "generated_utc": "2026-01-01T00:00:00+00:00",
        "founder_read_model": {"asset_id": "x"},
        "cockpit_state": {"cohort_aggregate": {"decision_card": {}}},
    }


def test_source_requires_signed_ingress() -> None:
    s1 = {"signed_ingress_required": True}
    assert source_requires_signed_ingress(s1)
    s2 = {"signing_keys": [{"key_id": "a", "secret_hash": "ab" * 32, "status": "active"}]}
    assert source_requires_signed_ingress(s2)
    s3 = {"shared_secret_hash": hash_shared_secret("x")}
    assert not source_requires_signed_ingress(s3)


def test_signing_keys_retired_excluded_without_grace(tmp_path: Path) -> None:
    src = {
        "active_signing_key_id": "k2",
        "accept_previous_key_until": None,
        "signing_keys": [
            {"key_id": "k1", "secret_hash": hash_shared_secret("old"), "status": "retired", "created_at": "2020-01-01"},
            {"key_id": "k2", "secret_hash": hash_shared_secret("new"), "status": "active", "created_at": "2026-01-01"},
        ],
    }
    keys = signing_keys_for_verification(src, now=datetime.now(timezone.utc))
    assert [k["key_id"] for k in keys] == ["k2"]


def test_replay_guard_blocks_duplicate_nonce(tmp_path: Path) -> None:
    p = tmp_path / "rg.json"
    p.write_text('{"schema_version":1,"entries":[]}', encoding="utf-8")
    now = datetime.now(timezone.utc)
    a, _ = try_register_nonce(p, source_id="s", nonce="n1", signature_digest="d1", now=now)
    b, r2 = try_register_nonce(p, source_id="s", nonce="n1", signature_digest="d2", now=now)
    assert a
    assert not b and r2 == "nonce_replay"


def test_signed_verify_good_and_bad(tmp_path: Path) -> None:
    sec = "sign-secret-xyz"
    src = {
        "signed_ingress_required": True,
        "active_signing_key_id": "k1",
        "signing_keys": [
            {"key_id": "k1", "secret_hash": hash_shared_secret(sec), "status": "active", "created_at": "2026-01-01"},
        ],
    }
    body = b'{"a":1}'
    now = datetime.now(timezone.utc)
    ts = now.isoformat().replace("+00:00", "Z")
    nonce = "nonce-one"
    canon = canonical_signing_string(timestamp=ts, nonce=nonce, source_id="src1", raw_body=body)
    sig = compute_hmac_hex(sec, canon)
    ok, reason, kid = verify_signed_request(
        src,
        raw_body=body,
        source_id="src1",
        timestamp_header=ts,
        signature_header=sig,
        nonce_header=nonce,
        presented_plain_secret=sec,
        now=now,
    )
    assert ok and kid == "k1"
    bad, r2, _ = verify_signed_request(
        src,
        raw_body=body,
        source_id="src1",
        timestamp_header=ts,
        signature_header="0" * 64,
        nonce_header=nonce,
        presented_plain_secret=sec,
        now=now,
    )
    assert not bad and r2 == "bad_signature"


def test_stale_timestamp_rejected(tmp_path: Path) -> None:
    sec = "sign-secret-stale"
    src = {
        "signed_ingress_required": True,
        "active_signing_key_id": "k1",
        "signing_keys": [
            {"key_id": "k1", "secret_hash": hash_shared_secret(sec), "status": "active", "created_at": "2026-01-01"},
        ],
    }
    body = b"{}"
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    nonce = "n-stale"
    canon = canonical_signing_string(timestamp=old, nonce=nonce, source_id="s", raw_body=body)
    sig = compute_hmac_hex(sec, canon)
    ok, reason, _ = verify_signed_request(
        src,
        raw_body=body,
        source_id="s",
        timestamp_header=old,
        signature_header=sig,
        nonce_header=nonce,
        presented_plain_secret=sec,
        now=now,
    )
    assert not ok and reason == "stale_timestamp"


def test_health_merge_parity_isolated_registry(tmp_path: Path) -> None:
    root = tmp_path
    dr = root / "data" / "research_runtime"
    dr.mkdir(parents=True, exist_ok=True)
    iso = dr / "iso_registry.json"
    iso.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_name": "iso",
                        "source_type": "webhook",
                        "source_id": "iso1",
                        "enabled": True,
                        "shared_secret_hash": hash_shared_secret("z"),
                        "allowed_raw_event_types": ["watchlist_submit"],
                        "normalized_trigger_allowlist": ["manual_watchlist"],
                        "rate_limit_per_minute": 99,
                        "max_events_per_window": 99,
                        "window_seconds": 3600,
                        "queue_mode": "direct",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ing = dr / "ing.json"
    ing.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    bud = dr / "external_source_budget_state_v1.json"
    bud.write_text(json.dumps({"schema_version": 1, "by_source_id": {}}), encoding="utf-8")
    q = dr / "external_event_queue_v1.json"
    q.write_text(json.dumps({"schema_version": 1, "max_depth": 500, "items": []}), encoding="utf-8")
    dl = dr / "dl.json"
    dl.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    rg = dr / "rg.json"
    rg.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    h = build_runtime_health_summary(
        repo_root=root,
        ingest_registry_path=ing,
        external_source_registry_path=iso,
        external_budget_state_path=bud,
        external_event_queue_path=q,
        dead_letter_path=dl,
        replay_guard_path=rg,
    )
    assert h.get("external_source_activity_v52") is not None
    assert h["external_source_activity_v52"].get("registry_path")
    assert (h.get("external_ingress_phase53") or {}).get("signed_ingress_configured") is False


def test_legacy_external_ingest_disabled_by_default(tmp_path: Path) -> None:
    bpath = tmp_path / "b46.json"
    bpath.write_text(json.dumps(_bundle()), encoding="utf-8")
    ap = tmp_path / "a.json"
    dp = tmp_path / "d.json"
    ap.write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    dp.write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    st = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)
    ev = {
        "source_type": "file_drop",
        "source_id": "legacy",
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": "a"},
        "payload": {"note": "n"},
    }
    raw = json.dumps(ev).encode("utf-8")
    code, obj = dispatch_json(st, method="POST", path="/api/runtime/external-ingest", body=raw)
    assert code == 403
    assert obj.get("error") == "legacy_external_ingest_disabled"


def test_governed_signed_ingress_end_to_end(tmp_path: Path) -> None:
    sec = "e2e-sign-secret"
    src_reg = tmp_path / "src_reg.json"
    save_source_registry(
        src_reg,
        {
            "schema_version": 1,
            "sources": [
                {
                    "source_name": "e2e",
                    "source_type": "webhook",
                    "source_id": "e2e_src",
                    "enabled": True,
                    "signed_ingress_required": True,
                    "active_signing_key_id": "k1",
                    "signing_keys": [
                        {"key_id": "k1", "secret_hash": hash_shared_secret(sec), "status": "active", "created_at": "2026-01-01"},
                    ],
                    "allowed_raw_event_types": ["watchlist_submit"],
                    "normalized_trigger_allowlist": ["manual_watchlist"],
                    "rate_limit_per_minute": 50,
                    "max_events_per_window": 500,
                    "window_seconds": 3600,
                    "queue_mode": "direct",
                }
            ],
        },
    )
    bud = tmp_path / "bud.json"
    bud.write_text(json.dumps({"schema_version": 1, "by_source_id": {}}), encoding="utf-8")
    q = tmp_path / "q.json"
    q.write_text(json.dumps({"schema_version": 1, "max_depth": 500, "items": []}), encoding="utf-8")
    ing = tmp_path / "ing.json"
    ing.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    aud = tmp_path / "aud.json"
    aud.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    cp = tmp_path / "cp.json"
    cp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "enabled": True,
                "maintenance_mode": False,
                "max_cycles_per_window": 10,
                "window_seconds": 3600,
                "disabled_trigger_types": [],
                "allowed_trigger_types": ["manual_watchlist"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    dl = tmp_path / "dl.json"
    dl.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
    rg = tmp_path / "rg.json"
    rg.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")

    body = {
        "source_type": "webhook",
        "source_id": "e2e_src",
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": "a1"},
        "payload": {"note": "e2e", "suggested_job_type": "debate.execute"},
    }
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    now = datetime.now(timezone.utc)
    ts = now.isoformat().replace("+00:00", "Z")
    nonce = "e2e-nonce-1"
    canon = canonical_signing_string(timestamp=ts, nonce=nonce, source_id="e2e_src", raw_body=raw)
    hdr = {"X-Webhook-Timestamp": ts, "X-Webhook-Nonce": nonce, "X-Webhook-Signature": compute_hmac_hex(sec, canon)}
    out = process_governed_external_ingest(
        body,
        source_id_header="e2e_src",
        webhook_secret=sec,
        repo_root=tmp_path,
        source_registry_path=src_reg,
        budget_state_path=bud,
        queue_path=q,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp,
        raw_body=raw,
        http_headers=hdr,
        replay_guard_path=rg,
        dead_letter_path=dl,
    )
    assert out.get("ok")
    assert (out.get("registry_entry") or {}).get("status") == "accepted"


def test_phase53_smoke_bundle(tmp_path: Path) -> None:
    p52 = Path(__file__).resolve().parents[2] / "docs/operator_closeout/phase52_webhook_auth_routing_bundle.json"
    if not p52.is_file():
        import pytest

        pytest.skip("phase52 bundle missing")
    out = run_phase53_signed_payload_hmac_smoke(input_phase52_bundle_path=str(p52), repo_root=tmp_path)
    assert out.get("smoke_metrics_ok")
    for k in (
        "ok",
        "phase",
        "generated_utc",
        "input_phase52_bundle_path",
        "signed_ingress_enabled",
        "signature_failures_recorded",
        "replay_attempts_blocked",
        "sources_with_rotation_enabled",
        "dead_letter_counts",
        "dead_letter_replay_summary",
        "runtime_health_summary",
        "legacy_ingest_status",
        "phase54",
    ):
        assert k in out
