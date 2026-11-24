"""The forecast — a dated, immutable, scorable guess about when the vote lands.

    python3 engine/forecast.py 119 hr 2347 --start 2026-11-30 --end 2026-12-11 \\
        --confidence 40 --basis "Senate amendment awaits House concurrence; ..."
    python3 engine/forecast.py --report
    python3 engine/forecast.py --score 1 --outcome miss --on 2026-12-15 --note "..."

THE RULE: **one forecast per bill per day, and it is never revised.** The store enforces it —
a UNIQUE constraint for the day, triggers against UPDATE and DELETE — because a rule held only
by the author's discipline is not a rule. A second attempt on the same day is REFUSED and says
so, rather than being silently swallowed.

Why this shape, and why it is the project's own thesis turned inward:

Boule exists to make the difference between what is claimed and what happened visible. A
forecast that can be edited after the event is not a forecast, it is commentary with the
benefit of hindsight — so Boule's own claims get exactly the treatment it gives a reading: the
record stands as written, and a *separate* record says what became of it. Scoring is the only
thing that separates a forecast from a horoscope, so an unscored forecast is reported as
unscored rather than quietly counted as a win.

A forecast is OPINION, and the page must say so: it is Boule's, not CRS's, and it is never the
only thing on the screen (DESIGN.md §the reading stack).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE / "boule.db"

AUTHOR = "h3rm5k1 (AI)"
METHOD_VERSION = "boule-forecast/1"


class AlreadyForecastToday(RuntimeError):
    """The one-a-day rule. Raised, never swallowed: a refusal must be visible."""


class NotScorable(RuntimeError):
    """A forecast that does not exist, or one already scored."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make(con: sqlite3.Connection, congress: int, bill_type: str, number: int,
         made_on: str, window_start: str, window_end: str, confidence: int,
         basis: str, author: str = AUTHOR) -> int:
    """Record today's forecast. Refuses a second one for the same bill on the same day."""
    if window_start > window_end:
        raise ValueError(f"window_start {window_start} is after window_end {window_end}")
    if not (0 <= confidence <= 100):
        raise ValueError(f"confidence {confidence} is not a percentage")
    if not basis.strip():
        raise ValueError("a forecast with no stated basis is a horoscope")
    try:
        cur = con.execute(
            "INSERT INTO forecasts (congress, bill_type, number, made_on, window_start, "
            "window_end, confidence, basis, author, method_version, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (congress, bill_type, number, made_on, window_start, window_end,
             confidence, basis.strip(), author, METHOD_VERSION, _now()))
    except sqlite3.IntegrityError as exc:
        raise AlreadyForecastToday(
            f"{bill_type}{number} already has a forecast for {made_on}. "
            f"One per bill per day — the record stands.") from exc
    con.commit()
    assert cur.lastrowid is not None
    return int(cur.lastrowid)


def latest(con: sqlite3.Connection, congress: int, bill_type: str, number: int):
    """The most recent forecast for a bill, with its outcome if one has been recorded."""
    return con.execute(
        "SELECT f.*, o.outcome, o.resolved_on, o.vote_ref, o.note AS outcome_note "
        "  FROM forecasts f LEFT JOIN forecast_outcomes o USING (forecast_id) "
        " WHERE f.congress = ? AND f.bill_type = ? AND f.number = ? "
        " ORDER BY f.made_on DESC, f.forecast_id DESC LIMIT 1",
        (congress, bill_type, number)).fetchone()


def history(con: sqlite3.Connection, congress: int, bill_type: str, number: int):
    return con.execute(
        "SELECT f.*, o.outcome, o.resolved_on FROM forecasts f "
        "LEFT JOIN forecast_outcomes o USING (forecast_id) "
        "WHERE f.congress = ? AND f.bill_type = ? AND f.number = ? "
        "ORDER BY f.made_on DESC", (congress, bill_type, number)).fetchall()


def tally(con: sqlite3.Connection, congress: int, bill_type: str, number: int) -> dict:
    """The scoreboard for one bill — because a single unscored guess shows nothing.

    The page shows the LATEST forecast, so without this the moment a new day's guess is
    written, yesterday's outcome disappears from view. Accountability that vanishes when it
    becomes interesting is not accountability.
    """
    row = con.execute(
        "SELECT COUNT(*) AS total, "
        "       SUM(CASE WHEN o.outcome = 'hit'  THEN 1 ELSE 0 END) AS hits, "
        "       SUM(CASE WHEN o.outcome = 'miss' THEN 1 ELSE 0 END) AS misses, "
        "       SUM(CASE WHEN o.outcome = 'void' THEN 1 ELSE 0 END) AS voids, "
        "       SUM(CASE WHEN o.outcome IS NULL   THEN 1 ELSE 0 END) AS unscored "
        "  FROM forecasts f LEFT JOIN forecast_outcomes o USING (forecast_id) "
        " WHERE f.congress = ? AND f.bill_type = ? AND f.number = ?",
        (congress, bill_type, number)).fetchone()
    return {k: (row[k] or 0) for k in row.keys()} if row else {}


