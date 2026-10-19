-- ATRIA: local/synthetic ER MVP schema for Supabase Postgres.
-- Run once in the project's SQL Editor. Safe to rerun; no legacy table drops/resets.
-- Public client access is READ ONLY and limited to the active synthetic run.
-- Writes require the SQL Editor or an authorized backend service-role client.
BEGIN;

CREATE TABLE IF NOT EXISTS public.er_demo_runs (
  run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scenario text NOT NULL DEFAULT 'er-reassessment-v1',
  active boolean NOT NULL DEFAULT true,
  cursor integer NOT NULL DEFAULT 0 CHECK (cursor BETWEEN 0 AND 3),
  version bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
  replay_time timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  demo boolean NOT NULL DEFAULT true CHECK (demo)
);
CREATE UNIQUE INDEX IF NOT EXISTS er_one_active_run
  ON public.er_demo_runs(active) WHERE active;

CREATE TABLE IF NOT EXISTS public.er_encounters (
  run_id uuid NOT NULL REFERENCES public.er_demo_runs(run_id) ON DELETE RESTRICT,
  patient_id text NOT NULL,
  bay text NOT NULL,
  arrival_time timestamptz NOT NULL,
  initial_triage smallint NOT NULL CHECK (initial_triage BETWEEN 1 AND 5),
  chief_complaint text NOT NULL,
  intake_json jsonb NOT NULL CHECK (
    jsonb_typeof(intake_json) = 'object'
    AND intake_json ?& ARRAY['hr','spo2','pain','bp_sys','bp_dia','temp_c','rr']
  ),
  demo boolean NOT NULL DEFAULT true CHECK (demo),
  PRIMARY KEY (run_id, patient_id),
  UNIQUE (run_id, bay)
);

CREATE TABLE IF NOT EXISTS public.er_patient_events (
  event_id text PRIMARY KEY,
  run_id uuid NOT NULL,
  patient_id text NOT NULL,
  sequence_no bigint NOT NULL CHECK (sequence_no >= 0),
  event_time timestamptz NOT NULL,
  received_time timestamptz NOT NULL DEFAULT now(),
  event_type text NOT NULL CHECK (event_type IN
    ('intake','measurement','pain_report','symptom_report','observation')),
  payload_json jsonb NOT NULL CHECK (
    jsonb_typeof(payload_json) = 'object' AND payload_json <> '{}'::jsonb
  ),
  demo boolean NOT NULL DEFAULT true CHECK (demo),
  FOREIGN KEY (run_id, patient_id)
    REFERENCES public.er_encounters(run_id, patient_id) ON DELETE RESTRICT,
  UNIQUE (run_id, patient_id, sequence_no)
);
CREATE INDEX IF NOT EXISTS er_events_patient_time
  ON public.er_patient_events(run_id, patient_id, event_time, sequence_no);

CREATE TABLE IF NOT EXISTS public.er_reassessment_requests (
  action_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL,
  patient_id text NOT NULL,
  signal_version bigint NOT NULL CHECK (signal_version >= 0),
  actor text NOT NULL CHECK (length(btrim(actor)) BETWEEN 1 AND 100),
  reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 1000),
  requested_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  origin text NOT NULL CHECK (origin IN ('synthetic_fixture','human_demo_action')),
  demo boolean NOT NULL DEFAULT true CHECK (demo),
  FOREIGN KEY (run_id, patient_id)
    REFERENCES public.er_encounters(run_id, patient_id) ON DELETE RESTRICT,
  UNIQUE (run_id, patient_id)
);

-- Intake is read-only; source observations and requests are append-only.
-- A demo reset archives its run rather than deleting its audit history.
CREATE OR REPLACE FUNCTION public.er_reject_history_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  RAISE EXCEPTION 'ER intake, events and requests are immutable in the synthetic MVP';
END;
$$;
REVOKE ALL ON FUNCTION public.er_reject_history_mutation() FROM PUBLIC, anon, authenticated;
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['er_encounters','er_patient_events','er_reassessment_requests'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_trigger
      WHERE tgrelid = format('public.%I', t)::regclass AND tgname = 'er_immutable_history') THEN
      EXECUTE format('CREATE TRIGGER er_immutable_history BEFORE UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.er_reject_history_mutation()', t);
    END IF;
  END LOOP;
END;
$$;

-- No anonymous INSERT/UPDATE/DELETE and no client-callable privileged write RPC.
ALTER TABLE public.er_demo_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.er_encounters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.er_patient_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.er_reassessment_requests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.er_demo_runs, public.er_encounters,
  public.er_patient_events, public.er_reassessment_requests FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.er_demo_runs, public.er_encounters,
  public.er_patient_events, public.er_reassessment_requests TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.er_demo_runs, public.er_encounters,
  public.er_patient_events, public.er_reassessment_requests TO service_role;

