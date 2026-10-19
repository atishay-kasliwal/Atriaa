# ER Priority with Atria

**See who's getting worse while they wait.** Triage happens once, at the door. Atria keeps watching after that: patients check in on their phone, nurses set priority and record re-checks, and Atria flags anyone whose readings worsen on every check, so a nurse can act. All patients are made up. Not a medical device.

One app, three views (`er-priority/frontend`, Next.js), backed by the Atria API (`backend`, FastAPI, not user-facing):

| Page | Who | What |
|---|---|---|
| `/` | everyone | Home: choose patient or nurse station |
| `/checkin` → `/status/<id>` | patient | Check in, see ticket and place in line, send "I feel worse" / pain updates |
| `/nurse` | nurse | Waiting room: priority, re-checks, Atria alerts, acknowledge + raise priority, call in, sample-room demo controls |
| `/nurse/ask` | nurse | Ask Atria about the waiting room (Gemini, or a labeled sourced fallback) |
| `/nurse/intake` | front desk | Check in a walk-in on their behalf |

## Quick start
```
uv pip install --python .venv/bin/python -r backend/requirements-dev.txt
./scripts/dev.sh          # API on :8001 + app on :3000
```
Open http://localhost:3000. Use `localhost`, not `127.0.0.1`: Next's dev server blocks its scripts on other hosts. For judges on other devices: `cloudflared tunnel --url http://localhost:3000` (the app proxies `/api` to the backend, so one tunnel is enough).

## Demo (3 minutes)
1. **Nurse station → Load sample**: 8 fictional patients, already triaged (Maya Patel is Priority 3, #6 in line). **Play** feeds in their scripted re-checks.
2. Maya's HR, SpO2 and pain worsen on every reading. Atria raises a red alert and puts her first on its attention list. Her priority and place in line don't change: Atria never changes priority.
3. **Request re-check**: her phone (`/status/<id>`) shows "A nurse wants to re-check you".
4. **Acknowledge + Priority 1**: she moves to #1 in the official line. The alert turns green and comes back if a newer reading keeps worsening.
5. **Ask Atria**: "Who should be re-checked next?" The answer cites tickets, readings and times.
6. Live: a judge checks in at `/checkin` on their phone, the nurse sets priority, and their ticket shows their place in line.

## 1. Supabase
In the SQL Editor (or `psql "$ATRIA_DATABASE_URL" -f ...`), run in order:

1. `supabase/migrations/202610190001_er_reassessment.sql` - `patients`, `events`, `audit_log`
2. `supabase/migrations/202610190002_demo_seed.sql` - original 4-patient seed (optional; Reset replaces it)
3. `supabase/migrations/202610190003_demo_runs.sql` - `atria_demo_runs`, run/idempotency columns
4. `supabase/migrations/202610190004_event_key_unique.sql` - unique keys used for idempotent writes
5. `supabase/migrations/202610190005_checkins.sql` - `checkins` for the live waiting room; makes `patients.initial_triage` nullable (live patients have no priority until staff set one)

All are additive and safe to repeat; existing `er_*` tables are untouched. Put the Project URL and a backend secret / service_role key in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

## 2. Gemini
Key from aistudio.google.com/apikey in `GEMINI_API_KEY`. Default model `gemini-3.5-flash`, then `gemini-flash-latest` (override with `GEMINI_MODEL`). Calls time out after 12s with no SDK retries; on failure, or if the answer cites a number not in the evidence, Ask Atria returns a labeled deterministic fallback built from the same evidence.

## 3. Run the API alone
```
.venv/bin/python -m uvicorn --app-dir backend main:app --port 8001
```
Env is read from process env, then `backend/.env`, then the repo `.env.local`. Without Supabase credentials (or with `ATRIA_STORE=memory`) the API runs fully in memory, which is useful offline or as a demo fallback.

## 4. Frontend
```
cd er-priority/frontend && npm ci && npm run dev
```
`/api/*` is proxied to `ATRIA_API_URL` (default `http://127.0.0.1:8001`). Readings come from the pain score at check-in, the patient's own updates, and nurse re-checks (HR, SpO2, pain). The sample waiting room replays the fixed 8-patient scenario in `backend/scenario.py` through the same live pages. The original scripted endpoints (`/demo/*`, `/queue`, `/patient/*`) remain in the API and are covered by tests, but no UI uses them.

## Tests
```
cd backend && ../.venv/bin/python -m pytest -q tests
```
Covers trajectory rules, the Bay 4/7/9/2 acceptance scenario, the live check-in → priority → re-check → flag → patient-status loop, deterministic resets, run-scoped and idempotent audit, Gemini grounding check and fallback, and the Raleigh snapshot.

## Layout
| File | Role |
|---|---|
| `backend/core.py` | Vital / Trend / Context agents, Patient and Waiting Room coordinators, queue policy |
| `backend/scenario.py` | Fixed 8-patient synthetic scenario |
| `backend/engine.py` | Backend-owned replay (reset/step/status), queue and evidence projections |
| `backend/live.py` | Live waiting room: check-ins, patient updates, staff re-checks, live queue and patient status |
| `er-priority/frontend` | The product UI: home, patient check-in/status, nurse station, Ask Atria |
| `scripts/dev.sh` | Starts API + app together |
| `backend/store.py` | Supabase store and in-memory store |
| `backend/assistant.py` | Gemini prompt, grounding check, deterministic fallback |
| `backend/raleigh.py` | Wake County GIS hospitals (API only; no longer shown in the UI) |
| `backend/observability.py` | Sentry (no-op without `SENTRY_DSN`) |

## Rules
- Trend logic is plain Python: `persistent_change` needs at least 2 of 3 signals (HR up, SpO2 down, pain up) worsening by a minimum step on every consecutive reading. One signal = `mixed_change`; a non-persistent deviation from intake = `transient_change`. Thresholds are illustrative, not clinical.
- Queue order: trajectory tier, then number of worsening signals, then size of change (changing patients only), then intake ESI, then waiting time. Intake ESI is never modified.
- The independent open model is shown as **unavailable**, never as a reassuring vote.
- The service_role key bypasses Row Level Security - backend only, never in a frontend.
