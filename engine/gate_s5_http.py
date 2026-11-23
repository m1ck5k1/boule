"""S5 gate, over HTTP — the claim tested the way it will actually be exercised.

    python3 engine/gate_s5_http.py

`gate_s5.py` proves the database refuses a second reading. This proves the SERVER
does: it starts the real service against a throwaway database and drives the real
endpoints, because a rule that is true in the schema and false in the running
server is not true.

  * POST /api/device issues a key and sets the cookie
  * a reading with that cookie is recorded as 'device'
  * the SAME cookie is REFUSED (409) on the same (bill, version)
  * no cookie is a legitimate anonymous reading, and stays repeatable
  * an UNKNOWN key is refused (400) rather than quietly filed as anonymous
  * the database stores a HASH of the key, never the key

Exits 0 on pass, 1 on fail.
"""
from __future__ import annotations

import http.client
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PORT = 8199
BASE = f"127.0.0.1:{PORT}"
STAMP = "2026-11-19T00:00:00+00:00"


def post(path: str, form: dict, cookie: str | None = None):
    body = urllib.parse.urlencode(form)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if cookie:
        headers["Cookie"] = cookie
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=8)
    try:
        conn.request("POST", path, body=body, headers=headers)
        r = conn.getresponse()
        payload = r.read()
        return r.status, dict(r.getheaders()), payload
    finally:
        conn.close()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="boule-s5-"))
    db = tmp / "gate.db"
    con = sqlite3.connect(db)
    con.executescript((HERE / "schema.sql").read_text())
    con.execute("INSERT INTO bills (congress, bill_type, number, title, ingested_at) "
                "VALUES (119, 'hr', 2347, 'A real bill', '2026-11-19')")
    con.commit()
    con.close()

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "web" / "server.py"), "--port", str(PORT),
         "--bind", "127.0.0.1", "--db", str(db)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

        vote = {"congress": "119", "bill_type": "hr", "number": "2347",
                "version_code": "00", "choice": "yea", "confirm": "1"}
        results: list[tuple[str, bool]] = []

        # --- issuance -----------------------------------------------------------
        status, headers, _ = post("/api/device", {})
        set_cookie = headers.get("Set-Cookie", "")
        results.append(("POST /api/device issues a key", status == 200 and "=" in set_cookie))
        device_cookie = set_cookie.split(";")[0]
        results.append(("the cookie is HttpOnly + Secure + SameSite=Lax",
                        all(f in set_cookie for f in ("HttpOnly", "Secure", "SameSite=Lax"))))

        # --- the claim ----------------------------------------------------------
        status, _, _ = post("/api/vote", vote, cookie=device_cookie)
        results.append(("a keyed reading is accepted", status == 302))
        status, _, body = post("/api/vote", vote, cookie=device_cookie)
        results.append(("the SAME device is REFUSED on the same (bill, version)",
                        status == 409))
        results.append(("and the refusal is a readable page, not a bare error",
                        b"Already recorded" in body))

        # --- anonymous is still a real tier -------------------------------------
        s1, _, _ = post("/api/vote", vote)
        s2, _, _ = post("/api/vote", vote)
        results.append(("CONTROL: an anonymous reading is repeatable (S3 intact)",
                        s1 == 302 and s2 == 302))

        # --- an unknown key is refused, not ignored -----------------------------
        status, _, _ = post("/api/vote", vote, cookie="boule_device=not-a-real-key")
        results.append(("an UNKNOWN key is refused rather than filed as anonymous",
                        status == 400))

        # --- what actually landed ------------------------------------------------
        check = sqlite3.connect(db)
        check.row_factory = sqlite3.Row
        per = dict(check.execute("SELECT provenance, COUNT(*) FROM votes GROUP BY provenance"))
        results.append(("the store holds 1 device reading and 2 anonymous",
                        per == {"device": 1, "anonymous": 2}))

        row = check.execute("SELECT voter_key FROM votes WHERE provenance = 'device'").fetchone()
        dev = check.execute("SELECT device_id, key_hash FROM devices").fetchone()
        results.append(("the reading points at a device_id, not a key",
                        row["voter_key"] == dev["device_id"]))
        results.append(("the database stores a HASH of the key, never the key",
                        dev["key_hash"] not in device_cookie and len(dev["key_hash"]) == 64))
        check.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    for label, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")
    ok = all(passed for _, passed in results)
    print(f"\nS5 HTTP gate: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
