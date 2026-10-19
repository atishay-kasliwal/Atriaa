-- Atria ER reassessment demo: Supabase schema + seed data
-- Paste into Supabase SQL editor and run once.

create extension if not exists pgcrypto;

create table patients (
  id uuid primary key,
  bay text not null,
  arrival_time timestamptz not null,
  initial_triage int not null,
  chief_complaint text,
  created_at timestamptz default now()
);

create table events (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  observed_at timestamptz not null,
  hr int,
  spo2 int,
  pain int,
  note text,
  created_at timestamptz default now()
);

create table audit_log (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid references patients(id) on delete cascade,
  actor text not null,
  action text not null check (action in ('acknowledge', 'request_reassessment', 'resolve')),
  reason text,
  created_at timestamptz default now()
);

-- Seed patients (fixed UUIDs so the backend/demo script can reference them directly)
insert into patients (id, bay, arrival_time, initial_triage, chief_complaint) values
('00000000-0000-0000-0000-000000000007', 'Bay 7', '2026-10-19 10:02:00+00', 2, 'Chest discomfort (synthetic demo)'),
('00000000-0000-0000-0000-000000000004', 'Bay 4', '2026-10-19 10:02:00+00', 3, 'Mild shortness of breath (synthetic demo)'),
('00000000-0000-0000-0000-000000000005', 'Bay 2', '2026-10-19 09:40:00+00', 3, 'Ankle pain (synthetic demo)'),
('00000000-0000-0000-0000-000000000006', 'Bay 9', '2026-10-19 10:05:00+00', 3, 'Headache (synthetic demo)');

-- Bay 7: higher initial severity, comparatively flat trend
insert into events (patient_id, observed_at, hr, spo2, pain, note) values
('00000000-0000-0000-0000-000000000007', '2026-10-19 10:10:00+00', 88, 97, 5, null),
('00000000-0000-0000-0000-000000000007', '2026-10-19 10:18:00+00', 89, 97, 5, null),
('00000000-0000-0000-0000-000000000007', '2026-10-19 10:25:00+00', 87, 98, 4, null),
('00000000-0000-0000-0000-000000000007', '2026-10-19 10:36:00+00', 88, 97, 5, null);

-- Bay 4: lower initial severity, persistent worsening trend (headline demo case)
insert into events (patient_id, observed_at, hr, spo2, pain, note) values
('00000000-0000-0000-0000-000000000004', '2026-10-19 10:10:00+00', 96, 97, 4, null),
('00000000-0000-0000-0000-000000000004', '2026-10-19 10:18:00+00', 101, 96, 5, null),
('00000000-0000-0000-0000-000000000004', '2026-10-19 10:25:00+00', 110, 94, 6, 'Reports worsening breathlessness'),
('00000000-0000-0000-0000-000000000004', '2026-10-19 10:36:00+00', 121, 91, 7, null);

-- Bay 2: long-waiting but stable (waiting time alone must not dominate attention)
insert into events (patient_id, observed_at, hr, spo2, pain, note) values
('00000000-0000-0000-0000-000000000005', '2026-10-19 09:48:00+00', 78, 99, 3, null),
('00000000-0000-0000-0000-000000000005', '2026-10-19 10:05:00+00', 79, 99, 3, null),
('00000000-0000-0000-0000-000000000005', '2026-10-19 10:25:00+00', 77, 99, 2, null),
('00000000-0000-0000-0000-000000000005', '2026-10-19 10:40:00+00', 78, 99, 3, null);

-- Bay 9: one-off spike that resolves (must not be narrated as persistent change)
insert into events (patient_id, observed_at, hr, spo2, pain, note) values
('00000000-0000-0000-0000-000000000006', '2026-10-19 10:12:00+00', 82, 98, 3, null),
('00000000-0000-0000-0000-000000000006', '2026-10-19 10:20:00+00', 115, 93, 6, 'Possible anxiety episode'),
('00000000-0000-0000-0000-000000000006', '2026-10-19 10:28:00+00', 85, 98, 3, null),
('00000000-0000-0000-0000-000000000006', '2026-10-19 10:38:00+00', 83, 98, 2, null);
