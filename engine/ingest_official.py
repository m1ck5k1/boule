#!/usr/bin/env python3
"""Boule — ingest the official tally.

    python3 engine/ingest_official.py --db engine/boule.db
    python3 engine/ingest_official.py --db engine/boule.db --add <url> <bill_type> <number>

Walks every action that carries a recorded vote, fetches the roll call from the
source that published it, and stores the tally.

Three things it refuses to do, because each would be a lie:

  1. **Attach a vote to the wrong bill.** The roll call is asked which bill it is
     about, and if the answer does not match the bill we came from, nothing is
     stored. (The clerk's roll138 was found by date while chasing H.R. 2347 and is
     actually H.R. 7959.)
  2. **Turn a parse failure into a zero.** A dead senate.gov path returns an HTML
     error page with HTTP 200; the parser raises instead, and this script counts it
     as an error rather than a tally of 0-0.
  3. **Hide a disagreement.** Re-ingesting a vote that no longer matches what we
     stored is reported, not overwritten. Either the source changed or we mis-parsed,
     and both are worth seeing.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import official  # noqa: E402
import retention  # noqa: E402


def _store(con, congress, bill_type, number, t) -> str:
    """Idempotent insert. Returns: 'new' | 'same' | 'DISAGREES' | 'refused'."""
    ref = t.get("bill_ref")
    if ref != (bill_type.lower(), int(number)):
        return f"refused (vote is about {ref}, not {bill_type.upper()} {number})"

    row = con.execute(
        """SELECT yea, nay, present, not_voting FROM official_tallies
           WHERE congress=? AND bill_type=? AND number=? AND chamber=? AND roll_call=?""",
        (congress, bill_type, number, t["chamber"], t["roll_call"])).fetchone()
    if row:
        if (row[0], row[1], row[2], row[3]) == (t["yea"], t["nay"], t["present"], t["not_voting"]):
            return "same"
        return (f"DISAGREES (stored {row[0]}-{row[1]}, source now says "
                f"{t['yea']}-{t['nay']}) — NOT overwritten")

    con.execute(
        """INSERT INTO official_tallies
           (congress, bill_type, number, chamber, roll_call, question, result, vote_class,
            yea, nay, present, not_voting, members_recorded, source_url, fetched_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (congress, bill_type, number, t["chamber"], t["roll_call"], t["question"], t["result"],
         t["vote_class"], t["yea"], t["nay"], t["present"], t["not_voting"],
         t["members_recorded"], t["source_url"], retention.now_iso()))
    return "new"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--add", nargs=3, action="append", metavar=("URL", "TYPE", "NUMBER"),
                    default=[], help="a vote found by discovery, not by the actions feed")
    a = ap.parse_args()

    con = sqlite3.connect(a.db)
    jobs: list[tuple[int, str, int, str]] = []
    for r in con.execute("""SELECT congress, bill_type, number, record_url FROM actions
                            WHERE has_vote = 1 AND record_url IS NOT NULL AND record_url != ''"""):
        jobs.append((r[0], (r[1] or "").lower(), r[2], r[3]))
    for url, bt, num in a.add:
        jobs.append((119, bt.lower(), int(num), url))

    counts = {"new": 0, "same": 0, "error": 0, "refused": 0, "DISAGREES": 0}
    print(f"  {len(jobs)} recorded vote(s) to fetch\n")
    for congress, bt, num, url in jobs:
        label = f"{congress} {bt.upper()} {num}"
        try:
            t = official.tally_from_url(url)
        except Exception as exc:
            counts["error"] += 1
            print(f"  ERROR   {label}  {type(exc).__name__}: {str(exc)[:90]}")
            continue
        verdict = _store(con, congress, bt, num, t)
        key = "refused" if verdict.startswith("refused") else ("DISAGREES" if verdict.startswith("DISAGREES") else verdict)
        counts[key] = counts.get(key, 0) + 1
        print(f"  {verdict.split(' ')[0].upper():9} {label}  {t['vote_class']:11} "
              f"{t['yea']}-{t['nay']}  rc={t['roll_call']}  {(t['question'] or '')[:44]}")
        if verdict.startswith(("refused", "DISAGREES")):
            print(f"            {verdict}")
    con.commit()

    print()
    print("  --- stored tallies by class:")
    for r in con.execute("""SELECT vote_class, COUNT(*) FROM official_tallies
                            GROUP BY vote_class ORDER BY 2 DESC"""):
        print(f"      {r[0]:12} {r[1]}")
    gaps = con.execute("SELECT COUNT(*) FROM official_tallies WHERE vote_class='of_the_text'").fetchone()[0]
    print(f"\n  >>> {gaps} vote(s) OF THE TEXT — those are the only ones that may carry a gap.")
    print(f"  result: {counts}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
