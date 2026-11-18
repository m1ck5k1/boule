# Boule — Publication Standard

**The ledger is public. This file defines what that means.**

Boule publishes its readings so anyone can recompute every tally it shows — and disagree with
us in public. A number nobody can check is a claim, and this project exists to audit claims.

> **The data is here to help, not to be abused.** One line, and every rule below serves it.

---

## The absolute rule

> **Nothing published may be used to identify, target or single out a person, on any level.**

This outranks every argument for richer data. If a field cannot be justified against this rule,
it does not ship. If a field is useful *and* risky, it is coarsened until the risk is gone or it
is dropped.

**Use the honest word.** What we produce is **pseudonymised**, not "anonymised". Data that can
single out one person is not anonymous, and this project does not get to use a word loosely.

---

## Never published — no exceptions

| Never | Why |
|---|---|
| **Raw IP address** | Directly identifying. |
| **`ip_hash`, in any form** | A stable hash is a pseudonym that follows a device across every bill. Publishing it is a fingerprint, and a fingerprint is a target. |
| **Device key / any voter key** | It is the only credential. Publishing it publishes the voter. |
| **Name, email, or account id** | Boule does not hold them. If it ever does, they never leave. |
| **User agent, headers, referrer** | Quasi-identifiers; a combination narrows a crowd to a person. |
| **Precise timestamp (seconds)** | Time-to-the-second plus any other field is a fingerprint. The day is the finest granularity we publish. |
| **Row order / insertion sequence** | The sequence is metadata. An export is shuffled, and no ordinal is carried. |
| **Geography of any kind** | Country, region, timezone. All quasi-identifiers, all excluded. An approximate *state* may be derived at ingest — then folded into a count and discarded (below) — but it is never a field on a row and never published. |

---

## Capture and retention — internal, and expiring

Geography is **captured, never stored as a record, and never published.**

- **Derived at ingest, from the connection.** A bundled GeoIP table resolves the request's
  approximate **state** — no third-party lookup, so the address never leaves the box.
- **Folded into a counter, then discarded.** The state increments a
  `(state, bill, version, day, choice)` count, and the per-reading value is **gone**. It is not a
  column on any row, so there is nothing to link, leak or subpoena. This is the strongest form of
  the rule: geography never becomes a per-reading fact at all.
- **The address is a working value with a TTL.** `ip_hash` exists only to catch a burst of readings
  from one network. It is held for **30 days**, then purged. *(What enforces one reading per device
  is the **device key**, not the address.)*
- **Expiry is a job, not an intention.** Every retained value carries a `retire_after` date; a
  scheduled purge deletes what has expired, and says so in the log when it runs.

**Two consequences, stated plainly.**

1. **Per-reading geography is unrecoverable by design.** If the GeoIP table is later found wrong for
   some period, that period's state splits cannot be corrected — the inputs are gone. That
   irreversibility is the price of the guarantee, and it is the right way round.
2. **Expiry collides with append-only — so separate them.** The `votes` table refuses `UPDATE` and
   `DELETE` by trigger, so its contents *cannot* expire: a purge would simply be refused. The
   address must therefore live in a **separate, mutable table** — `vote_nets(vote_id, ip_hash,
   retire_after)` — which the purge may empty freely, while `votes` stays append-only and holds
   nothing personal. The address becomes the only thing with a lifetime, and the only thing that
   needs one.


## Published — the audit pack

One row per reading, and **only** these fields:

| Field | Value | Why it is here | Why it is safe |
|---|---|---|---|
| `congress`, `bill_type`, `number` | as recorded | The reading is of *this* bill. | Public record. |
| `version_code` | e.g. `00` | The reading is of *this text*. | Public record. |
| `choice` | `yea` \| `nay` | The reading itself. | Public record. |
| `day` | `YYYY-MM-DD`, UTC | Anomaly detection needs time; the day is the coarsest useful bucket. | A day cannot single out a moment. |
| `reading` | a **random per-bill pseudonym** | Lets rows within one bill be grouped and ordered so anomaly *shape* is visible. | Random, and **re-issued per bill** — so it cannot link one device across two bills. This is the field that makes the corpus safe. |
| `provenance` | `device` \| `anonymous` | Interpretation: does this reading stand on something durable? | A coarse attribute, not an identifier. |

**The export is shuffled.** Row order carries no information by construction.

---

## Aggregates — the primary artifact

Counts per `(bill, version, choice)` and per `(bill, version, day, choice)`.

**Minimum cell size `k = 10`.** Any cell below `k` is **withheld** — and *marked withheld*,
never zeroed and never dropped silently. Same rule as the gap: an absent number is a fact; a
zero is a claim.

---

## The honest limit — and where it lands

Network-level clustering — "one network cast 500 readings" — is visible **only to the server**,
which holds the `ip_hash` that is never published. So the public corpus supports **statistical**
anomaly detection (bursts, uniformity, timing, improbable agreement) and **cannot** support
network attribution. That is the deliberate trade, and it is the right way round: the ability to
*check the tally* is public; the ability to *identify a device* is not.

What the server sees, it publishes as **opinion beside the raw data** — never as a verdict,
never as the only text on the page. The aggregates let anyone check the arithmetic underneath it.

---

## The publication gate

**No export runs without passing `engine/gate_publish.py`.** Pass criteria, fixed before the
build:

1. **ALLOW-LIST** — every published column is in the table above; nothing else is emitted.
2. **NO IDENTIFIER** — no forbidden field (or its hash) appears anywhere in the output.
3. **NO CROSS-BILL LINK** — no `reading` pseudonym is shared between two different bills.
4. **NO FINE TIME** — every `day` is a date, never a datetime.
5. **NO SMALL CELL** — every aggregate cell is either ≥ `k` or explicitly `withheld`.
6. **SHUFFLED** — the export order is not the insertion order.

A failure is a **stop**, not a warning.

---

## Changelog

| Date | Change |
|---|---|
| 2026-11-18 | Standard established. The device model settled; the ledger becomes a published artifact; the absolute no-identification rule adopted; `k = 10`; per-bill pseudonyms and day-granularity timestamps chosen as the anti-linkage device. |
| 2026-11-18 | **Geography settled.** State-level is analytically the right grain (it is the unit the official record is territorial in — the Senate; town-level has no counterpart and is dropped). Geography is captured **internally only**, derived at ingest, folded into a counter and discarded — never a field on a row, never published. `ip_hash` given a **30-day TTL** and moved to a separate mutable `vote_nets` table, because expiry cannot live inside an append-only table. |
