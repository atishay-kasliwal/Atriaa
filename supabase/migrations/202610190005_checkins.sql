-- Live check-ins from the ER Priority intake (er-priority/frontend).
-- A check-in creates a patients row (so Atria can watch its events) plus this row.
-- Priority is assigned by a human; it stays NULL until staff review.
BEGIN;
SET LOCAL search_path TO public;

-- Live patients have no intake severity until staff assign one.
ALTER TABLE public.patients ALTER COLUMN initial_triage DROP NOT NULL;

CREATE TABLE IF NOT EXISTS public.checkins (
  id uuid PRIMARY KEY REFERENCES public.patients(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS atria_checkins_status_created_idx
  ON public.checkins (status, created_at);

-- Backend uses the service role; keep the table closed to anon/browser keys.
ALTER TABLE public.checkins ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
COMMIT;
