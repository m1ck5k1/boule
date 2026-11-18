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
