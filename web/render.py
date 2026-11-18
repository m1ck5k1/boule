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
import sqlite3
from datetime import date
from pathlib import Path

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
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{body}
<nav class="nav" aria-label="Sections">
{nav}
</nav>
<footer class="note">
  <b>Boule is a second tally that runs beside the real one, so the gap becomes
  visible.</b> This is the read-only build: bills and their stages are real and
  come from Congress.gov. Voting is not open yet, so no public tally and no gap
  are shown — an empty tally is a fact, a zero would be a claim.
  <span class="legal-links"><a href="{href('/privacy')}">Privacy</a></span>
</footer>
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
  </div>
  <div class="dateline">{tail}</div>
</header>
"""


def bill_row(row: sqlite3.Row) -> str:
    bill_type = (row["bill_type"] or "").upper()
    number = row["number"]
    title = row["title"] or "(no title)"
    stage = stage_text(row["stage"], row["chamber"], row["current_chamber"])
    label = f"{bill_type} {number}"
    return f"""    <li><article class="bill" aria-labelledby="b-{esc(bill_type)}-{esc(number)}">
      <div>
        <div class="bill-id">{esc(label)}</div>
        <h2 class="bill-title" id="b-{esc(bill_type)}-{esc(number)}">{esc(title)}</h2>
        <p class="stage"><span class="dot" aria-hidden="true"></span>{esc(stage)}</p>
      </div>

      <p class="sr-only">
        No public tally yet — voting is not open. No official tally recorded yet.
        No gap can be reported without both.
      </p>
      <div class="tallies" aria-hidden="true">
        <div class="trow">
          <span class="tlabel">Public</span>
          <span class="track"></span>
          <span class="tpct">—</span>
          <span class="tcount">—</span>
        </div>
        <div class="trow">
          <span class="tlabel">Official</span>
          <span class="track"></span>
          <span class="tpct">—</span>
          <span class="tcount">—</span>
        </div>
        <p class="nogap">No tallies yet — no gap to report.</p>
      </div>

      <div class="act">
        <span class="voted">Voting not open</span>
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
               b.latest_action_date, s.stage, s.chamber, s.current_chamber
          FROM bills b
          LEFT JOIN stages s USING (congress, bill_type, number)
         ORDER BY COALESCE(b.latest_action_date, '') DESC, b.bill_type, b.number
        """
    ).fetchall()

    if rows:
        ledger = "\n".join(bill_row(r) for r in rows)
    else:
        ledger = ('    <li class="empty">No bills ingested yet. Run '
                  '<code>python3 engine/poll.py</code>.</li>')

    body = masthead([
        f'Today — <b><time datetime="{esc(today)}">{esc(human_date(today))}</time></b>',
        f"Bills tracked: <b>{len(rows)}</b>",
        "Vote open: <b>0</b>",
    ]) + f"""
<main id="main">
  <ul class="ledger">
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
