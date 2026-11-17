# Boule

## Mission
A general-public, **real-time proxy voting machine** for legislation. Mirror the US
legislative process — bills, stages, floor votes — from the Congress.gov APIs, and open each
bill to a **public vote running in tandem with the official one**. The purpose is to make the
gap between voters and elected officials visible, bill by bill.

## Operating Principles
- **The AI observes; it does not decide.** Flag anomalies (coordinated/duplicate votes,
  IP-level clustering, timing patterns) and publish the reading as *opinion* beside the raw
  tally — never as a verdict or as authority over the result.
- **Tone:** neutral, evidence-first, procedural. No editorialising.
- **Zero-Trust on data:** every bill, stage, and vote count carries a source.
- **Neutral on policy:** no prior that any bill is good or bad. (The retired "every bipartisan
  bill is a fiscal trap" prior is dead — it turned the agent system into a consensus machine.)

## Status
Boule was renamed from **The Policy Prowler**. The project moved from a financial-analysis
model to a public real-time proxy voting machine. The Congress.gov ingestion pipeline carries
forward as the substrate; the financial-audit framing is retired and preserved as historical
work under `research/audits/` and `articles/published/`. The voting layer is not built yet.

## Directory Structure
- `data/bills/`          — Raw bill text, amendments, diffs
- `data/cbo_reports/`    — CBO reports (external fiscal data)
- `data/archive/`        — Superseded or historical data
- `data/triage_logs/`    — Daily bill-monitor triage output
- `research/audits/`     — Historical forensic breakdowns (Policy Prowler era)
- `articles/published/`  — Historical noir dispatches (Policy Prowler era)
- `templates/`           — Scaffolding for new work
- `tools/`               — Ingestion, formatting, and pipeline scripts

## File Naming Convention
`YYMMDD_Short_Title.md` — e.g., `260222_Lobbyist_ROI_Audit.md`
Audit IDs follow the pattern: `AUD-YYMMDD-SUBJECT` (embedded in front-matter of each audit).

## Ingestion Workflow (full detail in SOP.md)
1. **Ingest** — Pull new bills/reports into `/data`
2. **Scan** — Keyword + Haiku triage for relevance (`tools/poll_bills.py`)
3. **Diff** — Compare House vs. Senate versions; track delta
4. **Audit** — (Historical desk) forensics on a bill of interest
5. **Sync** — Push any record to Airtable institutional memory

## Citation Protocol (Open Ledger)
- Every fact, dollar amount, and vote count requires a source citation.
- Cross-reference local files in `data/` against Airtable source IDs.
- Canonical sources: CBO (cbo.gov), bill text (congress.gov), House votes (clerk.house.gov),
  Senate votes (senate.gov/legislative/votes_new.htm), Treasury data (fiscaldata.treasury.gov).

## Congress.gov API Notes
- Base `https://api.congress.gov/v3`, key in the `x-api-key` header.
- 5,000 requests/hour; 20 results/page by default, 250 max (`offset` + `pagination.next`).
- **Stage history + roll calls:** `/bill/{congress}/{type}/{number}/actions` — the endpoint
  that matters; `recordedVotes` is inline.
- House roll calls: JSON. Senate roll calls: no dedicated endpoint — parse the linked
  `senate.gov` XML.
- Build the stage machine on **action type + `sourceSystem.code` + text matching**, never on
  `actionCode` (authoritative only for Library-of-Congress actions; Senate actions carry none).
- **No CBO cost-estimate endpoint** — fiscal data comes from `cbo.gov`.

## Institutional Memory (Airtable)
Access via the Airtable MCP tools available in this Claude Code session.
- **Base ID:** `appA8bFOOAw72AZ24` (shared with TheVaultWatcher)
- **Audits table ID:** `tbl92R4P97QrUZvFE`
- **Bills table ID:** `tbl4eVGyE4Kc1ZqRt` — tracked legislation
- **VaultWatcher_Alerts table ID:** `tblxnMKuEGpAsB3m3` — VaultWatcher alerts (read-only from this desk)
- **convergence_events table ID:** `tblSf6ZOr0qHTbuD0` — joint intelligence log

To sync a record: run `tools/sync_audit.py <file_path>`. Requires `AIRTABLE_PAT` in `.env`
(`AIRTABLE_API_KEY` accepted as fallback).

### Cross-Desk Convergence Protocol (inherited, Policy Prowler era)
When a record involves silver market mechanics, CFTC exemptions, COMEX delivery rules,
Treasury precious-metal rulemaking, or sanctions affecting SGE settlement:
1. Check `VaultWatcher_Alerts` for active alerts in the same date window
2. If a matching market signal exists, create a `convergence_events` record
3. The `Audits` table shows linked convergence events via back-link field `fldBYESGlKg7LQ2xx`

Note: The IDs in the original GEMINI.md (`76526270-...`, `2f9416d1-...`) were NotebookLM
source IDs, not Airtable. They are no longer relevant.

## Session Context
Historical legislative intel lives in `prowler_intel_feb26.md`.

## Research Index
Historical audits and published articles are registered in `RESEARCH_INDEX.md`.
