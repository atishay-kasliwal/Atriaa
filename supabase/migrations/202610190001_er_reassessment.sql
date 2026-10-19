-- Feature-pass-1: ER reassessment tables. Preserves existing rows.
-- Run in the Supabase SQL Editor. Safe to repeat for this schema.
-- Seed data is kept separately in atria_schema.sql.
BEGIN;

SET LOCAL search_path TO public;

-- Atria ER reassessment demo: Supabase schema + seed data
-- Paste into Supabase SQL editor and run once.

create extension if not exists pgcrypto;

create table if not exists patients (
  id uuid primary key,
  bay text not null,
  arrival_time timestamptz not null,
  initial_triage int not null,
  chief_complaint text,
  created_at timestamptz default now()
);

create table if not exists events (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  observed_at timestamptz not null,
  hr int,
  spo2 int,
  pain int,
  note text,
  created_at timestamptz default now()
);

create table if not exists audit_log (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  actor text not null,
  action text not null check (action in ('acknowledge', 'request_reassessment', 'resolve')),
  reason text,
  created_at timestamptz default now()
);


-- Fail and roll back if an older, incompatible patients table exists.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM (VALUES
      ('patients','id'), ('patients','bay'), ('patients','arrival_time'),
      ('patients','initial_triage'), ('patients','chief_complaint'),
      ('events','patient_id'), ('events','observed_at'),
      ('events','hr'), ('events','spo2'), ('events','pain'), ('events','note'),
      ('audit_log','patient_id'), ('audit_log','actor'),
      ('audit_log','action'), ('audit_log','reason'), ('audit_log','created_at')
    ) AS required(table_name,column_name)
    WHERE NOT EXISTS (
      SELECT 1 FROM information_schema.columns c
      WHERE c.table_schema = 'public'
        AND c.table_name = required.table_name
        AND c.column_name = required.column_name
    )
  ) THEN
    RAISE EXCEPTION 'Existing tables conflict with feature-pass-1 schema. Migration rolled back; reconcile schemas before retrying.';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS atria_events_patient_observed_idx
  ON public.events (patient_id, observed_at);
CREATE INDEX IF NOT EXISTS atria_audit_patient_created_idx
  ON public.audit_log (patient_id, created_at);

NOTIFY pgrst, 'reload schema';
COMMIT;
