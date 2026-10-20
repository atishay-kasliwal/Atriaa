# Atria application prototype

Next.js application for patient check-in, ticket updates, and the nurse station.
The public early-access landing page lives separately in `../../landing` at
https://atria.atriveo.com. This application is a synthetic demonstration, not a
clinical product.

## Run

From the repository root, `./scripts/dev.sh` starts the FastAPI backend on port
8001 and this frontend on port 3000. To start only the frontend:

```sh
npm ci
npm run dev
```

`predev` and `prebuild` download Switzer 400, 500, 600, and 700 directly from
Fontshare into ignored `public/fonts/`. The files are self-hosted by Next.js and
are not redistributed in Git. A first build needs access to Fontshare; subsequent
builds reuse the files. Content and navigation remain visible without JavaScript;
live features require it.

## Pages

| Route | Purpose |
| --- | --- |
| `/` | Choose patient check-in or the nurse station |
| `/checkin` | Patient check-in |
| `/status/<id>` | Patient ticket, nurse requests, and patient updates |
| `/nurse` | Queue, human priority, readings, reassessment, and beds |
| `/nurse/intake` | Front-desk check-in |
| `/nurse/ask` | On-demand explanations from current recorded data |
| `/nurse/trends` | Tiger Data history and aggregates |
| `/nurse/nearby` | Nearby emergency department directory |

The API proxy uses `ATRIA_API_URL`, defaulting to `http://127.0.0.1:8001`.
Set that value **before building**, because Next.js records rewrites at build time.
Database and model credentials belong only in the backend environment.

The prototype uses a consistent light palette even with dark system preferences.
Text uses dark slate; actions use deep blue. Native scrolling and navigation stay
under Next.js control. The small route animation cleans up on navigation and is
disabled when reduced motion is requested. No loader obscures the application.
Patient tickets and staff pages deliberately use `noindex, nofollow`; search
content belongs on the public landing page.

## Verify

```sh
npm run lint
npm run build
npx playwright install chromium
npm run test:browser
```

The browser suite starts a production Next.js server on port 4410 and an isolated
in-memory API on port 8801. It never uses configured database or model credentials.
Install the backend's `../../backend/requirements.txt` first. On a Mac with Chrome
already installed, use `PLAYWRIGHT_CHANNEL=chrome npm run test:browser`.
The GitHub application workflow runs lint and this suite for application changes.

## Deploy

The existing application target is https://atria-er.vercel.app. Use Vercel root
directory `er-priority/frontend`, build command `npm run build`, and set
`ATRIA_API_URL` to the deployed FastAPI origin. Pushing the feature branch does
not replace the production application unless that branch is configured for
production in Vercel. The Cloudflare landing deployment is separate.
