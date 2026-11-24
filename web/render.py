"""Render Boule's pages from the database.

Every value on these pages comes from SQLite. Nothing about a bill is hard-coded
here — that is the S2 gate: change a row, and the page changes with no HTML edit.

Deliberately NOT rendered yet, because the data does not exist:
  - public tallies    (no votes table until S3)
  - official tallies  (no roll-call ingestion yet)
  - the gap           (needs both)
Each bill therefore shows the honest empty state. A `0` would be a claim; "no
votes yet" is a fact. That distinction is the whole product.
"""
from __future__ import annotations

import html
import math
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The whitelist sanitiser lives in engine/ with no imports of its own, so the web tier can
# use it without pulling the Congress.gov client (and its dotenv loading) into the server.
sys.path.insert(0, str(HERE.parent / "engine"))

import sanitize  # noqa: E402
import forecast as forecast_mod  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEGAL = ROOT / "legal"

STAGE_LABEL = {
    "introduced": "Introduced",
    "in_committee": "In committee",
    "reported": "Reported",
    "passed_house": "Passed the House",
    "passed_senate": "Passed the Senate",
    "resolving_differences": "Resolving differences",
    "to_president": "To the President",
    "enacted": "Enacted",
    "failed": "Failed",
    "vetoed": "Vetoed",
    "unknown": "Stage unknown",
}
CHAMBER = {"house": "the House", "senate": "the Senate", "both": "both chambers"}

NAV = [("Today", "/"), ("Bills", "/bills"), ("The Gap", "/gap"), ("Me", "/me")]

# One source of truth for what exists. The server, the static build and the gate
# all read this, so they cannot disagree about which pages are real — the LINKS
# failure came from exactly that disagreement.
ROUTES: list[tuple[str, str, str]] = [
    # (url path, static filename, nav label marked current)
    ("/", "index.html", "Today"),
    ("/bills", "bills.html", "Bills"),
    ("/gap", "gap.html", "The Gap"),
    ("/me", "me.html", "Me"),
    ("/privacy", "privacy.html", ""),
]

# A bill detail page is a DYNAMIC route: one URL per bill in the database. It is
# not in ROUTES because ROUTES is the fixed floor; routes_for() adds the bills.
BILL_PATH = re.compile(r"^/bill/(\d+)/([a-z]+)/(\d+)/?$")


