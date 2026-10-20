# Atria Redesign - awwwards skill workflow

## Brief
Subject: Atria - AI-powered emergency department waiting room monitoring and reassessment system
Audience: Emergency department clinical staff (nurses, physicians, healthcare administrators)
Site job:
1. Landing page: Communicate Atria's value proposition, explain continuous monitoring workflow, drive early-access sign-ups
2. Application: Provide an intuitive, high-information-density ED operations console that helps clinicians quickly identify patients who need reassessment
Language: English (US)
Constraints: Must preserve existing backend APIs, use Next.js/Tailwind stack where practical, focus on clinical usability over marketing flair

Explicit assumptions (placeholder content):
- Atria uses Tiger Data for longitudinal patient history
- Atria provides explanations from evidence (likely using Gemini or similar)
- The system flags meaningful changes in patient condition since check-in
- Nurses set priority; Atria only flags changes for human review
- Realistic demo data is available in the repository
- The system integrates with existing ED workflows and systems

## Concept Card
Idea:        Atria functions like the heart's atria - receiving and continuously monitoring patient data streams to detect meaningful changes that require clinical attention
Metaphor:    The site borrows from cardiovascular physiology - specifically how atria receive blood and monitor flow conditions
Signature:   The continuous flow visualization where patient data streams enter monitoring channels and abnormal patterns trigger subtle but clear alerts
Emotion:     Calm vigilance - the feeling of monitoring a vital sign where small changes matter but panic is never productive
Motion verb: Pulse and flow - subtle, rhythmic movements like blood flow that convey continuous monitoring without distraction
Screenshot:  A central visualization showing patient data (vitals, symptoms) flowing into the system, with one stream highlighted to show detected change
Anchor:      The name "Atria" comes from anatomy (heart chambers), making this concept specific to this brand and impossible to move to another

## Art Direction System
**Palette:**
- Ground: #f8fafc (slate-50) - background, clean clinical feel
- Ink: #1e293b (slate-800) - primary text, excellent readability
- Muted: #64748b (slate-500) - secondary text, good contrast on ground
- Line: #e2e8f0 (slate-200) - borders/dividers, subtle but visible
- Accent: #0ea5e9 (sky-500) - highlights changes and important data, clinical blue
- Curtain: #0f172a (slate-900) - overlays/focused areas

**Type:**
- Display: Switzer (Fontshare: switzer) - neo-grotesk, neutral Swiss, closest free to Neue Montreal/Suisse
- Text: Switzer (Fontshare: switzer) - same family, different weights for hierarchy
- Reasoning: Single family ensures consistency and readability; Switzer's neutral Swiss character fits clinical precision without coldness

**Grid & rhythm:**
- 12 columns with fluid gutter (--gutter: 1rem)
- Vertical rhythm: tight (8px), normal (16px), airy (24px), full viewport - assigned deliberately per section
- Outer margin = gutter; four-corner frame (name, nav, context, action) maintained
- Text blocks start on strong vertical lines (columns 2, 6, 10) for visible logic

**Shape:**
- Radius: 4px for interactive elements (buttons, inputs, cards)
- Radius: 0px for layout/dividers - clean clinical lines where separation is functional

**Motion language:**
- Ease: soft (power3.out) for all interactions - gentle, natural movement
- Duration:
  - Hover / press feedback: 0.3s
  - Text line reveal: 1.2s, stagger 0.08s
  - Image reveal / clip: 1.4s
  - Curtain / page transition: 0.9s each way
  - Loader total: 1.5s (real progress tracking)
- Motion verb: "Pulse and flow" implemented as:
  - Primary targets: subtle fill from pointer's side on hover/press
  - Continuous idle state: slow ±2% scale pulse (1.5s cycle) on concept-carrying elements
  - Transitions: overlap outgoing/incoming pages by 0.2s for continuity
  - Data updates: gentle pulse on changed values (0.8s soft ease)

