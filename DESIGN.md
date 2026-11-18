# Boule — Design System

> **Look like the document, not the brochure.**

Companion to [`VISION.md`](VISION.md). That document says what Boule is; this one says what it
looks like and, more importantly, what is **forbidden**.

---

## 1. The test that governs everything else

> **Remove all styling. Are the two numbers still the loudest thing on the page?**

If yes, the design is inside the system. If no, it has drifted back toward the brochure.

### The naming rule — the joke keeps a straight face

> **Boule is also known as Boule Schit. It is never explained, never coloured, never set apart.**

- **British irony is structural, not announced.** The words are laid out in the same
  register as everything else, and the page never acknowledges them. A joke that is
  labelled, or set in a different typeface, or winked at, is not British — it is a novelty.
- **Two placements, both in the flattest spot available.** The dictionary entry in the
  masthead (*Boule Schit /ˌbuːl ˈʃɪt/ — (n.) 1. a council that prepared the motions;
  2. what became of them.*) and the *also known as* line in the footer small print.
  Nowhere else.
- **It never touches the numbers.** Not the vote button, not the tallies, not the gap.
  Decorating the legible register is how civic-tech funk fails. The joke lives *around*
  the data, never on it.
- **The name does not change.** Repo, URL and wordmark stay `boule` — this is what the
  trade calls it, not what it is registered as.
- **The LOUD register may shout it.** On a poster, a QR card or social it may be the
  headline, larger than the wordmark. In the product it is a footnote.

---

## 2. What is banned, and why

"Corporate" design is not a vibe — it is a specific grammar:

> hero band → three feature cards → gradient blob → friendly rounded sans → pastel →
> stock photo → "trusted by" badges.

Its function is to **signal confidence**, not to convey information.

**Why that is disqualifying here specifically:** that grammar *is the UI of the thing Boule
audits.* Congress.gov, the CBO summary, the bill landing page — all of them look like that.
Adopt it and the audit instrument wears the costume of its subject.

Also banned: decorative gradients, glassmorphism, icon toppers, accent rails, feature-tile
grids, monument statistics, centred stacks, emoji, and any colour used for mood.

---

## 3. Schools considered

| | School | Verdict |
|---|---|---|
| **A** | Public-information / ballot vernacular (ballot papers, official notices, forms, ISO safety signage) | **Accepted — primary.** Instantly civic; owned by nobody |
| **B** | Editorial / financial page (broadsheet, ledger) | **Accepted — for dense views.** The historical Gap page is a financial page |
| **C** | Data-native / procedural (Isotype/Neurath, Tufte lineage) | **Accepted — primary.** Nothing decorative; everything encodes |
| **D** | Terminal / documentation (man page, diff, log) | **Accepted — sub-register only.** The audit/integrity log should look like a log |
| **E** | Brutalist web / anti-design | **Rejected.** Reads unfinished; unfinished is not trusted with a vote |
| **F** | Zine / protest print | **Rejected.** Reads as a campaign, which breaks "not a rival" |

**The direction is A + C: a ballot rendered by the data.**

---

## 4. Tokens

```
--paper      #FAF9F6    surface (a document, not a screen)
--ink        #14130F    primary text + data
--ink-2      #4A463D    secondary text, the "official" bar
--rule       #D9D5CC    hairlines
--track      #E7E3DA    empty bar track
--signal     #C8442A    THE GAP. Nothing else. Ever.
--ch-house   #DCE4EC    chamber of origin: House   (not the signal family)
--ch-senate  #E8DFC6    chamber of origin: Senate  (not the signal family)
```

Inverted ("ink") mode swaps paper/ink; `--signal` lifts to `#E4643F` for contrast on dark, and
the chamber tints darken to `#1D2933` / `#2C2818`.

> **Known gap:** the chamber tints are deliberately quiet (see the colour law), and on the ink
> ground they only just separate. Tighten them when ink mode is actually reachable — it has no
> toggle and no `prefers-color-scheme` today, so no reader can see it yet.

### Type

- **One grotesque**, system stack: `"Helvetica Neue", Helvetica, Arial, sans-serif`.
  The grotesque of forms and notices. Chosen, not defaulted to.
- **Tabular figures are mandatory** (`font-variant-numeric: tabular-nums`). If the numerals
  do not align column-to-column, the gap is unreadable. This is product, not style.
- **Mono** (`ui-monospace, "SF Mono", Menlo, monospace`) for bill identifiers and raw counts.
- **Letterspaced caps** (`0.14em`) for labels and states — form language, not UI language.
- **The wordmark carries a dictionary gloss.** `BOULE /ˈbuːli/` — the pronunciation of the
  *ancient-Greek council* sense, which is the sense the project is named after. Note the
  homographs: /buːl/ ("BOOL") is the gem/pétanque word and is **wrong** here; Modern Greek
  is *Vouli* (βουλή). The gloss resets the wordmark's caps and letterspacing, and is
  `aria-hidden` — IPA helps the eye, and a screen reader would read it as punctuation soup.
- **The masthead is always two lines:** wordmark + gloss on line 1 with sign-in pushed right,
  the tagline on line 2.
- **No icons.** Hierarchy comes from scale, weight, and rules.

### The reading stack — four depths, none of them ours

Nobody reads 214 pages, including the people who vote on them. So the Bill page is a **depth
stack**, and the first three layers carry **no Boule-authored prose**:

| Layer | Content | Author |
|---|---|---|
| **L0** | one line: what it does | condensed from CRS, attributed |
| **L1** | the official CRS summary, pinned to the version being voted on | **CRS** |
| **L2** | what changed since the last version | `diff_bills.sh` |
| **L3** | the full text, one link to congress.gov | **the bill itself** |

