"""Gap gate — the licence under which a Δ may be drawn at all.

    python3 engine/gate_gap.py

The gap is the product, so the rules that decide when one may be drawn are the rules
that decide whether this project is telling the truth. Three of them, fixed before the
fix was written:

  1. CLASSIFY     a vote on an AMENDMENT is never `of_the_text`. An amendment vote is
                  the chamber deciding what the text will SAY, not whether it agrees
                  with the bill — so a gap against one subtracts two different
                  questions. (A passage vote still is `of_the_text`; a cloture motion
                  still is not.)
  2. NO GAP       where the only recorded vote is an amendment, the page draws NO gap
                  and says why. This is the live defect: HR 2347's headline Δ14 was
                  measured against "On the Amendment S.Amdt. 6883" (69-27) while the
                  readings were pinned to the as-introduced text.
  3. CONDITIONS   a drawn gap carries its reading count, its 95% interval, and the
                  version the readings are pinned to. A gap without its conditions is
                  a claim, and this project publishes claims it cannot check.

And one CONTROL, because a rule that suppresses everything would pass the first two:

  4. NOISE IS NOT A GAP — at 7 readings against a 96-vote roll call the interval is
                  wider than the difference, so the page says "not yet distinguishable"
                  instead of claiming one. At 400 readings the same code MUST draw a
                  real Δ, or it is not measuring anything.

Exits 0 on pass, 1 on fail.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "web"))

import official  # noqa: E402
import render  # noqa: E402

SCHEMA = (HERE / "schema.sql").read_text()
STAMP = "2026-11-24T00:00:00+00:00"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def fixture(*, amendment_only: bool, readings: int, yea_share: float,
            off_yea: int, off_nay: int):
    """A one-bill world with exactly the votes we say it has."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.execute("INSERT INTO bills (congress, bill_type, number, title, ingested_at) "
                "VALUES (119, 'hr', 2347, 'A Bill', ?)", (STAMP,))
    con.execute("INSERT INTO bill_versions (congress, bill_type, number, version_code, "
                "label, first_seen) VALUES (119, 'hr', 2347, '00', "
                "'Introduced in House', '2025-03-25')")

    yea = round(readings * yea_share)
    for i in range(readings):
        con.execute(
            "INSERT INTO votes (congress, bill_type, number, version_code, choice, "
            "provenance, voter_key, cast_at) VALUES (119, 'hr', 2347, '00', ?, "
            "'anonymous', NULL, ?)", ("yea" if i < yea else "nay", STAMP))

    question = ("On the Amendment S.Amdt. 6883 to H.R. 2347 (No short title on file)"
                if amendment_only else "On Passage of the Bill H.R. 2347")
    con.execute(
        "INSERT INTO official_tallies (congress, bill_type, number, chamber, roll_call, "
        "question, result, vote_class, yea, nay, present, not_voting, members_recorded, "
        "source_url, fetched_at) VALUES (119, 'hr', 2347, 'senate', ?, ?, ?, ?, ?, ?, "
        "0, 0, ?, 'https://example.invalid/rc', ?)",
        ("119-2-267", question, "Agreed to", official.classify(question),
         off_yea, off_nay, off_yea + off_nay, STAMP))
    return con


def main() -> int:
    print("GAP GATE — the licence to draw a Δ\n")

    # --- 1. CLASSIFY -------------------------------------------------------------
    print("1. classification — what a vote is a vote ON")
    cases = [
        ("On the Amendment S.Amdt. 6883 to H.R. 2347 (No short title on file)", "other"),
        ("On agreeing to the amendment", "other"),
        ("On Passage", "of_the_text"),
        ("On Passage of the Bill H.R. 2347", "of_the_text"),
        ("Suspend the Rules and Pass, as Amended", "of_the_text"),
        ("On Cloture on the Motion to Proceed H.R. 2347", "procedural"),
        ("On the Motion to Proceed H.R. 2347", "procedural"),
        ("On the Motion to Table the Motion to Proceed", "procedural"),
    ]
    bad = [f"{q!r} -> {official.classify(q)} (wanted {want})"
           for q, want in cases if official.classify(q) != want]
    check(f"an amendment vote is never `of_the_text` ({len(cases)} questions)",
          not bad, "; ".join(bad))

    # --- 2. NO GAP AGAINST AN AMENDMENT ------------------------------------------
    print("\n2. no gap may be drawn against an amendment")
    con = fixture(amendment_only=True, readings=7, yea_share=0.857, off_yea=69, off_nay=27)
    page = render.bill_page(con, 119, "hr", 2347)
    drew = "&#916;" in page
    said_why = "No recorded vote on the text yet" in page
    check("the page draws NO gap", not drew,
          "" if not drew else "an amendment vote was measured against")
    check("and says why, rather than showing nothing", said_why)
    con.close()

    # --- 3. CONDITIONS TRAVEL WITH A DRAWN GAP -----------------------------------
    print("\n3. a drawn gap carries its conditions")
    con = fixture(amendment_only=False, readings=400, yea_share=0.9, off_yea=69, off_nay=27)
    page = render.bill_page(con, 119, "hr", 2347)
    check("the reading count travels", "400 readings" in page)
    check("the 95% interval travels", "points at 95%" in page)
    check("the version the readings are pinned to travels",
          "v00 (Introduced in House)" in page)
    check("the official roll call and its n travel",
          "119-2-267" in page and "(n=96)" in page)
    check("and it draws a real Δ at that sample size", "public ahead" in page)
    con.close()

    # --- 4. CONTROL: NOISE IS NOT A GAP ------------------------------------------
    print("\n4. control — a gap inside the interval is not claimed")
    con = fixture(amendment_only=False, readings=7, yea_share=0.857, off_yea=69, off_nay=27)
    page = render.bill_page(con, 119, "hr", 2347)
    check("7 readings against a 96-vote roll call reads 'not yet distinguishable'",
          "not yet distinguishable" in page)
    check("and the spoken equivalent carries the same condition",
          page.count("not yet distinguishable") >= 2,
          f"found {page.count('not yet distinguishable')}")
    con.close()

    failed = [n for n, ok, _ in RESULTS if not ok]
    print()
    if failed:
        print(f"GAP GATE: FAIL — {len(failed)} of {len(RESULTS)}")
        for n in failed:
            print(f"  FAIL  {n}")
        return 1
    print(f"GAP GATE: PASS — {len(RESULTS)}/{len(RESULTS)}")
    print("""
  NOT CLAIMED:
   * The version axis is only LABELLED, not enforced. Where the readings are pinned to
     one version and the official vote was on another, the page now says which version
     the readings are on — a reader can see the mismatch, but the code does not yet
     refuse the comparison. That needs official votes attributed to versions, which is
     the /actions feed work.
   * Whether an interval is the right instrument at these sample sizes is a statistical
     judgement, not a test. This gate proves the interval is printed and honoured.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
