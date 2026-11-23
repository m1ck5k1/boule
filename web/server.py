"""Boule — the front door.

    python3 web/server.py [--port 8123] [--bind 127.0.0.1] [--db engine/boule.db]

Stdlib only, on purpose. The interesting part of this project is the gap, not the
web framework; there is no dependency here that can rot.

One SQLite connection is opened per request. That is deliberate: sqlite3
connections are not safe to share across threads, and ThreadingHTTPServer serves
each request in its own thread. At preview traffic the cost is irrelevant.

S5 adds exactly two things, and no accounts: a device key is issued, and a reading
is bound to the DEVICE. The server stores only the key's hash, so it can recognise
a device and still be unable to resolve one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sqlite3
import sys
import urllib.parse
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "engine"))

import render  # noqa: E402
import retention  # noqa: E402


def _hash_ip(addr: str | None) -> str:
    """The client address, hashed. Never the raw value, never published."""
    return hashlib.sha256((addr or "").encode()).hexdigest()[:32]


def _hash_key(key: str) -> str:
    """The device key, hashed in full. The raw key is never stored and never logged."""
    return hashlib.sha256(key.encode()).hexdigest()


STATIC = (HERE / "static").resolve()
CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}

# S5 — the device cookie. Two years: a reading is per device, so the key has to
# outlive the tab. HttpOnly because no script needs to read it; Secure because the
# app is only ever reached over TLS (tailscale serve terminates it).
DEVICE_COOKIE = "boule_device"
DEVICE_COOKIE_SECONDS = 2 * 365 * 24 * 60 * 60


class Handler(BaseHTTPRequestHandler):
    server_version = "boule/0.1"
    db_path = "engine/boule.db"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:    # noqa: A002 - base class name
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")

    def _send(self, code: int, body, ctype: str = "text/html; charset=utf-8",
              extra_headers: tuple[tuple[str, str], ...] = (),
              head_only: bool = False) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for name, value in extra_headers:
            self.send_header(name, value)
        self.end_headers()
        # A HEAD response carries the headers a GET would, and no body. Sending one
        # anyway is a small lie that only shows up when something reads it.
        if not head_only:
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

    def _db_rw(self) -> sqlite3.Connection:
        # S3 — the ballot box needs a WRITABLE handle. The read handle above stays
        # read-only on purpose: the front door must never rewrite the legislative
        # record. Votes are a separate, append-only surface (DB triggers enforce it).
        con = sqlite3.connect(f"file:{self.db_path}?mode=rw", uri=True)
        con.row_factory = sqlite3.Row
        return con

    # --- S5: the device key -----------------------------------------------------

    def _cookie(self, name: str) -> str:
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return urllib.parse.unquote(v)
        return ""

    def _device_id_for(self, con: sqlite3.Connection, key: str) -> str | None:
        """Resolve a presented key to a device. Never trusts the key's contents."""
        row = con.execute(
            "SELECT device_id, retired_at FROM devices WHERE key_hash = ?",
            (_hash_key(key),),
        ).fetchone()
        if row is None or row["retired_at"]:
            return None
        return row["device_id"]

    def _issue_device(self) -> None:
        """Issue a key and hand it to the device in a cookie.

        The raw key exists in exactly one place after this returns: the client. The
        database keeps a hash, so a dump of the database cannot be replayed to vote.

        SameSite=Lax is the CSRF control here, not decoration. A cross-site POST does
        not carry the cookie, so a forged submission can only ever record an
        ANONYMOUS reading — it cannot burn this device's one reading on a version.
        """
        key = secrets.token_urlsafe(32)
        device_id = secrets.token_hex(16)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        con = self._db_rw()
        try:
            con.execute(
                "INSERT INTO devices (device_id, key_hash, issued_at) VALUES (?, ?, ?)",
                (device_id, _hash_key(key), now),
            )
            con.commit()
        except sqlite3.Error as exc:
            return self._send(500, f"device not issued: {exc}",
                              "text/plain; charset=utf-8")
        finally:
            con.close()

        cookie = (f"{DEVICE_COOKIE}={urllib.parse.quote(key)}; Path=/; HttpOnly; "
                  f"Secure; SameSite=Lax; Max-Age={DEVICE_COOKIE_SECONDS}")
        return self._send(200, json.dumps({"issued": True}), "application/json; charset=utf-8",
                          extra_headers=(("Set-Cookie", cookie),))

    def do_HEAD(self) -> None:                            # noqa: N802
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False) -> None:     # noqa: N802
        path = urllib.parse.urlparse(self.path).path

        if path == "/health":
            return self._send(200, "ok", "text/plain; charset=utf-8", head_only=head_only)

        if path.startswith("/static/"):
            return self._static(path)

        # Any route render knows about — including the per-bill detail pages, which
        # are dynamic. An unknown path falls through to render's KeyError -> 404.
        con = self._db()
        try:
            body = render.render_route(path, con, date.today().isoformat())
        except KeyError:
            con.close()
            return self._send(404, "no such route", "text/plain; charset=utf-8",
                              head_only=head_only)
        finally:
            con.close()
        return self._send(200, body, head_only=head_only)

    def do_POST(self) -> None:                            # noqa: N802
        """The write surface: the device key, and one append-only vote row."""
        path = urllib.parse.urlparse(self.path).path

        # S5 — issuance. Called at install (S6 wires the service worker to it); the
        # response sets the cookie, so the rest of the app needs no JavaScript.
        if path == "/api/device":
            return self._issue_device()

        if path != "/api/vote":
            return self._send(404, "not found", "text/plain; charset=utf-8")

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 2048:
            return self._send(400, "bad request", "text/plain; charset=utf-8")
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "replace"))

        def one(key: str) -> str:
            return (form.get(key) or [""])[0].strip()

        choice = one("choice").lower()
        bill_type = one("bill_type").lower()
        version_code = one("version_code")
        try:
            congress = int(one("congress"))
            number = int(one("number"))
        except ValueError:
            return self._send(400, "bad bill", "text/plain; charset=utf-8")
        if choice not in ("yea", "nay") or not bill_type or not version_code:
            return self._send(400, "bad vote", "text/plain; charset=utf-8")

        # 'click once, click to confirm' — nothing is written until the confirm
        # page is submitted, so a stray click cannot record a ballot.
        if one("confirm") != "1":
            con = self._db()
            try:
                row = con.execute(
                    "SELECT title FROM bills WHERE congress = ? AND bill_type = ? AND number = ?",
                    (congress, bill_type, number),
                ).fetchone()
            finally:
                con.close()
            title = (row["title"] if row else "") or "(no title)"
            label = f"{bill_type.upper()} {number}"
            hidden = "".join(
                f'<input type="hidden" name="{k}" value="{render.esc(v)}">'
                for k, v in (("congress", congress), ("bill_type", bill_type),
                             ("number", number), ("version_code", version_code),
                             ("choice", choice), ("confirm", "1"),
                             ("next", one("next") or "/"))
            )
            return self._send(200, render.confirm_vote(label, title, choice, hidden))

        # The stamp is the server's, never the client's word.
        cast_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ip_hash = _hash_ip(self.client_address[0])
        label = f"{bill_type.upper()} {number}"
        base_path = ""

        # S5 — who is this reading from? A presented key resolves to a device; no key
        # means an anonymous reading, which is a legitimate tier and not a failure.
        # An UNKNOWN key is refused rather than quietly downgraded to anonymous: a
        # key that silently stops working would file the reading as somebody else.
        presented = one("device_key") or self._cookie(DEVICE_COOKIE)

        con = self._db_rw()
        try:
            device_id = None
            if presented:
                device_id = self._device_id_for(con, presented)
                if device_id is None:
                    return self._send(400, "unknown device key",
                                      "text/plain; charset=utf-8")

            provenance = "device" if device_id else "anonymous"

            # The reading goes into the append-only table, which holds nothing personal
            # and therefore nothing that can expire. The single retained value -- the
            # hashed address -- goes to `vote_nets`, which is mutable and purged on its
            # own clock. (DATA.md: expiry is the licence to publish, not hygiene.)
            cur = con.execute(
                "INSERT INTO votes "
                "(congress, bill_type, number, version_code, choice, provenance, "
                "voter_key, cast_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (congress, bill_type, number, version_code, choice, provenance,
                 device_id, cast_at),
            )
            if device_id:
                con.execute("UPDATE devices SET last_seen_at = ? WHERE device_id = ?",
                            (cast_at, device_id))
            con.execute(
                "INSERT INTO vote_nets (vote_id, ip_hash, retire_after) VALUES (?, ?, ?)",
                (cur.lastrowid, ip_hash, retention.retire_after(retention.ADDRESS_DAYS)),
            )
            con.commit()
        except sqlite3.IntegrityError as exc:
            con.rollback()
            # The one refusal S5 adds. It is the DATABASE saying no -- a partial
            # UNIQUE index on (bill, version, voter_key) -- not this function
            # remembering to check, so there is no window to race.
            if "ux_votes_device_version" in str(exc) or "UNIQUE constraint failed" in str(exc):
                con2 = self._db()
                try:
                    row = con2.execute(
                        "SELECT title FROM bills WHERE congress = ? AND bill_type = ? "
                        "AND number = ?", (congress, bill_type, number)).fetchone()
                finally:
                    con2.close()
                title = (row["title"] if row else "") or "(no title)"
                return self._send(409, render.one_reading_page(label, title, base_path))
            return self._send(400, f"vote rejected: {exc}", "text/plain; charset=utf-8")
        except sqlite3.Error as exc:
            con.rollback()
            return self._send(500, f"vote not recorded: {exc}", "text/plain; charset=utf-8")
        finally:
            con.close()

        return self._redirect(one("next") or "/")


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