DO $$
DECLARE t text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public'
      AND tablename='er_demo_runs' AND policyname='er_active_demo_read') THEN
    CREATE POLICY er_active_demo_read ON public.er_demo_runs FOR SELECT TO anon, authenticated
      USING (demo AND active);
  END IF;
  FOREACH t IN ARRAY ARRAY['er_encounters','er_patient_events','er_reassessment_requests'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public'
        AND tablename=t AND policyname='er_active_demo_read') THEN
      EXECUTE format('CREATE POLICY er_active_demo_read ON public.%I FOR SELECT TO anon, authenticated USING (demo AND EXISTS (SELECT 1 FROM public.er_demo_runs r WHERE r.run_id = %I.run_id AND r.active AND r.demo))', t, t);
    END IF;
  END LOOP;
END;
$$;

-- Fixed, clearly synthetic intake fixture. Existing runs are never reset by this file.
INSERT INTO public.er_demo_runs (run_id, replay_time)
SELECT 'a7100000-0000-4000-8000-000000000001', '2026-10-19T10:02:00Z'
WHERE NOT EXISTS (SELECT 1 FROM public.er_demo_runs)
ON CONFLICT DO NOTHING;

INSERT INTO public.er_encounters
  (run_id, patient_id, bay, arrival_time, initial_triage, chief_complaint, intake_json)
SELECT 'a7100000-0000-4000-8000-000000000001', v.patient_id, v.bay,
  v.arrival_time::timestamptz, v.triage, 'Synthetic demo complaint; not a diagnosis',
  jsonb_build_object('hr', v.hr, 'spo2', v.spo2, 'pain', v.pain,
                    'bp_sys',120, 'bp_dia',78, 'temp_c',36.8, 'rr',18)
FROM (VALUES
  ('bay7','Bay 7','2026-10-19T09:41:00Z',2,104,95,5),
  ('bay4','Bay 4','2026-10-19T10:02:00Z',3,92,98,4),
  ('bay9','Bay 9','2026-10-19T08:10:00Z',4,78,98,2),
  ('bay2','Bay 2','2026-10-19T09:26:00Z',3,84,98,3)
) AS v(patient_id,bay,arrival_time,triage,hr,spo2,pain)
WHERE EXISTS (SELECT 1 FROM public.er_demo_runs
  WHERE run_id='a7100000-0000-4000-8000-000000000001')
ON CONFLICT DO NOTHING;

INSERT INTO public.er_patient_events
  (event_id,run_id,patient_id,sequence_no,event_time,event_type,payload_json)
SELECT 'intake:' || e.run_id::text || ':' || e.patient_id,
  e.run_id, e.patient_id, 0, e.arrival_time, 'intake', e.intake_json
FROM public.er_encounters e
WHERE e.run_id='a7100000-0000-4000-8000-000000000001'
ON CONFLICT DO NOTHING;

-- Explicit fixture request, not an AI clinical decision or a fabricated human click.
INSERT INTO public.er_reassessment_requests
  (run_id,patient_id,signal_version,actor,reason,requested_at,origin)
SELECT run_id, patient_id, 0, 'Synthetic intake nurse',
  'Existing review request in the synthetic fixture', arrival_time, 'synthetic_fixture'
FROM public.er_encounters
WHERE run_id='a7100000-0000-4000-8000-000000000001' AND patient_id='bay7'
ON CONFLICT DO NOTHING;

-- Add only the new tables; retain the existing publication and legacy subscriptions.
DO $$
DECLARE t text;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname='supabase_realtime') THEN
    FOREACH t IN ARRAY ARRAY['er_demo_runs','er_encounters','er_patient_events','er_reassessment_requests'] LOOP
      IF NOT EXISTS (SELECT 1 FROM pg_publication_tables
          WHERE pubname='supabase_realtime' AND schemaname='public' AND tablename=t) THEN
        EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', t);
      END IF;
    END LOOP;
  END IF;
END;
$$;
COMMIT;

-- Expected after applying: one active synthetic run, four encounters, four intake
-- events and one fixture review request. New FastAPI write endpoints are not built yet.
SELECT 'er_demo_runs' AS entity, count(*) FROM public.er_demo_runs
UNION ALL SELECT 'er_encounters', count(*) FROM public.er_encounters
UNION ALL SELECT 'er_patient_events', count(*) FROM public.er_patient_events
UNION ALL SELECT 'er_reassessment_requests', count(*) FROM public.er_reassessment_requests;
