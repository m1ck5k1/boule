"""Ingest one bill from Congress.gov into SQLite.

    python3 engine/ingest.py 119 hr 10983 [--db engine/boule.db]

Idempotent: re-running adds only genuinely new actions (append-only), and refreshes
the derived stage.
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
import stages  # noqa: E402

DEFAULT_DB = HERE / "boule.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _name(value):
    """congress.gov sometimes returns a string, sometimes {"name": ...}."""
    if isinstance(value, dict):
        return value.get("name")
    return value


def connect(db_path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
    return con


def ingest(con: sqlite3.Connection, congress_no: int, bill_type: str,
           number: int, verbose: bool = True) -> dict:
    bt = bill_type.lower()
    bill = congress.fetch_bill(congress_no, bt, number)
    actions = congress.fetch_actions(congress_no, bt, number)
    ts = now_iso()
    latest = bill.get("latestAction") or {}

    con.execute(
        """
        INSERT INTO bills (congress, bill_type, number, title, origin_chamber,
                           introduced_on, latest_action, latest_action_date,
                           update_date, ingested_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(congress, bill_type, number) DO UPDATE SET
          title              = excluded.title,
          latest_action      = excluded.latest_action,
          latest_action_date = excluded.latest_action_date,
          update_date        = excluded.update_date,
          ingested_at        = excluded.ingested_at
        """,
        (congress_no, bt, number, bill.get("title"), _name(bill.get("originChamber")),
         bill.get("introducedDate"), latest.get("text"), latest.get("actionDate"),
         bill.get("updateDate"), ts),
    )

    new_actions = 0
    for a in actions:
        votes = a.get("recordedVotes") or []
        first_vote = votes[0] if votes else None
        cur = con.execute(
            """
            INSERT OR IGNORE INTO actions
              (congress, bill_type, number, action_date, action_code, source_system,
               source_name, action_type, text, has_vote, record_url)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (congress_no, bt, number, a.get("actionDate"), a.get("actionCode"),
             (a.get("sourceSystem") or {}).get("code"),
             (a.get("sourceSystem") or {}).get("name"),
             a.get("type"), a.get("text") or "",
             1 if first_vote else 0, (first_vote or {}).get("url")),
        )
        new_actions += cur.rowcount

    derived = stages.derive(actions)
    deciding_id = None
    if derived["basis"]:
        row = con.execute(
            """SELECT action_id FROM actions
                WHERE congress=? AND bill_type=? AND number=? AND text=?
                ORDER BY action_date DESC LIMIT 1""",
            (congress_no, bt, number, derived["basis"]),
        ).fetchone()
        deciding_id = row["action_id"] if row else None

    con.execute(
        """
        INSERT INTO stages (congress, bill_type, number, stage, chamber,
                            determined_by, basis, computed_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(congress, bill_type, number) DO UPDATE SET
          stage=excluded.stage, chamber=excluded.chamber,
          determined_by=excluded.determined_by, basis=excluded.basis,
          computed_at=excluded.computed_at
        """,
        (congress_no, bt, number, derived["stage"], derived["chamber"],
         deciding_id, derived["basis"], ts),
    )
    con.commit()

    result = {
        "bill": f"{congress_no} {bt} {number}",
        "title": bill.get("title"),
        "actions_fetched": len(actions),
        "actions_new": new_actions,
        "latest_action": latest.get("text"),
        "stage": derived["stage"],
        "chamber": derived["chamber"],
        "determined_by_action": derived["basis"],
        "basis_date": derived["date"],
        "used_demo_key": congress.using_demo_key(),
    }
    if verbose:
        print(f"{result['bill']}: {result['title']}")
        print(f"  actions fetched {result['actions_fetched']} "
              f"(new: {result['actions_new']})")
        print(f"  congress.gov latestAction : {result['latest_action']}")
        print(f"  derived stage             : {result['stage']} "
              f"({result['chamber']}) on {result['basis_date']}")
        print(f"  decided by                : {result['determined_by_action']}")
        if result["used_demo_key"]:
            print("  NOTE: DEMO_KEY in use — heavily throttled, fine for a gate only")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("congress", type=int)
    ap.add_argument("bill_type")
    ap.add_argument("number", type=int)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()
    con = connect(args.db)
    try:
        ingest(con, args.congress, args.bill_type, args.number)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
