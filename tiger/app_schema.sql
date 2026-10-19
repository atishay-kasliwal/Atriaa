-- Atria system of record on Tiger Data (Postgres). Same tables the Supabase migrations
-- created, in one file. The vitals hypertable for trends lives in tiger/schema.sql.
-- Safe to repeat:  psql "$TIGER_DATABASE_URL" -f tiger/app_schema.sql

CREATE TABLE IF NOT EXISTS patients (
  id uuid PRIMARY KEY,
  bay text NOT NULL,
  arrival_time timestamptz NOT NULL,
  initial_triage int,                      -- NULL until staff set a priority (live check-ins)
  chief_complaint text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  observed_at timestamptz NOT NULL,
  hr int,
  spo2 int,
  pain int,
  note text,
  run_id text,
  event_key text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_patient_observed_idx ON events (patient_id, observed_at);

CREATE TABLE IF NOT EXISTS audit_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  actor text NOT NULL,
  action text NOT NULL CHECK (action IN ('acknowledge', 'request_reassessment', 'resolve')),
  reason text,
  run_id text,
  queue_version text,
  idempotency_key text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_patient_created_idx ON audit_log (patient_id, created_at);

CREATE TABLE IF NOT EXISTS atria_demo_runs (
  run_id text PRIMARY KEY,
  started_at timestamptz NOT NULL DEFAULT now(),
  "cursor" int NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'paused' CHECK (status IN ('paused', 'running', 'complete')),
  speed numeric NOT NULL DEFAULT 1,
  active boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS atria_demo_runs_one_active_uidx ON atria_demo_runs (active) WHERE active;

CREATE TABLE IF NOT EXISTS checkins (
  id uuid PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
  ticket text NOT NULL,
  display_name text NOT NULL,
  date_of_birth date,
  symptoms text[] NOT NULL DEFAULT '{}',
  notes text,
  priority int CHECK (priority BETWEEN 1 AND 3),
  status text NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting', 'called')),
  reassessment_requested_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS checkins_status_created_idx ON checkins (status, created_at);

-- Beds: a check-in that is roomed has status 'called' and a bed; discharge frees the bed.
-- suggested_priority is the front desk's suggestion; a nurse approves it into `priority`.
ALTER TABLE checkins ADD COLUMN IF NOT EXISTS bed text;
ALTER TABLE checkins ADD COLUMN IF NOT EXISTS suggested_priority int CHECK (suggested_priority BETWEEN 1 AND 3);
ALTER TABLE checkins DROP CONSTRAINT IF EXISTS checkins_status_check;
ALTER TABLE checkins ADD CONSTRAINT checkins_status_check CHECK (status IN ('waiting', 'called', 'discharged'));
CREATE UNIQUE INDEX IF NOT EXISTS checkins_one_patient_per_bed ON checkins (bed) WHERE status = 'called' AND bed IS NOT NULL;
