#!/usr/bin/env python3
"""Local HTTP server for Phase 47 founder cockpit (stdlib only)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_PKG = Path(__file__).resolve().parent
_SRC_ROOT = _PKG.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from phase47_runtime.routes import dispatch_json
from phase47_runtime.runtime_state import CockpitRuntimeState, default_repo_root


def _content_type(name: str) -> str:
    if name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if name.endswith(".html"):
        return "text/html; charset=utf-8"
    if name.endswith(".css"):
        return "text/css; charset=utf-8"
    return "application/octet-stream"


def make_handler(state: CockpitRuntimeState):
    class CockpitHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, code: int, obj: object) -> None:
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self._send(code, b, "application/json; charset=utf-8")

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path or "/"
            q = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            if path in ("/", "/index.html"):
                p = _PKG / "static" / "index.html"
                if not p.is_file():
                    self._send_json(500, {"ok": False, "error": "missing_index_html"})
                    return
                self._send(200, p.read_bytes(), _content_type("index.html"))
                return
            if path.startswith("/static/"):
                rel = path[len("/static/") :].lstrip("/")
                if ".." in rel or rel.startswith("/"):
                    self.send_error(400)
                    return
                sp = _PKG / "static" / rel
                if not sp.is_file() or not str(sp.resolve()).startswith(str((_PKG / "static").resolve())):
                    self.send_error(404)
                    return
                self._send(200, sp.read_bytes(), _content_type(rel))
                return
            if path.startswith("/api/"):
                hdrs = {
                    "X-User-Language": (self.headers.get("X-User-Language") or ""),
                    "X-Cockpit-Lang": (self.headers.get("X-Cockpit-Lang") or ""),
                }
                code, obj = dispatch_json(state, method="GET", path=path, body=None, query=q, headers=hdrs)
                self._send_json(code, obj)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path or "/"
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else None
            if path.startswith("/api/"):
                hdrs = {
                    "X-Source-Id": (self.headers.get("X-Source-Id") or ""),
                    "X-Webhook-Secret": (self.headers.get("X-Webhook-Secret") or ""),
                    "X-Webhook-Timestamp": (self.headers.get("X-Webhook-Timestamp") or ""),
                    "X-Webhook-Signature": (self.headers.get("X-Webhook-Signature") or ""),
                    "X-Webhook-Nonce": (self.headers.get("X-Webhook-Nonce") or ""),
                }
                code, obj = dispatch_json(state, method="POST", path=path, body=body, query={}, headers=hdrs)
                self._send_json(code, obj)
                return
            self.send_error(404)

    return CockpitHandler


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 47 founder cockpit HTTP server")
    # AGH v1 Patch 8 E4 — honor Railway's $PORT convention so the same
    # entry-point works locally (8765), in CI, and on the hosted web
    # service. Explicit --host/--port / PHASE47_* still take priority.
    _default_host = os.environ.get("PHASE47_HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    _default_port = int(os.environ.get("PHASE47_PORT") or os.environ.get("PORT") or "8765")
    ap.add_argument("--host", default=_default_host)
    ap.add_argument("--port", type=int, default=_default_port)
    ap.add_argument(
        "--phase46-bundle",
        default=os.environ.get(
            "PHASE47_PHASE46_BUNDLE",
            "docs/operator_closeout/phase46_founder_decision_cockpit_bundle.json",
        ),
        help="Path to phase46_founder_decision_cockpit_bundle.json",
    )
    ap.add_argument(
        "--repo-root",
        default=os.environ.get("PHASE47_REPO_ROOT", ""),
        help="Repository root (default: parent of src/)",
    )
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if str(args.repo_root).strip() else default_repo_root()
    bundle_path = Path(args.phase46_bundle)
    if not bundle_path.is_absolute():
        bundle_path = (root / bundle_path).resolve()
    if not bundle_path.is_file():
        print(json.dumps({"ok": False, "error": "phase46_bundle_missing", "path": str(bundle_path)}), file=sys.stderr)
        return 1
    # MVP: Today reads Brain/registry first unless operator sets METIS_TODAY_SOURCE (see Unified Product Spec §3.3).
    os.environ.setdefault("METIS_TODAY_SOURCE", "registry")
    state = CockpitRuntimeState.from_paths(repo_root=root, phase46_bundle_path=bundle_path)
    handler = make_handler(state)
    httpd = HTTPServer((args.host, args.port), handler)
    print(
        json.dumps(
            {
                "ok": True,
                "listening": f"http://{args.host}:{args.port}",
                "phase46_bundle": str(bundle_path),
            },
            indent=2,
        ),
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nphase47_runtime_shutdown", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
