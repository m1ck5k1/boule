# BOULE: STANDARD OPERATING PROCEDURE

## 0.0 SCOPE
Boule is a general-public, real-time proxy voting machine for legislation. It mirrors the US
legislative process from the Congress.gov APIs and opens each bill to a public vote running in
tandem with the official one. The Congress.gov ingestion pipeline below is the current
operational backbone; the voting layer is not built yet (target host: `mbp9`).

## 1.0 THE CITATION PROTOCOL (Open Ledger)
- **Zero-Trust Rule:** Every fact, dollar amount, and vote count must be followed by a source.
- **Source Map:**
    - Legislative Text: https://www.congress.gov
    - CBO Data: https://www.cbo.gov (reports mirrored locally in `data/cbo_reports/`)
    - House Vote Records: https://clerk.house.gov
    - Senate Vote Records: https://www.senate.gov/legislative/votes_new.htm
    - Daily Treasury Statement: https://fiscaldata.treasury.gov/datasets/daily-treasury-statement
- **Verification:** Any record must cross-reference the local file (e.g., 260211_CBO_Budget_Outlook.md) against the Airtable source ID.

## 2.0 INGESTION WORKFLOW
- **Step 1: Ingest.** Pull raw bills/reports into /data (`tools/ingest_bill.sh --id <congress><type><number>`).
- **Step 2: Scan.** Keyword + Haiku triage for relevance (`tools/poll_bills.py`).
- **Step 3: Diff.** Compare House vs. Senate versions of text (`tools/diff_bills.sh`).
- **Step 4: Audit.** (Historical desk) Forensics on a bill of interest → `research/audits`.
- **Step 5: Sync.** Push the record to institutional memory (Airtable) via
  `tools/sync_audit.py <file>`. Requires `AIRTABLE_PAT` in `.env` (`AIRTABLE_API_KEY` accepted as fallback).
- **Step 6: Converge.** (Inherited) If a record touches silver/CFTC/COMEX vault mechanics,
  check `VaultWatcher_Alerts` and, on a match, write a `convergence_events`
  record per the Cross-Desk Convergence Protocol in CLAUDE.md.

## 3.0 DATA VISUALIZATION
- **LaTeX Tables:** Use for budget/table comparisons to ensure 3-decimal precision and Substack compatibility.
