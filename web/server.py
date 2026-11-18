"""Boule — the front door.

    python3 web/server.py [--port 8123] [--bind 127.0.0.1] [--db engine/boule.db]

Stdlib only, on purpose. The interesting part of this project is the gap, not the
web framework; there is no dependency here that can rot.

One SQLite connection is opened per request. That is deliberate: sqlite3
connections are not safe to share across threads, and ThreadingHTTPServer serves
each request in its own thread. At preview traffic the cost is irrelevant.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import render  # noqa: E402

STATIC = (HERE / "static").resolve()
CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "boule/0.1"
    db_path = "engine/boule.db"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:    # noqa: A002 - base class name
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")

    def _send(self, code: int, body, ctype: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, to: str) -> None:
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _static(self, path: str) -> None:
        rel = urllib.parse.unquote(path[len("/static/"):])
        target = (STATIC / rel).resolve()
        # refuse anything that escapes the static directory
        if not str(target).startswith(str(STATIC) + "/") or not target.is_file():
            return self._send(404, "not found", "text/plain; charset=utf-8")
        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        return self._send(200, target.read_bytes(), ctype)

    def _db(self) -> sqlite3.Connection:
        # Read-only on purpose: the front door must never write the legislative
        # record, and a read-only handle lets the service run under
        # ProtectHome=read-only. Requires a non-WAL database file (no -shm needed).
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    def do_HEAD(self) -> None:                            # noqa: N802
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False) -> None:     # noqa: N802
        path = urllib.parse.urlparse(self.path).path

        if path == "/health":
            return self._send(200, "ok", "text/plain; charset=utf-8")

        if path.startswith("/static/"):
            return self._static(path)

        if path in ("/", "/today"):
            con = self._db()
            try:
                body = render.today_page(con, date.today().isoformat())
            finally:
                con.close()
            return self._send(200, body)

        if path == "/privacy":
            return self._send(200, render.privacy_page())

        # /bills, /gap, /me are named in the nav but not built yet. Say so plainly
        # rather than pretending they work.
        if path in ("/bills", "/gap", "/me"):
            body = render.page(
                f"Boule — {path.strip('/')}",
                render.masthead([f"<b>{path.strip('/').title()}</b> — not built yet"])
                + '<main id="main"><p class="empty">This surface is not built yet.</p></main>',
                path.strip("/").title(),
            )
            return self._send(200, body)

        body = render.page(
            "Boule — not found",
            render.masthead(["<b>404</b> — not found"])
            + '<main id="main"><p class="empty">No such page.</p></main>',
            "",
        )
        return self._send(404, body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--bind", default="127.0.0.1",
                    help="0.0.0.0 to be reachable from the network")
    ap.add_argument("--db", default=str(HERE.parent / "engine" / "boule.db"))
    args = ap.parse_args()

    Handler.db_path = args.db
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"boule serving on http://{args.bind}:{args.port}  (db: {args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
