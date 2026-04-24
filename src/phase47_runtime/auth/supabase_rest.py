"""Patch 12 — minimal Supabase REST client backed by ``urllib.request``.

We intentionally avoid the official ``supabase-py`` SDK so we keep the
runtime dependency footprint flat. The handful of things we need from
PostgREST are: SELECT / INSERT / UPSERT on a few tables using the service
role key.

Every call is done with ``urllib`` and therefore testable via
``unittest.mock.patch``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


class SupabaseRestError(RuntimeError):
    """Raised when a Supabase REST call returns a non-2xx response."""

    def __init__(self, status: int, body: str, *, path: str) -> None:
        super().__init__(f"supabase_rest_error status={status} path={path}")
        self.status = status
        self.body = body
        self.path = path


@dataclass(frozen=True)
class SupabaseRestClient:
    url: str
    service_role_key: str
    timeout_seconds: float = 10.0

    def _endpoint(self, table: str, *, query: dict[str, str] | None = None) -> str:
        base = f"{self.url.rstrip('/')}/rest/v1/{table}"
        if query:
            return f"{base}?{urllib.parse.urlencode(query)}"
        return base

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        h = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, str]:
        req = urllib.request.Request(url=url, method=method, headers=headers, data=body)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, raw
        except urllib.error.HTTPError as http_err:
            detail = ""
            try:
                detail = http_err.read().decode("utf-8")
            except Exception:  # pragma: no cover - defensive
                detail = str(http_err)
            raise SupabaseRestError(http_err.code, detail, path=url) from http_err

    def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        limit: int | None = None,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        q: dict[str, str] = {"select": columns}
        if filters:
            q.update(filters)
        if limit is not None:
            q["limit"] = str(int(limit))
        if order:
            q["order"] = order
        url = self._endpoint(table, query=q)
        status, body = self._request("GET", url, headers=self._headers())
        if status not in (200, 206):
            raise SupabaseRestError(status, body, path=url)
        try:
            parsed = json.loads(body or "[]")
        except json.JSONDecodeError as exc:
            raise SupabaseRestError(status, body, path=url) from exc
        if isinstance(parsed, dict):
            return [parsed]
        return list(parsed)

    def insert(
        self,
        table: str,
        rows: Iterable[dict[str, Any]],
        *,
        return_representation: bool = False,
        on_conflict: str | None = None,
    ) -> list[dict[str, Any]]:
        rows_list = [dict(r) for r in rows]
        if not rows_list:
            return []
        q: dict[str, str] = {}
        if on_conflict:
            q["on_conflict"] = on_conflict
        url = self._endpoint(table, query=q or None)
        prefer_parts = []
        if return_representation:
            prefer_parts.append("return=representation")
        else:
            prefer_parts.append("return=minimal")
        if on_conflict:
            prefer_parts.append("resolution=merge-duplicates")
        prefer = ",".join(prefer_parts)
        headers = self._headers(prefer=prefer)
        status, body = self._request(
            "POST",
            url,
            headers=headers,
            body=json.dumps(rows_list).encode("utf-8"),
        )
        if status not in (200, 201, 204):
            raise SupabaseRestError(status, body, path=url)
        if not body:
            return []
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict):
            return [parsed]
        return list(parsed)

    def update(
        self,
        table: str,
        *,
        filters: dict[str, str],
        patch: dict[str, Any],
    ) -> list[dict[str, Any]]:
        url = self._endpoint(table, query=dict(filters))
        status, body = self._request(
            "PATCH",
            url,
            headers=self._headers(prefer="return=representation"),
            body=json.dumps(patch).encode("utf-8"),
        )
        if status not in (200, 204):
            raise SupabaseRestError(status, body, path=url)
        if not body:
            return []
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict):
            return [parsed]
        return list(parsed)


__all__ = ["SupabaseRestClient", "SupabaseRestError"]
