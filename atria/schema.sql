-- Dedicated synthetic ER SQLite schema. No legacy tables or destructive reset SQL.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS er_demo_runs (
    run_id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    cursor INTEGER NOT NULL DEFAULT 0 CHECK (cursor BETWEEN 0 AND 3),
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    replay_time TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS er_one_active_run
    ON er_demo_runs(active) WHERE active = 1;

CREATE TABLE IF NOT EXISTS er_encounters (
    run_id TEXT NOT NULL REFERENCES er_demo_runs(run_id) ON DELETE RESTRICT,
    patient_id TEXT NOT NULL,
    bay TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    initial_triage INTEGER NOT NULL CHECK (initial_triage BETWEEN 1 AND 5),
    chief_complaint TEXT NOT NULL,
    intake_json TEXT NOT NULL,
    PRIMARY KEY (run_id, patient_id),
    UNIQUE (run_id, bay)
);
CREATE TRIGGER IF NOT EXISTS er_intake_immutable
BEFORE UPDATE ON er_encounters
BEGIN
    SELECT RAISE(ABORT, 'intake is immutable; corrections require a separate human workflow');
END;

CREATE TABLE IF NOT EXISTS er_patient_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    event_time TEXT NOT NULL,
    received_time TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN
      ('intake', 'measurement', 'pain_report', 'symptom_report', 'observation')),
    payload_json TEXT NOT NULL,
    FOREIGN KEY (run_id, patient_id)
      REFERENCES er_encounters(run_id, patient_id) ON DELETE RESTRICT,
    UNIQUE (run_id, patient_id, sequence_no)
);
CREATE INDEX IF NOT EXISTS er_events_patient_time
    ON er_patient_events(run_id, patient_id, event_time, sequence_no);

-- One pending request per patient/run in the minimal demo. No automatic completion.
CREATE TABLE IF NOT EXISTS er_reassessment_requests (
    action_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    signal_version INTEGER NOT NULL CHECK (signal_version >= 0),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('synthetic_fixture', 'human_demo_action')),
    FOREIGN KEY (run_id, patient_id)
      REFERENCES er_encounters(run_id, patient_id) ON DELETE RESTRICT,
    UNIQUE (run_id, patient_id)
);
PRAGMA user_version = 1;
