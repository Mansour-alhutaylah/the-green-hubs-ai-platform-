# The Green Hubs — Frontend

React/TypeScript client for the Green Hubs platform: design system and tokens, app shell
(Command Rail + Context Bar), routing and RBAC, real Supabase authentication, and the live
document upload/processing/analysis paths against the FastAPI backend. See
`../CLAUDE.md`/`backend/CLAUDE.md` for overall project scope and sprint discipline.

The UX Product Experience Specification (v1.0) is the source of truth for every visual and
behavioral decision below; section references (`§n`) point back to it.

## Setup

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Copy `.env.example` to `.env.local` and fill in the values you
need — Live mode needs the API and Supabase variables, Preview mode needs none of them.

## Live and Preview

The app runs in one of two modes, decided **at build time** and nowhere else.

### Live (the default, and what Production always runs)

Live mode talks to the real services and shows only what they actually return.

- **Authentication** is Supabase email/password (`signInWithPassword`), followed by
  `GET /api/v1/auth/me` to resolve the backend profile. That is the entire sign-in flow:
  one step, no second factor. A Supabase session with no application profile is signed
  back out rather than left half-authenticated.
- **Accounts** are created by an administrator in the real environment. There are no
  built-in accounts, no shared password, and no credentials in this repository or in this
  document.
- **Tenant scope** is derived server-side from the bearer token. The frontend never sends
  an `organization_id` (enforced by `src/lib/api/__tests__/tenantScope.test.ts`).
- **Capabilities that do not exist on the backend yet say so.** The Dashboard is the
  clearest case: there is no dashboard-summary endpoint, so Live mode states that metrics
  are not connected instead of showing a number. Nothing is estimated, sampled, or filled
  in. Global search is likewise presented as unavailable rather than as a working control.

### Preview (an explicitly built, clearly labelled demonstration)

Preview mode renders deterministic synthetic fixtures so screens can be reviewed without any
infrastructure.

- **Activation requires two agreeing build-time variables**, `VITE_APP_MODE=preview` and
  `VITE_APP_ENVIRONMENT=preview`. Anything else — missing, blank, mis-cased, padded,
  truthy-looking, or inconsistent — resolves to Live. This is a fail-closed rule: a
  Production build cannot fall into Preview by omission or by one mistyped value.
- **Nothing at runtime can switch modes.** Query parameters, hash fragments, route
  parameters, `localStorage`, `sessionStorage`, cookies, request bodies, headers, user
  input, and the organization selector are all excluded by construction — the decision reads
  build-time configuration only (`src/lib/data/source.ts`).
- **Zero network boundary.** Preview makes no `fetch`, no Supabase call, and no
  `apiRequest`. Preview sign-in has no credential form at all: it mints a local synthetic
  session for one obviously fake identity ("Demo Administrator") and cannot fall through to
  real authentication.
- **Persistent disclosure.** A non-dismissible ribbon sits at the top of every protected
  screen in both languages, stating that the data and actions are demonstrations and that
  the build is not connected to Production. It is absent from Live mode.
- **Scenarios.** `VITE_PREVIEW_SCENARIO` selects which state the fixtures render:
  `populated` (default), `empty`, `loading`, `error`, `forbidden`, `partial`.

To run Preview locally, put these in `.env.local`:

```
VITE_APP_MODE=preview
VITE_APP_ENVIRONMENT=preview
```

**Hosted Preview is not configured yet.** Deploying one requires setting those two
non-secret variables (values exactly `preview`) on the Preview environment of the hosting
project — and only that environment. No such change has been made, so there is currently no
working hosted Preview URL. Production must keep `VITE_APP_MODE` unset (or anything other
than `preview`) and `VITE_APP_ENVIRONMENT=production`.

Preview fixtures are a review aid. They are **not** acceptance evidence: the MVP's Golden
Journey must be demonstrated against real integrated services, with no fixtures involved.

## Data layer

```
src/lib/data/
  contracts/   one normalized frontend domain model — branded ids, validated ISO instants,
               closed state unions. Never display strings: no "2 days ago", no "8.4 MB",
               no translated status labels stored as data.
  adapters/    the explicit mapping boundary between backend wire schemas and that model.
               Live responses and Preview fixtures converge here, so a fixture that drifts
               from the wire contract fails to compile.
  fixtures/    deterministic Preview data. No Math.random(), no Date.now(), synthetic
               identities only.
  scenarios/   populated | empty | loading | error | forbidden | partial
  source.ts    the fail-closed Live/Preview selection described above
  hooks/       what pages consume; live/ and preview/ never mix
```

The Dashboard is the first (and, in this phase, only) migrated consumer. Other feature pages
still read their own modules and will be migrated as their real integrations land.

## Not implemented yet

Stated here so nothing in the UI has to imply otherwise:

- **Multi-factor authentication / OTP.** Not implemented, not simulated, and not presented
  anywhere as active. Real MFA is a later dedicated security phase. The `OtpCells` visual
  primitive still exists but is unused by any flow.
- **Invitation acceptance.** The invite route explains that the flow is not connected and
  collects nothing.
- **Forgot / reset password.** UI-only; no backing service call yet.
- **Global search / Retrieval.** Presented as coming later; no search request is emitted.
- **Evidence Review and Retrieval integration.** Both exist on the backend and are the first
  real integration targets of the next frontend phase, along with the existing
  organizations/engagements endpoints and the document upload → processing → embedding →
  analysis paths. Preview may demonstrate their visual states with labelled synthetic
  fixtures; Live will use real endpoints or state that the capability is unavailable.
