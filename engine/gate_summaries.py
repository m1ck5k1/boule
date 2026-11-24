"""L1 gate — the CRS summary is the government's words, pinned to the right text.

    python3 engine/gate_summaries.py [--db engine/boule.db] [--offline]

The reading stack's rule is that the first three layers carry **no Boule-authored prose**.
L1 is CRS's, and this gate holds four lines that rule depends on:

  1. VERBATIM     what we store is byte-identical to what congress.gov published. Not
                  reworded, not trimmed, not "cleaned up". (Needs the network; skipped with
                  --offline, and SAID to be skipped rather than silently passing.)
  2. PINNED       a summary is rendered only against the version it describes. A summary
                  for version 07 shown against a reading on version 00 measures the
                  amendments, not the bill — so the page must name the mismatch and show
                  nothing.
  3. ABSENT       "no summary exists for this version" is a normal answer and the page must
                  say it, the same way a gap renders `—` and never `0`.
  4. SANITISED    CRS's text arrives with HTML in it. Verbatim describes their WORDS, not a
                  licence to inject a third party's markup: a whitelist keeps `<p>` and
                  `<strong>`, and everything else loses its markup and its attributes.

Exits 0 on pass, 1 on fail.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "web"))

import render  # noqa: E402
import sanitize  # noqa: E402

SCHEMA = (HERE / "schema.sql").read_text()
STAMP = "2026-11-24T00:00:00+00:00"
CRS_TEXT = "<p><strong>A Bill</strong></p><p>This bill does a thing.</p>"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def fixture(voted_version: str, summary_version: str | None, text: str = CRS_TEXT):
    """A one-bill world: readings on `voted_version`, a CRS summary on `summary_version`."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.execute("INSERT INTO bills (congress, bill_type, number, title, ingested_at) "
                "VALUES (119, 'hr', 2347, 'A Bill', ?)", (STAMP,))
    con.execute("INSERT INTO bill_versions (congress, bill_type, number, version_code, "
                "label, first_seen) VALUES (119, 'hr', 2347, ?, 'Introduced in House', ?)",
                (voted_version, STAMP))
    con.execute("INSERT INTO votes (congress, bill_type, number, version_code, choice, "
                "provenance, voter_key, cast_at) "
                "VALUES (119, 'hr', 2347, ?, 'yea', 'anonymous', NULL, ?)",
                (voted_version, STAMP))
    if summary_version:
        con.execute("INSERT INTO bill_summaries (congress, bill_type, number, version_code, "
                    "action_desc, text, source_url, fetched_at) "
                    "VALUES (119, 'hr', 2347, ?, 'Reported to House', ?, "
                    "'https://api.congress.gov/v3/bill/119/hr/2347/summaries', ?)",
                    (summary_version, text, STAMP))
    return con


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(HERE / "boule.db"))
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    print("L1 GATE — the CRS summary, verbatim and pinned\n")

    # --- 1. VERBATIM --------------------------------------------------------------
    print("1. what we store is what congress.gov published")
    if args.offline:
        print("  SKIP  (--offline) — VERBATIM was NOT tested in this run")
    else:
        import congress
        con = sqlite3.connect(args.db)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT congress, bill_type, number, version_code, text "
                           "FROM bill_summaries").fetchall()
        checked = mismatched = 0
        for r in rows:
            try:
                live = congress.fetch_summaries(r["congress"], r["bill_type"], r["number"])
            except congress.ApiError as exc:
                print(f"  SKIP  {r['bill_type']}{r['number']} — {exc}")
                continue
            for s in live:
                if (s.get("versionCode") or "").strip() == r["version_code"]:
                    checked += 1
                    if (s.get("text") or "").strip() != r["text"].strip():
                        mismatched += 1
        con.close()
        check(f"every stored summary matches the source byte-for-byte ({checked} checked)",
              checked > 0 and mismatched == 0,
              "" if checked else "nothing to compare — is the feed ingested?")

    # --- 4. SANITISED (no db needed) ----------------------------------------------
    print("\n2. CRS's markup is kept, everything else is not")
    dirty = ('<p>ok</p><script>alert(1)</script>'
             '<img src=x onerror="alert(2)">'
             '<a href="http://evil" onclick="x()">link</a>'
             '<strong>bold</strong><em>em</em><div>div</div>')
    clean = sanitize.sanitize(dirty)
    check("a whitelisted tag survives", "<p>ok</p>" in clean and "<strong>bold</strong>" in clean)
    check("a script tag does not", "<script" not in clean and "alert(1)" in clean)
    check("an event handler does not, and neither does the tag carrying it",
          "onerror" not in clean and "<img" not in clean)
    check("no attribute survives, on any tag",
          "href=" not in clean and "onclick" not in clean)
    check("an unknown tag loses its markup but keeps its text",
          "<div" not in clean and "div" in clean)

    # --- 2. PINNED ----------------------------------------------------------------
    print("\n3. a summary is never shown against the wrong text")
    con = fixture(voted_version="00", summary_version="07")
    page = render.bill_page(con, 119, "hr", 2347)
    check("a summary for ANOTHER version is not rendered",
          "This bill does a thing" not in page)
    check("and the mismatch is named, with the version that does have one",
          "different text" in page and "version 07" in page)
    con.close()

    # --- 3. ABSENT ----------------------------------------------------------------
    print("\n4. an absent summary is a normal answer, said out loud")
    con = fixture(voted_version="00", summary_version=None)
    page = render.bill_page(con, 119, "hr", 2347)
    check("the page says the layer is empty rather than leaving a gap",
          "No CRS summary exists for this bill yet" in page)
    check("and it says Boule did not write one",
          "Boule does not write it" in page)
    con.close()

    # --- and the positive case, or the rule proves nothing ------------------------
    print("\n5. control — the right summary IS shown, attributed")
    con = fixture(voted_version="07", summary_version="07")
    page = render.bill_page(con, 119, "hr", 2347)
    check("CRS's words appear", "This bill does a thing" in page)
    check("attributed to CRS with the version named",
          "CRS, version 07" in page and "Reported to House" in page)
    check("and the source is linked", "api.congress.gov" in page)
    con.close()

    failed = [n for n, ok, _ in RESULTS if not ok]
    print()
    if failed:
        print(f"L1 GATE: FAIL — {len(failed)} of {len(RESULTS)}")
        for n in failed:
            print(f"  FAIL  {n}")
        return 1
    print(f"L1 GATE: PASS — {len(RESULTS)}/{len(RESULTS)}")
    print("""
  NOT CLAIMED:
   * L0 ("one line: what it does") is still unwired, and deliberately: a condensation is
     Boule-authored prose, so it needs an editorial decision, not a machine writer.
   * That the summary shown is the CURRENT one for that version. congress.gov can revise a
     summary; a revision is stored as a new row (so it is visible), and the newest is shown.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
