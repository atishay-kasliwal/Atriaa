# Atria landing release review

Reviewed October 19, 2026. Scope: `landing/`, the design brief, README, and landing
CI. The clinical slate/blue direction and Switzer typeface are preserved.

## Release defects found and fixed

| Finding | Result | Verification |
|---|---|---|
| CSS and JavaScript linked from paths outside the Worker asset directory | Fixed with a production build that copies CSS and bundles one client entry into `dist/` | Build checks every local asset reference in home, privacy, and 404; Worker browser run has no failed requests |
| ES modules loaded as classic scripts, plus TypeScript syntax in `.js` files | Replaced the unused scaffold with an executable GSAP client bundle | Production build, browser console checks |
| Inline menu/form code blocked by the Content Security Policy | External client bundle with no inline handlers or inline styles | Browser run against Wrangler with the actual `_headers` policy: zero errors |
| Consent serialized as a string and incomplete signup confirmation/error UI | Boolean consent, bounded input, duplicate-safe storage, durable confirmation, accessible failure/retry states | Unit and real Worker browser tests |
| Switzer specified but font files missing | Build fetches original WOFF2 from Fontshare and serves them locally; binaries excluded from Git | Production font requests succeed; see `FONTS.md` |
| Blocking loader, invisible reveal states, and animation scaffolding without a working lifecycle | Content visible from first paint; one GSAP clock for the conceptual flow, paused offscreen and in hidden tabs | Reduced-motion and JavaScript-disabled browser tests |
| Invalid closing link and invented privacy contact address | Valid markup and a real project contact route | HTML audit and privacy navigation check |
| First-pass 404 recovery button had matching foreground/fill | Contrasting recovery label in all states | Second desktop/mobile/focus/hover pass |
| First-pass mobile pulse symbol rotated sideways | Symbol stays upright within vertical mobile connectors | Second mobile screenshots |
| First-pass inline event link focus/hover and small credit target | Visible immediate keyboard focus, whole-link hover fill, increased target heights | Second keyboard/hover/mobile reports |

## Verification

- Eleven unit tests cover validation, persistence confirmation, storage failure,
  origin/method/content-type controls, body-size bounds, rate limiting, routing,
  canonical redirects, stale forms, and HTML response headers.
- Seven browser tests cover responsive signup, mobile keyboard menu, failed writes,
  privacy/404 navigation, reduced motion, readable content without JavaScript, and
  text contrast under light and dark system preferences on desktop and phone.
- Production assets were served at `127.0.0.1:4400` for independent visual QA.
  Form/CSP checks used the actual local Cloudflare Worker on port 8792.
- Two visual passes cover home, privacy, and 404 on desktop, a throttled 390px
  phone, reduced motion, keyboard focus, hover, and page navigation.
- Final static production audit: **0 FAIL, 0 WARN**. Main page is approximately
  **113 KB** of loaded assets, including **28 KB gzipped JavaScript**.
- Browser coverage is Chromium/Chrome and mobile emulation, not a physical-device
  or Safari/Firefox certification. Metrics are local lab measurements.

## Original launch measured results (light system setting)

| Page | Throttled mobile LCP | CLS | Mobile scroll FPS | Axe violations | Overflow / hidden reduced-motion text |
|---|---:|---:|---:|---:|---|
| Home | 864 ms | 0 | 60 | 0 | None |
| Privacy | 560 ms | 0 | 61 | 0 | None |
| 404 | 516 ms | 0 | 60 | 0 | None |

The final pass found zero invisible focus stops, zero controls without a hover
response, and zero undersized mobile targets in the sampled controls. `colorOnly`
leads were checked against the screenshots: they are whole-link background fills,
not text-color-only feedback. Raw compact results are in `review/summary.json`
and `review/audit.txt`; full local evidence is under ignored `.jury/pass-2/`.

## Contrast correction after launch

The original review missed the system dark-mode case. A fresh audit of the
published page found **43 failing text nodes**: the partial dark theme changed
inherited text to near-white while cards and fields retained white backgrounds.

The corrected palette stays light under both system preferences. Text uses dark
slate (`#0f172a`), secondary labels use `#475569`, and text links/buttons use deep
blue (`#075985`). Inputs, placeholders, and pending buttons retain readable text.
The layout is unchanged. The primary text is approximately 17:1 against the page,
secondary text exceeds 6:1 on the used light surfaces, and button labels exceed 7:1.

Two new browser regressions run axe color-contrast checks on home, privacy, and
404 at 1440px and 390px, each under light and dark system preferences. All twelve
page/viewport/preference combinations pass with zero contrast violations. The
seven browser tests and eleven unit tests pass. Before/after form screenshots
were also inspected; evidence is under ignored `.wrangler/contrast-before/` and
`.wrangler/contrast-after/`. The earlier visual scores apply to the light setting
reviewed at launch, not the broken automatic dark theme.

## SEO report dispositions

The initial registered SEO report returned seven findings, with complete affected
URL lists for home and privacy. It returned no separate inventories. A fresh
follow-up crawl and report on the same local URL retain two review observations,
handled below. Search Console visibility
was skipped because no Search Console connection/export was supplied; this review
does not establish indexing, rankings, traffic, or clinical effectiveness.

