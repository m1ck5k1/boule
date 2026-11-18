"""S1 gate — the test that decides whether S1 is done.

Pass criteria (fixed before the build, per ROADMAP.md):

  1. COVERAGE   every action the API reports for the bill is stored
  2. ORDER      actions are stored and sort chronologically
  3. STAGE      the derived stage is a known stage, not 'unknown'
  4. CONSISTENT the derived stage does not contradict congress.gov's latestAction
  5. APPEND-ONLY an UPDATE and a DELETE on `actions` are both REFUSED by the trigger
  6. PROVENANCE every action row records its source system

Exit 0 only if all six pass. Costs one API request.

    python3 engine/gate_s1.py 119 hr 10983
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import congress  # noqa: E402
import stages  # noqa: E402
from ingest import DEFAULT_DB, connect  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("congress", type=int)
    ap.add_argument("bill_type")
    ap.add_argument("number", type=int)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    c, bt, n = args.congress, args.bill_type.lower(), args.number
    con = connect(args.db)

    bill = congress.fetch_bill(c, bt, n)
    api_count = (bill.get("actions") or {}).get("count")
    latest = (bill.get("latestAction") or {}).get("text")
    print(f"\nS1 gate — {c} {bt} {n}: {bill.get('title')}")
    print(f"congress.gov says: actions.count={api_count}, latestAction={latest!r}\n")

    # 1. COVERAGE
    db_count = con.execute(
        "SELECT COUNT(*) FROM actions WHERE congress=? AND bill_type=? AND number=?",
        (c, bt, n)).fetchone()[0]
    check("COVERAGE", api_count is not None and db_count == api_count,
          f"stored {db_count}, api reports {api_count}")

    # 2. ORDER
    dates = [r[0] for r in con.execute(
        "SELECT action_date FROM actions WHERE congress=? AND bill_type=? AND number=? "
        "ORDER BY action_id", (c, bt, n))]
    check("ORDER", dates == sorted(dates),
          f"{len(dates)} actions, {dates[0] if dates else '-'} → {dates[-1] if dates else '-'}")

    # 3. STAGE
    row = con.execute(
        "SELECT stage, chamber, basis, determined_by FROM stages "
        "WHERE congress=? AND bill_type=? AND number=?", (c, bt, n)).fetchone()
    stage = row["stage"] if row else None
    check("STAGE", stage in stages.STAGES or stage in stages.TERMINAL,
          f"stage={stage} chamber={row['chamber'] if row else '-'}")

    # 4. CONSISTENT — the newest decisive action must not contradict the stage
    hit = stages.match(latest or "")
    if hit is None:
        check("CONSISTENT", True, f"latestAction {latest!r} is not decisive; no contradiction")
    else:
        check("CONSISTENT", hit[0] == stage,
              f"latestAction implies {hit[0]!r}, derived {stage!r}")

    # 5. APPEND-ONLY — try to break it
    refused = []
    for sql in ("UPDATE actions SET text='tampered' WHERE congress=? AND bill_type=? AND number=?",
                "DELETE FROM actions WHERE congress=? AND bill_type=? AND number=?"):
        try:
            con.execute(sql, (c, bt, n))
            con.rollback()
        except sqlite3.Error as exc:
            refused.append(str(exc))
            con.rollback()
    check("APPEND-ONLY", len(refused) == 2,
          "UPDATE and DELETE both refused" if len(refused) == 2
          else f"only {len(refused)}/2 refused — the record is mutable")

    # 6. PROVENANCE
    missing = con.execute(
        "SELECT COUNT(*) FROM actions WHERE congress=? AND bill_type=? AND number=? "
        "AND source_system IS NULL", (c, bt, n)).fetchone()[0]
    check("PROVENANCE", missing == 0, f"{missing} actions with no source_system")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)

    print("\nEvidence trail — the actions the stage was derived from "
          "(compare against congress.gov):")
    for r in con.execute(
            "SELECT action_date, action_type, source_name, text FROM actions "
            "WHERE congress=? AND bill_type=? AND number=? "
            "ORDER BY action_date DESC, action_id DESC LIMIT 8", (c, bt, n)):
        print(f"  {r['action_date']}  [{r['source_name']}]  {(r['text'] or '')[:88]}")

    con.close()
    print(f"\nS1 GATE: {passed}/{total} — " + ("PASS" if passed == total else "FAIL"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
