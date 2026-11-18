"""S3 gate — the one test that must pass before S3 is called done.

    python3 engine/gate_s3.py

The gate, fixed before the build (ROADMAP §the stage ladder):

  * changing a vote ADDS a row and never mutates the old one
  * no UPDATE or DELETE can run on `votes`   (enforced by DB triggers)

That is the whole claim of the ballot box: a tally you can rewrite is not
evidence. If this test fails, S3 is not done.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = (HERE / "schema.sql").read_text()

STAMP = "2026-11-18T00:00:00+00:00"


def main() -> int:
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)

    con.execute(
        "INSERT INTO bills (congress, bill_type, number, title, ingested_at) "
        "VALUES (119, 'hr', 2347, 'x', '2026-11-18')"
    )

    def cast(choice: str) -> None:
        con.execute(
            "INSERT INTO votes "
            "(congress, bill_type, number, version_code, choice, provenance, cast_at) "
            "VALUES (119, 'hr', 2347, '00', ?, 'anonymous', ?)",
            (choice, STAMP),
        )

    results: list[tuple[str, bool]] = []

    # 1. a changed vote is a NEW row, not an edit
    cast("yea")
    after_first = con.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    cast("nay")
    after_second = con.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    results.append(("changing a vote adds a row", after_first == 1 and after_second == 2))

    # 2. the original row is untouched — still 'yea'
    first_choice = con.execute(
        "SELECT choice FROM votes ORDER BY vote_id LIMIT 1"
    ).fetchone()[0]
    results.append(("the earlier vote is never mutated", first_choice == "yea"))

    # 3. and the record cannot be rewritten or erased at all
    for stmt, label in (
        ("UPDATE votes SET choice = 'nay'", "UPDATE is refused"),
        ("DELETE FROM votes", "DELETE is refused"),
    ):
        try:
            con.execute(stmt)
            refused = False
        except sqlite3.IntegrityError:
            refused = True
        results.append((label, refused))

    # 4. a vote is keyed to a VERSION, so two versions are two separate records
    con.execute(
        "INSERT INTO votes "
        "(congress, bill_type, number, version_code, choice, provenance, cast_at) "
        "VALUES (119, 'hr', 2347, 'enr', 'nay', 'anonymous', ?)",
        (STAMP,),
    )
    per_version = dict(
        con.execute(
            "SELECT version_code, COUNT(*) FROM votes GROUP BY version_code"
        ).fetchall()
    )
    results.append(("votes are keyed to (bill, version)", per_version == {"00": 2, "enr": 1}))

    for label, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")

    ok = all(passed for _, passed in results)
    print(f"\nS3 gate: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
