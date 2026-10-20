# Atria by Atriveo — landing and early access

Cloudflare preview: **https://atria-landing.s6-backend-spike.workers.dev**.

Public destination: **https://atria.atriveo.com**. The custom domain must be attached
from the Cloudflare account that owns the `atriveo.com` zone; it is not activated
just by checking in a configuration file. The preview is deployed; the current
Cloudflare login cannot access the `atriveo.com` zone, so the custom domain is
pending access to its owning account. GitHub automatic deployment is also
pending the dedicated token described below.

This directory contains a standalone landing page, a durable email waitlist, and
the Cloudflare Worker that serves them. It links to the existing product demo at
https://atria-er.vercel.app. The clinical prototype remains in `er-priority/frontend`
and `backend`; the waitlist has no access to patient tables or product credentials.

## Run locally

```sh
cd landing
npm ci
npm run db:local
npm run dev
```

Open `http://localhost:8787`. If that port is occupied, use
`npm run dev -- --port 8791`. Local development writes to a local D1 database under
the ignored `.wrangler/` directory.

```sh
npm run build
npm run check
npx playwright install chromium
npm run test:browser
npx wrangler deploy --dry-run
```

The browser suite runs a Worker on port 8791 (override with `ATRIA_TEST_PORT`)
and tests desktop/mobile layouts, keyboard menu behavior,
successful signup, failed signup, privacy navigation, and 404 handling. For an
installed Google Chrome, use `PLAYWRIGHT_CHANNEL=chrome npm run test:browser`.

## Hosting

The deployment uses [Cloudflare Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/),
one small Worker, and [D1](https://developers.cloudflare.com/d1/). A small esbuild
step creates `dist/` with the HTML, design tokens, Switzer fonts, and a bundled
GSAP flow animation. Wrangler runs `npm run build` before preview and deployment.
No Next.js adapter is needed for this standalone landing page.

`wrangler.jsonc` tracks the Worker name, account, database binding, assets, and
rate limit. Account and database IDs are identifiers, not credentials. Never put
Cloudflare tokens, database passwords, or product API keys in the static assets.

From an authenticated account matching the config:

```sh
npx wrangler whoami
npm run db:remote
npm run deploy
```

For a different Cloudflare account, update `account_id`, create a database with
`npx wrangler d1 create atria-waitlist`, and copy its ID into `wrangler.jsonc`.
Apply migrations before deploying. Do not delete a database containing signups
when moving accounts; export and transfer the records first.

### Attach atria.atriveo.com

1. Confirm the deploying account has access to the existing `atriveo.com` zone.
2. Check whether `atria.atriveo.com` already has DNS records before replacing any.
3. Add this top-level configuration, then run `npm run deploy`:

```json
"routes": [
  { "pattern": "atria.atriveo.com", "custom_domain": true }
]
```

Cloudflare manages the DNS record and certificate for a
[Worker Custom Domain](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).
Confirm both `https://atria.atriveo.com/` and `/api/health` respond successfully.
The root Atriveo site and other product subdomains should continue serving their
existing Workers. After the domain responds, update the canonical and Open Graph
URLs in both HTML pages, `robots.txt`, and `sitemap.xml` to the new public domain.
Until then they intentionally identify the working Cloudflare preview.

## GitHub and continuous deployment

The existing repository is `atishay-kasliwal/Atriaa`. The landing page belongs here
alongside the application; no second source repository is needed.

`.github/workflows/landing.yml` checks pull requests and changes on `main`.
It deploys only after the repository variable `CLOUDFLARE_DEPLOY_ENABLED` is `true`.
Before enabling it, add:

- Repository secret `CLOUDFLARE_API_TOKEN`: a dedicated token for the destination
  account with Workers Scripts Edit, D1 Edit, and the zone permissions needed
  for the custom domain (Zone Read and Workers Routes Edit). Use Cloudflare's
  Workers token template and include D1 access. Do not copy a personal OAuth
  session into GitHub secrets.
- Repository variable `CLOUDFLARE_ACCOUNT_ID`: the account in `wrangler.jsonc`.
- Repository variable `CLOUDFLARE_DEPLOY_ENABLED`: `true` once the above is ready.

Merging a landing-page change into `main` then runs checks, applies any new D1
migrations, and deploys. A manual workflow run on `main` follows the same checks.
The existing Render and Vercel product deployments are separate. The landing
release does not include the unfinished Next.js motion-engine changes. See
[the release review](REVIEW.md) for checks, measurements, and remaining limits.

Cloudflare Workers Builds is an alternative to GitHub Actions. Connect this
repository, choose root directory `landing`, branch `main`, build command
`npm ci && npm run check`, and deploy command `npm run db:remote && npm run deploy`.
Choose one deployment mechanism to avoid simultaneous releases.

## Waitlist behavior and access

`POST /api/waitlist` accepts email, optional name, role, explicit consent, and a
hidden spam field. The server validates input and origin, bounds request size,
and uses a rate-limit binding. An email can only be stored once; repeated
submissions return the same confirmation. A storage failure returns an error,
and the UI keeps the form available for retry. A signup is not a product account.

Records live in D1 database `atria-waitlist`, table `waitlist`. Authorized team
members can inspect or export them through the Cloudflare D1 console. There is
no public listing endpoint. The handler does not log form bodies or save IPs.
No emails are sent automatically by this implementation.

For a deletion request, find the requested email in the D1 console and delete only
that record. Keep exported lists private and out of Git. The landing page's
`/privacy` page explains data use and how to request removal.

## Content provenance

- Parent brand/domain: Atriveo, `atria.atriveo.com`, confirmed by the project owner.
- Event: [Hacktoberfest Hacks @ All Things Open](https://www.mlh.com/events/hacktoberfest-hacks-all-things-open).
- Award: **Winner — Best Use of Tiger Data**, confirmed by the project owner.
- The product illustration is explicitly synthetic. Product capabilities are
  based on this repository; no clinical outcome, customer, or performance claims
  are implied by the landing page.

## Product work after the landing launch

Waitlist registration is the scope of this release. Before a real product pilot,
define account and organization access, replace open demo actions with authorized
workflows, add operational monitoring and data retention controls, and validate
the reassessment workflow with qualified care teams. Keep synthetic demo data
separate from any future production encounters.

## Fonts and motion

Switzer is fetched from Fontshare at build time and self-hosted for this site.
Font binaries are ignored in Git; see [font provenance](FONTS.md). Content remains
visible without JavaScript. The single GSAP ticker animates the conceptual flow
only while it is visible and the tab is active. Reduced motion stops it entirely.
The page uses native scrolling, no blocking loader, and no WebGL requirement.
