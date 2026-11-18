"""Poll Congress.gov for recently-updated bills and ingest them.

    python3 engine/poll.py [--congress 119] [--limit 20] [--db engine/boule.db]

Replaces nothing from the historical tools/poll_bills.py: that one scored bills for
fiscal-exploit vectors, which is the retired framing. This one just keeps the
legislative record current.

Cost: 1 request to list, then 2 per bill (metadata + actions). At 5,000 requests
per hour that is nothing; at DEMO_KEY's 10 it is impossible.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import congress  # noqa: E402
from ingest import DEFAULT_DB, connect, ingest  # noqa: E402


def recent_bills(congress_no: int, limit: int = 20) -> list[dict]:
    data = congress.get(f"/bill/{congress_no}", sort="updateDate desc", limit=limit)
    return data.get("bills", [])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--congress", type=int, default=119)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--pace", type=float, default=0.2,
                    help="seconds between bills; be a good citizen")
    args = ap.parse_args()

    if congress.using_demo_key():
        print("WARNING: DEMO_KEY in use — 10 requests/hour. This poll will fail. "
              "Put CONGRESS_API_KEY in .env.")

    listed = recent_bills(args.congress, args.limit)
    print(f"{len(listed)} bill(s) listed as recently updated in the "
          f"{args.congress}th Congress\n")

    con = connect(args.db)
    done = failed = 0
    try:
        for entry in listed:
            bill_type = (entry.get("type") or "").lower()
            number = entry.get("number")
            if not bill_type or number is None:
                continue
            try:
                ingest(con, args.congress, bill_type, number, verbose=False)
                row = con.execute(
                    "SELECT stage, chamber FROM stages WHERE congress=? AND bill_type=? "
                    "AND number=?", (args.congress, bill_type, number)).fetchone()
                print(f"  {entry.get('type','?'):<6} {number:<6} "
                      f"{(row['stage'] if row else '?'):<22} "
                      f"{(entry.get('title') or '')[:60]}")
                done += 1
            except Exception as exc:                      # noqa: BLE001
                failed += 1
                print(f"  {entry.get('type','?')} {number}: FAILED — {exc}")
            time.sleep(args.pace)
    finally:
        con.close()

    print(f"\ningested {done}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
