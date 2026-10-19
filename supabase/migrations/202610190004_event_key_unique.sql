-- ON CONFLICT (event_key) needs a non-partial unique index; NULLs stay allowed.
BEGIN;
SET LOCAL search_path TO public;
DROP INDEX IF EXISTS public.atria_events_event_key_uidx;
CREATE UNIQUE INDEX IF NOT EXISTS atria_events_event_key_key ON public.events (event_key);
DROP INDEX IF EXISTS public.atria_audit_idempotency_uidx;
CREATE UNIQUE INDEX IF NOT EXISTS atria_audit_idempotency_key ON public.audit_log (idempotency_key);
NOTIFY pgrst, 'reload schema';
COMMIT;
