#!/usr/bin/env python3
"""Delete every retained value that has passed its `retire_after`.

    python3 engine/purge.py --db engine/boule.db [--dry-run]

A silent purge is indistinguishable from a purge that never happened — which is the
same as no purge at all. So this always reports what it removed. **Zero is a valid,
informative answer; silence is not.**

Thin on purpose: it walks every table that carries a `retire_after` column, so adding
a retained table means adding one name here and nothing else.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import retention  # noqa: E402

# Every table that carries a lifetime. The append-only `votes` table is deliberately
# absent: its triggers refuse UPDATE and DELETE, so nothing inside it can expire.
RETAINED_TABLES = ("vote_nets",)


def purge(db: str, *, dry_run: bool = False) -> int:
    stamp = retention.now_iso()
    con = sqlite3.connect(db)
    try:
        # A table that does not exist yet is not an error — it is simply nothing to do.
        existing = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        total = 0
        for table in RETAINED_TABLES:
            if table not in existing:
                print(f"{table}: table absent — nothing to do")
                continue
            if dry_run:
                n = con.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE retire_after < ?", (stamp,)
                ).fetchone()[0]
            else:
                n = con.execute(
                    f"DELETE FROM {table} WHERE retire_after < ?", (stamp,)
                ).rowcount
                con.commit()
            total += n
            print(f"{table}: {n} retired (as of {stamp})" + ("  [dry-run]" if dry_run else ""))
        print(f"TOTAL: {total}")
        return total
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="path to boule.db")
    ap.add_argument("--dry-run", action="store_true", help="report, delete nothing")
    args = ap.parse_args()
    purge(args.db, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
