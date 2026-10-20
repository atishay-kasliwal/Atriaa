# Atria custom-domain launch

Atria is deployed at **https://atria.atriveo.com** in the account that owns
`atriveo.com`. On October 19, 2026, the owner requested a fresh launch in this
account instead of transferring records from the original preview account.

| Active resource | Value |
|---|---|
| Cloudflare account | `a4e4f5c1214af712b0f5f48ef7c722ec` |
| Worker | `atria-landing` |
| D1 database | `atria-waitlist` / `6e7c11bc-adbc-4cdf-a49f-43bbdddd1135` |
| Schema | `0001_waitlist.sql`, applied remotely |
| Custom domain | `atria.atriveo.com` |
| New preview | `atria-landing.katishay.workers.dev`, redirects to the public domain |

The new database was empty before launch verification. The original account,
Worker, and database were not changed or deleted, and no legacy signup records
were imported. The original `s6-backend-spike.workers.dev` preview is independent
of this launch and does not redirect to the new domain.

## Verification

- Cloudflare and Google public DNS resolvers return the new hostname's records.
- HTTPS serves the landing with valid certificate verification enabled.
- Live signup succeeds; two submissions of one synthetic address produced one
  database row. That verification record was deleted afterward.
- The public home/privacy pages identify their own canonical URLs. New preview
  GET/HEAD requests redirect with 308 and retain path/query; missing pages return
  an actual 404. The Atriveo project entry points to the custom domain.
- Eleven unit tests and seven browser tests cover normal signup, failures,
  navigation, responsive layouts, contrast under both system preferences,
  reduced motion, no JavaScript, redirects, stale forms, and response headers.
- HTML responses preserve the strict CSP and exclude automatic edge script
  injection with `Cache-Control: no-transform`; other assets retain compression.

The local OS initially retained an earlier NXDOMAIN result. Public DNS answers
and HTTPS were checked independently. Browser verification used the address
published by those public resolvers while retaining full hostname/certificate
validation; no TLS errors were ignored.

## Redirect-report evidence and limits

The registered redirect-trace report returned zero findings and no inventories,
with unknown acquisition coverage. Its initial final-page fetch was blocked by
the local DNS cache; that report is not an all-clear. Independent browser checks
verify the actual redirected page. Compact evidence is under the ignored
`.wrangler/account-migration/` directory. No Search Console or ranking evidence
was supplied, so this record makes no indexing or search-performance claim.

| URL | Disposition | Verification |
|---|---|---|
| `https://atria.atriveo.com/` | Serve the fresh landing | HTTPS 200, matching canonical, working signup |
| `https://atria.atriveo.com/privacy` | Serve the privacy notice | HTTPS 200, matching canonical |
| New preview `/privacy?from=preview` | Redirect to the same public path/query | HTTP 308 followed by public page 200 |
| Original preview | Leave unchanged, per fresh-start scope | No source-account writes or deployments performed |

No database export or OAuth session copy belongs in Git. Temporary session
copies are removed after launch; the normal Wrangler login remains in the
destination account. GitHub automatic deployment remains separately gated on
a dedicated scoped API token.
