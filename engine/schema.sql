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
  UNIQUE (congress, bill_type, number, action_date, text),
  FOREIGN KEY (congress, bill_type, number) REFERENCES bills
);

-- The derived stage. Recomputed, never hand-edited.
CREATE TABLE IF NOT EXISTS stages (
  congress      INTEGER NOT NULL,
  bill_type     TEXT    NOT NULL,
  number        INTEGER NOT NULL,
  stage         TEXT    NOT NULL,
  chamber       TEXT,
  determined_by INTEGER,                 -- actions.action_id that decided it
  basis         TEXT,                    -- the action text, so the call is auditable
  computed_at   TEXT    NOT NULL,
  PRIMARY KEY (congress, bill_type, number),
  FOREIGN KEY (congress, bill_type, number) REFERENCES bills
);

CREATE TRIGGER IF NOT EXISTS actions_no_update BEFORE UPDATE ON actions
BEGIN SELECT RAISE(ABORT, 'actions is append-only: UPDATE refused'); END;

CREATE TRIGGER IF NOT EXISTS actions_no_delete BEFORE DELETE ON actions
BEGIN SELECT RAISE(ABORT, 'actions is append-only: DELETE refused'); END;

CREATE INDEX IF NOT EXISTS idx_actions_bill ON actions (congress, bill_type, number, action_date);
CREATE INDEX IF NOT EXISTS idx_bills_update  ON bills (update_date DESC);
