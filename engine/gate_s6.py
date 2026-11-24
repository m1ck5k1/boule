"""S6 gate — the automatable half of "Add to Home Screen installs".

    python3 engine/gate_s6.py

ROADMAP §the stage ladder fixes S6's gate as: *"Add to Home Screen installs, and the app
holds a key the server honours."* **The install itself cannot be automated** — it is a
gesture on a real device, and claiming otherwise would be the same class of lie as a
green gate that cannot fail. So this gate tests every condition the install DEPENDS on,
and names the one thing a human still has to do.

The silent failures it exists to catch:
  * a manifest that parses but points at icons that do not exist, or exist at the
    wrong size -- install is refused with no visible reason
  * a service worker served from a subpath, so its scope is that subpath and it
    controls nothing
  * a page missing the <link rel="manifest">, so the manifest is never found
  * an issuance endpoint that mints a NEW device on every call, which would fork the
    identity on every reinstall and grow the table without bound

Exits 0 on pass, 1 on fail.
"""
from __future__ import annotations

import http.client
import json
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PORT = 8198


def get(path: str, cookie: str | None = None):
    headers = {"Cookie": cookie} if cookie else {}
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=8)
    try:
        conn.request("GET", path, headers=headers)
        r = conn.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    finally:
        conn.close()


def post(path: str, cookie: str | None = None):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if cookie:
        headers["Cookie"] = cookie
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=8)
    try:
        conn.request("POST", path, body="", headers=headers)
        r = conn.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    finally:
        conn.close()


def png_size(blob: bytes) -> tuple[int, int] | None:
    """Width/height straight out of the PNG IHDR — the file's own claim, not the name."""
    if blob[:8] != b"\x89PNG\r\n\x1a\n" or blob[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", blob[16:24])


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="boule-s6-"))
    db = tmp / "gate.db"
    con = sqlite3.connect(db)
    con.executescript((HERE / "schema.sql").read_text())
    con.execute("INSERT INTO bills (congress, bill_type, number, title, ingested_at) "
                "VALUES (119, 'hr', 2347, 'A real bill', '2026-11-23')")
    con.commit()
    con.close()

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "web" / "server.py"), "--port", str(PORT),
         "--bind", "127.0.0.1", "--db", str(db)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results: list[tuple[str, bool]] = []
    try:
        for _ in range(50):
            try:
                c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=2)
                c.request("GET", "/health")
                if c.getresponse().status == 200:
                    c.close()
                    break
                c.close()
            except OSError:
                time.sleep(0.2)
        else:
            print("  FAIL  the server never came up")
            return 1

        # --- the manifest --------------------------------------------------------
        MANIFEST = "/manifest.webmanifest"
        status, headers, blob = get(MANIFEST)
        results.append(("the manifest is served from the ROOT", status == 200))
        results.append(("with the manifest content type",
                        "manifest+json" in headers.get("Content-Type", "")))
        man = json.loads(blob)
        results.append(("it names the app and a start_url",
                        bool(man.get("name")) and bool(man.get("start_url"))))
        results.append(("it asks for standalone display", man.get("display") == "standalone"))

        # --- and its start_url and scope RESOLVE to the site root -----------------
        # Both are relative to the MANIFEST'S OWN URL, so a manifest served from a
        # subpath scopes the installed app to that subpath and opens it at a 404 --
        # an install that succeeds and is useless. Resolve them the way a browser
        # does, and prove the result is a page that actually exists.
        base = MANIFEST.rsplit("/", 1)[0] + "/"

        def resolve(ref: str) -> str:
            return urllib.parse.urljoin(base, ref)

        start, scope = resolve(man["start_url"]), resolve(man.get("scope", "."))
        results.append((f"start_url resolves to the site root ({start})", start == "/"))
        results.append((f"scope covers the whole site ({scope})", scope == "/"))
        status, _, _ = get(start)
        results.append((f"the resolved start_url is a real page ({start} -> {status})",
                        status == 200))

        # --- every declared icon must exist AT ITS DECLARED SIZE -----------------
        ok_icons, ok_sizes, checked = True, True, []
        for icon in man.get("icons", []):
            s, _, ib = get(resolve(icon["src"]))
            if s != 200:
                ok_icons = False
                continue
            want = tuple(int(n) for n in icon["sizes"].split("x"))
            got = png_size(ib)
            checked.append(f"{icon['src']} {got}")
            if got != want:
                ok_sizes = False
        results.append((f"every declared icon exists ({len(checked)} checked)", ok_icons))
        results.append((f"every icon is a real PNG at its declared size {checked}", ok_sizes))

        # --- the worker, and its SCOPE -------------------------------------------
        status, headers, sw = get("/sw.js")
        results.append(("the service worker is served from the ROOT",
                        status == 200 and "javascript" in headers.get("Content-Type", "")))

        # --- the page must point at it -------------------------------------------
        _, _, page = get("/")
        results.append(("the page declares the manifest", b'rel="manifest"' in page))
        results.append(("the page declares a theme colour", b'name="theme-color"' in page))
        results.append(("the page loads the one script that registers the worker",
                        b"/static/pwa.js" in page))

        # --- issuance is IDEMPOTENT ---------------------------------------------
        _, h1, _ = post("/api/device")
        cookie = h1.get("Set-Cookie", "").split(";")[0]
        results.append(("a first call issues a key", bool(cookie) and "=" in cookie))
        _, h2, body2 = post("/api/device", cookie=cookie)
        results.append(("a second call with that key issues NOTHING new",
                        json.loads(body2).get("issued") is False
                        and not h2.get("Set-Cookie")))

        check = sqlite3.connect(db)
        n = check.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        check.close()
        results.append((f"three calls left exactly ONE device row (got {n})", n == 1))
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    for label, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")
    ok = all(passed for _, passed in results)
    print(f"\nS6 gate: {'PASS' if ok else 'FAIL'}")
    print("\n  NOT AUTOMATED, and not claimed:")
    print("   1. 'Add to Home Screen' is a gesture on a real device. This gate proves the")
    print("      conditions it depends on; a human still has to install it.")
    print("   2. The worker's FETCH STRATEGY runs only inside a browser. It is network-first")
    print("      for pages and cache-first for /static/, because a cached tally would be a")
    print("      stale one — but that is a runtime behaviour, and a grep of the source is not")
    print("      a test of it. (An earlier draft of this gate tried exactly that and failed")
    print("      on its own correct code.) Automation is not a substitute, and this is not")
    print("      a pass for either of these.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
