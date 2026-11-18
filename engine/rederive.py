"""Recompute every stage from the stored actions. No network.

    python3 engine/rederive.py [--db engine/boule.db] [--show]

This is the payoff of keeping `actions` append-only: the derived stage is a pure
function of the raw record, so a rule fix is a recomputation rather than a
re-crawl. Run this after changing stages.py.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import stages  # noqa: E402
from ingest import DEFAULT_DB, connect  # noqa: E402


def rederive(db_path: str, show: bool = False) -> list[tuple]:
    con = connect(db_path)
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    changed: list[tuple] = []

    bills = con.execute(
        "SELECT congress, bill_type, number FROM bills ORDER BY congress, bill_type, number"
    ).fetchall()

    for bill in bills:
        key = (bill["congress"], bill["bill_type"], bill["number"])
        rows = con.execute(
            "SELECT action_id, action_date, text, source_name FROM actions "
            "WHERE congress=? AND bill_type=? AND number=? ORDER BY action_date",
            key,
        ).fetchall()

        before = con.execute(
            "SELECT stage FROM stages WHERE congress=? AND bill_type=? AND number=?",
            key).fetchone()
        derived = stages.derive([dict(r) for r in rows])

        deciding_id = None
        if derived["basis"]:
            hit = con.execute(
                "SELECT action_id FROM actions WHERE congress=? AND bill_type=? "
                "AND number=? AND text=? LIMIT 1", (*key, derived["basis"])).fetchone()
            deciding_id = hit["action_id"] if hit else None

        con.execute(
            """
            INSERT INTO stages (congress, bill_type, number, stage, chamber,
                                determined_by, basis, current_chamber, current_basis,
                                computed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(congress, bill_type, number) DO UPDATE SET
              stage=excluded.stage, chamber=excluded.chamber,
              determined_by=excluded.determined_by, basis=excluded.basis,
              current_chamber=excluded.current_chamber,
              current_basis=excluded.current_basis,
              computed_at=excluded.computed_at
            """,
            (*key, derived["stage"], derived["chamber"], deciding_id,
             derived["basis"], derived.get("current_chamber"),
             derived.get("current_basis"), ts),
        )

        was = before["stage"] if before else None
        if was != derived["stage"]:
            changed.append((f"{key[0]} {key[1]} {key[2]}", was, derived["stage"]))
            if show:
                print(f"  {key[0]} {key[1]} {key[2]}: {was} → {derived['stage']}")

    con.commit()
    con.close()
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    changed = rederive(args.db, show=True)
    print(f"\n{len(changed)} stage(s) changed")


    # what we ended up with
    con = sqlite3.connect(args.db)
    for stage, n in con.execute(
            "SELECT stage, COUNT(*) FROM stages GROUP BY stage ORDER BY 2 DESC"):
        print(f"  {stage:<14} {n}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