**The rule:** an AI summary of a bill is the same category of artefact Boule exists to audit. If
Boule narrates the bill, Boule becomes a narrator with an agenda — indistinguishable from the
corporate cost estimates it was built to check. So the reading layer is the government's own
material, and every layer names its source.

Where Boule *does* interpret, it is **boxed, labelled Opinion, and never the only text on the
screen** — and it states that it was not written by CRS.

**Accessibility note — target size.** WCAG 2.2 AA (2.5.8) requires **24×24 CSS px**, not 44; 44 is
the AAA/Apple-HIG figure. Hold **≥44px on genuine controls** (buttons, nav links, skip link) and ≥24px
on links that sit inline in a sentence, which 2.5.8 explicitly exempts.

### The vote button — a three-state rule

The button is **not always on**. It appears when Boule can name the official vote the public
tally will be compared against, and its meaning changes with the stage:

| State | Trigger (from `/actions`) | Control | Counts as |
|---|---|---|---|
| **Open** | version on the floor / called up, no `recordedVote` yet | solid **Put it to the vote** | the gap |
| **Early** | bill live, no official vote scheduled | outline **Record a view** | a leaning, not a gap |
| **Closed** | a `recordedVote` is present | none → **Record closed** | frozen |

Hierarchy is carried by **form** (solid vs outline), never by hue. An early view can forecast but
cannot measure — there is no official comparator to subtract it from. This is why the front page
reads `Vote open: 1 · Early views: 2` rather than a single inflated count.

**Focus rings are `--ink`, not `--signal`.** A red focus ring spends the gap colour on something
that is not a gap, which breaks the colour law.

### Colour law

- Paper and ink carry the structure.
- **`--signal` is reserved for the gap** and its Δ readout. Nothing else.
- **State is carried by form, not hue** — an open bill has a *solid* dot, a closed one a
  *hollow* dot. Nav current-page is an ink underline, not a coloured one.
- The single exception: focus rings may use `--signal` (accessibility beats purity).
- **One other colour role exists: `--ch-house` / `--ch-senate`, the chamber a bill starts in.** It
  sits deliberately *outside* the signal family, so it can never be mistaken for the gap. It is
  information, not ornament: the chamber a bill starts in decides which body votes first, and it is
  the one thing a reader wants at a glance once a list mixes the two. Types are mapped by chamber,
  so the rule covers all eight and not merely HR and S.
  - **Never colour-alone.** The letterform (HR / S) is always present, so the distinction survives
    monochrome and colour-blindness. An unmapped type takes the neutral track tint rather than
    being silently handed a chamber it does not have.

---

## 5. The gap — how it is drawn

The gap is **drawn, never framed**.

- Two tracks share one 0–100% scale: **PUBLIC** (ink) above **OFFICIAL** (`--ink-2`) below.
- The **official bar carries a `--signal` tail** that reaches the public bar's end.
  The tail *is* the difference. No box, no border, no highlight — a bordered region reads
  as a selection state, which is a lie.
- A `Δ n points` readout in mono sits beneath, in `--signal`.
- **Where no official vote exists, no gap is drawn.** The official track stays empty and
  reads `—`, with the note *"No recorded vote yet — no gap to report."* A forecast is not
  a gap, and the design must not imply one.

---

## 6. Composition

- **Surface first.** The front page is an **Operate** surface (the user acts) with
  **Compare** secondary. It is *not* a Decide/Learn surface — **no hero, no feature tiles.**
- **Masthead** = a document header: letterspaced wordmark, one-line tagline, sign-in. Thin.
- **Dateline** = where-am-I state, not marketing: the date and how many bills are open.
- **The ledger** = hairlines between rows. **No cards, no shadows, no border radii.**
- **Nav** = a row of caps text links, like a form footer. Four pages only:
  Today · Bills · The Gap · Me.
- **Density over airiness.** This is a document a person reads to decide something.

---

## 7. Motion

Only where it encodes a change. A bar may animate when a tally changes. Nothing ambient,
nothing looping, nothing that delays the user. Respect `prefers-reduced-motion`.

---

## 8. Accessibility

- **The bars are decoration; the numbers are the data.** Every bar block is `aria-hidden`,
  and each record carries a visually-hidden sentence with the real figures *and* the gap.
- **Nothing is conveyed by colour alone.** The gap is red *and* labelled *and* positioned;
  open/closed state is carried by form, not hue.
- **Distinct accessible name per control.** Three "Put it to the vote" buttons must not read
  identically to a screen reader — each carries the bill it belongs to.
- **One `<h1>`, real landmarks, a skip link, 44px hit targets, visible focus,**
  `prefers-reduced-motion` honoured.
- **Automated audit is the floor, not the proof.** `axe-core` must report zero violations on
  every screen; a real screen-reader pass is still required. See [`ROADMAP.md`](ROADMAP.md).

---

## 9. Files

- `design/front-page.html` — the front page mock (self-contained; `?ink=1` for dark mode).
  Sample data, clearly labelled.

---

## 10. Changelog

| Date | Change |
|---|---|
| 2026-11-17 | Accessibility pass. Added `<h1>`, landmarks, skip link, spoken equivalents for every tally, distinct button names, 44px targets. `axe-core`: 0 violations (paper + ink). Added §8. |
| 2026-11-17 | System established. A+C fusion adopted; E and F rejected. The gap drawn as a tail on the official bar after a bordered caliper was found to read as a selection state. Colour law tightened so `--signal` is the gap only. |
