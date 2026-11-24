-- Boule engine schema.
--
-- Two rules are enforced in the database itself, not by convention, because a
-- convention is what gets broken at 2am:
--   1. `actions` is the raw legislative record -> append-only (triggers below).
--   2. A public vote is keyed to a (bill, VERSION), never to a bill alone, so a
--      vote on the introduced text can never be compared to a vote on the
--      enrolled text.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bills (
  congress           INTEGER NOT NULL,
  bill_type          TEXT    NOT NULL,   -- lower-case: hr, s, hjres, sjres, hconres ...
  number             INTEGER NOT NULL,
  title              TEXT,
  origin_chamber     TEXT,
  introduced_on      TEXT,               -- ISO 8601 date
  latest_action      TEXT,               -- congress.gov latestAction.text
  latest_action_date TEXT,
  update_date        TEXT,               -- congress.gov updateDate; drives the poller
  ingested_at        TEXT    NOT NULL,
  PRIMARY KEY (congress, bill_type, number)
);

-- A bill has many versions. This is the anchor for the public vote.
CREATE TABLE IF NOT EXISTS bill_versions (
  version_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  congress     INTEGER NOT NULL,
  bill_type    TEXT    NOT NULL,
  number       INTEGER NOT NULL,
  version_code TEXT    NOT NULL,         -- congress.gov versionCode: '00', 'rh', 'enr' ...
  label        TEXT    NOT NULL,         -- human label, e.g. 'Introduced in House'
  first_seen   TEXT    NOT NULL,
  UNIQUE (congress, bill_type, number, version_code),
  FOREIGN KEY (congress, bill_type, number) REFERENCES bills
);

-- The raw record. Append-only; there is no legitimate UPDATE or DELETE.
CREATE TABLE IF NOT EXISTS actions (
  action_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  congress      INTEGER NOT NULL,
  bill_type     TEXT    NOT NULL,
  number        INTEGER NOT NULL,
  action_date   TEXT    NOT NULL,        -- ISO 8601 date
  action_code   TEXT,                    -- recorded, never trusted (see stages.py)
  source_system INTEGER,                 -- congress.gov sourceSystem.code
  source_name   TEXT,                    -- congress.gov sourceSystem.name
  action_type   TEXT,                    -- IntroReferral, Committee, Floor, ...
  text          TEXT    NOT NULL,
  has_vote      INTEGER NOT NULL DEFAULT 0,  -- 1 when this action carries a recordedVotes link
  record_url    TEXT,
  FOREIGN KEY (congress, bill_type, number) REFERENCES bills
);

-- Action identity. Deliberately NOT a table constraint: SQLite treats NULLs as
-- distinct in UNIQUE, so a null action_code would let the same action insert
-- twice and break idempotency. COALESCE collapses the nulls, and source_system is
-- part of the key because the same event is legitimately reported by both the
-- chamber and the Library of Congress.
CREATE UNIQUE INDEX IF NOT EXISTS ux_actions_identity ON actions (
  congress, bill_type, number, action_date,
  COALESCE(source_system, -1), COALESCE(action_code, ''), text
);

-- The derived stage. Recomputed, never hand-edited.
CREATE TABLE IF NOT EXISTS stages (
  congress        INTEGER NOT NULL,
  bill_type       TEXT    NOT NULL,
  number          INTEGER NOT NULL,
  stage           TEXT    NOT NULL,      -- the FURTHEST milestone reached
  chamber         TEXT,                  -- chamber of that milestone
  determined_by   INTEGER,               -- actions.action_id that decided it
  basis           TEXT,                  -- the action text, so the call is auditable
  -- Where the bill sits NOW, which is often a different chamber: HR 2347 passed
  -- the House and now sits on the Senate calendar. One linear ladder cannot say
  -- both, so we store both.
  current_chamber TEXT,
  current_basis   TEXT,
  computed_at     TEXT    NOT NULL,
  PRIMARY KEY (congress, bill_type, number),
  FOREIGN KEY (congress, bill_type, number) REFERENCES bills
);

