-- Fixed synthetic demo fixtures. Re-runs preserve existing patients and readings.
BEGIN;
SET LOCAL search_path TO public;
CREATE TEMP TABLE atria_seed_patients (LIKE public.patients INCLUDING DEFAULTS) ON COMMIT DROP;
CREATE TEMP TABLE atria_seed_events (LIKE public.events INCLUDING DEFAULTS) ON COMMIT DROP;

-- Seed patients (fixed UUIDs so the backend/demo script can reference them directly)
insert into atria_seed_patients (id, bay, arrival_time, initial_triage, chief_complaint) values
('00000000-0000-0000-0000-000000000007', 'Bay 7', '2026-10-19 10:02:00+00', 2, 'Chest discomfort (synthetic demo)'),
('00000000-0000-0000-0000-000000000004', 'Bay 4', '2026-10-19 10:02:00+00', 3, 'Mild shortness of breath (synthetic demo)'),
('00000000-0000-0000-0000-000000000005', 'Bay 2', '2026-10-19 09:40:00+00', 3, 'Ankle pain (synthetic demo)'),
('00000000-0000-0000-0000-000000000006', 'Bay 9', '2026-10-19 10:05:00+00', 3, 'Headache (synthetic demo)');

-- Bay 7: higher initial severity, comparatively flat trend
insert into atria_seed_events (patient_id, observed_at, hr, spo2, pain, note) values
('00000000-0000-0000-0000-000000000007', '2026-10-19 10:10:00+00', 88, 97, 5, null),
('00000000-0000-0000-0000-000000000007', '2026-10-19 10:18:00+00', 89, 97, 5, null),
('00000000-0000-0000-0000-000000000007', '2026-10-19 10:25:00+00', 87, 98, 4, null),
('00000000-0000-0000-0000-000000000007', '2026-10-19 10:36:00+00', 88, 97, 5, null);

-- Bay 4: lower initial severity, persistent worsening trend (headline demo case)
insert into atria_seed_events (patient_id, observed_at, hr, spo2, pain, note) values
('00000000-0000-0000-0000-000000000004', '2026-10-19 10:10:00+00', 96, 97, 4, null),
('00000000-0000-0000-0000-000000000004', '2026-10-19 10:18:00+00', 101, 96, 5, null),
('00000000-0000-0000-0000-000000000004', '2026-10-19 10:25:00+00', 110, 94, 6, 'Reports worsening breathlessness'),
('00000000-0000-0000-0000-000000000004', '2026-10-19 10:36:00+00', 121, 91, 7, null);

-- Bay 2: long-waiting but stable (waiting time alone must not dominate attention)
insert into atria_seed_events (patient_id, observed_at, hr, spo2, pain, note) values
('00000000-0000-0000-0000-000000000005', '2026-10-19 09:48:00+00', 78, 99, 3, null),
('00000000-0000-0000-0000-000000000005', '2026-10-19 10:05:00+00', 79, 99, 3, null),
('00000000-0000-0000-0000-000000000005', '2026-10-19 10:25:00+00', 77, 99, 2, null),
('00000000-0000-0000-0000-000000000005', '2026-10-19 10:40:00+00', 78, 99, 3, null);

-- Bay 9: one-off spike that resolves (must not be narrated as persistent change)
insert into atria_seed_events (patient_id, observed_at, hr, spo2, pain, note) values
('00000000-0000-0000-0000-000000000006', '2026-10-19 10:12:00+00', 82, 98, 3, null),
('00000000-0000-0000-0000-000000000006', '2026-10-19 10:20:00+00', 115, 93, 6, 'Possible anxiety episode'),
('00000000-0000-0000-0000-000000000006', '2026-10-19 10:28:00+00', 85, 98, 3, null),
('00000000-0000-0000-0000-000000000006', '2026-10-19 10:38:00+00', 83, 98, 2, null);

INSERT INTO public.patients (id, bay, arrival_time, initial_triage, chief_complaint)
SELECT id, bay, arrival_time, initial_triage, chief_complaint
FROM atria_seed_patients
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.events (patient_id, observed_at, hr, spo2, pain, note)
SELECT s.patient_id, s.observed_at, s.hr, s.spo2, s.pain, s.note
FROM atria_seed_events s
WHERE NOT EXISTS (
  SELECT 1 FROM public.events e
  WHERE e.patient_id = s.patient_id AND e.observed_at = s.observed_at
);
COMMIT;