def score(con: sqlite3.Connection, forecast_id: int, outcome: str, resolved_on: str,
          vote_ref: str | None = None, note: str | None = None) -> int:
    """Record what became of a forecast. Never edits the forecast itself."""
    if outcome not in ("hit", "miss", "void"):
        raise ValueError(f"outcome must be hit/miss/void, not {outcome!r}")
    row = con.execute("SELECT forecast_id FROM forecasts WHERE forecast_id = ?",
                      (forecast_id,)).fetchone()
    if row is None:
        raise NotScorable(f"no forecast {forecast_id}")
    if con.execute("SELECT 1 FROM forecast_outcomes WHERE forecast_id = ?",
                   (forecast_id,)).fetchone():
        raise NotScorable(f"forecast {forecast_id} is already scored; scoring is not a redo")
    cur = con.execute(
        "INSERT INTO forecast_outcomes (forecast_id, resolved_on, outcome, vote_ref, note, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (forecast_id, resolved_on, outcome, vote_ref, note, _now()))
    con.commit()
    return int(cur.lastrowid)


def report(con: sqlite3.Connection) -> None:
    rows = con.execute(
        "SELECT f.forecast_id, f.bill_type, f.number, f.made_on, f.window_start, "
        "f.window_end, f.confidence, o.outcome "
        "  FROM forecasts f LEFT JOIN forecast_outcomes o USING (forecast_id) "
        " ORDER BY f.made_on DESC, f.number").fetchall()
    if not rows:
        print("no forecasts on record")
        return
    print(f"{'id':>3}  {'bill':<9} {'made':<11} {'window':<24} {'conf':>4}  outcome")
    for r in rows:
        win = f"{r['window_start']} → {r['window_end']}"
        print(f"{r['forecast_id']:>3}  {r['bill_type']}{r['number']:<7} {r['made_on']:<11} "
              f"{win:<24} {r['confidence']:>3}%  {r['outcome'] or 'unscored'}")
    scored = [r for r in rows if r["outcome"] in ("hit", "miss")]
    hits = [r for r in scored if r["outcome"] == "hit"]
    print(f"\n{len(rows)} forecast(s), {len(scored)} scored, "
          f"{len(rows) - len(scored)} unscored")
    if scored:
        print(f"hit rate: {len(hits)}/{len(scored)} = {round(100 * len(hits) / len(scored))}%")
    else:
        print("hit rate: unknown — nothing scored yet, and an unscored forecast is not a win")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("congress", nargs="?", type=int)
    ap.add_argument("bill_type", nargs="?")
    ap.add_argument("number", nargs="?", type=int)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--start", help="earliest plausible vote date")
    ap.add_argument("--end", help="latest plausible vote date")
    ap.add_argument("--confidence", type=int)
    ap.add_argument("--basis")
    ap.add_argument("--on", help="the day the forecast is made (default: today)")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--score", type=int, metavar="FORECAST_ID")
    ap.add_argument("--outcome", choices=("hit", "miss", "void"))
    ap.add_argument("--vote-ref")
    ap.add_argument("--note")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    con.executescript((HERE / "schema.sql").read_text())

    if args.report:
        report(con)
        con.close()
        return 0

    if args.score:
        if not args.outcome or not args.on:
            ap.error("--score needs --outcome and --on")
        try:
            score(con, args.score, args.outcome, args.on, args.vote_ref, args.note)
        except NotScorable as exc:
            print(f"REFUSED: {exc}")
            con.close()
            return 1
        print(f"scored forecast {args.score}: {args.outcome}")
        con.close()
        return 0

    if not (args.congress and args.bill_type and args.number):
        ap.error("give congress bill_type number, or --report, or --score N")
    if not (args.start and args.end and args.confidence is not None and args.basis):
        ap.error("a forecast needs --start, --end, --confidence and --basis")

    try:
        fid = make(con, args.congress, args.bill_type, args.number,
                   args.on or date.today().isoformat(), args.start, args.end,
                   args.confidence, args.basis)
    except AlreadyForecastToday as exc:
        print(f"REFUSED: {exc}")
        con.close()
        return 1
    print(f"forecast {fid} recorded for {args.bill_type}{args.number} "
          f"({args.start} → {args.end}, {args.confidence}%)")
    report(con)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
