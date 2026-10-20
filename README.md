# Atria by Atriveo

**See what changes while patients wait.**

Atria is an Atriveo project that began at
[MLH's Hacktoberfest Hacks @ All Things Open](https://www.mlh.com/events/hacktoberfest-hacks-all-things-open),
where it won **Best Use of Tiger Data**.

The public landing page and early-access waitlist are in [`landing/`](landing/README.md),
published at [the Cloudflare preview](https://atria-landing.s6-backend-spike.workers.dev)
and prepared for **atria.atriveo.com** (custom domain pending Cloudflare zone access).
The landing page has its
own D1 signup database and links to the existing working prototype. Signup does
not create a clinical-product account.

| Component | Source | Hosting |
|---|---|---|
| Landing + early-access waitlist | `landing/` | Cloudflare Workers + D1 |
| Interactive product prototype | `er-priority/frontend/` | Vercel |
| Product API | `backend/` | Render |
| Patient history and application data | `tiger/` | Tiger Data |

For landing setup, custom-domain attachment, GitHub deployment, and managing
signups, see the [landing deployment guide](landing/README.md). The checked-in
[GitHub workflow](.github/workflows/landing.yml) runs landing checks; deployment
is enabled only after adding the Cloudflare account configuration and scoped token.

## ER Priority prototype

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

## 1. Database: Tiger Data
Tiger (Postgres + TimescaleDB) is the system of record. Put the service URL in `TIGER_DATABASE_URL` and, if the URL has no password, the password in `TIGER_PASSWORD` (both in `.env.local`). Then create the tables once (safe to repeat):
```
PGPASSWORD="$TIGER_PASSWORD" psql "$TIGER_DATABASE_URL" -f tiger/app_schema.sql   # patients, events, audit_log, demo runs, checkins
PGPASSWORD="$TIGER_PASSWORD" psql "$TIGER_DATABASE_URL" -f tiger/schema.sql       # vitals hypertable + aggregates for trends
```
`ATRIA_STORE` overrides the choice: `memory` (offline, used by tests), `tiger`, or `supabase` (legacy; the `supabase/migrations` files still work).

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

## Deploying
Live: app https://atria-er.vercel.app, API https://atria-api-lzin.onrender.com, data in Tiger.

**API (Render).** `render.yaml` is a Render Blueprint: Docker build from `Dockerfile`, branch `main`, health check `/health`. Every push to `main` redeploys it. Secrets are set in the Render dashboard, never in git: `GEMINI_API_KEY`, `SENTRY_DSN`, `TIGER_DATABASE_URL`, `TIGER_PASSWORD`. The free plan sleeps after about 15 idle minutes, so open the site a couple of minutes before a demo.

**App (Vercel).** No `vercel.json` is needed; Vercel detects Next.js. The only setting is `ATRIA_API_URL`, which `er-priority/frontend/next.config.ts` uses to forward `/api/*` to the API. It must be set at build time, because Next bakes the forwarding into the build. From `er-priority/frontend`:
```
npx vercel login
npx vercel link            # choose the existing project "atria-er" (ask to be added under Settings > Members)
npx vercel deploy --prod \
  --build-env ATRIA_API_URL=https://atria-api-lzin.onrender.com \
  --env ATRIA_API_URL=https://atria-api-lzin.onrender.com
```
This deploys the local folder, including uncommitted changes, so commit first. Pushing to GitHub does not update the app unless the Vercel project is connected to the repo (Vercel > atria-er > Settings > Git: root directory `er-priority/frontend`, branch `main`, plus `ATRIA_API_URL` under Environment Variables).

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
