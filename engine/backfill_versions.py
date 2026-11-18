"""Create the INTRODUCED version row for every bill that lacks one.

    python3 engine/backfill_versions.py [path/to/boule.db]

Every bill has exactly one introduced version — Congress.gov versionCode ``00`` —
and we already hold its chamber (``bills.origin_chamber``) and date
(``bills.introduced_on``). So this is derived from data on hand, not invented.

LIMITATION — deliberate, for future-selves
------------------------------------------
Only the *introduced* version is created. Later versions (reported, engrossed,
enrolled) are not ingested yet, so a vote is currently pinned to the bill **as
introduced**. The UI says so. Closing this is a feed to add to the poller — it is
not something to paper over with a default that quietly claims more than we know.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    db = Path(argv[1] if len(argv) > 1 else "engine/boule.db")
    con = sqlite3.connect(db)
    rows = con.execute(
        """
        SELECT b.congress, b.bill_type, b.number, b.origin_chamber, b.introduced_on
          FROM bills b
         WHERE NOT EXISTS (
               SELECT 1 FROM bill_versions v
                WHERE v.congress = b.congress
                  AND v.bill_type = b.bill_type
                  AND v.number = b.number)
        """
    ).fetchall()

    created = 0
    for congress, bill_type, number, chamber, introduced in rows:
        label = f"Introduced in {chamber}" if chamber in ("House", "Senate") else "Introduced"
        con.execute(
            "INSERT INTO bill_versions "
            "(congress, bill_type, number, version_code, label, first_seen) "
            "VALUES (?, ?, ?, '00', ?, ?)",
            (congress, bill_type, number, label, introduced or ""),
        )
        created += 1
    con.commit()

    total = con.execute("SELECT COUNT(*) FROM bill_versions").fetchone()[0]
    print(f"created {created} introduced version row(s); bill_versions now {total}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
