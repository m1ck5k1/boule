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
| **S1** | Congress.gov client → SQLite (`bills`, `bill_versions`, `actions`) | for one real bill the DB holds its actions in order and the derived **stage matches congress.gov** | ⬜ next |
| **S2** | front page renders from the DB, not from HTML | edit a DB row → the page changes **without touching HTML** | ⬜ |
| **S3** | ballot box: append-only `votes`, `POST /api/vote`, server-side stamp, keyed `(bill, version)` | changing a vote **adds a row and never mutates the old one**; no `UPDATE`/`DELETE` can run (DB trigger) | ⬜ |
| **S4** | gap computed from public ⨯ official | the gap equals `public% − official%` on a known bill; a bill with **no** official vote renders `—`, never `0` | ⬜ |
| **S5** | identity + one-per-person | two accounts cannot double-vote the same `(bill, version)`; provenance tier visible | ⬜ |
| **S6** | installable PWA (tailscale cert, manifest, service worker, icons) | "Add to Home Screen" **installs** — opens without browser chrome | ⬜ |
| **S7** | public deploy (VPS + domain) | first non-tailnet visitor can vote | ⬜ |

**Order rationale:** each stage is falsifiable on its own and none depends on a later one. S1–S2
give an honest read-only site before a single vote exists — the site is useful with zero voters.

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
