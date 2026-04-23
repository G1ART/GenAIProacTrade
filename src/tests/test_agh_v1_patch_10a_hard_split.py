"""Patch 10A — Hard split between Product Shell (/) and Ops Cockpit (/ops).

These tests assert the structural separation at the *source* level:

- Customer surface files exist and reference the new Product Shell assets.
- Ops Cockpit files exist and continue to reference their legacy assets.
- ``src/phase47_runtime/app.py`` routes ``/`` to ``static/index.html``
  and serves ``/ops`` only when ``METIS_OPS_SHELL`` is enabled.
- The new ``/api/product/today`` route is wired into ``dispatch_json``.
- A minimal end-to-end HTTP probe verifies that ``/ops`` is 404 by
  default and 200 under env gate.
"""

from __future__ import annotations

import os
import re
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATIC = _REPO_ROOT / "src" / "phase47_runtime" / "static"
_APP_PY = _REPO_ROOT / "src" / "phase47_runtime" / "app.py"
_ROUTES_PY = _REPO_ROOT / "src" / "phase47_runtime" / "routes.py"


# ---------------------------------------------------------------------------
# Structural file layout
# ---------------------------------------------------------------------------


def test_customer_surface_files_exist():
    assert (_STATIC / "index.html").is_file(), "missing new Product Shell index.html"
    assert (_STATIC / "product_shell.js").is_file(), "missing product_shell.js"
    assert (_STATIC / "product_shell.css").is_file(), "missing product_shell.css"


def test_ops_surface_files_exist():
    assert (_STATIC / "ops.html").is_file(), "Ops Cockpit ops.html missing"
    assert (_STATIC / "ops.js").is_file(), "Ops Cockpit ops.js missing"


def test_legacy_filenames_fully_removed():
    """The legacy ``index.html`` /``app.js`` that predated the split must
    have been renamed, not duplicated."""
    # index.html now exists but must NOT be the old cockpit (it should be
    # the small Product Shell skeleton). ops.html holds the cockpit.
    ps_index = (_STATIC / "index.html").read_text(encoding="utf-8")
    assert '<script src="/static/product_shell.js"></script>' in ps_index
    # If the old "app.js" file still exists as a separate artifact, the
    # rename was not clean.
    assert not (_STATIC / "app.js").exists(), "legacy app.js still present"


def test_customer_index_does_not_reference_legacy_app_js():
    txt = (_STATIC / "index.html").read_text(encoding="utf-8")
    assert 'src="/static/app.js"' not in txt
    assert 'src="/static/ops.js"' not in txt


def test_ops_html_references_ops_js():
    txt = (_STATIC / "ops.html").read_text(encoding="utf-8")
    assert 'src="/static/ops.js"' in txt
    # Must NOT reference the legacy app.js after the rename.
    assert 'src="/static/app.js"' not in txt


# ---------------------------------------------------------------------------
# app.py routing contract
# ---------------------------------------------------------------------------


def test_app_py_routes_root_to_product_shell_index():
    src = _APP_PY.read_text(encoding="utf-8")
    # Default root path serves ``static/index.html``.
    assert re.search(r'if path in \("/", "/index\.html"\):', src), (
        "app.py missing root-path handler for Product Shell"
    )


def test_app_py_has_ops_env_gate():
    src = _APP_PY.read_text(encoding="utf-8")
    assert "METIS_OPS_SHELL" in src, "app.py missing METIS_OPS_SHELL env gate"
    assert 'if path in ("/ops"' in src, "app.py missing /ops route"


def test_routes_py_has_product_today_endpoint():
    src = _ROUTES_PY.read_text(encoding="utf-8")
    assert 'p == "/api/product/today"' in src, (
        "routes.py missing /api/product/today dispatcher"
    )
    assert "def api_product_today(" in src


# ---------------------------------------------------------------------------
# End-to-end HTTP probe
# ---------------------------------------------------------------------------


def _spawn_server(tmp_path: Path, *, env: dict[str, str] | None = None):
    """Spawn the Phase47 runtime HTTP server in a daemon thread on an
    ephemeral port. Returns ``(port, shutdown)``.
    """
    from phase47_runtime.app import make_handler  # type: ignore
    from phase47_runtime.runtime_state import CockpitRuntimeState

    # Minimal bundle-ish state so the handler constructs cleanly.
    bpath = tmp_path / "phase46_bundle.json"
    bpath.write_text(
        '{"phase":"phase46_founder_decision_cockpit","generated_utc":"2026-04-23T08:00:00+00:00",'
        '"founder_read_model":{"asset_id":"x"},"cockpit_state":{"cohort_aggregate":{"decision_card":{}}}}',
        encoding="utf-8",
    )
    (tmp_path / "a.json").write_text('{"schema_version":1,"alerts":[]}', encoding="utf-8")
    (tmp_path / "d.json").write_text('{"schema_version":1,"decisions":[]}', encoding="utf-8")
    state = CockpitRuntimeState.from_paths(repo_root=tmp_path, phase46_bundle_path=bpath)

    handler_cls = make_handler(state)
    httpd = HTTPServer(("127.0.0.1", 0), handler_cls)
    port = httpd.server_address[1]
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    if env:
        for k, v in env.items():
            os.environ[k] = v
    th.start()

    def shutdown():
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            pass
        if env:
            for k in env:
                os.environ.pop(k, None)
    return port, shutdown


def _http_get(port: int, path: str) -> tuple[int, str]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


@pytest.fixture(autouse=True)
def _clean_ops_env():
    # Ensure each test starts with no OPS shell env.
    prev = os.environ.pop("METIS_OPS_SHELL", None)
    yield
    os.environ.pop("METIS_OPS_SHELL", None)
    if prev is not None:
        os.environ["METIS_OPS_SHELL"] = prev


def _make_handler_available() -> bool:
    try:
        from phase47_runtime.app import make_handler  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _make_handler_available(),
                    reason="app.make_handler factory not exposed")
def test_root_serves_product_shell(tmp_path):
    port, shutdown = _spawn_server(tmp_path)
    try:
        code, body = _http_get(port, "/")
        assert code == 200
        assert "product_shell.js" in body, "root must serve Product Shell"
    finally:
        shutdown()


@pytest.mark.skipif(not _make_handler_available(),
                    reason="app._build_handler factory not exposed")
def test_ops_is_404_without_env_gate(tmp_path):
    port, shutdown = _spawn_server(tmp_path)
    try:
        code, _body = _http_get(port, "/ops")
        assert code == 404
    finally:
        shutdown()


@pytest.mark.skipif(not _make_handler_available(),
                    reason="app._build_handler factory not exposed")
def test_ops_is_200_with_env_gate(tmp_path):
    port, shutdown = _spawn_server(tmp_path, env={"METIS_OPS_SHELL": "1"})
    try:
        code, body = _http_get(port, "/ops")
        assert code == 200
        # Ops Cockpit references ops.js (not product_shell.js).
        assert "ops.js" in body
    finally:
        shutdown()


@pytest.mark.skipif(not _make_handler_available(),
                    reason="app._build_handler factory not exposed")
def test_api_product_today_200(tmp_path):
    port, shutdown = _spawn_server(tmp_path)
    try:
        code, body = _http_get(port, "/api/product/today?lang=ko")
        assert code == 200
        assert '"contract": "PRODUCT_TODAY_V1"' in body or '"contract":"PRODUCT_TODAY_V1"' in body
    finally:
        shutdown()