CREATE TRIGGER IF NOT EXISTS actions_no_update BEFORE UPDATE ON actions
BEGIN SELECT RAISE(ABORT, 'actions is append-only: UPDATE refused'); END;

CREATE TRIGGER IF NOT EXISTS actions_no_delete BEFORE DELETE ON actions
BEGIN SELECT RAISE(ABORT, 'actions is append-only: DELETE refused'); END;

CREATE INDEX IF NOT EXISTS idx_actions_bill ON actions (congress, bill_type, number, action_date);
CREATE INDEX IF NOT EXISTS idx_bills_update  ON bills (update_date DESC);

-- S3 — the ballot box.
--
-- Append-only, for the same reason as `actions`: the public tally is a RECORD,
-- not a field. A person changing their mind is a NEW row, never an edit — the
-- old row stays, because a tally you can rewrite is not evidence.
--
-- Two inherited rules are enforced here:
--   1. Keyed to a (bill, VERSION), never the bill alone (see header).
--   2. `provenance` exists from the very first row. At S3 the only tier is
--      'anonymous', but a later tier (S5 sign-in) must be unable to retro-label
--      the history — so the column is not optional from the start.
CREATE TABLE IF NOT EXISTS votes (
  vote_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  congress     INTEGER NOT NULL,
  bill_type    TEXT    NOT NULL,
  number       INTEGER NOT NULL,
  version_code TEXT    NOT NULL,          -- pins the vote to the exact text
  choice       TEXT    NOT NULL CHECK (choice IN ('yea', 'nay')),
  provenance   TEXT    NOT NULL DEFAULT 'anonymous',   -- tier; 'anonymous' at S3
  voter_key    TEXT,                      -- pseudonymous key; NULL at S3, set at S5
  cast_at      TEXT    NOT NULL,          -- SERVER stamp, never the client's word
  ip_hash      TEXT,                      -- sha256(client ip); never the raw ip
  FOREIGN KEY (congress, bill_type, number) REFERENCES bills
);

CREATE INDEX IF NOT EXISTS idx_votes_bill  ON votes (congress, bill_type, number, version_code);
CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes (voter_key) WHERE voter_key IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS votes_no_update BEFORE UPDATE ON votes
BEGIN SELECT RAISE(ABORT, 'votes is append-only: UPDATE refused'); END;

CREATE TRIGGER IF NOT EXISTS votes_no_delete BEFORE DELETE ON votes
BEGIN SELECT RAISE(ABORT, 'votes is append-only: DELETE refused'); END;

-- S5 — the device key, and the identity mechanism the project actually uses.
--
-- There is no identity provider and no account: a key is issued once, and the
-- reading is bound to the DEVICE rather than to a person. The server stores only
-- the key's hash, so it can recognise a device and still be unable to resolve one.
--
-- `device_id` is an opaque random id, and it is what a vote points at -- not the
-- hash of the secret. So a `device_id` that leaks into the published data cannot
-- be replayed to vote: it is an address, not a credential.
CREATE TABLE IF NOT EXISTS devices (
  device_id    TEXT PRIMARY KEY,        -- opaque; what a reading points at
  key_hash     TEXT NOT NULL UNIQUE,    -- sha256(device key); the raw key is never stored
  issued_at    TEXT NOT NULL,
  last_seen_at TEXT,
  retired_at   TEXT                     -- retirement never touches the votes
);

-- One reading per device, per VERSION of the text — enforced by the database, for
-- the same reason as every other rule here: a convention is what gets broken at 2am.
--
-- PARTIAL on purpose (WHERE voter_key IS NOT NULL). An unkeyed reading is anonymous,
-- and Boule cannot deduplicate what it cannot identify — so anonymous readings stay
-- repeatable, and S3's "changing a vote appends a row" survives S5 intact. This is
-- the whole design: the limit is a claim about DEVICES, and it must not silently
-- become a claim about people.
CREATE UNIQUE INDEX IF NOT EXISTS ux_votes_device_version
  ON votes (congress, bill_type, number, version_code, voter_key)
  WHERE voter_key IS NOT NULL;

