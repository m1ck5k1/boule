# Boule

> *A general-public, real-time proxy voting machine for legislation.*
> *Every bill, voted in tandem with the real congressional process.*

---

## What This Is

**Boule** (βουλή — the Athenian council that prepared motions for the assembly to vote on)
is a **parallel legislature**. It mirrors the stages of the real US legislative process —
introduction, committee, floor, passage — using the Congress.gov APIs as the source of
truth, and opens each bill to a **public vote that runs in real time alongside the official
one**.

The point is the gap. Shown side by side, the public tally and the official tally make the
division between **voters and elected officials** visible, bill by bill.

**The AI observes; it does not decide.** The agent layer flags anomalies — coordinated or
duplicate votes, IP-level clustering, timing patterns — and publishes its reading as
*opinion* beside the raw tally. It holds no authority over the result.

---

## Status — pivot in progress

Boule was **renamed from The Policy Prowler**, a forensic fiscal-journalism pipeline. The
project has **moved from a financial-analysis model to a general-public real-time proxy
voting machine**.

- **Carried forward:** the *ingestion substrate* — the Congress.gov bill monitor and triage
  pipeline that tells the system which bills exist and where they sit in the process.
- **Retired:** the financial-audit framing. The former audits and dispatches are preserved
  under `research/audits/` and `articles/published/` as historical work.
- **Not built yet:** the voting layer itself. It is to be developed on a branch and hosted
  on `mbp9`.

---

## The Process It Mirrors

Stage state is read from the Congress.gov **actions feed**
(`/bill/{congress}/{type}/{number}/actions`) — the one endpoint that carries stage history
*and* roll-call links together.

| Stage | Source |
|---|---|
| Introduced / referred | actions feed |
| Committee milestones | actions feed (`sourceSystem`, action text) |
| Floor / passage | actions feed `recordedVotes` → House (JSON) / Senate (XML) |
| Enacted | actions feed |

House roll calls are ingested as JSON; Senate roll calls are parsed from the linked
`senate.gov` XML. Two pipelines, one canonical stage machine.

> **Design note (from the Congress.gov API assessment):** the stage machine is keyed on
> **action type + `sourceSystem.code` + text matching**, not on `actionCode` — the code list
> is authoritative only for Library-of-Congress actions (`sourceSystem` 9), House codes have
> no published list, and Senate actions carry no `actionCode` at all. The Congress.gov API
> also has **no CBO cost-estimate endpoint**; any fiscal data must be sourced externally
> from `cbo.gov`.

---

## Repository Layout

```
data/
  bills/          — Raw bill text, amendments, diffs
  cbo_reports/    — CBO reports (external fiscal data)
  archive/        — Superseded or historical data
  triage_logs/    — Daily bill-monitor triage output

research/
  audits/         — Historical forensic breakdowns (Policy Prowler era)

articles/
  published/      — Historical noir dispatches (Policy Prowler era)

templates/        — Scaffolding
tools/            — Ingestion, triage, formatting, and sync pipeline scripts
```

---

## Pipeline (carried forward)

| Script | Purpose |
|---|---|
| `tools/poll_bills.py` | Poll Congress.gov for new bills; Claude Haiku triage for relevance |
| `tools/ingest_bill.sh` | Download and stage bill text from congress.gov |
| `tools/diff_bills.sh` | Diff two bill versions to surface delta |
| `tools/format_table.py` | Render LaTeX budget-comparison tables (3-decimal, Substack-compatible) |
| `tools/sync_audit.py` | Sync audit YAML front-matter to Airtable institutional memory |
| `tools/publish.py` | Finalize and stamp a dispatch for `articles/published/` |

### Automated Bill Monitor

`tools/poll_bills.py` runs on a daily schedule, pulling recently updated legislation from
the Congress.gov API, applying keyword pre-filters, then scoring survivors with Claude Haiku.
High-scoring bills are auto-staged for review.

```bash
python3 tools/poll_bills.py [--dry-run] [--hours N] [--min-score N]
```

Output is a JSON list of scored bills, ready to feed into the next stage.

---

## Setup

```bash
cp .env.example .env
# Fill in the keys:
#   CONGRESS_API_KEY   — free at api.congress.gov/sign-up
#   ANTHROPIC_API_KEY  — Anthropic console
#   AIRTABLE_PAT       — Airtable personal access token (data.records:write scope)

pip install anthropic requests pyaml
```

> `AIRTABLE_PAT` is the canonical Airtable variable (matches vault-watcher and the GitHub
> Actions secret). `AIRTABLE_API_KEY` is accepted as a backward-compatible fallback.

---

## Citation Protocol

Every published fact requires a source. Canonical sources:

- **Bill text:** congress.gov
- **CBO data:** cbo.gov
- **House votes:** clerk.house.gov
- **Senate votes:** senate.gov/legislative/votes_new.htm
- **Treasury data:** fiscaldata.treasury.gov

Historical audit records are registered in [`RESEARCH_INDEX.md`](RESEARCH_INDEX.md).

---

## File Naming

`YYMMDD_Short_Title.md` — e.g., `260222_Lobbyist_ROI_Audit.md`

Audit IDs: `AUD-YYMMDD-SUBJECT` (embedded in each audit's YAML front-matter)

---

## License

MIT — see [LICENSE](LICENSE).
