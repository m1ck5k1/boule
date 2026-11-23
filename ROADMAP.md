# Boule — Roadmap

Short on purpose. See [`VISION.md`](VISION.md) for what Boule is and [`DESIGN.md`](DESIGN.md)
for what it looks like. Nothing here overrides those two.

---

## Standing requirements — not phases

These apply to **every** line below. They are not a stage you reach; they are the floor you
stand on for the whole build.

### 1. Accessibility floor — WCAG 2.2 AA, every screen, every release

Not a later phase. A screen that excludes a blind or deaf citizen excludes *a citizen*, which
is the exact failure the project exists to audit.

- **Verified, not assumed.** Every UI change runs through an automated check (`axe-core`,
  0 violations required) **and** a manual pass — because automation cannot see the two worst
  failures here (a button with no context, and a chart with no spoken equivalent).
- **Every data visual carries a spoken equivalent.** The bars on the front page are
  `aria-hidden` decoration; the numbers are exposed as a sentence. This is a *rule*, not a fix.
- **Redundant encoding.** Nothing may be conveyed by colour alone. The gap is red *and*
  labelled *and* positioned; open/closed state is carried by form, not hue.
- **Keyboard first.** Visible focus, logical tab order, no traps, skip link, 44px minimum
  hit targets.
- **Motion opt-out.** Anything non-trivial respects `prefers-reduced-motion`.
- **Deaf users:** the LEGIBLE register today is text-only, so it is audio-free by
  construction. The moment the **LOUD** register ships any audio or video (posters do not,
  clips do), it needs **captions and a transcript** — no exceptions.

### 2. The design test
Remove all styling — are the two numbers still the loudest thing on the page? (DESIGN.md §1)

### 3. The feature filter
Does it make the gap clearer? If not, it does not ship. (VISION.md §9)

---

## Accessibility — where we actually are

| Item | State |
|---|---|
| Automated audit (`axe-core`, WCAG 2.2 A/AA + best-practice) | ✅ **0 violations** — paper and ink modes |
| Contrast (all text + non-text UI) | ✅ measured: worst case 4.62:1 (Δ red on paper) |
| Heading structure, landmarks, skip link | ✅ |
| Data visuals have spoken equivalents | ✅ |
| Distinct accessible name per vote button | ✅ |
| Hit targets ≥44px | ✅ |
| Reduced-motion honoured | ✅ |
| **Tested with a real screen reader** (VoiceOver / NVDA) | ❌ **not done — automation is not a substitute** |
| **Live tally updates announced** (`aria-live` / `role="status"`) | ❌ not built — needed when tallies stream |
| Sign-in form: labels, error states, autocomplete | ❌ not built |
| Colour-blind simulation (deuteranopia/protanopia) on the gap | ❌ not checked |
| Captions/transcripts for any LOUD-register audio or video | ❌ n/a yet; required when it ships |
| Plain-language summary per bill (cognitive load) | ❌ not built — strongly advised |

**The two open ones that matter most:** a real screen-reader pass, and `aria-live` for tallies
that change while you are on the page. Both are cheap now and expensive after the voting layer
exists.

---

## Data sources — what feeds what

The Schedule view exposed a gap in the pipeline: the poller only looks at **recent past**
activity (`sort=updateDate desc` + a look-back window). Nothing supplies future dates.

| Feed | Source | Status |
|---|---|---|
| Bills that recently moved | Congress.gov `/bill/{congress}?sort=updateDate desc` | ✅ live (existing poller) |
| Stage history + roll calls | Congress.gov `/bill/.../actions` | ⛔ not wired |
| **Future committee dates** | Congress.gov `/committee-meeting/{congress}/{chamber}` | ⛔ **not wired — required for Schedule** |
| Future floor dates | House/Senate leadership schedules — **not in the API** | ⛔ not available |
| **CRS summary (L1)** | Congress.gov `/bill/.../summaries` | ⛔ **not wired — required for the Bill page** |
| Bill full text (L3) | Congress.gov bill XML — `tools/ingest_bill.sh` | ✅ exists, not wired to the UI |
| Version diff (L2) | `tools/diff_bills.sh` | ✅ exists, not wired to the UI |

**CRS summaries are version-tagged** (`versionCode` + `actionDesc`, e.g. `00 / Introduced in
House`), which lines up with the `(bill, version)` vote key: the summary shown can be pinned to
the exact text being voted on. This is the only route to a defensible reading layer — Boule must
not author it.

**Consequence:** the Schedule can only be as good as row 3. Floor votes rarely carry a date in
advance, so most future entries will legitimately read **Expected** — undated — and the UI must
say so rather than invent one. Same rule as the gap: if the date does not exist, do not draw it.

---

## Wiring it up — the stage ladder

One stage at a time. **Each stage has a gate fixed before it is built**, and a gate is a
pass/fail test, not a demo. No stage starts until the previous gate passes.

