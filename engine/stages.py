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
    ("failed", None, (
        "failed", "rejected", "cloture not invoked", "not invoked",
        "motion to table", "motion to proceed rejected",
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


def derive(actions: list[dict]) -> dict:
    """The newest decisive action decides the stage.

    Returns {stage, chamber, date, basis}; stage is 'unknown' when no action in
    the history matches any rule — which is a real outcome, not an error.
    """
    ordered = sorted(actions, key=lambda a: a.get("actionDate") or "")
    for action in reversed(ordered):
        hit = match(action.get("text", ""))
        if hit:
            stage, chamber = hit
            return {
                "stage": stage,
                "chamber": chamber or _chamber_of(action),
                "date": action.get("actionDate"),
                "basis": action.get("text"),
            }
    return {"stage": "unknown", "chamber": None, "date": None, "basis": None}


def rank(stage: str) -> int:
    """Position in the ladder; -1 for terminal, -2 for unknown."""
    if stage in TERMINAL:
        return -1
    if stage not in STAGES:
        return -2
    return STAGES.index(stage)
