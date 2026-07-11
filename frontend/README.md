# The Green Hubs — Frontend

Phase 1 foundation: project architecture, design system/tokens, app shell (Command Rail +
Context Bar), routing, mock authentication, and RBAC. No business modules yet — see
`../CLAUDE.md`/`backend/CLAUDE.md` for overall project scope and sprint discipline.

The UX Product Experience Specification (v1.0) is the source of truth for every visual and
behavioral decision below; section references (`§n`) point back to it.

## Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Demo accounts

The backend has no auth endpoints yet, so Phase 1 ships a **mock** `AuthService`
(`src/features/auth/services/mockAuthService.ts`) behind a clean interface — swapping in real
Supabase auth later is one new implementation of that interface, no UI changes. Five seeded
users, one per role tier (`src/features/auth/services/demoUsers.ts`):

| Email                      | Role     |
| -------------------------- | -------- |
| owner@demo.greenhubs.sa    | Owner    |
| admin@demo.greenhubs.sa    | Admin    |
| approver@demo.greenhubs.sa | Approver |
| editor@demo.greenhubs.sa   | Editor   |
| viewer@demo.greenhubs.sa   | Viewer   |

Shared password: `Demo1234!`. OTP step: enter any code equal to the dev-mode code shown on
screen (`123456`) — there is no real SMS/email delivery yet. That hint (and the invite-accept
flow's fallback OTP check) reach the mock through two _optional_ `AuthService` interface members
(`getDevOtpHint`/`checkDevOtpCode`) rather than importing `mockAuthService` directly — a real
implementation simply omits them and the hint disappears with no UI change.

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
  app/            routing (route tree, guards) + navConfig (single source of truth for the
                  rail's items, RBAC nav-filtering, AND each gated route's minimum role
                  tier — Appendix A)
  design-system/  token-driven primitives (Button, Input, Dialog, Toast, PopoverMenu,
                  EmptyState, LoadingDiamond, the diamond status-glyph set, …)
  shell/          AppShell (Suspense + per-route RouteErrorBoundary around the Outlet),
                  Command Rail, Context Bar, Mobile Drawer, SkipLink, PageViewport/PageHeader
  features/
    auth/         mock AuthService, AuthContext, Login/OTP/Forgot/Reset/Invite pages
    rbac/         role model (Owner ⊃ Admin ⊃ Approver ⊃ Editor ⊃ Viewer) + gating hooks
    <module>/     one stub page per MVP route (dashboard, documents, analysis, reports,
                  organizations, users, settings, notifications, profile) — routing/layout/
                  RBAC proof, not business logic; every one is `React.lazy`-loaded and code-split
    placeholders/ the real §11.8 placeholder-module pattern for Hub Zero, Carbon, Telemetry,
                  Frameworks, Audit (Phase 2/3 modules) — also lazy-loaded
  lib/            i18n (English/Arabic + RTL), motion (`prefers-reduced-motion`), small utils
  styles/         tokens.css (§16, the literal source of truth — "tokens are law", §19) +
                  globals.css
```

All business-module and placeholder pages are dynamically imported (`app/router/routes.tsx`) so
none of them bundle into the initial chunk; AppShell wraps the routed `<Outlet/>` in one shared
`<Suspense>` (loading state) and a per-pathname `RouteErrorBoundary` (a render error in one page
shows that page's own failure state, rail/context bar intact, instead of white-screening the app).

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

## Known Phase 1 simplifications

- The Kufic square-lattice brand motif (login panel, placeholder dashed zones) is approximated
  with a CSS crosshatch (`.lattice-pattern`/`.lattice-pattern-forest` in `globals.css`) — no brand
  SVG asset was supplied to implement it verbatim.
- First-run coachmarks (§9.1) render as one sequential card rather than three DOM-anchored
  popovers pointing at the org switcher / Insight Ledger / upload entry — the Insight Ledger
  doesn't exist as business content yet to anchor to.
- Forgot-password / reset / invite-accept are UI-only (no backing service calls) since the mock
  auth service's real wiring effort went into the primary Login → OTP → session flow.
