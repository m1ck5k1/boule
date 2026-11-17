# Boule — Design System

> **Look like the document, not the brochure.**

Companion to [`VISION.md`](VISION.md). That document says what Boule is; this one says what it
looks like and, more importantly, what is **forbidden**.

---

## 1. The test that governs everything else

> **Remove all styling. Are the two numbers still the loudest thing on the page?**

If yes, the design is inside the system. If no, it has drifted back toward the brochure.

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
```

Inverted ("ink") mode swaps paper/ink; `--signal` lifts to `#E4643F` for contrast on dark.

### Type

- **One grotesque**, system stack: `"Helvetica Neue", Helvetica, Arial, sans-serif`.
  The grotesque of forms and notices. Chosen, not defaulted to.
- **Tabular figures are mandatory** (`font-variant-numeric: tabular-nums`). If the numerals
  do not align column-to-column, the gap is unreadable. This is product, not style.
- **Mono** (`ui-monospace, "SF Mono", Menlo, monospace`) for bill identifiers and raw counts.
- **Letterspaced caps** (`0.14em`) for labels and states — form language, not UI language.
- **No icons.** Hierarchy comes from scale, weight, and rules.

### Colour law

- Paper and ink carry the structure.
- **`--signal` is reserved for the gap** and its Δ readout. Nothing else.
- **State is carried by form, not hue** — an open bill has a *solid* dot, a closed one a
  *hollow* dot. Nav current-page is an ink underline, not a coloured one.
- The single exception: focus rings may use `--signal` (accessibility beats purity).

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

## 8. Files

- `design/front-page.html` — the front page mock (self-contained; `?ink=1` for dark mode).
  Sample data, clearly labelled.

---

## 9. Changelog

| Date | Change |
|---|---|
| 2026-11-17 | System established. A+C fusion adopted; E and F rejected. The gap drawn as a tail on the official bar after a bordered caliper was found to read as a selection state. Colour law tightened so `--signal` is the gap only. |