- **Public landing page.** Approved for the overall plan, deferred to its own later pull
  request.

## Scripts

- `npm run dev` — Vite dev server
- `npm run build` — type-check (`tsc -b`) then production build
- `npm run lint` / `npm run lint:fix` — oxlint
- `npm run format` / `npm run format:check` — Prettier
- `npm run typecheck` — `tsc -b --noEmit`
- `npm test` / `npm run test:watch` — Vitest + React Testing Library

## Architecture

```
src/
  app/            routing (route tree, guards, protected-route matcher, post-login return
                  path) + navConfig (single source of truth for the rail's items, RBAC
                  nav-filtering, AND each gated route's minimum role tier — Appendix A)
  design-system/  token-driven primitives (Button, Input, Dialog, Toast, PopoverMenu, Tabs,
                  Select, EmptyState, LoadingDiamond, the diamond status-glyph set, …)
  shell/          AppShell (Preview ribbon, Suspense + per-route RouteErrorBoundary around
                  the Outlet), Command Rail, Context Bar, Mobile Drawer, SkipLink,
                  PageViewport/PageHeader
  features/
    auth/         AuthContext + two never-overlapping services (live Supabase, local
                  Preview), Login/Forgot/Reset/Invite pages
    rbac/         role model (Owner ⊃ Admin ⊃ Approver ⊃ Editor ⊃ Viewer) + gating hooks
    <module>/     one page per MVP route (dashboard, documents, analysis, reports,
                  organizations, users, settings, notifications, profile); every one is
                  `React.lazy`-loaded and code-split
    placeholders/ the §11.8 placeholder-module pattern for Hub Zero, Carbon, Telemetry,
                  Frameworks, Audit
  lib/            data (contracts/adapters/fixtures/scenarios/hooks), api client and
                  endpoints, i18n (English/Arabic + RTL), motion, small utils
  styles/         tokens.css (§16, the literal source of truth — "tokens are law", §19) +
                  globals.css
```

All business-module and placeholder pages are dynamically imported (`app/router/routes.tsx`) so
none of them bundle into the initial chunk; AppShell wraps the routed `<Outlet/>` in one shared
`<Suspense>` (loading state) and a per-pathname `RouteErrorBoundary` (a render error in one page
shows that page's own failure state, rail/context bar intact, instead of white-screening the app).

## Routing behavior

- An authenticated deep link renders the route that was requested. It is no longer redirected
  to /dashboard first.
- An unauthenticated deep link to a real protected route goes to sign-in and returns to the
  requested route afterwards. The stored destination is validated (same-document absolute
  path, known protected route) before it is used, so it cannot become an open redirect — and
  it grants nothing: the destination still renders behind `ProtectedRoute`/`RoleGuard`.
- An unknown URL gets a 404, signed in or out. Previously every unknown public URL rendered
  the login screen, which implied the page existed.
- Frontend routing is not authorization. The backend remains the enforcement boundary.

## Design tokens

`src/styles/tokens.css` implements §16 as a Tailwind v4 `@theme` block: declaring a color there
both defines the real CSS custom property (`--color-forest-900`) and generates the matching
utility (`bg-forest-900`). No component should hard-code a raw color/radius/size/duration —
add a token instead.

Only these spacing utility keys are in use, matching §16's steps exactly (Tailwind's default
0.25rem base already lines up): `p-1/2/3/4/5/6/8/10/12/16` → 4/8/12/16/20/24/32/40/48/64px.

**Breakpoint alignment**: the spec's two breakpoints (768px, 1280px) happen to equal Tailwind's
built-in `md` and `xl` breakpoints — use `md:`/`xl:` for tablet/desktop overrides, not `sm:`/`lg:`.

Fonts ship as the spec's own documented fallback pair (Manrope / IBM Plex Sans Arabic) via
self-hosted `@fontsource` packages — swapping in the licensed Aeonik/Bahij TheSansArabic later is
a one-line change to `--font-latin`/`--font-arabic` in `tokens.css`.

Two colors deviate slightly from their literal §16/§3.1 hex/opacity values: `--color-gray-600`
and `--color-rail-muted` measured under WCAG AA (4.47:1 and ~4.05:1 via axe-core) against
backgrounds they're actually used on (`paper-50`, `tint-100`, the active rail-item state) — both
nudged darker/more-opaque to clear 4.5:1, since §17 commits the whole product to AA. See the
comments in `tokens.css` for the exact numbers.

## Known simplifications

- The Kufic square-lattice brand motif (login panel, placeholder dashed zones) is approximated
  with a CSS crosshatch (`.lattice-pattern`/`.lattice-pattern-forest` in `globals.css`) — no brand
  SVG asset was supplied to implement it verbatim.
- First-run coachmarks (§9.1) render as one sequential card rather than three DOM-anchored
  popovers pointing at the org switcher / Insight Ledger / upload entry — the Insight Ledger
  doesn't exist as business content yet to anchor to.
- Preview fixtures outside the Dashboard (`mockOrgs`, `mockDocuments`, `mockAnalysisData`)
  still carry realistic-sounding company and personal names from an earlier phase. They are
  Preview-only and will be replaced with obviously synthetic identities as each page is
  migrated to the typed data layer.
