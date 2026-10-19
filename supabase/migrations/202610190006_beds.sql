-- Beds and front-desk priority suggestions for the live waiting room. Safe to repeat.
BEGIN;
ALTER TABLE public.checkins ADD COLUMN IF NOT EXISTS bed text;
ALTER TABLE public.checkins ADD COLUMN IF NOT EXISTS suggested_priority int CHECK (suggested_priority BETWEEN 1 AND 3);
ALTER TABLE public.checkins DROP CONSTRAINT IF EXISTS checkins_status_check;
ALTER TABLE public.checkins ADD CONSTRAINT checkins_status_check CHECK (status IN ('waiting', 'called', 'discharged'));
CREATE UNIQUE INDEX IF NOT EXISTS checkins_one_patient_per_bed ON public.checkins (bed) WHERE status = 'called' AND bed IS NOT NULL;
NOTIFY pgrst, 'reload schema';
COMMIT;
