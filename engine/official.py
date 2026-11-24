"""Boule — the official tally.

The other half of the product. Fetches a recorded roll-call vote from the source
that published it and reduces it to a tally.

Two formats, because Congress has two houses and two websites:
  - Senate: senate.gov LIS XML  (/legislative/LIS/roll_call_votes/vote<c><s>/...)
  - House : clerk.house.gov XML (clerk.house.gov/evs/<year>/roll<nnn>.xml)

And one rule that matters more than either parser:

    A tally is only *of the text* if the vote was on the text.

A cloture motion, a motion to proceed, a motion to table — these are the chamber
deciding whether to do something, not whether it agrees with the bill. Drawing a
gap against one of those would claim the public's reading of a bill should match a
procedural manoeuvre. So each vote is classified, and only `of_the_text` may carry
a gap. Everything is still *recorded* — the official record is not ours to hide.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import congress  # noqa: E402  (reuse its CA-bundle handling and dotenv load)


# --- classification ---------------------------------------------------------

# Votes that decide whether to proceed, not whether to agree.
_PROCEDURAL = (
    "cloture", "motion to proceed", "motion to commit", "motion to table",
    "motion to reconsider", "previous question", "quorum", "adjourn",
    "motion to discharge", "motion to lay",
)

# Votes that are about the measure itself.
#
# "On the amendment" and "on agreeing to the amendment" are deliberately NOT here.
# A vote on an amendment decides what the text will SAY; it is not the chamber saying
# it agrees with the bill. Drawing a gap against one compares a reading of the bill
# with a vote on a proposal to change it -- two different questions, subtracted. That
# is the same error as drawing a gap against a procedural manoeuvre, one step subtler,
# and it was live: HR 2347's headline gap was measured against
# "On the Amendment S.Amdt. 6883" (amendment agreed to, 69-27) while the readings were
# pinned to the as-introduced text. Amendment votes are therefore classified `other`:
# recorded, listed, and never measured against.
_OF_THE_TEXT = (
    "on passage", "suspend the rules and pass", "on concurring",
    "on agreeing to the resolution", "on the resolution", "on the joint resolution",
    "override",
)

# Votes on a proposed change to the text -- recorded, never a gap.
_AMENDMENT = (
    "on the amendment", "on agreeing to the amendment",
)


def classify(question: str) -> str:
    """'procedural' | 'of_the_text' | 'other'.

    'other' is the honest middle: a vote we cannot place, OR a vote on a proposed
    change to the text. It is recorded, and it is NOT given a gap, because we will
    not guess what it measured -- and an amendment vote measured agreement with an
    amendment, not with the bill.
    """
    q = (question or "").lower()
    if any(k in q for k in _PROCEDURAL):
        return "procedural"
    if any(k in q for k in _AMENDMENT):
        return "other"
    if any(k in q for k in _OF_THE_TEXT):
        return "of_the_text"
    return "other"


# --- fetch ------------------------------------------------------------------

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": congress.USER_AGENT})
    with urllib.request.urlopen(req, timeout=30, context=congress._ssl_context()) as r:
        return r.read().decode("utf-8", "replace")


# --- parse ------------------------------------------------------------------

def _tag(raw: str, name: str) -> str | None:
    m = re.search(rf"<{name}>(.*?)</{name}>", raw, re.S)
    return m.group(1).strip() if m else None


def _int(v) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return 0


def _norm_type(t: str) -> str:
    """'H R' / 'H.R.' / 'hr' -> 'hr'.  One spelling per thing."""
    t = (t or "").lower()
    letters = re.sub(r"[^a-z]", "", t)
    return {
        "hr": "hr", "s": "s", "hjres": "hjres", "sjres": "sjres",
        "hconres": "hconres", "sconres": "sconres", "hres": "hres", "sres": "sres",
    }.get(letters, letters)


def bill_ref(raw: str, chamber: str, question: str) -> tuple[str, int] | None:
    """Which bill is this vote ACTUALLY about?

    Never assume it is the one we went looking for. The clerk's roll138 was found
    by date while chasing H.R. 2347, and turned out to be H.R. 7959 — attaching it
    to 2347 would have put another bill's numbers on our page, which is the worst
    lie this product could tell.
    """
    if chamber == "house":
        ln = _tag(raw, "legis-num") or ""
        letters, digits = re.sub(r"[^A-Za-z]", "", ln), re.sub(r"\D", "", ln)
        if letters and digits:
            return _norm_type(letters), int(digits)
    else:
        dt, dn = _tag(raw, "document_type"), _tag(raw, "document_number")
        if dt and dn and re.fullmatch(r"\d+", dn.strip()):
            # a real measure, not an amendment ('S.Amdt.' has no number here)
            if _norm_type(dt) in {"hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres"}:
                return _norm_type(dt), int(dn)
    m = re.search(r"\b(H\.?\s?R\.?|S)\.?\s*(\d+)\b", question or "")
    if m:
        return _norm_type(m.group(1)), int(m.group(2))
    return None


def parse(raw: str, source_url: str = "") -> dict:
    """Reduce either house's roll-call XML to one tally. Raises ValueError if the
    document is not a roll call we recognise.

    The soft-404 trap lives here: senate.gov serves an HTML error page with HTTP
    200 for a dead path, so 'parsed nothing' must be a LOUD failure, never a
    silent zero. A zero would be a claim; absence is a fact.
    """
    if "roll_call_vote" in raw or "vote_question_text" in raw:
        chamber = "senate"
        question = _tag(raw, "vote_question_text") or ""
        result = _tag(raw, "vote_result_text") or _tag(raw, "vote_result") or ""
        yea = _int(_tag(raw, "yeas"))
        nay = _int(_tag(raw, "nays"))
        casts = re.findall(r"<vote_cast>(.*?)</vote_cast>", raw, re.S)
        present = sum(1 for c in casts if "present" in c.lower())
        not_voting = sum(1 for c in casts if "not voting" in c.lower())
        members = len(casts)
        rc = f"{_tag(raw,'congress')}-{_tag(raw,'session')}-{_tag(raw,'vote_number')}"
    elif "rollcall-vote" in raw or "legis-num" in raw:
        chamber = "house"
        question = _tag(raw, "vote-question") or ""
        result = _tag(raw, "vote-result") or ""
        yea = _int(_tag(raw, "yea-total"))
        nay = _int(_tag(raw, "nay-total"))
        present = _int(_tag(raw, "present-total"))
        not_voting = _int(_tag(raw, "not-voting-total"))
        members = len(re.findall(r"<recorded-vote>", raw))
        rc = _tag(raw, "action-date") or ""
    else:
        raise ValueError(
            f"not a roll-call document (first 120 bytes: {raw[:120]!r}) — "
            "if this came from senate.gov, the path is probably dead and served "
            "an HTML error page with HTTP 200"
        )

    if not question and not result:
        raise ValueError("roll call parsed but carried neither a question nor a result")

    ref = bill_ref(raw, chamber, question)
    return {
        "chamber": chamber,
        "roll_call": rc,
        "question": question,
        "result": result,
        "yea": yea,
        "nay": nay,
        "present": present,
        "not_voting": not_voting,
        "members_recorded": members,
        "vote_class": classify(question),
        "bill_ref": ref,
        "source_url": source_url,
    }


def tally_from_url(url: str) -> dict:
    return parse(fetch(url), source_url=url)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True)
    a = ap.parse_args()
    print(json.dumps(tally_from_url(a.url), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
