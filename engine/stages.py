"""Derive a bill's stage from its actions.

Design rule, from the Congress.gov assessment: build on `type`, `sourceSystem` and
the action TEXT — never on `actionCode`. Congress.gov publishes an authoritative
code list for Library of Congress actions only (sourceSystem 9); House codes have
no published list, and Senate actions carry no actionCode at all. Designing on
actionCode would silently mis-stage every Senate action.

Scanning is newest-first, so the most recent decisive action wins: a bill that
failed cloture in March and passed in June reports "passed", not "failed".
"""
from __future__ import annotations

# Ordered from most to least advanced.
STAGES = [
    "introduced",
    "in_committee",
    "reported",
    "passed_house",
    "passed_senate",
    "resolving_differences",
    "to_president",
    "enacted",
]

TERMINAL = ["failed", "vetoed"]

# (stage, chamber, phrases) — newest-first match, first hit wins.
RULES: list[tuple[str, str | None, tuple[str, ...]]] = [
    ("enacted", "both", (
        "became public law", "signed by president",
    )),
    ("vetoed", None, (
        "vetoed by president", "veto message",
    )),
    ("to_president", "both", (
        "presented to president",
    )),
    ("resolving_differences", "both", (
        "conference report", "resolving differences",
        "agreed to house amendment", "agreed to senate amendment",
        "concurred in senate amendment", "concurred in house amendment",
    )),
    ("passed_senate", "senate", (
        "passed/agreed to in senate", "passed senate", "passed, senate",
    )),
    ("passed_house", "house", (
        "passed/agreed to in house", "passed house", "passed, house",
    )),
    # `failed` must mean THE MEASURE failed, not that a procedural motion failed.
    # A failed cloture is a vote on whether to proceed, and the Senate routinely
    # reconsiders — S 4784 (NDAA FY2027) was staged 'failed' this way while still
    # being actively pursued. Such actions change nothing, so they match no rule
    # and the bill keeps its previous stage. Also deliberately absent: "motion to
    # table" and "reconsider", both of which can revive a bill.
    ("failed", None, (
        "failed of passage", "failed to pass", "failed passage",
        "on passage failed", "failed on passage",
    )),
    ("reported", "house", (
        "reported by", "ordered to be reported", "placed on the union calendar",
        "placed on the house calendar", "reported (",
    )),
    ("reported", "senate", (
        "placed on senate legislative calendar", "reported by",
    )),
    ("in_committee", None, (
        "referred to", "received in the senate", "held at the desk",
    )),
    ("introduced", None, (
        "introduced in",
    )),
]


def _date_of(action: dict) -> str:
    """Accept both shapes. The API returns `actionDate`; a DB row returns
    `action_date`. Silently treating a missing date as '' collapses every match
    into one tie, which then resolves by stage preference instead of recency —
    that bug staged a bill awaiting Senate action as 'passed_house'."""
    return (action.get("actionDate") or action.get("action_date") or "")


def _chamber_of(action: dict) -> str | None:
    name = ((action.get("sourceSystem") or {}).get("name") or "").lower()
    if "house" in name:
        return "house"
    if "senate" in name:
        return "senate"
    return None


def match(text: str) -> tuple[str, str | None] | None:
    """Which rule does this action text hit? None if it is not decisive."""
    low = (text or "").lower()
    if not low:
        return None
    for stage, chamber, phrases in RULES:
        if any(p in low for p in phrases):
            return stage, chamber
    return None


def _pref(stage: str) -> int:
    """Preference among actions that share a date. Positive stages outrank
    terminal ones, which outrank unknown."""
    if stage in TERMINAL:
        return -1
    if stage in STAGES:
        return STAGES.index(stage)
    return -2


def derive(actions: list[dict]) -> dict:
    """The newest DATE holding a decisive action decides the stage.

    Why by date and not by list position: a bill is routinely introduced and
    referred to committee on the SAME day, so two actions share a date. Depending
    on the order congress.gov happens to return them in would report a referred
    bill as merely 'introduced'. So among actions on the newest decisive date we
    take the MOST ADVANCED stage — semantics, not array order.

    Returns {stage, chamber, date, basis}; stage is 'unknown' when no action
    matches any rule, which is a real outcome rather than an error.
    """
    matches = []
    for action in actions:
        hit = match(action.get("text", ""))
        if hit:
            matches.append((_date_of(action), _pref(hit[0]), hit, action))

    if not matches:
        return {"stage": "unknown", "chamber": None, "date": None, "basis": None}

    newest_date = max(m[0] for m in matches)
    newest = max((m for m in matches if m[0] == newest_date), key=lambda m: m[1])
    newest_stage = newest[2][0]

    if newest_stage in TERMINAL:
        # A terminal action is the end of the story and must not be masked by an
        # earlier success.
        chosen = newest
    else:
        # Otherwise report the FURTHEST milestone reached, not the latest one.
        # Congress is bicameral: HR 2347 passed the House and now sits on the
        # Senate calendar. "Senate calendar" ranks below "passed House" on a
        # linear ladder, so reporting the latest action made the bill look like it
        # had gone backwards. `chamber` below says where it is now.
        positive = [m for m in matches if m[2][0] not in TERMINAL]
        chosen = max(positive, key=lambda m: m[1]) if positive else newest

    date, _, hit, action = chosen
    stage, chamber = hit
    return {
        "stage": stage,
        "chamber": chamber or _chamber_of(action),
        "date": date,
        "basis": action.get("text"),
        # where the bill sits right now, which may be a different chamber
        "current_chamber": newest[2][1] or _chamber_of(newest[3]),
        "current_basis": newest[3].get("text"),
        "current_date": newest_date,
    }


def rank(stage: str) -> int:
    """Position in the ladder; -1 for terminal, -2 for unknown."""
    if stage in TERMINAL:
        return -1
    if stage not in STAGES:
        return -2
    return STAGES.index(stage)
