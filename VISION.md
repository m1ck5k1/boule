# Boule — Vision

> **Boule is a second tally that runs beside the real one, so the gap becomes visible.**

This is the north star. If a future decision contradicts this document, one of the two is
wrong — decide which, deliberately.

---

## 1. The thesis

Every day someone in Congress says *"the American people want this."* Everyone says it. It is
the most asserted and least measured claim in politics — measured once every two years, in an
aggregate that says nothing about any specific bill.

**Boule makes that claim measurable.** Not at election time, not as a poll — continuously, per
bill, at the moment the bill is actually decided.

So: **Boule is not a rival to Congress. It is an audit of representation.** It does not produce
a verdict. It produces a number that does not currently exist — the public's verdict on *this*
bill, timestamped to *this* stage — sitting beside the official one.

The word for that output is **the gap**.

---

## 2. What Boule is not

- **Not a rival legislature.** It cannot bind anyone. It observes.
- **Not a poll.** Polls are occasional and selective; this is continuous and per-bill.
- **Not a social network.** Engagement is not a goal. See §9.
- **Not a native app.** No app store, no gatekeeper, no second codebase.
- **Not distributed, not blockchain, not microservices.** Deliberately boring — see §11.

---

## 3. The core loop

1. **Congress moves.** A bill changes stage — introduced, out of committee, passed the House.
2. **The poller sees it.** The existing Bill Monitor watches the Congress.gov actions feed and
   publishes: *this bill is open at this stage.*
3. **The bill opens for a public vote.** One tap: *Put it to the vote!*
4. **People vote.** One person, one vote, tagged with how they were identified (§7).
5. **Two tallies are published side by side** — public and official.
6. **The gap is recorded.** When the stage closes, the public tally is frozen beside the
   official one. That frozen pair is the product.

The loop closes itself: the same feed that opens a vote closes it.

---

## 4. The gap

Everything exists to produce this:

```
        PUBLIC          OFFICIAL
  ────────────────────────────────
  H.R. 10983    68%    ████████░░   │  passed 219–207
  S. 4412       12%    █░░░░░░░░░   │  passed  71–29
```

Per bill. Per stage. Per year. Per party-in-power. The accumulated record of where the public
and its representatives disagree is the thing nobody has.

---

## 5. The data

Every vote is an append-only record. Anonymised, it is released for research.

- **Small.** One billion votes ≈ **40 GB** columnar. A laptop, not big data.
- **Immutable.** Append-only; nothing is edited after the fact.
- **Open.** The anonymised corpus is public. Foreign-journalism value, not just ours.

Caution carried forward: country/timezone/timestamp combinations are quasi-identifiers. Release
aggregates and coarse buckets; do not release anything that singles out a person in a small
group.

---

## 6. The identity stance

**Identity is not Boule's problem to solve.** We do not invent proof-of-personhood, Sybil
resistance, or eligibility rolls. We **delegate identity, and own the tally.**

Consequence: whether Boule is a *poll* or a *proxy vote* is a **configuration**, not a rewrite.
That choice is a product decision to be made on the evidence, not baked in now.

---

## 7. Trust, minimally

Not a distributed ledger. Three things:

1. **One identity provider** to start (Google sign-in), with a provenance tag on the vote.
2. **One append-only votes table.** A vote is written once and never changed.
3. **One signed daily root** of the tally, published. Enough that tampering is *detectable*.

That is the entire integrity story. It is enough.

---

## 8. The interface

**The front page is today's question** — not a menu.

```
┌──────────────────────────────────────────┐
│  BOULE                        [ sign in ] │
│  Today — Tue 17 Nov 2026                  │
├──────────────────────────────────────────┤
│  OPEN FOR A VOTE NOW                      │
│  ┌────────────────────────────────────┐  │
│  │ H.R. 10983 — short title           │  │
│  │ stage: Passed House → Senate       │  │
│  │  [ Put it to the vote! ]           │  │
│  │  public 1,204  ‖  official 219     │  │
│  └────────────────────────────────────┘  │
│  …and the other bills open today…         │
├──────────────────────────────────────────┤
│  [ Today ] [ Bills ] [ The Gap ] [ Me ]   │
└──────────────────────────────────────────┘
```

**The floor — four pages, near-certain:** Today · a Bill · The Gap · Me.

Everything else is one tap away and **can be promoted later** (§10).

---

## 9. The discipline

**Rank features by usefulness to the gap — not by clicks.** A feature that makes people stay
longer has earned nothing. A feature that makes the divergence clearer has.

If nothing else survives from the founding conversations, keep this filter.

---

## 10. The open slot — for future-selves

**We do not know what the popular features will be.** They do not exist yet; guessing them now
is the mistake.

So we leave a **slot**, not an answer:

1. **Instrument every interaction** anonymously, from day one.
2. **The nav is a leaderboard, not a manifesto.** Whatever earns its place by real use is
   promoted to the front; what nobody touches is retired.
3. **The requirement is that the page be cheap to rearrange** — not that we correctly predict
   the winners today.

When there is enough usage data, the vision is revised against it. Until then, this section is
deliberately unfinished.

---

## 11. The infrastructure

Three pieces:

```
   [ Congress.gov API ]
            │  (cron — already running)
            ▼
   ┌──────────────────┐      ┌───────────────────┐
   │  BILL ENGINE      │─────▶│  BALLOT BOX        │
   │  poller + stages  │      │  tiny API + 1 table│
   │  (exists today)   │◀─────│  append-only votes │
   └──────────────────┘      └───────────────────┘
            │                          ▲
            ▼                          │ tap = POST a vote
   ┌──────────────────────────────────┴─────┐
   │  FRONT DOOR — the website / PWA         │
   │  bill · stage · "Put it to the vote!"   │
   │  public tally  ‖  official tally        │
   └─────────────────────────────────────────┘
```

- **Stack:** plain HTML/CSS/JS, a small Python API, **SQLite** to start, one domain.
- **Hosting:** phase 1 on `mbp9` (ours, free, testable). Phase 2 moves the *identical* stack to
  one rented VPS when strangers need to vote. Design for portability; do not build the cloud
  version yet.
- The whole thing would run on a Raspberry Pi. That is a feature.

---

## 12. Deliberately out of scope (parked, not rejected)

These cost real effort and buy nothing until there are real users:

BitTorrent / IPFS distribution · Merkle-everything · provenance tier tuples ·
country / jurisdiction capture · the "cheat as a game" sandbox · differential privacy ·
decentralised DNS (Handshake / ENS) · native apps · any distributed consensus.

Revisit each only against §9.

---

## 13. The bet, and what would kill it

> **The bet:** for a meaningful fraction of bills, the public tally will diverge from the
> official tally — **systematically, not randomly.**

- If **true**, Boule is an instrument.
- If **false** — if the public tracks Congress bill-for-bill — Boule is a mirror that shows
  nothing. That is a clean, honest negative, and a perfectly good outcome.

**Kill criterion:** if, after a fair run, the gap is indistinguishable from noise, say so and
stop. "The hypothesis is dead" is a valid result.

---

*Founding session, 2026-11-17. Tagline declared canon by m1ck5k1.*