| Stage | Build | Gate — the test that must pass | State |
|---|---|---|---|
| **S0** | preview served by a supervised service | kill the process → systemd replaces it; survives reboot; HTTP 200 over tailnet | ✅ **done** |
| **S1** | Congress.gov client → SQLite (`bills`, `bill_versions`, `actions`) | for one real bill the DB holds its actions in order and the derived **stage matches congress.gov** | ✅ **done — 6/6 in CI** |
| **S2** | front page renders from the DB, not from HTML | edit a DB row → the page changes **without touching HTML** | ✅ **done — gate passed** |
| **S3** | ballot box: append-only `votes`, `POST /api/vote`, server-side stamp, keyed `(bill, version)`, two-step confirm | changing a vote **adds a row and never mutates the old one**; no `UPDATE`/`DELETE` can run (DB trigger) | ✅ **done** — `engine/gate_s3.py` |
| **S3.5** | the **Bill page** — a real `/bill/{congress}/{type}/{number}` route (the first dynamic route) | server and static are byte-identical for a bill page; the stage matches the DB; zero JS | ✅ **done** — TWIN gate 5/5 |
| **S4** | gap computed from public ⨯ official | the gap equals `public% − official%` on a known bill; a bill with **no** official vote renders `—`, never `0` | ✅ **done 19 Nov** — `f6b8988`, live, Δ 28 on HR 2347 |
| **S5** | the ballot box becomes **device-scoped**: a key is issued at install and refused a second reading on the same `(bill, version)` | the same device key **cannot** record two readings on one `(bill, version)`; `provenance` reads `device` vs `anonymous` | ✅ **done 19 Nov** — `gate_s5.py` 10/10 and `gate_s5_http.py` 10/10; the refusal is a 409 page, not an error |
| **S6** | **installable PWA** (manifest, service worker, icons) | "Add to Home Screen" installs, and the app holds a key the server honours | ⬜ **load-bearing — the install *is* the identity mechanism** |
| **S7** | **the published ledger** — `/data`, the audit pack, the aggregates (`DATA.md`) | `engine/gate_publish.py` passes, and the published tally recomputes to the same number the page shows | ⬜ |
| **S8** | public deploy (VPS + domain) *(was S7)* | first non-tailnet visitor can read and vote | ⬜ |

### Two ordering corrections, both forced by verified constraints

**1. HTTPS must move ahead of S5 AND S6 — for a different reason than we first wrote.** Not
OAuth (there is no identity provider any more) but the **service worker**: a service worker runs
only in a **secure context**, so an installable app cannot exist over plain HTTP. And the install
is what makes a device key durable — which is what turns "one reading per device" into a real
claim rather than a hopeful one. TLS is therefore the prerequisite of the *identity mechanism
itself*. A **Cloudflare Tunnel** on `boule.incidium.net` gives HTTPS on a domain we own, with no
open ports; that is the shortest path, and it also fronts S8.

**2. S3 must record provenance from its first row.** The column has to exist from the start, or
S5 arrives with a body of already-cast readings that cannot be attributed. **Settled in
practice:** `provenance` was created with the table, every existing row reads `anonymous`, and
that is exactly what those rows are.

**Consequence for the exit criteria:** the phase exit used to read *"open it, sign in, vote on a
real bill, and see both tallies"*. **Sign-in is struck out** — there is no sign-in, by design. The
exit is now: *install it, record one reading per device against a real bill, and see both tallies.*

### Identity prerequisites — SUPERSEDED

This section planned a Google OAuth consent screen, test-user allowlists and scope lists.
**None of it applies.** Boule has no identity provider, no consent screen, no OAuth domain
verification and no scopes — the device key removed the entire problem. Kept only so
future-selves can see the road not taken.

| | Needed for sign-in? | Needed for a logo on the consent screen? |
|---|---|---|
| OAuth consent screen configured | ✅ yes | ✅ yes |
| Redirect URI on HTTPS, non-IP host | ✅ yes | ✅ yes |
| **Privacy policy** | ⬜ no | ✅ yes |
| **Homepage on a domain you own** | ⬜ no | ✅ yes |
| **Search Console domain verification** | ⬜ no | ✅ yes |
| Google verification review | ⬜ no | ✅ yes (brand) |

So brand verification is **optional**, and the honest reason to do the policy and homepage anyway is
that a project recording people's political opinions owes them one regardless of what a vendor
requires — and any future sensitive scope makes it mandatory.

**Done:** `legal/privacy.html` is written and served at `/privacy`, linked from the homepage footer
(as Google requires), axe-clean. It names the exact three scopes, carries the required Limited Use
sentence and a link to the Google API Services User Data Policy, and states plainly what is never
done.

**The append-only / erasure tension is resolved in writing.** Deleting an account destroys the
identity link so the votes become permanently unlinkable, and the anonymous count stays. Changing a
vote appends a new record rather than editing the old one. That is the only honest way to reconcile
"never rewrite the record" with a right to erasure, and it needs to be in the policy, not discovered
later.

**Open, and listed in the policy as open** rather than promised: IP retention, whether an email is
stored at all, retention of anonymised votes in an already-published dataset, and whether any
analytics exist. The policy is marked **draft, not in force** until these are settled.

**Only a human can clear these:** create the GCP project + OAuth client; verify `incidium.net` in
Search Console with an account that owns the project; point a hostname at a machine with TLS.

