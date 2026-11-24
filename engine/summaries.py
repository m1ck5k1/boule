"""L1 — the CRS summary feed, pinned to the version it describes.

    python3 engine/summaries.py 119 hr 2347          # one bill
    python3 engine/summaries.py --all                # every tracked bill
    python3 engine/summaries.py --report             # what we hold, per bill/version

Why this exists, and why it is the layer that matters:

The reading stack says the first three layers carry **no Boule-authored prose**. L1 is the
government's own summary, and Boule must not write it — an AI summary of a bill is the same
category of artefact this project exists to audit. So this feed stores CRS's words
**verbatim**, attributed, and keyed to the `(bill, version)` pair they describe.

Two consequences that are the whole point of the module:

  * A summary is a property of a VERSION, not of a bill. congress.gov holds a summary for
    only some versions, so "no summary exists for the version being voted on" is a normal
    answer — and it must be reported as one, exactly like a gap that renders `—` and never
    `0`. Attaching a summary of version 07 to a reading on version 00 would measure the
    amendments, not the bill.
  * The text arrives with HTML in it (`<p>`, `<strong>`). It is stored raw and rendered
    through a strict whitelist, because "verbatim" describes CRS's words, not a licence to
    inject a third party's markup into our pages.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import congress  # noqa: E402

DEFAULT_DB = HERE / "boule.db"


def source_url(congress_no: int, bill_type: str, number: int) -> str:
    """Where the words came from. The API path, because that is literally the source."""
    return (f"https://api.congress.gov/v3/bill/{congress_no}/{bill_type}/{number}"
            f"/summaries")


def store(con: sqlite3.Connection, congress_no: int, bill_type: str, number: int,
          rows: list[dict]) -> int:
    """Store what is not already held. Append-only in spirit: a revised summary is a new
    row, so a summary that changed under us is visible rather than silently overwritten."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = source_url(congress_no, bill_type, number)
    added = 0
    for r in rows:
        text = (r.get("text") or "").strip()
        version_code = (r.get("versionCode") or "").strip()
        if not text or not version_code:
            continue
        cur = con.execute(
            "INSERT OR IGNORE INTO bill_summaries (congress, bill_type, number, "
            "version_code, action_desc, text, source_url, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (congress_no, bill_type, number, version_code, r.get("actionDesc"),
             text, url, stamp))
        added += cur.rowcount
    con.commit()
    return added


def ingest(con: sqlite3.Connection, congress_no: int, bill_type: str,
           number: int) -> tuple[int, int]:
    rows = congress.fetch_summaries(congress_no, bill_type, number)
    return len(rows), store(con, congress_no, bill_type, number, rows)


def report(con: sqlite3.Connection) -> None:
    print(f"{'bill':<12} {'ver':<5} {'chars':>6}  action")
    for r in con.execute(
            "SELECT congress, bill_type, number, version_code, action_desc, "
            "length(text) AS n FROM bill_summaries "
            "ORDER BY bill_type, number, version_code"):
        print(f"{r['bill_type']}{r['number']:<8} {r['version_code']:<5} {r['n']:>6}  "
              f"{r['action_desc']}")
    missing = con.execute(
        "SELECT COUNT(*) FROM bills b WHERE NOT EXISTS ("
        "  SELECT 1 FROM bill_summaries s WHERE s.congress = b.congress "
        "    AND s.bill_type = b.bill_type AND s.number = b.number)").fetchone()[0]
    print(f"\nbills with NO summary at all: {missing}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("congress", nargs="?", type=int)
    ap.add_argument("bill_type", nargs="?")
    ap.add_argument("number", nargs="?", type=int)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--all", action="store_true", help="every tracked bill")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    con.executescript((HERE / "schema.sql").read_text())

    if args.report:
        report(con)
        con.close()
        return 0

    if args.all:
        targets = [(r["congress"], r["bill_type"], r["number"]) for r in con.execute(
            "SELECT congress, bill_type, number FROM bills ORDER BY bill_type, number")]
    elif args.congress and args.bill_type and args.number:
        targets = [(args.congress, args.bill_type, args.number)]
    else:
        ap.error("give congress bill_type number, or --all, or --report")

    total_new = 0
    for c, t, n in targets:
        try:
            found, added = ingest(con, c, t, n)
        except congress.ApiError as exc:
            print(f"  {t}{n:<6} FAILED  {exc}")
            continue
        total_new += added
        print(f"  {t}{n:<6} {found} summary/ies at congress.gov, {added} new")
    print(f"\n{total_new} row(s) added")
    report(con)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
