-- Backend-owned demo replay state, event idempotency and run-scoped audit.
-- Additive only; safe to repeat. Existing er_* tables are untouched.
BEGIN;
SET LOCAL search_path TO public;

ALTER TABLE public.events ADD COLUMN IF NOT EXISTS run_id text;
ALTER TABLE public.events ADD COLUMN IF NOT EXISTS event_key text;
CREATE UNIQUE INDEX IF NOT EXISTS atria_events_event_key_uidx
  ON public.events (event_key) WHERE event_key IS NOT NULL;

ALTER TABLE public.audit_log ADD COLUMN IF NOT EXISTS run_id text;
ALTER TABLE public.audit_log ADD COLUMN IF NOT EXISTS queue_version text;
ALTER TABLE public.audit_log ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS atria_audit_idempotency_uidx
  ON public.audit_log (idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.atria_demo_runs (
  run_id text PRIMARY KEY,
  started_at timestamptz NOT NULL DEFAULT now(),
  cursor int NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'paused' CHECK (status IN ('paused', 'running', 'complete')),
  speed numeric NOT NULL DEFAULT 1,
  active boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS atria_demo_runs_one_active_uidx
  ON public.atria_demo_runs (active) WHERE active;

NOTIFY pgrst, 'reload schema';
COMMIT;
