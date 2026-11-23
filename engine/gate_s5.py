"""S5 gate — the one test that must pass before S5 is called done.

    python3 engine/gate_s5.py

The gate, fixed before the build (ROADMAP §the stage ladder):

  * a key is issued at install, and the store will not let two devices share one
  * the same device key CANNOT record two readings on one (bill, version)
  * `provenance` reads 'device' vs 'anonymous', and the store refuses to mislabel
    either: a device reading with no key, or an anonymous reading carrying one

That is the whole claim of S5: one reading per device, per version of the text.
It also carries two CONTROLS, because a constraint that is too broad passes the
first test and breaks something real:

  * the same device MUST still be able to read a DIFFERENT version of the bill
    (the limit is per-version, not per-device)
  * an anonymous reading MUST remain repeatable (an unkeyed reading is anonymous
    by construction, and Boule cannot dedupe what it cannot identify — S3's
    "changing a vote appends a row" must survive S5 intact)

If this test fails, S5 is not done.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = (HERE / "schema.sql").read_text()

STAMP = "2026-11-19T00:00:00+00:00"
KEY_A = "a" * 64          # a stand-in for sha256(device key)
KEY_B = "b" * 64


def main() -> int:
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    con.execute(
        "INSERT INTO bills (congress, bill_type, number, title, ingested_at) "
        "VALUES (119, 'hr', 2347, 'x', '2026-11-19')"
    )

    results: list[tuple[str, bool]] = []

    def device(device_id: str, key_hash: str) -> None:
        con.execute(
            "INSERT INTO devices (device_id, key_hash, issued_at) VALUES (?, ?, ?)",
            (device_id, key_hash, STAMP),
        )

    def cast(choice: str, version: str, *, device_id: str | None = None) -> None:
        """Record a reading. provenance is derived from the key, never passed in."""
        if device_id is None:
            con.execute(
                "INSERT INTO votes (congress, bill_type, number, version_code, choice, "
                "provenance, voter_key, cast_at) "
                "VALUES (119, 'hr', 2347, ?, ?, 'anonymous', NULL, ?)",
                (version, choice, STAMP),
            )
        else:
            con.execute(
                "INSERT INTO votes (congress, bill_type, number, version_code, choice, "
                "provenance, voter_key, cast_at) "
                "VALUES (119, 'hr', 2347, ?, ?, 'device', ?, ?)",
                (version, choice, device_id, STAMP),
            )

    def refused(fn) -> bool:
        try:
            fn()
            return False
        except sqlite3.IntegrityError:
            return True

    # --- issuance ---------------------------------------------------------------
    device("dev-a", KEY_A)
    results.append(("a device key is issued and stored", con.execute(
        "SELECT COUNT(*) FROM devices").fetchone()[0] == 1))
    results.append(("two devices cannot share one key", refused(lambda: device("dev-b", KEY_A))))
    device("dev-b", KEY_B)

    # --- the claim: one reading per device, per version -------------------------
    cast("yea", "00", device_id="dev-a")
    results.append(("a device reading is recorded as 'device'", con.execute(
        "SELECT provenance FROM votes WHERE voter_key = 'dev-a'").fetchone()[0] == "device"))

    results.append(("the SAME device cannot read the SAME version twice",
                    refused(lambda: cast("nay", "00", device_id="dev-a"))))
    # CONTROL, and the correction of a wrong assumption: the limit is per DEVICE,
    # not per version. A tally that refused a second device would be a tally of one.
    # The first draft of this gate asserted the opposite; the gate caught it.
    cast("nay", "00", device_id="dev-b")
    results.append(("CONTROL: a DIFFERENT device CAN read the same version",
                    con.execute("SELECT COUNT(*) FROM votes WHERE voter_key IS NOT NULL"
                                ).fetchone()[0] == 2))

    # --- controls: the constraint must not be broader than the claim ------------
    cast("nay", "enr", device_id="dev-a")
    results.append(("CONTROL: the same device CAN read a different version",
                    con.execute("SELECT COUNT(*) FROM votes WHERE voter_key = 'dev-a'"
                                ).fetchone()[0] == 2))

    cast("yea", "00")
    cast("nay", "00")
    results.append(("CONTROL: an anonymous reading stays repeatable (S3 intact)",
                    con.execute("SELECT COUNT(*) FROM votes WHERE provenance = 'anonymous'"
                                ).fetchone()[0] == 2))

    # --- the store refuses to mislabel -----------------------------------------
    results.append(("a 'device' reading with no key is refused", refused(lambda: con.execute(
        "INSERT INTO votes (congress, bill_type, number, version_code, choice, provenance, "
        "voter_key, cast_at) VALUES (119, 'hr', 2347, 'rs', 'yea', 'device', NULL, ?)",
        (STAMP,)))))
    results.append(("an 'anonymous' reading carrying a key is refused", refused(lambda: con.execute(
        "INSERT INTO votes (congress, bill_type, number, version_code, choice, provenance, "
        "voter_key, cast_at) VALUES (119, 'hr', 2347, 'rs', 'yea', 'anonymous', 'dev-a', ?)",
        (STAMP,)))))

    # --- both tallies remain, and are still distinguishable --------------------
    per_prov = dict(con.execute(
        "SELECT provenance, COUNT(*) FROM votes GROUP BY provenance").fetchall())
    results.append(("the two tiers are counted separately",
                    per_prov == {"device": 3, "anonymous": 2}))

    for label, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")

    ok = all(passed for _, passed in results)
    print(f"\nS5 gate: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except sqlite3.Error as exc:
        print(f"  FAIL  the store rejected a step S5 requires: {exc}")
        print("\nS5 gate: FAIL")
        raise SystemExit(1)