| Finding ID and title | Outcome | Reason and verification |
|---|---|---|
| `crawl:h1_missing` — h1_missing: Missing H1 (1 URL) | fixed | Privacy now has one topic-specific H1. Absent from the follow-up report. |
| `crawl:og_description_missing` — og_description_missing: og:description not set (2 URLs) | changed | Both public pages now have accurate share descriptions. Absent from follow-up. |
| `crawl:og_image_missing` — og_image_missing: Open Graph image missing (2 URLs) | changed | Both pages reference a real 1200×630 image of the rendered landing hero. Audit verifies the image loads; absent from follow-up. |
| `crawl:og_title_missing` — og_title_missing: Open Graph title missing (2 URLs) | changed | Accurate titles added to home and privacy; absent from follow-up. |
| `crawl:twitter_card_missing` — twitter_card_missing: No Twitter card declared (2 URLs) | changed | The launch page is intended to be shared; matching large-image card added. Absent from follow-up. |
| `crawl:canonical_missing` — canonical_missing: No canonical declared (2 URLs) | changed | Each page identifies its currently deployed Cloudflare URL. Follow-up observes those intended canonicals. |
| `crawl:structured_data_missing` — structured_data_missing: No structured data detected (2 URLs) | no-change | No specific rich-result type was established for this waitlist or privacy notice. No generic organization markup was added solely to clear a heuristic. |
| `crawl:canonicalized_page` — canonicalized_page: Canonicalized page (2 URLs; follow-up) | no-change | Localhost intentionally references the public custom domain. Canonical, OG, robots, and sitemap URLs now identify atria.atriveo.com. |

| Affected URL/page | Disposition | Evidence |
|---|---|---|
| `/` | Publish the reviewed landing and waitlist | Complete initial/follow-up affected lists, production HTML audit, responsive/functional/visual tests |
| `/privacy` | Publish the matching, corrected waitlist notice | Complete initial/follow-up affected lists, H1/share metadata audit, keyboard/mobile screenshots |
| Missing page / 404 | Serve an actual 404 with a visible home action; keep noindex | HTTP status test plus desktop/mobile/focus screenshots; deliberately excluded from sitemap |

## Deployment and source boundaries

The landing is live at **https://atria.atriveo.com**, served by Worker
`atria-landing` in the account that owns `atriveo.com`. The owner chose a fresh
waitlist database in that account; no records were imported from the old preview.
The old Worker and database remain untouched. The main Atriveo catalog points
to the public custom domain. See `MIGRATION.md` for the launch record.

GitHub automatic deployment remains gated on its documented dedicated Cloudflare
token and account variables. The production configuration, DNS attachment, and
manual deployment are complete.

The separate uncommitted Next.js application-engine changes remain local. They
currently fail a production build due to missing font files, incorrect CSS paths,
and missing engine exports, so they are excluded from this landing-only release.
No clinical application or backend change is included in the release commit.

The page's motion is deliberately quiet: native scrolling, no loading curtain,
no custom cursor, no WebGL requirement, and no blocking page transition. The
conceptual diagram uses synthetic values taken from `backend/scenario.py`.

## Independent visual score

Estimate, not affiliated with Awwwards. Two independent critics reviewed only the
screenshots and measurements, without source code or the design brief. The final
strict score is **7.46/10**, up from 6.80 in the first pass. The idea read from the
screen was: Atria brings patient updates and repeat readings together for human
review during the wait, matching the project brief.

| Criterion | Pass 1 | Final | Final evidence |
|---|---:|---:|---|
| Design (40%) | 7.0 | 7.3 | `home/d-01`, `d-02`, `d-07`: controlled hierarchy, clinical palette, signal diagram, form and footer |
| Usability (30%) | 6.5 | 8.0 | Phone diagram/metrics reflow; no overflow/small mobile targets; visible keyboard focus; 60–61 FPS |
| Creativity (20%) | 6.5 | 6.8 | Patient-to-review flow is specific; later sections use familiar landing patterns |
| Content (10%) | 7.5 | 7.8 | Labeled synthetic values, actual origin/award, candid prototype limits and data-use notice |

| Developer area | Final | Evidence |
|---|---:|---|
| Semantics/SEO | 8 | `review/audit.txt`: no failures or warnings; unique titles and H1s |
| Animations/transitions | 7 | Valid hover/fill feedback and idle flow; no theatrical route transition, by design |
| Accessibility | 8 | Reports: no axe violations, invisible focus, keyboard traps, or hidden reduced-motion text |
| WPO | 9 | LCP 864/560/516 ms, CLS 0, roughly 113 KB loaded assets |
| Responsive | 8 | No phone overflow or small targets; readable vertical figure and form |
| Markup/metadata | 8 | Clear audit, working share image, favicon, clean-page and real-404 metadata |

Using the Jury skill's two-reference-site calibration gives an illustrative jury
estimate of about 8.6. That small-sample offset is not an official jury score,
award prediction, or an Awwwards recognition claim. The strict critic score above
is the useful result for this review.

Remaining design opportunities are a complete synthetic review timeline, more
varied lower-page compositions, and a direct private contact destination when
one is supplied. Blocking route transitions were deliberately not added to this
small clinical-product landing page. A final desktop consent-link target was
enlarged after the second capture; that minor improvement is not reflected in
the critic's score. Screenshot review does not prove signup persistence; the
separate Worker browser tests and deployed signup verification do. The published
Worker returned HTTP 200 with no browser errors or failed asset requests; two
submissions of one synthetic address created exactly one D1 record. That test
record was removed afterward.
