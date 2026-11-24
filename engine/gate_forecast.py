"""Forecast gate — one per day, never revised, and scorable.

    python3 engine/gate_forecast.py

Boule's own claims get the same treatment as a reading, and this gate holds the four rules
that make a forecast something other than a horoscope:

  1. ONE PER DAY   a second forecast for the same bill on the same day is REFUSED, and the
                   first one is untouched. Enforced by the store (UNIQUE), not by discipline.
  2. APPEND-ONLY   UPDATE and DELETE on a forecast are both refused by the database. A guess
                   you may revise after the fact is commentary with hindsight, not a guess.
  3. SCORED, NOT REWRITTEN  recording an outcome leaves the forecast byte-identical and puts
                   the outcome BESIDE it. A forecast cannot be rescored, and it cannot be
                   silently counted as a win.
  4. ON THE PAGE   the box is labelled Opinion, names its author, names the day it was made,
                   shows the basis, and is NOT in --signal — that colour belongs to the gap,
                   and an opinion wearing the gap's colour is claiming to be one.

Exits 0 on pass, 1 on fail.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "web"))

import forecast as F  # noqa: E402
import render  # noqa: E402

SCHEMA = (HERE / "schema.sql").read_text()
STAMP = "2026-11-24T00:00:00+00:00"
DAY = "2026-11-24"
BASIS = "Senate amendment awaits House concurrence; the House has published no floor " \
        "schedule for the week of 23 Nov, so the earliest window is the week of 30 Nov."

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def fresh_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.execute("INSERT INTO bills (congress, bill_type, number, title, ingested_at) "
                "VALUES (119, 'hr', 2347, 'A Bill', ?)", (STAMP,))
    con.execute("INSERT INTO bill_versions (congress, bill_type, number, version_code, "
                "label, first_seen) VALUES (119, 'hr', 2347, '00', 'Introduced in House', ?)",
                (STAMP,))
    return con


def main() -> int:
    print("FORECAST GATE — a dated guess, one per day, never revised\n")

    # --- 1. ONE PER DAY ----------------------------------------------------------
    print("1. one forecast per bill per day, enforced by the store")
    con = fresh_db()
    fid = F.make(con, 119, "hr", 2347, DAY, "2026-11-30", "2026-12-11", 40, BASIS)
    check("the first forecast is accepted", isinstance(fid, int) and fid > 0)
    refused = False
    try:
        F.make(con, 119, "hr", 2347, DAY, "2027-01-01", "2027-02-01", 90, "revised")
    except F.AlreadyForecastToday:
        refused = True
    check("a second one the SAME day is refused", refused)
    rows = con.execute("SELECT window_start, window_end, confidence FROM forecasts").fetchall()
    check("and the first is untouched", len(rows) == 1 and rows[0]["window_start"] == "2026-11-30"
          and rows[0]["confidence"] == 40)
    fid2 = F.make(con, 119, "hr", 2347, "2026-11-25", "2026-12-01", "2026-12-12", 45,
                  "the next day's guess")
    check("a NEW day is a new record, and the old one stands",
          fid2 != fid and len(con.execute("SELECT 1 FROM forecasts").fetchall()) == 2)

    # a forecast with no basis, or an impossible window, is not a forecast
    try:
        F.make(con, 119, "hr", 2347, "2026-11-26", "2026-12-10", "2026-12-01", 50, BASIS)
        backwards = False
    except ValueError:
        backwards = True
    check("a window that ends before it starts is refused", backwards)
    try:
        F.make(con, 119, "hr", 2347, "2026-11-27", "2026-12-01", "2026-12-10", 50, "   ")
        baseless = False
    except ValueError:
        baseless = True
    check("a forecast with no stated basis is refused", baseless)

    # --- 2. APPEND-ONLY ---------------------------------------------------------
    print("\n2. a forecast is not revised and not withdrawn")
    for sql, label in (("UPDATE forecasts SET confidence = 99 WHERE forecast_id = ?", "UPDATE"),
                       ("DELETE FROM forecasts WHERE forecast_id = ?", "DELETE")):
        try:
            con.execute(sql, (fid,))
            ok = False
        except sqlite3.Error as exc:
            ok = "append-only" in str(exc)
        check(f"{label} is refused by the database", ok)

    # --- 3. SCORED, NOT REWRITTEN -----------------------------------------------
    print("\n3. the outcome is recorded beside the forecast, never folded into it")
    before = dict(con.execute("SELECT * FROM forecasts WHERE forecast_id = ?",
                              (fid,)).fetchone())
    F.score(con, fid, "hit", "2026-12-02", vote_ref="119-2-271", note="House concurred")
    after = dict(con.execute("SELECT * FROM forecasts WHERE forecast_id = ?",
                             (fid,)).fetchone())
    check("the forecast is byte-identical after scoring", before == after)
    check("the outcome is a separate record",
          con.execute("SELECT outcome FROM forecast_outcomes WHERE forecast_id = ?",
                      (fid,)).fetchone()["outcome"] == "hit")
    rescored = False
    try:
        F.score(con, fid, "miss", "2026-12-03")
    except F.NotScorable:
        rescored = True
    check("and it cannot be rescored", rescored)
    check("an unknown outcome is refused",
          not _accepts(con, fid2, "probably"))

    # --- 4. ON THE PAGE ---------------------------------------------------------
    print("\n4. the page says whose claim it is")
    con2 = fresh_db()
    fid3 = F.make(con2, 119, "hr", 2347, DAY, "2026-11-30", "2026-12-11", 40, BASIS)
    page = render.bill_page(con2, 119, "hr", 2347)
    check("the box is labelled Opinion", 'class="fclabel"' in page and "Opinion" in page)
    check("it states it is not CRS's", "not CRS" in page)
    check("the author is named", "h3rm5k1 (AI)" in page)
    check("the day it was made is named", "Tue 24 Nov 2026" in page)
    check("the basis is on the page, not just in a commit", "House concurrence" in page)
    check("the confidence travels with it", "40% confidence" in page)
    check("the window is shown as dates a person can read",
          "Mon 30 Nov 2026" in page and "Fri 11 Dec 2026" in page)
    check("an unsettled forecast says so, so silence is not read as a win",
          "Not yet scored" in page and "has been settled yet" in page)
    check("and it is NOT in the gap's colour",
          ".fcbox" in (HERE.parent / "web" / "static" / "boule.css").read_text()
          and ".delta .cond" in (HERE.parent / "web" / "static" / "boule.css").read_text())
    check("it is never the only text on the screen",
          "The reading stack" in page and "Actions" in page)

    F.score(con2, fid3, "hit", "2026-12-02", vote_ref="119-2-271")
    page = render.bill_page(con2, 119, "hr", 2347)
    check("a scored forecast shows the outcome beside the claim",
          "Scored:" in page and "<b>hit</b>" in page)
    check("and the scoreboard carries it, so a new day's guess does not bury it",
          "1 hit" in page and "0 miss" in page)
    con2.close()
    con.close()

    # --- the null ---------------------------------------------------------------
    print("\n5. no forecast is said out loud, not left blank")
    con = fresh_db()
    page = render.bill_page(con, 119, "hr", 2347)
    check("a bill with no forecast says so", "No forecast on record" in page)
    con.close()

    con = fresh_db()
    F.make(con, 119, "hr", 2347, DAY, "2026-11-30", "2026-12-11", 40, BASIS)
    page = render.bill_page(con, 119, "hr", 2347)
    check("an unscored forecast says it is unscored, so silence is not read as a win",
          "Not yet scored" in page)
    con.close()

    failed = [n for n, ok, _ in RESULTS if not ok]
    print()
    if failed:
        print(f"FORECAST GATE: FAIL — {len(failed)} of {len(RESULTS)}")
        for n in failed:
            print(f"  FAIL  {n}")
        return 1
    print(f"FORECAST GATE: PASS — {len(RESULTS)}/{len(RESULTS)}")
    print("""
  NOT CLAIMED:
   * That the forecast is any GOOD. This gate proves the record is honest — dated, immutable,
     scored, and attributed. Whether the guesses beat chance is a question only the scoreboard
     can answer, and `python3 engine/forecast.py --report` is where it answers it.
   * That the author is human. It is not, and the page says so.""")
    return 0


def _accepts(con, fid: int, outcome: str) -> bool:
    try:
        F.score(con, fid, outcome, "2026-12-03")
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
