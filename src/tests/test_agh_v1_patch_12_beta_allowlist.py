"""Patch 12 — beta_users_v1 allowlist probe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from phase47_runtime.auth.beta_allowlist import (
    ALLOWLIST_MODE_ENFORCE,
    ALLOWLIST_MODE_OFF,
    ALLOWLIST_MODE_SHADOW,
    clear_allowlist_cache,
    verify_user_is_active_beta,
)


@dataclass
class FakeRest:
    rows: list[dict[str, Any]]
    raise_error: bool = False

    def select(self, table, *, columns, filters, limit=None, order=None):
        if self.raise_error:
            from phase47_runtime.auth.supabase_rest import SupabaseRestError
            raise SupabaseRestError(500, "boom", path=table)
        return self.rows


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_allowlist_cache()
    yield
    clear_allowlist_cache()


def test_invited_row_passes():
    r = verify_user_is_active_beta(
        "u1",
        client=FakeRest(rows=[{"user_id": "u1", "status": "invited", "role": "beta_user"}]),
        mode_override=ALLOWLIST_MODE_ENFORCE,
    )
    assert r.ok and r.status == "invited" and r.role == "beta_user"


def test_active_row_passes():
    r = verify_user_is_active_beta(
        "u1",
        client=FakeRest(rows=[{"user_id": "u1", "status": "active", "role": "admin"}]),
        mode_override=ALLOWLIST_MODE_ENFORCE,
    )
    assert r.ok and r.role == "admin"


def test_paused_row_rejected():
    r = verify_user_is_active_beta(
        "u1",
        client=FakeRest(rows=[{"user_id": "u1", "status": "paused", "role": "beta_user"}]),
        mode_override=ALLOWLIST_MODE_ENFORCE,
    )
    assert not r.ok and r.reason == "allowlist_paused"


def test_revoked_row_rejected():
    r = verify_user_is_active_beta(
        "u1",
        client=FakeRest(rows=[{"user_id": "u1", "status": "revoked", "role": "beta_user"}]),
        mode_override=ALLOWLIST_MODE_ENFORCE,
    )
    assert not r.ok and r.reason == "allowlist_revoked"


def test_no_row_rejected_in_enforce():
    r = verify_user_is_active_beta(
        "u1", client=FakeRest(rows=[]), mode_override=ALLOWLIST_MODE_ENFORCE,
    )
    assert not r.ok and r.reason == "not_on_allowlist"


def test_off_mode_passes_everything():
    r = verify_user_is_active_beta(
        "u1", client=FakeRest(rows=[]), mode_override=ALLOWLIST_MODE_OFF,
    )
    assert r.ok


def test_shadow_mode_passes_on_missing_row():
    r = verify_user_is_active_beta(
        "u1", client=FakeRest(rows=[]), mode_override=ALLOWLIST_MODE_SHADOW,
    )
    assert r.ok and r.reason == "no_row_shadow_pass"


def test_lookup_failure_fails_closed_in_enforce():
    r = verify_user_is_active_beta(
        "u1", client=FakeRest(rows=[], raise_error=True), mode_override=ALLOWLIST_MODE_ENFORCE,
    )
    assert not r.ok and r.reason == "allowlist_lookup_failed"


def test_lookup_failure_passes_in_shadow():
    r = verify_user_is_active_beta(
        "u1", client=FakeRest(rows=[], raise_error=True), mode_override=ALLOWLIST_MODE_SHADOW,
    )
    assert r.ok and r.reason == "lookup_failed_shadow_pass"


def test_empty_user_id_rejected():
    r = verify_user_is_active_beta("", client=FakeRest(rows=[]), mode_override=ALLOWLIST_MODE_ENFORCE)
    assert not r.ok and r.reason == "empty_user_id"