**Domain reconnaissance:** `incidium.net` is theirs, DNS on Cloudflare, host on OVH, and the apex
serves the **live Incidium business site** — not to be touched. `*.incidium.net` is a **wildcard**,
so `boule.incidium.net` resolving proves nothing; it returns **000** over HTTPS because no
certificate exists for it. Google verifies the *top private domain*, so a homepage at
`boule.incidium.net` is fine while ownership is verified once for `incidium.net`.

**Order rationale:** each stage is falsifiable on its own and none depends on a later one. S1–S2
give an honest read-only site before a single vote exists — the site is useful with zero voters.

### Hosting architecture: the split, and where the money actually is

**Decision (18 Nov): split the read path from the write path.** Reading is static; only voting
needs a live origin.

| Tier | Workload | Host | Free ceiling | First dollar |
|---|---|---|---|---|
| **Read** | pages | static — GitHub Pages, R2, any web server | **3.9M views/month** (Pages' 100 GB soft cap) | $0 |
| **Write** | one INSERT per vote | tiny API — Cloudflare Worker + D1 | **3.45M votes** (500 MB D1 cap; 100k writes/day) | **$5/month** |
| **Corpus** | publish the dataset | R2 | 10 GB | $2/month at 1B votes |
| Identity | OAuth | Google / Microsoft | — | $0 |
| TLS + DNS | — | Cloudflare | — | $0 |

**Measured, not guessed:** a page view is **25,557 B cold / 16,079 B cached**; a vote is **~145 B**
including its index; the front-page query runs in **0.04 ms**. Egress is the only line that scales
with success, and a static read path has none. The vote ledger — the thing that *sounds* like it
needs a cluster — is 145 bytes a row, so a billion votes is 145 GB, and R2 charges **zero egress**
(verified), which retires the original reason BitTorrent was on the list.

**The catch, recorded now rather than discovered later:** a static page cannot show a live tally.
The gap changes, so it must either be rebuilt on a schedule — stale by that interval — or fetched
client-side, which means a JS dependency and moving the `sr-only` tally equivalents into a proper
live region. That is real S3 work and a deliberate staleness decision, not a footnote.

**Reversibility is the whole point.** The static half can move to R2 or any web server with a
one-line change, so choosing GitHub Pages today does not commit the project to GitHub. That matters
here: a platform recording people's political opinions on someone else's infrastructure is a
dependency worth keeping cheap to leave.

**Enabling capability, built and gated (5/5):** `web/build.py` emits the whole read path as static
files, `render.ROUTES` is the single source of truth for what exists, and `web/gate_static.py`
proves it. The load-bearing check is **TWIN** — the built pages must be *byte-identical* to what the
server serves for the same database, so the static site and the live site cannot drift apart.

The gate earned that on its first run: it caught that the nav linked to `/bills`, `/gap` and `/me`
while the build emitted neither, so **three of four nav links would have 404'd on Pages**. Fixed by
rendering every route in `ROUTES` through the same function the server uses, including honest
`stub_page` output for surfaces that are named but not built — a link to a 404 is the same class of
lie as a button that does nothing.

### S1 blocker — resolved, with a caveat

`CONGRESS_API_KEY` is **not** local (the repo `.env` holds only `AIRTABLE_PAT`), and GitHub
Actions secrets cannot be read back. However **`DEMO_KEY` works** (verified: HTTP 200, real
payload) at **`x-ratelimit-limit: 10`** — enough to *prove* the S1 gate against one bill, not
enough to run the poller. The real key is still needed for the pipeline proper.

---

## Phases

### Phase 0 — the mock ✅
`DESIGN.md` + `design/front-page.html`. Design language settled; accessibility audited and
passing automation.

### Phase 1 — the ballot box (mbp9)
The smallest thing that actually works: one identity provider, one append-only votes table,
the front page reading real bills from the existing poller.

**Exit criteria:** a real person can open it, sign in, vote on a real bill, and see both
tallies. Accessibility floor met on the real screens, not just the mock.

### Phase 2 — go public
The identical stack on a rented box with a real domain. Then:
- `aria-live` announcements for changing tallies
- screen-reader pass on every screen
- the QR code regenerated against the live URL (`marketing/make_qr.py`)

### Phase 3 — The Gap
The page that is the product: divergence over time, per bill and in aggregate. Editorial
register (DESIGN.md school B).

### Parked (revisit against the feature filter)
BitTorrent/IPFS distribution · the "cheat as a game" sandbox · differential privacy ·
decentralised DNS · the LOUD/marketing register · native apps.

---

## Changelog

| Date | Change |
|---|---|
| 2026-11-17 | Roadmap opened. Accessibility added as a standing requirement, with its current state recorded honestly rather than assumed. |
| 2026-11-19 | **S4 closed** (Δ 28 on HR 2347). **S5 built and gated**: a device key is issued at `/api/device` and set as an HttpOnly/Secure/SameSite cookie, one reading per device per version is refused by a **partial UNIQUE index** (not by a code check, so there is no window to race), and `provenance` is forced to agree with `voter_key` by trigger. Anonymous readings stay repeatable — the limit is a claim about *devices*, and must not silently become one about people. |
