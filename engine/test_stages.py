"""Unit tests for the stage rule table.

The rule table is the riskiest thing in S1: get it wrong and every bill is
mis-staged, silently. These cases are SYNTHETIC action texts, not captured
payloads — they test the rules, not the API. The live S1 gate is gate_s1.py.

    python3 engine/test_stages.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stages  # noqa: E402

CASES: list[tuple[str, list[dict], str]] = []


def case(name: str, actions: list[dict], expected: str) -> None:
    CASES.append((name, actions, expected))


def a(text: str, date: str = "2026-01-01", source: str = "Library of Congress",
      code: str | None = None) -> dict:
    return {"text": text, "actionDate": date,
            "sourceSystem": {"name": source},
            **({"actionCode": code} if code else {})}


case("introduced", [a("Introduced in House")], "introduced")
case("referred to committee", [a("Referred to the House Committee on Energy and Commerce.")],
     "in_committee")
case("reported", [a("Reported by the Committee on Energy and Commerce.")], "reported")
case("passed the House", [a("Passed/agreed to in House", source="House floor actions")],
     "passed_house")
case("passed the Senate", [a("Passed/agreed to in Senate", source="Senate")], "passed_senate")
case("enacted", [a("Became Public Law No: 119-1.")], "enacted")
case("presented to President", [a("Presented to President.")], "to_president")

# Newest decisive action wins: cloture failed in March, it passed in June.
case(
    "newest wins over older failure",
    [
        a("Motion to invoke cloture on the motion to proceed not invoked.",
          "2026-03-01", "Senate"),
        a("Passed/agreed to in Senate", "2026-06-01", "Senate"),
    ],
    "passed_senate",
)

# The whole reason we do not design on actionCode: Senate actions carry none.
case(
    "Senate action with NO actionCode still stages",
    [a("Passed/agreed to in Senate", "2026-06-01", "Senate", code=None)],
    "passed_senate",
)

# Introduced and referred on the SAME day — the real 119 HR 10983 case that made
# the gate fail. Order in the array must not matter; the advanced stage wins.
case(
    "same date: referral outranks introduction",
    [
        a("Referred to the House Committee on Energy and Commerce.", "2026-11-10",
          "House floor actions", code="H11100"),
        a("Introduced in House", "2026-11-10", "Library of Congress", code="Intro-H"),
    ],
    "in_committee",
)

# ...and the reverse array order must give the same answer.
case(
    "same date: order-independent",
    [
        a("Introduced in House", "2026-11-10", "Library of Congress", code="Intro-H"),
        a("Referred to the House Committee on Energy and Commerce.", "2026-11-10",
          "House floor actions", code="H11100"),
    ],
    "in_committee",
)

# The NDAA case, in full. A failed cloture is a vote on whether to PROCEED; the
# Senate reconsidered and kept pushing. Staging this 'failed' was a real bug.
case(
    "a failed cloture does not kill a bill (S 4784)",
    [
        a("Placed on Senate Legislative Calendar under General Orders. Calendar No. 436.",
          "2026-06-15", "Senate"),
        a("Cloture motion on the motion to proceed to the measure not invoked in Senate.",
          "2026-07-14", "Senate"),
        a("Motion by Senator Thune to reconsider the vote by which cloture on the motion "
          "to proceed was not invoked.", "2026-07-14", "Senate"),
        a("Motion to proceed to consideration of measure made in Senate.", "2026-07-27",
          "Senate"),
    ],
    "reported",
)

# ...but a failure OF THE MEASURE is terminal and must still register.
case(
    "a measure that fails of passage is failed",
    [a("On passage Failed by the Yeas and Nays (2/3 required).", "2026-05-01",
       "House floor actions")],
    "failed",
)

# Shape-independence, and the bicameral rule together: the API hands derive()
# camelCase, a DB row hands it snake_case, and in both the FURTHEST milestone wins
# (the bill passed the House; the Senate-calendar entry is where it sits, not a
# regression). If only one shape were understood, every date would read as ''.
_DB_SHAPE = [
    {"text": "Passed/agreed to in House: On motion to suspend the rules.",
     "action_date": "2026-04-27", "source_name": "House floor actions"},
    {"text": "Read the second time. Placed on Senate Legislative Calendar under General Orders.",
     "action_date": "2026-07-14", "source_name": "Senate"},
]
case("DB-shaped rows (snake_case): furthest milestone wins", _DB_SHAPE, "passed_house")

_API_SHAPE = [
    {"text": "Passed/agreed to in House: On motion to suspend the rules.",
     "actionDate": "2026-04-27", "sourceSystem": {"name": "House floor actions"}},
    {"text": "Read the second time. Placed on Senate Legislative Calendar under General Orders.",
     "actionDate": "2026-07-14", "sourceSystem": {"name": "Senate"}},
]
case("API-shaped rows (camelCase): same answer", _API_SHAPE, "passed_house")

# Non-decisive chatter must not match anything.
case("unknown when nothing is decisive",
     [a("Held at the desk.", "2026-06-01")], "in_committee")
case("truly unknown text",
     [a("Some procedural noise nobody defined.", "2026-06-01")], "unknown")


def main() -> int:
    failures = 0
    for name, actions, expected in CASES:
        got = stages.derive(actions)["stage"]
        ok = got == expected
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: expected {expected!r}, got {got!r}")

    # the ladder ordering must be self-consistent
    ranks = [stages.rank(s) for s in stages.STAGES]
    ok = ranks == sorted(ranks) and len(set(ranks)) == len(ranks)
    failures += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] ladder ranks strictly increasing: {ranks}")

    # bicameral: reached the House floor, now sitting in the Senate — the stage is
    # the milestone, current_chamber is where it actually is
    d = stages.derive(_DB_SHAPE)
    ok = d["stage"] == "passed_house" and d.get("current_chamber") == "senate"
    failures += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] bicameral split: milestone={d['stage']!r} "
          f"now_in={d.get('current_chamber')!r} (want 'passed_house'/'senate')")

    # a terminal action must NOT be masked by an earlier success
    d = stages.derive([
        {"text": "Passed/agreed to in House", "action_date": "2026-04-27",
         "source_name": "House floor actions"},
        {"text": "On passage Failed by the Yeas and Nays.", "action_date": "2026-06-01",
         "source_name": "Senate"},
    ])
    ok = d["stage"] == "failed"
    failures += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] terminal action beats earlier success: "
          f"got {d['stage']!r} (want 'failed')")

    print(f"\nSTAGE RULES: {len(CASES) + 3 - failures}/{len(CASES) + 3} — "
          + ("PASS" if failures == 0 else f"FAIL ({failures})"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