-- `provenance` is not a label anyone may write freely: it must AGREE with voter_key.
-- 'device' means a key was presented; 'anonymous' means none was. A CHECK cannot be
-- added to an existing table in SQLite, and the append-only triggers forbid
-- rebuilding it in place -- so this is a trigger: same enforcement, no rebuild.
CREATE TRIGGER IF NOT EXISTS votes_provenance_coherent BEFORE INSERT ON votes
WHEN (NEW.provenance = 'device' AND NEW.voter_key IS NULL)
  OR (NEW.provenance = 'anonymous' AND NEW.voter_key IS NOT NULL)
BEGIN
  SELECT RAISE(ABORT, 'votes.provenance must agree with voter_key');
END;

-- --- Anything with a lifetime lives OUTSIDE the append-only table ---------------
-- `votes` refuses UPDATE and DELETE by trigger, which is exactly what makes it
-- trustworthy -- and it also means nothing inside it can expire: a purge against it
-- is not merely unwise, it is rejected outright. So the working values sit here,
-- keyed to the reading, free to be purged. The bonus is that `votes` then holds
-- nothing personal at all, and is publishable exactly as it stands.
--
-- NOTE: `votes.ip_hash` (above) is LEGACY from before this split and is no longer
-- written. Retiring the column needs a table rebuild -- the triggers will not allow
-- it to be dropped or nulled in place. The published allow-list excludes it.
CREATE TABLE IF NOT EXISTS vote_nets (
  vote_id      INTEGER PRIMARY KEY,      -- the reading this working value belongs to
  ip_hash      TEXT    NOT NULL,         -- sha256(client ip); never the raw ip
  retire_after TEXT    NOT NULL,         -- ISO-8601 UTC; the purge job deletes past this
  FOREIGN KEY (vote_id) REFERENCES votes (vote_id)
);

CREATE INDEX IF NOT EXISTS idx_vote_nets_retire ON vote_nets (retire_after);

-- --- The OTHER tally ------------------------------------------------------------
-- An official vote is a CITATION of Congress's record, not ours, so this table is
-- not append-only in the same sense: a re-fetch that disagrees with what we stored
-- means either the source changed or we mis-parsed, and BOTH deserve to be seen.
-- The ingest therefore inserts idempotently and REPORTS a disagreement rather than
-- silently overwriting it.
--
-- `vote_class` is the honesty column. Only 'of_the_text' may carry a gap: a cloture
-- motion is the chamber deciding whether to proceed, and drawing a gap against it
-- would claim the public's reading should match a procedural manoeuvre.
CREATE TABLE IF NOT EXISTS official_tallies (
  tally_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  congress      INTEGER NOT NULL,
  bill_type     TEXT    NOT NULL,
  number        INTEGER NOT NULL,
  chamber       TEXT    NOT NULL CHECK (chamber IN ('house', 'senate')),
  roll_call     TEXT    NOT NULL,
  question      TEXT    NOT NULL,
  result        TEXT,
  vote_class    TEXT    NOT NULL CHECK (vote_class IN ('of_the_text', 'procedural', 'other')),
  yea           INTEGER NOT NULL,
  nay           INTEGER NOT NULL,
  present       INTEGER NOT NULL DEFAULT 0,
  not_voting    INTEGER NOT NULL DEFAULT 0,
  members_recorded INTEGER NOT NULL DEFAULT 0,
  source_url    TEXT    NOT NULL,
  fetched_at    TEXT    NOT NULL,
  UNIQUE (congress, bill_type, number, chamber, roll_call)
);

CREATE INDEX IF NOT EXISTS idx_official_bill
  ON official_tallies (congress, bill_type, number, vote_class);