def routes_for(con: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """ROUTES plus one page per bill.

    The static build and the twin gate both call this, so neither can disagree
    about which pages are real — the class of bug the LINKS check was added for.
    """
    out = list(ROUTES)
    for r in con.execute(
        "SELECT congress, bill_type, number FROM bills ORDER BY bill_type, number"
    ).fetchall():
        congress, bill_type, number = r[0], r[1], r[2]
        out.append((f"/bill/{congress}/{bill_type}/{number}",
                    f"bill/{congress}/{bill_type}/{number}/index.html", ""))
    return out


def page(title: str, body: str, current_nav: str = "Today",
         base_path: str = "") -> str:
    """`base_path` exists so the same markup serves both ways.

    Served from a root domain, base_path is "". Built as static files for a
    subpath host (m1ck5k1.github.io/boule/ or an R2 bucket), every absolute URL
    has to carry the prefix — otherwise the CSS and the nav 404 the moment the
    site is not at the root. Getting this wrong is invisible locally and total
    once deployed.
    """
    def href(path: str) -> str:
        return f"{base_path}{path}"

    nav = "\n".join(
        f'<a href="{href(nav_href)}"'
        + (' aria-current="page"' if label == current_nav else "")
        + f">{esc(label)}</a>"
        for label, nav_href in NAV
    )
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{href('/static/boule.css')}">
<!-- S6 — the installable PWA. The design rule is "no icons"; a LAUNCHER icon is not a
     UI icon, it is the one place a name is all that fits. The manifest is what makes the
     app installable, and the install is what makes a device key durable. -->
<meta name="theme-color" content="#14130F">
<link rel="icon" href="{href('/static/icon.svg')}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{href('/static/icon-180.png')}">
<link rel="manifest" href="{href('/manifest.webmanifest')}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{body}
<nav class="nav" aria-label="Sections">
{nav}
</nav>
<footer class="note">
  <b>Boule is a second tally that runs beside the real one, so the gap becomes
  visible.</b> Bills and their stages are real and come from Congress.gov. Public
  tallies are live; the official tally is not recorded yet, so no gap is shown —
  an empty tally is a fact, a zero would be a claim.
  <span class="aka">Also known as <b>Boule Schit</b>.</span>
  <span class="legal-links"><a href="{href('/privacy')}">Privacy</a></span>
</footer>
<!-- The only script in the project. A service worker cannot be registered without one,
     and without a worker there is no install — so this is the deliberate, recorded
     exception to "no JavaScript", not the thin end of a framework. It registers the
     worker and asks for the device key; nothing else. -->
<script src="{href('/static/pwa.js')}" defer></script>
</body>
</html>
"""


def privacy_page(base_path: str = "") -> str:
    """Serve the policy from legal/privacy.html — one source, no markdown step."""
    body_html = (LEGAL / "privacy.html").read_text(encoding="utf-8")
    body = masthead(["<b>Privacy</b> — what Boule collects, and what it never does"])
    body += f"""
<main id="main" class="legal">
{body_html}
</main>
"""
    return page("Boule — privacy policy", body, "", base_path=base_path)


def stub_page(path: str, base_path: str = "") -> str:
    """A surface named in the nav but not built yet.

    It exists because the nav links to it, and a link to a 404 is the same class
    of lie as a button that does nothing. Saying "not built yet" plainly is the
    honest option; linking nowhere is not.
    """
    label = path.strip("/").title()
    body = masthead([f"<b>{label}</b> — not built yet"])
    body += '<main id="main"><p class="empty">This surface is not built yet.</p></main>'
    return page(f"Boule — {path.strip('/')}", body, label, base_path=base_path)


def confirm_vote(bill_label: str, title: str, choice: str, hidden: str,
                 base_path: str = "") -> str:
    """S3 — 'click once, click to confirm'.

    A choice is not a vote. Nothing is written until THIS page is submitted, so a
    stray click on the ledger cannot record a ballot.
    """
    word = "for" if choice == "yea" else "against"
    body = f"""
<main id="main">
  <section class="confirm" aria-labelledby="c-h">
    <h1 id="c-h" class="confirm-h">Confirm your vote</h1>
    <p class="cbill"><b>{esc(bill_label)}</b> <span class="cs">{esc(title)}</span></p>
    <p class="cchoice">You are about to vote <b>{esc(choice.upper())}</b> ({word}) on this bill.
      This will be recorded and cannot be edited.</p>
    <form class="votebox confirm" method="post" action="/api/vote">
      {hidden}
      <button type="submit" class="vote cf">Confirm {esc(choice.upper())}</button>
      <a class="cancel" href="{esc(base_path)}/">Cancel</a>
    </form>
  </section>
</main>
"""
    return page("Boule — confirm your vote", body, "", base_path)


def one_reading_page(bill_label: str, title: str, base_path: str = "") -> str:
    """S5 — the refusal, said plainly.

    This is not an error and must not be dressed as one. The reading was already
    recorded, the record stands, and nothing is lost. A refusal that reads like a
    fault teaches the user the system is broken, when what actually happened is
    that it counted honestly.
    """
    body = f"""
<main id="main">
  <section class="confirm" aria-labelledby="r-h">
    <h1 id="r-h" class="confirm-h">Already recorded</h1>
    <p class="cbill"><b>{esc(bill_label)}</b> <span class="cs">{esc(title)}</span></p>
    <p class="cchoice">This device has already recorded a reading on <b>this version</b> of
      the text. One reading per device is what makes the tally a count of <em>devices</em>
      rather than a count of clicks — so the earlier reading stands, and this one was not
      added.</p>
    <p><a class="cancel" href="{esc(base_path)}/">Back to the ledger</a></p>
  </section>
</main>
"""
    return page("Boule — already recorded", body, "", base_path)


CONGRESS_SLUG = {
    "hr": "house-bill", "s": "senate-bill",
    "hjres": "house-joint-resolution", "sjres": "senate-joint-resolution",
    "hconres": "house-concurrent-resolution", "sconres": "senate-concurrent-resolution",
    "hres": "house-resolution", "sres": "senate-resolution",
}


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def congress_url(congress: int, bill_type: str, number: int) -> str:
    slug = CONGRESS_SLUG.get((bill_type or "").lower(), "house-bill")
    return f"https://www.congress.gov/bill/{_ordinal(congress)}-congress/{slug}/{number}"


# Chamber of origin. This is information, not decoration: the chamber a bill starts in
# decides which body votes first, and it is the one thing a reader wants at a glance
# once a list mixes the two. Types are mapped by chamber, so the rule covers all eight
# rather than only HR and S.
_HOUSE_TYPES = {"hr", "hjres", "hconres", "hres"}
_SENATE_TYPES = {"s", "sjres", "sconres", "sres"}


def chamber(bill_type: str) -> str:
    """'house', 'senate' or 'other' — the chamber of origin."""
    t = (bill_type or "").strip().lower()
    if t in _HOUSE_TYPES:
        return "house"
    if t in _SENATE_TYPES:
        return "senate"
    return "other"


def bill_id_html(bill_type: str, number) -> str:
    """The identifier as a chamber-tinted chip.

    The letterform (HR / S) carries the fact and is always present; the tint only
    reinforces it. The distinction therefore never rests on colour alone, which is
    what keeps it legible in monochrome and to a colour-blind reader.
    """
    label = f"{(bill_type or '').upper()} {number}"
    return f'<span class="chamber {chamber(bill_type)}">{esc(label)}</span>'


def bill_page(con: sqlite3.Connection, congress: int, bill_type: str, number: int,
              base_path: str = "") -> str:
    """The second screen of the floor: one bill, its real record, and the vote.

    The reading stack is the government's own material — L1 is CRS, L2 is a diff of
    the text, L3 is a link. Boule must not narrate the bill, so an unwired layer is
    shown as unwired, never filled with an AI-written summary.
    """
    row = con.execute(
        """
        SELECT b.*, s.stage, s.chamber, s.current_chamber
          FROM bills b LEFT JOIN stages s USING (congress, bill_type, number)
         WHERE b.congress = ? AND b.bill_type = ? AND b.number = ?
        """, (congress, bill_type, number)).fetchone()
    if not row:
        raise KeyError(f"no bill {congress}/{bill_type}/{number}")

    version = con.execute(
        "SELECT version_code, label FROM bill_versions "
        "WHERE congress = ? AND bill_type = ? AND number = ? "
        "ORDER BY first_seen DESC, version_id DESC LIMIT 1",
        (congress, bill_type, number)).fetchone()

    # L1 — the CRS summary, pinned to the version being voted on. `other` is a summary that
    # exists for a DIFFERENT version: named so the reader knows the layer is not simply
    # missing, and never shown, because its words describe other text.
    summary = other_summary = None
    version_label = (f"v{version['version_code']} ({version['label']})"
                     if version else None)
    try:
        if version:
            summary = con.execute(
                "SELECT version_code, action_desc, text, source_url FROM bill_summaries "
                "WHERE congress = ? AND bill_type = ? AND number = ? AND version_code = ? "
                "ORDER BY summary_id DESC LIMIT 1",
                (congress, bill_type, number, version["version_code"])).fetchone()
        if summary is None:
            other_summary = con.execute(
                "SELECT version_code, action_desc FROM bill_summaries "
                "WHERE congress = ? AND bill_type = ? AND number = ? "
                "ORDER BY summary_id DESC LIMIT 1",
                (congress, bill_type, number)).fetchone()
    except sqlite3.OperationalError:      # table absent on an older db
        pass

    counts: dict = {}
    if version:
        for r in con.execute(
            "SELECT choice, COUNT(*) FROM votes "
            "WHERE congress = ? AND bill_type = ? AND number = ? AND version_code = ? "
            "GROUP BY choice",
            (congress, bill_type, number, version["version_code"])).fetchall():
            counts[r[0]] = r[1]
    yea, nay = counts.get("yea", 0), counts.get("nay", 0)
    total = yea + nay
    pct_int = round(100 * yea / total) if total else None
    off = official_tally(con, congress, bill_type, number)
    off_int = official_pct(off)

    if total:
        public_pct, public_count = f"{pct_int}%", f"{yea} yea · {nay} nay"
    else:
        public_pct, public_count = "—", "—"

    # The drawn bars (DESIGN.md §5). PUBLIC fills in ink; OFFICIAL in --ink-2 and carries
    # the --signal tail that *is* the difference. A gap is drawn ONLY against a vote of
    # the text: a procedural vote is the chamber deciding whether to proceed, and a gap
    # against it would compare a reading of the bill with a manoeuvre. Where no such vote
    # exists, nothing is drawn and the note says why — a forecast is not a gap.
    if off is not None and off_int is not None and pct_int is not None:
        lo, hi = sorted((pct_int, off_int))
        official_html = tally_row("Official", f"{off_int}%",
                                  f"{off['yea']} yea · {off['nay']} nay",
                                  fill_pct=off_int, off=True, gap=(lo, hi))
    else:
        official_html = tally_row("Official", "—", "—", fill_pct=None)
    tallies_html = (tally_row("Public", public_pct, public_count, fill_pct=pct_int)
                    + official_html)
    gap_html = gap_block(
        pct_int, off,
        "No recorded vote on the text yet — no gap to report." if total
        else "No votes yet — no gap to report.",
        yea=yea, nay=nay,
        version_label=(f"v{version['version_code']} ({version['label']})"
                       if version else None))

    # The block above is aria-hidden, so the figures have to live in a spoken sentence.
    # The spoken version carries the SAME conditions as the printed one — an accessible
    # equivalent that claims more than the visible line would be a second, quieter lie.
    if total:
        sr = f"Public tally: {yea} for, {nay} against — {total} cast, {pct_int}% in favour."
        if off is not None and off_int is not None:
            d = pct_int - off_int
            n_off = int(off["yea"]) + int(off["nay"])
            ci = _ci_points(yea / total, total,
                            int(off["yea"]) / n_off if n_off else 0.0, n_off)
            sr += (f" Official tally: {off['yea']} for, {off['nay']} against, "
                   f"{off_int}% in favour, {off['chamber']} roll call {off['roll_call']}. ")
            if abs(d) <= ci:
                sr += (f"Gap: {abs(d)} points, which is inside the margin of error at "
                       f"this sample size — not yet distinguishable from the official "
                       f"figure.")
            else:
                sr += (f"Gap: {abs(d)} point{'s' if abs(d) != 1 else ''} "
                       f"{'public ahead' if d > 0 else 'official ahead' if d < 0 else 'level'}.")
        else:
            sr += " No recorded vote on the text yet, so no gap can be reported."
    else:
        sr = ("No public tally yet. "
              + (f"Official tally on record: {off['yea']} for, {off['nay']} against."
                 if off is not None and off_int is not None
                 else "No official tally recorded yet."))

    label = f"{(bill_type or '').upper()} {number}"
    stage = stage_text(row["stage"], row["chamber"], row["current_chamber"])

    state = vote_state(off)
    if version and state == "closed":
        vote_ui = '<span class="voted">Record closed</span>'
    elif version:
        vote_ui = f"""<form class="votebox" method="post" action="/api/vote">
        <input type="hidden" name="congress" value="{esc(congress)}">
        <input type="hidden" name="bill_type" value="{esc(bill_type)}">
        <input type="hidden" name="number" value="{esc(number)}">
        <input type="hidden" name="version_code" value="{esc(version['version_code'])}">
        <input type="hidden" name="next" value="{esc(base_path)}/bill/{esc(congress)}/{esc(bill_type)}/{esc(number)}">
        <button type="submit" class="vote early" name="choice" value="yea">Yea</button>
        <button type="submit" class="vote early" name="choice" value="nay">Nay</button>
      </form><span class="hint">click once, click to confirm</span>
      <p class="vstate">Record a view — a leaning, not a gap. There is no recorded vote on
      this text yet, so nothing here can be compared to an official figure.</p>"""
    else:
        vote_ui = '<span class="voted">Voting not open — no text version</span>'

    actions = con.execute(
        "SELECT action_date, action_type, text FROM actions "
        "WHERE congress = ? AND bill_type = ? AND number = ? ORDER BY action_date, action_id",
        (congress, bill_type, number)).fetchall()
    timeline = "\n".join(
        f'        <li class="arow"><time datetime="{esc(a[0])}">{esc(a[0])}</time>'
        f'<span class="atype">{esc(a[1] or "")}</span>'
        f'<span class="atext">{esc(a[2])}</span></li>'
        for a in actions) or '        <li class="arow"><span class="atext">No actions recorded.</span></li>'
    l1 = l1_html(summary, other_summary, version_label)

    # The forecast — Boule's own claim, and the one place the page says something about the
    # future. Read here, never written here: the web tier has a read-only handle.
    try:
        fc = forecast_mod.latest(con, congress, bill_type, number)
        fc_tally = forecast_mod.tally(con, congress, bill_type, number)
    except sqlite3.OperationalError:      # table absent on an older db
        fc, fc_tally = None, {}
    fc_html = forecast_html(fc, fc_tally)

    introduced = human_date(row["introduced_on"]) if row["introduced_on"] else "date unknown"
    ver_line = (f"Version pinned: <b>{esc(version['version_code'])} · {esc(version['label'])}</b>"
                " — this vote is on that text." if version else "No text version recorded yet.")

    body = masthead([
        f'{bill_id_html(bill_type, number)} — <b>{esc(row["title"] or "(no title)")}</b>',
        f"Introduced {esc(introduced)}",
    ]) + f"""
<main id="main" class="single">
  <p class="back"><a href="{esc(base_path)}/">&#8592; Today</a></p>
  <p class="stage"><span class="dot" aria-hidden="true"></span>{esc(stage)}</p>

  <p class="sr-only">{esc(sr)}</p>
  <div class="tallies" aria-hidden="true">
{tallies_html}
    {gap_html}
  </div>

{fc_html}

  <div class="act" style="text-align:left">
    {vote_ui}
  </div>

  <h2 class="sect-h">The reading stack — none of it ours</h2>
  <div class="layer">
    <div class="lh"><span class="ltag">L0 — one line</span><span class="lsrc">condensed from CRS</span></div>
    <p class="lbody notwired">Not wired — and not for want of a feed. A one-line condensation
      is Boule-authored prose, so it needs an editorial decision, not a machine writer.</p>
  </div>
  <div class="layer">
    <div class="lh"><span class="ltag">L1 — official summary</span><span class="lsrc">source: CRS</span></div>
    {l1}
  </div>
  <div class="layer">
    <div class="lh"><span class="ltag">L2 — what changed</span><span class="lsrc">source: diff_bills.sh</span></div>
    <p class="lbody notwired">Tool exists, not yet wired to the UI.</p>
  </div>
  <div class="layer">
    <div class="lh"><span class="ltag">L3 — full text</span><span class="lsrc">source: the bill itself</span></div>
    <p class="lbody">Read the bill on congress.gov —
      <a href="{esc(congress_url(congress, bill_type, number))}" rel="noopener">{esc(label)}, {esc(_ordinal(congress))} Congress</a>.</p>
  </div>

  <h2 class="sect-h">Actions — {len(actions)} recorded</h2>
  <ul class="atl">
{timeline}
  </ul>

  <p class="hint">{ver_line}</p>
</main>
"""
    return page(f"Boule — {label}", body, "Bills", base_path)


def render_route(path: str, con, today: str, base_path: str = "") -> str:
    """One renderer for the server AND the static build.

    If these diverged, the twin gate would be the only thing standing between a
    working preview and a broken deploy.
    """
    if path in ("/", "/today"):
        return today_page(con, today, base_path)
    if path == "/privacy":
        return privacy_page(base_path)
    if path in ("/bills", "/gap", "/me"):
        return stub_page(path, base_path)
    m = BILL_PATH.match(path)
    if m:
        return bill_page(con, int(m.group(1)), m.group(2), int(m.group(3)), base_path)
    raise KeyError(f"no route for {path}")


def stage_text(stage: str | None, chamber: str | None, current: str | None) -> str:
    """The milestone, plus where the bill actually sits when that differs.

    A bill that passed the House and is now on the Senate calendar must not read
    as if it went backwards, so both facts are shown.
    """
    label = STAGE_LABEL.get(stage or "unknown", stage or "unknown")
    where = CHAMBER.get(chamber or "")
    now = CHAMBER.get(current or "")
    if now and current != chamber:
        return f"{label} · now in {now}"
    if where:
        return f"{label} · {where}"
    return label


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def masthead(dateline_bits: list[str]) -> str:
    """No sign-in control until sign-in exists.

    A button that does nothing is a lie, and this page's whole argument is that it
    does not claim things it cannot show. The mock had one; the served page does
    not, until S5 gives it something to do.
    """
    tail = "".join(f"<span>{b}</span>" for b in dateline_bits)
    return f"""<header class="doc">
  <div class="masthead">
    <h1 class="wordmark">Boule <span class="pron" aria-hidden="true">/ˈbuːli/</span></h1>
    <p class="tag">A second tally that runs beside the real one, so the gap becomes visible.</p>
    <p class="aka"><b>Boule Schit</b><span class="pron" aria-hidden="true"> /ˌbuːl ˈʃɪt/</span> — (n.) 1. a council that prepared the motions; 2. what became of them.</p>
  </div>
  <div class="dateline">{tail}</div>
</header>
"""


def tally_row(label: str, pct: str, count: str, fill_pct: int | None = None,
              off: bool = False, gap: tuple[int, int] | None = None) -> str:
    """One drawn tally row (DESIGN.md §5).

    The bar is decoration — the caller marks the block aria-hidden and carries the
    figures in a spoken sentence. `fill_pct` is the 0-100 share the bar draws to;
    None means "nothing recorded", so the track stays empty rather than showing a
    zero, which would be a claim.

    `gap` is the difference, drawn: a --signal tail spanning a..b on this track.
    The tail IS the difference — no box, no border, no highlight, because a bordered
    region reads as a selection state, which is a lie.
    """
    inner = ""
    if fill_pct is not None:
        cls = "fill off" if off else "fill"
        inner = f'<span class="{cls}" style="--p:{fill_pct}%"></span>'
    if gap is not None:
        a, b = gap
        inner += f'<span class="gapfill" style="--a:{a}%; --b:{b}%"></span>'
    return (f'<div class="trow"><span class="tlabel">{esc(label)}</span>'
            f'<span class="track">{inner}</span>'
            f'<span class="tpct">{esc(pct)}</span>'
            f'<span class="tcount">{esc(count)}</span></div>')


def official_tally(con: sqlite3.Connection, congress: int, bill_type: str, number: int):
    """The official vote a gap may be drawn against, or None.

    **Only `of_the_text` qualifies.** A cloture motion or a motion to proceed is the
    chamber deciding whether to *do* something, not whether it agrees with the bill;
    drawing a gap against one would claim the public's reading should match a
    procedural manoeuvre. Where no such vote exists, no gap is drawn — a forecast is
    not a gap. Among qualifying votes, the most recent wins.

    Every qualifying vote is still *recorded* and listed; this only decides which one
    the drawn difference is measured against.
    """
    try:
        return con.execute(
            """SELECT chamber, roll_call, question, result, yea, nay, present,
                      not_voting, source_url, vote_class
                 FROM official_tallies
                WHERE congress = ? AND bill_type = ? AND number = ?
                  AND vote_class = 'of_the_text'
                ORDER BY roll_call DESC LIMIT 1""",
            (congress, bill_type, number)).fetchone()
    except sqlite3.OperationalError:      # table absent on an older db
        return None


def official_pct(row) -> int | None:
    """The official share in favour, or None if there is no vote to divide."""
    if not row:
        return None
    y, n = int(row["yea"]), int(row["nay"])
    return round(100 * y / (y + n)) if (y + n) else None


def _ci_points(p1: float, n1: int, p2: float, n2: int) -> float:
    """Half-width of the 95% interval for the DIFFERENCE of two proportions.

    The gap is a subtraction, so its uncertainty is the uncertainty of the
    subtraction — not the uncertainty of either side. At 7 readings against a 96-vote
    roll call that is ±27 points, which is the entire reason this number is printed.
    """
    if n1 <= 0 or n2 <= 0:
        return 100.0
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return 1.96 * se * 100


def gap_block(public_pct: int | None, off, note_when_none: str, *,
              yea: int = 0, nay: int = 0, version_label: str | None = None) -> str:
    """Either the Δ readout — WITH its conditions — or the note saying why there is none.

    A gap is a subtraction of two numbers that must measure the same thing, and the
    subtraction carries its own uncertainty. So the readout names the reading count,
    the interval, and the version the readings are pinned to; and where the interval
    is wider than the gap it reports that instead of claiming a difference. A gap that
    cannot be told apart from noise is not a gap, and this project does not publish one.
    """
    off_int = official_pct(off)
    if public_pct is None or off_int is None:
        return f'<p class="nogap">{esc(note_when_none)}</p>'

    n1 = int(yea) + int(nay)
    n2 = int(off["yea"]) + int(off["nay"])
    ci = _ci_points(int(yea) / n1 if n1 else 0.0, n1,
                    int(off["yea"]) / n2 if n2 else 0.0, n2)

    d = public_pct - off_int
    if abs(d) <= ci:
        claim = (f"&#916; {abs(d)} point{'' if abs(d) == 1 else 's'} — not yet "
                 f"distinguishable from the official figure")
    elif d == 0:
        claim = "&#916; 0 points — level"
    else:
        claim = (f"&#916; {abs(d)} point{'' if abs(d) == 1 else 's'} "
                 f"{'public ahead' if d > 0 else 'official ahead'}")

    bits = [f'{n1} reading{"" if n1 == 1 else "s"}',
            f"&#177;{ci:.0f} points at 95%",
            f'{esc(off["chamber"])} roll call {esc(str(off["roll_call"]))} (n={n2})']
    if version_label:
        bits.append(f"readings on {esc(version_label)}")
    # The conditions ride in their own element so the typography can hold them quieter
    # than the claim -- and so a test can prove they are still there.
    return (f'<p class="delta">{claim}'
            f'<span class="cond"> · {" · ".join(bits)}</span></p>')


def l1_html(summary, other, version_label: str | None) -> str:
    """L1 — the CRS summary, VERBATIM, pinned to the version being voted on.

    Three cases, and the difference between them is the whole point:

      * a summary for THIS version  -> CRS's words, attributed, with its version named;
      * no summary for this version, but one exists for a DIFFERENT text -> say so, and do
        NOT show the other one. A summary of other words attached to this vote measures
        the amendments, not the bill -- the same failure as a gap drawn across versions;
      * no summary at all -> say so.

    Boule does not write this layer. Not even a one-line condensation: an AI summary of a
    bill is the same category of artefact this project exists to audit.
    """
    if summary is not None:
        ver = esc(str(summary["version_code"]))
        desc = summary["action_desc"] or ""
        attrib = f"CRS, version {ver}" + (f" — {esc(desc)}" if desc else "")
        return (f'<div class="lbody"><p class="lattr">{attrib}. '
                f'<a href="{esc(summary["source_url"])}" rel="noopener">source</a></p>'
                f'<div class="crs">{sanitize.sanitize(summary["text"])}</div></div>')

    if other is not None:
        return (f'<p class="lbody notwired">No CRS summary exists for '
                f'{esc(version_label or "this version")}. congress.gov has one for '
                f'version {esc(str(other["version_code"]))}'
                + (f' — {esc(other["action_desc"])}' if other["action_desc"] else "")
                + f', which is a <b>different text</b>, so it is not shown here.</p>')

    return ('<p class="lbody notwired">No CRS summary exists for this bill yet, so this '
            'layer is empty. Boule does not write it.</p>')


def forecast_html(fc, tally: dict | None = None) -> str:
    """The forecast — Boule's own claim, boxed, labelled, and scorable.

    OPINION, and it says so on its face: the author is named, the day it was made is named,
    and the basis is on the page rather than in a commit message. It is never the only thing
    on the screen (DESIGN.md), and it is never in `--signal`, which belongs to the gap and to
    nothing else.

    Where an outcome has been recorded it is shown BESIDE the claim, not folded into it — the
    forecast is not rewritten to match what happened. Where none has, the page says
    "unscored" rather than letting silence read as a win. That is the whole point of the daily
    rule: a guess you may revise after the fact cannot be scored, and an unscorable guess is
    a horoscope.
    """
    if fc is None:
        return ('<p class="nogap">No forecast on record for this bill — and no path to a '
                'vote identified, so there is nothing worth guessing about.</p>')

    span = (f'{human_date(fc["window_start"])} – {human_date(fc["window_end"])}'
            if fc["window_start"] != fc["window_end"]
            else human_date(fc["window_start"]))

    outcome = fc["outcome"] if "outcome" in fc.keys() else None
    if outcome == "hit":
        verdict = ('<p class="fcverdict hit">Scored: <b>hit</b> — the vote landed '
                   f'{esc(human_date(fc["resolved_on"]))}.</p>')
    elif outcome == "miss":
        verdict = ('<p class="fcverdict miss">Scored: <b>miss</b> — the vote came '
                   f'{esc(human_date(fc["resolved_on"]))}, outside the window.</p>')
    elif outcome == "void":
        verdict = ('<p class="fcverdict">Scored: <b>void</b> — the bill died with the '
                   'Congress, so no vote was ever due.</p>')
    else:
        verdict = ('<p class="fcverdict">Not yet scored — the vote has not happened.</p>')

    # The scoreboard. Without it, the moment tomorrow's guess is written yesterday's outcome
    # falls off the page, and the accountability only shows while it is uninteresting.
    t = tally or {}
    if t.get("hits") or t.get("misses") or t.get("voids"):
        record = (f'Record on this bill: <b>{t.get("hits", 0)} hit</b> · '
                  f'{t.get("misses", 0)} miss · {t.get("voids", 0)} void · '
                  f'{t.get("unscored", 0)} unscored')
    else:
        record = 'No forecast on this bill has been settled yet.'
    verdict += f'<p class="fcverdict">{record}</p>'

    return (f'<div class="fcbox">'
            f'<p class="fclabel">Opinion — Boule\'s, not CRS\'s</p>'
            f'<p class="fctext">Next gap-eligible vote expected <b>{span}</b> '
            f'({fc["confidence"]}% confidence).</p>'
            f'<p class="fcbasis">{esc(fc["basis"])}</p>'
            f'<p class="fcmeta">Forecast by {esc(fc["author"])}, made '
            f'{esc(human_date(fc["made_on"]))} · {esc(fc["method_version"])} · '
            f'one per day, never revised</p>'
            f'{verdict}</div>')


def vote_state(off) -> str:
    """DESIGN.md §the vote button — the three-state rule, as far as it can be known.

    'open' means the version is on the floor with no recorded vote yet — which needs the
    /actions feed and cannot be known today, so it is not returned. Until then the honest
    state is 'early': the reading is a leaning, not a gap, and the page says so. 'closed'
    is a passage vote of the measure on record: there is nothing current left to compare
    a reading against, so the control is withdrawn rather than left inviting.
    """
    return "closed" if off is not None else "early"


def bill_row(row: sqlite3.Row, version_code: str | None, tally: dict, base_path: str = "",
             official=None) -> str:
    bill_type = (row["bill_type"] or "").upper()
    number = row["number"]
    title = row["title"] or "(no title)"
    stage = stage_text(row["stage"], row["chamber"], row["current_chamber"])
    label = f"{bill_type} {number}"
    label_html = bill_id_html(bill_type, number)
    detail_href = (f"{base_path}/bill/{esc(row['congress'])}/"
                   f"{esc((row['bill_type'] or '').lower())}/{esc(number)}")

    yea = int(tally.get("yea", 0))
    nay = int(tally.get("nay", 0))
    total = yea + nay
    pct_int = round(100 * yea / total) if total else None
    off_int = official_pct(official)

    if total:
        public_pct, public_count = f"{pct_int}%", f"{yea} yea · {nay} nay"
    else:
        public_pct, public_count = "—", "—"

    # Same rule as the bill page: the tail is the difference, and only a vote OF THE
    # TEXT may carry one.
    if official is not None and off_int is not None and pct_int is not None:
        lo, hi = sorted((pct_int, off_int))
        official_html = tally_row("Official", f"{off_int}%",
                                  f"{official['yea']} yea · {official['nay']} nay",
                                  fill_pct=off_int, off=True, gap=(lo, hi))
    else:
        official_html = tally_row("Official", "—", "—", fill_pct=None)
    row_tallies = (tally_row("Public", public_pct, public_count, fill_pct=pct_int)
                   + official_html)

    if total:
        sr = f"Public tally: {yea} for, {nay} against — {total} cast, {pct_int}% in favour."
        if official is not None and off_int is not None and pct_int is not None:
            d = pct_int - off_int
            sr += (f" Official: {official['yea']} for, {official['nay']} against, "
                   f"{off_int}% in favour. Gap: {abs(d)} point"
                   f"{'s' if abs(d) != 1 else ''} "
                   f"{'public ahead' if d > 0 else 'official ahead' if d < 0 else 'level'}.")
        else:
            sr += " No recorded vote on the text yet, so no gap can be reported."
    else:
        sr = "No public tally yet. No gap can be reported without both tallies."

    # On the list, an absent gap is a dash: the REASON is a property of the day, not of
    # the row, so it is said once above the list rather than twelve times inside it.
    gap_html = gap_block(pct_int, official, "—",
                         yea=yea, nay=nay, version_label=version_code)

    # S3 — the ballot box. A plain form POST, no JS: the vote is the one write,
    # and it goes to the server, which stamps it and appends it.
    state = vote_state(official)
    if version_code and state == "closed":
        vote_ui = '<span class="voted">Record closed</span>'
    elif version_code:
        vote_ui = f"""<form class="votebox" method="post" action="/api/vote">
        <input type="hidden" name="congress" value="{esc(row['congress'])}">
        <input type="hidden" name="bill_type" value="{esc((row['bill_type'] or '').lower())}">
        <input type="hidden" name="number" value="{esc(number)}">
        <input type="hidden" name="version_code" value="{esc(version_code)}">
        <input type="hidden" name="next" value="/">
        <button type="submit" class="vote early" name="choice" value="yea">Yea</button>
        <button type="submit" class="vote early" name="choice" value="nay">Nay</button>
      </form><span class="actnote">Record a view — a leaning, not a gap</span>"""
    else:
        vote_ui = '<span class="voted">Voting not open — no text version</span>'

    return f"""    <li><article class="bill" aria-labelledby="b-{esc(bill_type)}-{esc(number)}">
      <div>
        <div class="bill-id">{label_html}</div>
        <h2 class="bill-title" id="b-{esc(bill_type)}-{esc(number)}"><a class="bill-link" href="{detail_href}">{esc(title)}</a></h2>
        <p class="stage"><span class="dot" aria-hidden="true"></span>{esc(stage)}</p>
      </div>

      <p class="sr-only">{esc(sr)}</p>
      <div class="tallies" aria-hidden="true">
        {row_tallies}
        {gap_html}
      </div>

      <div class="act">
        {vote_ui}
      </div>
    </article></li>"""


def human_date(iso: str) -> str:
    """The design says dates are read by people, not parsed by machines:
    'Tue 18 Nov 2026', not '2026-11-18'. The <time> attribute keeps the ISO form
    for anything that needs to sort."""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b %Y')}"


def today_page(con: sqlite3.Connection, today: str, base_path: str = "") -> str:
    rows = con.execute(
        """
        SELECT b.congress, b.bill_type, b.number, b.title, b.latest_action,
               b.latest_action_date, s.stage, s.chamber, s.current_chamber,
               (SELECT v.version_code FROM bill_versions v
                 WHERE v.congress = b.congress AND v.bill_type = b.bill_type
                   AND v.number = b.number
                 ORDER BY v.first_seen DESC, v.version_id DESC LIMIT 1) AS version_code
          FROM bills b
          LEFT JOIN stages s USING (congress, bill_type, number)
         ORDER BY COALESCE(b.latest_action_date, '') DESC, b.bill_type, b.number
        """
    ).fetchall()

    # Public tallies, keyed to the exact (bill, version) being voted on. If the
    # votes table is absent (a pre-S3 database), every tally is simply empty.
    counts: dict = {}
    try:
        for r in con.execute(
            "SELECT congress, bill_type, number, version_code, choice, COUNT(*) "
            "FROM votes GROUP BY 1, 2, 3, 4, 5"
        ).fetchall():
            counts[(r[0], r[1], r[2], r[3], r[4])] = r[5]
    except sqlite3.OperationalError:
        pass

    def tally_for(r: sqlite3.Row) -> dict:
        vc = r["version_code"]
        if not vc:
            return {}
        return {c: counts.get((r["congress"], r["bill_type"], r["number"], vc, c), 0)
                for c in ("yea", "nay")}

    # The official tallies that MAY carry a gap: votes of the text only. A procedural
    # vote is the chamber deciding whether to proceed, not whether it agrees, so it is
    # recorded but never measured against. Ordered ASC so the latest overwrites.
    official: dict = {}
    try:
        for o in con.execute(
            """SELECT congress, bill_type, number, chamber, roll_call, question,
                      yea, nay, vote_class
                 FROM official_tallies WHERE vote_class = 'of_the_text'
                ORDER BY roll_call ASC"""):
            official[(o["congress"], o["bill_type"], o["number"])] = o
    except sqlite3.OperationalError:
        pass

    if rows:
        ledger = "\n".join(
            bill_row(r, r["version_code"], tally_for(r), base_path,
                     official.get((r["congress"], r["bill_type"], r["number"])))
            for r in rows)
    else:
        ledger = ('    <li class="empty">No bills ingested yet. Run '
                  '<code>python3 engine/poll.py</code>.</li>')

    # An absent gap is a property of the DAY, not of a row: said once, above the list,
    # instead of the same sentence twelve times inside it.
    if official:
        gap_note = ""
    else:
        gap_note = ('  <p class="empty">No tracked bill has a passage vote recorded yet, '
                    'so no gap can be reported for any of them. A reading is still '
                    'welcome — it is recorded as a leaning.</p>\n')

    open_count = sum(1 for r in rows if vote_state(
        official.get((r["congress"], r["bill_type"], r["number"]))) == "open")

    body = masthead([
        f'Today — <b><time datetime="{esc(today)}">{esc(human_date(today))}</time></b>',
        f"Bills tracked: <b>{len(rows)}</b>",
        f"Vote open: <b>{open_count}</b>",
    ]) + f"""
<main id="main">
{gap_note}  <ul class="ledger">
{ledger}
  </ul>

  <section class="sched" aria-labelledby="sched-h">
    <h2 class="sched-h" id="sched-h">Schedule <span class="sub">— what's coming, and when</span></h2>
    <ul class="slist">
      <li class="srow undated">
        <span class="sdate">No date set</span>
        <span class="sbill">Committee-meeting dates are not ingested yet</span>
        <span class="swhat">Feed not wired</span>
        <span class="sflag"><b class="uns">Expected</b></span>
      </li>
    </ul>
    <p class="snote">
      Dated entries come from published <b>committee</b> schedules, which are not
      ingested yet. Floor votes are rarely scheduled more than a few days ahead, so
      most bills will legitimately carry no date and are shown as
      <b>Expected</b> — never given an invented one. Same rule as the gap: if the
      date does not exist, do not draw it.
    </p>
  </section>
</main>
"""
    return page("Boule — today's bills", body, "Today", base_path=base_path)
