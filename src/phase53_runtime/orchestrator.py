"""Phase 53 authoritative smoke: signed HMAC, replay guard, dead-letter, health parity."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from phase52_runtime.governed_ingress import process_governed_external_ingest
from phase52_runtime.source_registry import save_source_registry
from phase52_runtime.webhook_auth import hash_shared_secret

from phase51_runtime.runtime_health import build_runtime_health_summary

from phase53_runtime.dead_letter_registry import load_dead_letter
from phase53_runtime.phase54_recommend import recommend_phase54
from phase53_runtime.signed_auth import canonical_signing_string, compute_hmac_hex


def _signed_headers(*, body: dict[str, Any], source_id: str, secret: str, nonce: str, ts: datetime) -> dict[str, str]:
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ts_s = ts.isoformat().replace("+00:00", "Z")
    canon = canonical_signing_string(timestamp=ts_s, nonce=nonce, source_id=source_id, raw_body=raw)
    sig = compute_hmac_hex(secret, canon)
    return {
        "X-Webhook-Timestamp": ts_s,
        "X-Webhook-Nonce": nonce,
        "X-Webhook-Signature": sig,
    }


def run_phase53_signed_payload_hmac_smoke(
    *,
    input_phase52_bundle_path: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    p52 = Path(input_phase52_bundle_path)
    if not p52.is_absolute():
        p52 = (root / p52).resolve()

    data_rt = root / "data" / "research_runtime"
    data_rt.mkdir(parents=True, exist_ok=True)
    src_reg = data_rt / "phase53_smoke_source_registry_v1.json"
    bud = data_rt / "phase53_smoke_budget_v1.json"
    q = data_rt / "phase53_smoke_queue_v1.json"
    ing = data_rt / "phase53_smoke_ingest_v1.json"
    aud = data_rt / "phase53_smoke_audit_v1.json"
    cp = data_rt / "phase53_smoke_control_plane_v1.json"
    dl = data_rt / "phase53_smoke_dead_letter_v1.json"
    rg = data_rt / "phase53_smoke_replay_guard_v1.json"

    sign_secret = "phase53-signing-secret-alpha"
    key_id = "k_active_v1"
    body_base = {
        "source_type": "webhook",
        "source_id": "s53_signed",
        "raw_event_type": "watchlist_submit",
        "asset_scope": {"asset_id": "phase53_asset"},
        "payload": {"note": "signed-smoke", "suggested_job_type": "debate.execute"},
    }

    src = {
        "source_name": "signed_smoke",
        "source_type": "webhook",
        "source_id": "s53_signed",
        "enabled": True,
        "signed_ingress_required": True,
        "active_signing_key_id": key_id,
        "signing_keys": [
            {
                "key_id": key_id,
                "secret_hash": hash_shared_secret(sign_secret),
                "status": "active",
                "created_at": "2026-04-14T00:00:00+00:00",
            },
            {
                "key_id": "k_retired_v0",
                "secret_hash": hash_shared_secret("old-secret-retired"),
                "status": "retired",
                "created_at": "2025-01-01T00:00:00+00:00",
            },
        ],
        "allowed_raw_event_types": ["watchlist_submit"],
        "normalized_trigger_allowlist": ["manual_watchlist"],
        "rate_limit_per_minute": 200,
        "max_events_per_window": 500,
        "window_seconds": 3600,
        "queue_mode": "direct",
        "notes": "phase53 smoke signed-only",
    }

    save_source_registry(src_reg, {"schema_version": 1, "sources": [src]})
    bud.write_text(json.dumps({"schema_version": 1, "by_source_id": {}}, indent=2, ensure_ascii=False), encoding="utf-8")
    q.write_text(json.dumps({"schema_version": 1, "max_depth": 500, "items": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    ing.write_text(json.dumps({"schema_version": 1, "entries": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    aud.write_text(json.dumps({"schema_version": 1, "entries": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    dl.write_text(json.dumps({"schema_version": 1, "entries": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    rg.write_text(json.dumps({"schema_version": 1, "entries": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    cp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "enabled": True,
                "maintenance_mode": False,
                "max_cycles_per_window": 120,
                "window_seconds": 3600,
                "disabled_trigger_types": [],
                "allowed_trigger_types": ["manual_watchlist"],
                "legacy_external_ingest_enabled": False,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    now = datetime.now(timezone.utc)
    nonce_ok = f"n-{now.timestamp()}-ok"
    raw_ok = json.dumps(body_base, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    hdr_ok = _signed_headers(body=body_base, source_id="s53_signed", secret=sign_secret, nonce=nonce_ok, ts=now)

    good = process_governed_external_ingest(
        body_base,
        source_id_header="s53_signed",
        webhook_secret=sign_secret,
        repo_root=root,
        source_registry_path=src_reg,
        budget_state_path=bud,
        queue_path=q,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp,
        raw_body=raw_ok,
        http_headers=hdr_ok,
        replay_guard_path=rg,
        dead_letter_path=dl,
    )

    nonce_bad = f"n-{now.timestamp()}-badsig"
    hdr_bad = dict(hdr_ok)
    hdr_bad["X-Webhook-Nonce"] = nonce_bad
    hdr_bad["X-Webhook-Signature"] = "0" * 64
    bad_sig = process_governed_external_ingest(
        body_base,
        source_id_header="s53_signed",
        webhook_secret=sign_secret,
        repo_root=root,
        source_registry_path=src_reg,
        budget_state_path=bud,
        queue_path=q,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp,
        raw_body=raw_ok,
        http_headers=hdr_bad,
        replay_guard_path=rg,
        dead_letter_path=dl,
    )

    stale = now - timedelta(hours=2)
    nonce_stale = f"n-{now.timestamp()}-stale"
    hdr_stale = _signed_headers(body=body_base, source_id="s53_signed", secret=sign_secret, nonce=nonce_stale, ts=stale)
    stale_out = process_governed_external_ingest(
        body_base,
        source_id_header="s53_signed",
        webhook_secret=sign_secret,
        repo_root=root,
        source_registry_path=src_reg,
        budget_state_path=bud,
        queue_path=q,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp,
        raw_body=raw_ok,
        http_headers=hdr_stale,
        replay_guard_path=rg,
        dead_letter_path=dl,
    )

    nonce_replay = f"n-{now.timestamp()}-replay"
    hdr_r1 = _signed_headers(body=body_base, source_id="s53_signed", secret=sign_secret, nonce=nonce_replay, ts=now)
    r1 = process_governed_external_ingest(
        body_base,
        source_id_header="s53_signed",
        webhook_secret=sign_secret,
        repo_root=root,
        source_registry_path=src_reg,
        budget_state_path=bud,
        queue_path=q,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp,
        raw_body=raw_ok,
        http_headers=hdr_r1,
        replay_guard_path=rg,
        dead_letter_path=dl,
    )
    r2 = process_governed_external_ingest(
        body_base,
        source_id_header="s53_signed",
        webhook_secret=sign_secret,
        repo_root=root,
        source_registry_path=src_reg,
        budget_state_path=bud,
        queue_path=q,
        ingest_registry_path=ing,
        audit_path=aud,
        control_plane_path=cp,
        raw_body=raw_ok,
        http_headers=hdr_r1,
        replay_guard_path=rg,
        dead_letter_path=dl,
    )

    dl_entries = load_dead_letter(dl).get("entries") or []
    sig_failures = sum(1 for e in dl_entries if str(e.get("failure_stage")) == "signature")
    replay_blocked = 1 if not r2.get("ok") and r2.get("error") == "replay_blocked" else 0
    dl_counts: dict[str, int] = {}
    for e in dl_entries:
        st = str(e.get("failure_stage") or "unknown")
        dl_counts[st] = dl_counts.get(st, 0) + 1

    health = build_runtime_health_summary(
        repo_root=root,
        ingest_registry_path=ing,
        external_source_registry_path=src_reg,
        external_budget_state_path=bud,
        external_event_queue_path=q,
        dead_letter_path=dl,
        replay_guard_path=rg,
    )

    replay_summary: dict[str, Any] = {
        "cli_replay": "replay-phase53-dead-letter",
        "note": "Replays re-enter governed ingress with current rules; use CLI with corrected secret/signature material.",
    }

    gen = datetime.now(timezone.utc).isoformat()
    metrics_ok = (
        good.get("ok")
        and not bad_sig.get("ok")
        and not stale_out.get("ok")
        and r1.get("ok")
        and not r2.get("ok")
        and sig_failures >= 1
        and health.get("external_source_activity_v52") is not None
        and (health.get("external_ingress_phase53") or {}).get("dead_letter_total_entries", 0) >= 1
    )

    return {
        "ok": metrics_ok,
        "phase": "phase53_signed_payload_hmac_dead_letter",
        "generated_utc": gen,
        "input_phase52_bundle_path": str(p52),
        "signed_ingress_enabled": True,
        "signature_failures_recorded": sig_failures,
        "replay_attempts_blocked": replay_blocked,
        "sources_with_rotation_enabled": 1,
        "dead_letter_counts": dl_counts,
        "dead_letter_replay_summary": replay_summary,
        "runtime_health_summary": health,
        "legacy_ingest_status": health.get("legacy_ingest_status") or {},
        "phase54": recommend_phase54(),
        "smoke_metrics_ok": metrics_ok,
        "good_ingress_ok": bool(good.get("ok")),
        "paths": {
            "source_registry": str(src_reg),
            "dead_letter": str(dl),
            "replay_guard": str(rg),
        },
    }