**Composition plan (by page type):**
- Landing:
  * Hero: Statement (name + value proposition) over flowing data visualization
  * How it works: Index list with cursor-following preview (desktop) / inline thumbnails (touch)
  * Our story: Asymmetric pair - narrative text with schematic workflow visualization
  * Early access: Poster - bold statement + form
  * Footer: Finale - giant name + real links + local time
- Application:
  * Dashboard: Sticky narrative - patient queue as main story, controls as side chapters
  * Patient detail: Statement + Data/facts - vital trends + timeline
  * Alerts/reassessment: Asymmetric pair - evidence visualization + clinical actions

**Explainer figure (optional):**
Yes - the concept benefits from showing how Atria detects meaningful changes. Sequence:
Patient checks in → Initial vitals recorded → Continuous monitoring (5-min intervals) →
New reading compared to baseline → Significant change detected (multi-vital trend) →
Alert triggered with evidence → Nurse reviews recommended reassessment
If anatomy skill available: build as isometric figure showing data flow through monitoring stages
If not: build as timed sequence visualization with patient data streams

**Genericness test - Changes made to avoid AI/default outputs:**
Changed from generic model likely output:
- Purple/blue gradients → Slate palette with deliberate blue accent (#0ea5e9)
- Glassmorphism everywhere → Zero glassmorphism, clean lines and subtle shadows only
- Three equal feature cards → Purposeful layout families (statement, index list, asymmetric pair)
- Excessive rounded rectangles → 4px radius only on interactive elements, 0px on layout/dividers
- Floating decorative blobs → Motion serves concept (data pulse/flow), no decoration
- Purple SaaS styling → Clinical slate palette, professional not "techy"
- Generic metric cards with fake numbers → Real data visualization, specific clinical units
- Stock healthcare imagery → Anatomy-inspired metaphor (atria/heart monitoring) and data flow visuals
- Acid-green on black → No neon colors, slate-based accent for trustworthiness
- Centered hero over gradient blob → Statement hero over purposeful data visualization
- Eyebrow label above every heading -> Reserved for specific section introductions only
- Decorative 01/02/03 sequencing → Only used where actual sequence/process is being shown
- Scroll-jacking → Native scroll with purposeful motion enhancements
- Horizontal-scroll gallery as only idea → Varied layout families, galleries only when showing real sequences

## Landing release implementation and QA

The deployed landing release uses the clinical slate palette, Switzer, 4px
controls, a statement hero, a patient-to-review flow diagram, an indexed workflow,
an asymmetric story, and a signup section. The flow is a conceptual SVG figure,
explicitly labeled as illustrative. It is not a screenshot or a claim of live
sensor integration, fixed measurement intervals, or integration with hospital systems.

One GSAP ticker advances the diagram's dots and pulse. It pauses offscreen and in
hidden tabs; reduced motion removes the ticker. Native scrolling and visible
server-rendered content are deliberate usability decisions. A blocking loader,
custom cursor, and full-page transition were removed because they delayed or
obscured a small product landing page. Buttons and navigation retain hover,
press, and focus feedback. No WebGL is needed to communicate this workflow.

Switzer is fetched directly from Fontshare at build time for the site's own use;
font binaries are not redistributed through the source repository. The waitlist
is a separate Cloudflare D1 store with explicit consent and durable confirmation.

This release covers `landing/` only. The separate Next.js engine work in
`er-priority/frontend` remains local because its font paths, CSS imports, and
engine exports currently fail production compilation. Product-engine repair is
not required to publish this standalone landing page.

See `landing/REVIEW.md` for the browser checks and evidence-based release review.

The first independent review identified a low-contrast 404 recovery button,
small inline-link targets, weak hover feedback, and a rotated pulse symbol on
phones. These were corrected. The flow now includes the repository's synthetic
Bay 4 baseline/current values (HR 92 to 121, SpO2 98 to 91, pain 4 to 7). These
are illustrative demo readings, not outcomes or a real patient record.
