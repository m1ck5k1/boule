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

Every reading is an append-only record, and **the whole ledger is published** — because a number
nobody can check is a claim, and this project exists to audit claims.

- **Immutable.** Append-only; nothing is edited after the fact. A changed mind is a new row.
- **Open.** What is published is the *evidence*, not a summary of it. Anyone can recompute every
  tally Boule shows, and say so in public when we are wrong.
- **Small.** One billion readings ≈ 40 GB columnar. A laptop, not big data.

**The publication rule is absolute: nothing Boule publishes may be used to identify, target or
single out a person, on any level.** That is a constraint on the *standard*, not a hope, and it
outranks every argument for richer data. `DATA.md` states what is published, what is never
published, and why each field is there.

---

## 6. The identity stance

**Identity is not Boule's problem to solve — and Boule does not solve it.**

- **No accounts. No email. No sign-in. No identity provider.** We are not in the identity business.
- **The unit of a reading is a device.** The installed app is issued a key at install and keeps it.
  The server refuses a second reading from that key on the same `(bill, version)`.
- **The claim is exactly that, and no more: one reading per device.** Not one per person. A phone
  and a laptop are two devices; a reinstall is a new one. The wording must never overstate the unit.
- **A browser reading is weaker, and is labelled so.** Browser storage can be cleared, so that
  reading stands on nothing durable. The `provenance` column records which it was (`device` vs
  `anonymous`), and the tally can say how many readings rest on something that persists.

The pleasing symmetry: Congress's own tally is also scoped to *seats*, not to people. Neither
number counts individuals; both count readings from units. Ours says which unit.

---

## 7. Trust, minimally

Not a distributed ledger. Three things:

1. **A device key**, issued at install — the only credential, and it is not an identity.
2. **One append-only votes table.** A reading is written once and never changed.
3. **The whole ledger, published.** Not a summary of the tally — the readings themselves, to the
   standard in `DATA.md`, so tampering is not merely *detectable* but *checkable* by anyone.

That is the entire integrity story. It is enough — and the third part is what gives the other two
their force, because it hands the checking to everybody else.

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
