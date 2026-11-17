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
