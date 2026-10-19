# Atria - ER reassessment demo

**See what changed while patients wait.** Synthetic ER waiting room → timestamped events → deterministic agents → Attention Queue → nurse reviews evidence → Ask Atria explains → nurse action is audited. All patient data is synthetic. Not a medical device.

## 1. Supabase
In the SQL Editor (or `psql "$ATRIA_DATABASE_URL" -f ...`), run in order:

1. `supabase/migrations/202610190001_er_reassessment.sql` - `patients`, `events`, `audit_log`
2. `supabase/migrations/202610190002_demo_seed.sql` - original 4-patient seed (optional; Reset replaces it)
3. `supabase/migrations/202610190003_demo_runs.sql` - `atria_demo_runs`, run/idempotency columns
4. `supabase/migrations/202610190004_event_key_unique.sql` - unique keys used for idempotent writes

All are additive and safe to repeat; existing `er_*` tables are untouched. Put the Project URL and a backend secret / service_role key in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

## 2. Gemini
Key from aistudio.google.com/apikey in `GEMINI_API_KEY`. Default model `gemini-3.5-flash`, then `gemini-flash-latest` (override with `GEMINI_MODEL`). Calls time out after 12s with no SDK retries; on failure, or if the answer cites a number not in the evidence, Ask Atria returns a labeled deterministic fallback built from the same evidence.

## 3. Run
```
uv pip install --python .venv/bin/python -r backend/requirements-dev.txt
cd backend
uvicorn main:app --reload --port 8000
```
Open http://localhost:8000 - the backend serves the frontend. (`frontend/index.html` also works from a static server; add `?api=http://host:port` to point it elsewhere.)

Env is read from process env, then `backend/.env`, then the repo `.env.local`. Without Supabase credentials (or with `ATRIA_STORE=memory`) the backend runs fully in memory, which is useful offline or as a demo fallback.

## 4. Demo
1. **Reset** - fresh synthetic run: 8 patients with intake readings only.
2. **Start** (1x/2x/5x) or **Next Event** - the backend replays 25 fixed events; the board polls the backend.
3. Bay 4 (ESI 3) rises to #1 on persistent change (HR 92→121, SpO2 98→91%, pain 4→7) while Bay 7 (ESI 2) stays visible and stable. Bay 9's single spike shows as *transient*, then resolves. Bay 2's long wait doesn't push it up. Bay 6's pain-only change shows **LOW CONSENSUS**.
4. Click Bay 4: intake/current/delta, sparklines, agent findings, timeline. **Request Nurse Reassessment** writes a confirmed, idempotent audit event.
5. Ask Atria: "Why did Bay 4 move above Bay 7?" - answer cites values, times and the queue version, labeled Gemini or fallback.
6. **Raleigh Overview** tab: real Wake County GIS facility data (22 emergency facilities, 10 in Wake County) on a map, with source, dates and limitations. Live query with a bundled snapshot fallback.

## Tests
```
cd backend && ../.venv/bin/python -m pytest -q tests
```
Covers trajectory rules, the Bay 4/7/9/2 acceptance scenario, deterministic resets, run-scoped and idempotent audit, Gemini grounding check and fallback, and the Raleigh snapshot.

## Layout
| File | Role |
|---|---|
| `backend/core.py` | Vital / Trend / Context agents, Patient and Waiting Room coordinators, queue policy |
| `backend/scenario.py` | Fixed 8-patient synthetic scenario |
| `backend/engine.py` | Backend-owned replay (reset/step/status), queue and evidence projections |
| `backend/store.py` | Supabase store and in-memory store |
| `backend/assistant.py` | Gemini prompt, grounding check, deterministic fallback |
| `backend/raleigh.py` | Wake County GIS hospitals (live + snapshot in `backend/data/`) |
| `backend/observability.py` | Sentry (no-op without `SENTRY_DSN`) |

## Rules
- Trend logic is plain Python: `persistent_change` needs at least 2 of 3 signals (HR up, SpO2 down, pain up) worsening by a minimum step on every consecutive reading. One signal = `mixed_change`; a non-persistent deviation from intake = `transient_change`. Thresholds are illustrative, not clinical.
- Queue order: trajectory tier, then number of worsening signals, then size of change (changing patients only), then intake ESI, then waiting time. Intake ESI is never modified.
- The independent open model is shown as **unavailable**, never as a reassuring vote.
- The service_role key bypasses Row Level Security - backend only, never in a frontend.