-- L1 of the reading stack: the CRS summary. The government's own text, stored VERBATIM
-- with its attribution — Boule does not write this layer, and an AI summary of a bill is
-- the same category of artefact this project exists to audit.
--
-- Keyed to the VERSION it describes, not to the bill. A summary is not a property of a
-- bill; it is a property of a (bill, version) pair. Congress.gov has a summary for only
-- some versions, so the honest state "no summary exists for the version being voted on"
-- is a normal outcome the UI must be able to say out loud — the same rule as a gap that
-- renders `—` and never `0`.
CREATE TABLE IF NOT EXISTS bill_summaries (
  summary_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  congress     INTEGER NOT NULL,
  bill_type    TEXT    NOT NULL,
  number       INTEGER NOT NULL,
  version_code TEXT    NOT NULL,          -- congress.gov versionCode, e.g. '07'
  action_desc  TEXT,                      -- congress.gov actionDesc, e.g. 'Reported to House'
  text         TEXT    NOT NULL,          -- CRS's words, verbatim. Never edited, never condensed.
  source_url   TEXT    NOT NULL,
  fetched_at   TEXT    NOT NULL,
  UNIQUE (congress, bill_type, number, version_code, text)
);

CREATE INDEX IF NOT EXISTS idx_summaries_bill
  ON bill_summaries (congress, bill_type, number, version_code);

-- The forecast: a dated guess about WHEN the next gap-eligible vote will land.
--
-- It is append-only, one per bill per day, and NEVER edited — the rule is enforced by the
-- store (the UNIQUE below, plus the triggers), not by anyone's good intentions. A forecast
-- that can be revised after the fact is not a forecast, it is a commentary; and this
-- project's entire subject is the difference between a claim and what actually happened.
-- So Boule's own claims get the same treatment as a reading: the record stands, and a later
-- record says what became of it.
--
-- `made_on` is a DAY, not a timestamp, because the rule is a daily one. `author` is never
-- blank: an anonymous forecast is a horoscope.
CREATE TABLE IF NOT EXISTS forecasts (
  forecast_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  congress       INTEGER NOT NULL,
  bill_type      TEXT    NOT NULL,
  number         INTEGER NOT NULL,
  made_on        TEXT    NOT NULL,      -- ISO date: the day the forecast was made
  window_start   TEXT    NOT NULL,      -- earliest plausible vote date
  window_end     TEXT    NOT NULL,      -- latest plausible vote date
  confidence     INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  basis          TEXT    NOT NULL,      -- what it rests on, in the author's own words
  author         TEXT    NOT NULL,      -- e.g. 'h3rm5k1 (AI)'. Never empty.
  method_version TEXT    NOT NULL,
  created_at     TEXT    NOT NULL,
  UNIQUE (congress, bill_type, number, made_on)
);

CREATE TRIGGER IF NOT EXISTS forecasts_no_update BEFORE UPDATE ON forecasts
BEGIN SELECT RAISE(ABORT, 'forecasts is append-only: a forecast is not revised'); END;

CREATE TRIGGER IF NOT EXISTS forecasts_no_delete BEFORE DELETE ON forecasts
BEGIN SELECT RAISE(ABORT, 'forecasts is append-only: a forecast is not withdrawn'); END;

-- What became of a forecast. A separate append-only table for the same reason votes never
-- get updated: the forecast is not rewritten to match the outcome, the outcome is recorded
-- beside it. Scoring is the only thing that makes a forecast more than an opinion.
CREATE TABLE IF NOT EXISTS forecast_outcomes (
  outcome_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  forecast_id INTEGER NOT NULL REFERENCES forecasts(forecast_id),
  resolved_on TEXT    NOT NULL,
  outcome     TEXT    NOT NULL CHECK (outcome IN ('hit', 'miss', 'void')),
  vote_ref    TEXT,                     -- the roll call that settled it, when there is one
  note        TEXT,
  created_at  TEXT    NOT NULL
);

CREATE TRIGGER IF NOT EXISTS outcomes_no_update BEFORE UPDATE ON forecast_outcomes
BEGIN SELECT RAISE(ABORT, 'forecast_outcomes is append-only'); END;

CREATE TRIGGER IF NOT EXISTS outcomes_no_delete BEFORE DELETE ON forecast_outcomes
BEGIN SELECT RAISE(ABORT, 'forecast_outcomes is append-only'); END;

CREATE INDEX IF NOT EXISTS idx_forecasts_bill
  ON forecasts (congress, bill_type, number, made_on);
