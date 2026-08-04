# Phase 1 MVP Slice 2 Server-Side Authorization Design

Evidence IDs: **EV-SEC-01**, **EV-ARC-AUTHZ-01**

Date: 2026-08-04 (Asia/Riyadh)

Branch: `feat/mvp-server-side-authorization`

Starting commit: `e45be9eacc9338152843de698268ed15daf0d8a7`

Backlog reference: `Phase1_Recommended_Backlog.md` Epic A (FND-SEC-01), stories
A-1, A-2 and A-3.

## Scope

Slice 2 gives the FastAPI backend its own authorization decision. It adds no
product feature, page, route, endpoint, table, migration or dependency, and it
changes no retrieval, embedding, parsing, prompt or audit behaviour.

It does **not** complete tenant isolation, evidence lifecycle, human approval,
audit or prompt-injection protection. Those remain later slices.

## Security finding addressed

Phase 0 audit **BLOCKER-2 (CRITICAL)**, recorded in
`01-baseline/SIP_Phase0_Baseline_Audit.md`:

> `users.role` is read in exactly one place in the entire backend —
> `backend/app/api/v1/auth.py:31` — where it is echoed back to the client. The
> five-tier model lives entirely in `frontend/src/features/rbac/roles.ts`, whose
> own comment states *"Server re-validates everything; this is a UX layer only."*
> **The server does not.**

The recorded concrete failure was that a `viewer` who is denied the Upload
control by `RoleGuard` could still call `POST /api/v1/documents` directly with a
valid token and succeed, and that the same held for process, embeddings, analyze
and engagement create/update. Every authenticated organization member therefore
held effective Owner-level API access.

## Trusted sources verified before design

| Concern | Authoritative source | Verified at |
|---|---|---|
| Identity | Supabase ES256 JWT `sub`, verified server-side | `app/infrastructure/security/supabase_jwt.py`; `deps.get_current_auth_identity` |
| Profile | `public.users` row loaded by that id; absence raises `ProfileNotProvisionedError` | `deps.get_current_user` |
| Organization | `users.organization_id` on the loaded profile | `app/domain/entities/user.py` |
| Role | `users.role` on the loaded profile | `app/infrastructure/db/models/user.py:30` |

No client-supplied value participates in any of the four. `RequestContext` is
enriched from the resolved profile only, and its own docstring already states it
is "never an authorization input".

### Role source characteristics

`users.role` is `VARCHAR(50) NULL` with **no** enum, check constraint or foreign
key (`migrations/versions/12c7b2051fc6_...py:43`). It is therefore a trusted
*location* but an unconstrained *vocabulary*, so the policy must decide which
stored strings are recognized and refuse everything else.

### Conflict assessment

Only one role vocabulary is defined anywhere in the repository:
`frontend/src/features/rbac/roles.ts` — `viewer`, `editor`, `approver`, `admin`,
`owner`, attributed by its own comment to spec §4 / Appendix A.

The string `"member"` appears in `tests/api/test_correlation_id.py`, but that
test builds its own isolated FastAPI application with a fake user repository and
never mounts the product routers. It is an arbitrary fixture value, **not** a
competing server-side role model. No conflicting role model exists.

## Governance position on M-4 — read before extending this policy

Management decision **M-4** ("What is the authoritative role model — are the five
UI tiers correct? — and who holds which approval authority") is recorded as
**OPEN** in the Phase 0 audit, and backlog risk **R-1** warns:

> *"M-4 does not arrive, and engineering invents a role model. Highest-probability
> failure mode — it would embed an unapproved authority model into the system's
> foundation."*

This slice was therefore scoped **deliberately narrow**, on explicit operator
direction, to avoid inventing authority:

1. The role **names** are taken verbatim from `roles.ts`. No new vocabulary is
   introduced.
2. The **split** encodes only what repository artefacts already state:
   - `viewer` is read-only — the exact bypass BLOCKER-2 recorded;
   - every other recognized role may write — backlog A-3 requires Viewer denial,
     and states nothing finer;
   - organization management is admin-class — `navConfig.ts` gates Settings and
     Users at `Role.Admin`.
3. The `editor` / `approver` / `admin` distinction is **not encoded**. `approver`
   currently equals `editor` because no approval route exists yet.

**M-4 remains required.** Ratifying it should be a single edit to
`ROLE_PERMISSIONS`, and `test_permissions.py` will fail if the backend enum ever
diverges from `roles.ts`.

## Module structure

| File | Role |
|---|---|
| `backend/app/domain/security/permissions.py` | `Permission`, `Role`, `ROLE_PERMISSIONS`, `resolve_trusted_role()`, `permissions_for_role()`, `has_permission()` |
| `backend/app/domain/security/__init__.py` | Public surface of the module |
| `backend/app/api/deps.py` | `require_permission()` — the FastAPI binding |

The policy module imports no FastAPI symbol, matching the repository's existing
Clean Architecture separation and keeping the catalog testable as a pure unit.
The location follows the backlog's own plan, which named `app/domain/security/`
for "new `Permission` / `Role` value objects and the permission map".

## Permission catalog

Only capabilities required by routes that exist today are catalogued.

| Permission | Justifying existing routes |
|---|---|
| `organization.manage` | `POST /organizations`, `PATCH /organizations/{id}` |
| `engagement.manage` | `POST /engagements`, `PATCH /engagements/{id}` |
| `document.upload` | `POST /documents` |
| `document.process` | `POST /documents/{id}/process`, `POST /documents/{id}/embeddings` |
| `analysis.run` | `POST /analysis/documents/{id}/analyze`, `POST /analysis/engagements/{id}/analyze` |

There is deliberately **no** `user.manage`, `membership.manage`, `evidence.*`,
`answer.approve` or `audit.*` permission, because no such route exists. Adding
one belongs to the slice that adds the route.

## Role policy

| Role | Permissions | Why |
|---|---|---|
| `viewer` | *(none)* | Read-only. Closes the recorded BLOCKER-2 bypass directly. |
| `editor` | `engagement.manage`, `document.upload`, `document.process`, `analysis.run` | `navConfig.ts` gates Upload at `Role.Editor`, so Editor is the lowest write tier. |
| `approver` | identical to `editor` | Above Editor in the UI tier order, so it cannot hold less. No approval route exists yet to distinguish it — deferred to M-4. |
| `admin` | editor set + `organization.manage` | `navConfig.ts` gates Settings and Users at `Role.Admin`. |
| `owner` | identical to `admin` | Highest tier; holds every catalogued permission. |

Deny-by-default is structural, not a fallback branch: a role's permissions come
from an explicit map entry, and anything absent grants nothing.

## Fail-closed behaviour

| Input | Outcome |
|---|---|
| `role` is `NULL` | Denied — `resolve_trusted_role` returns `None`, which holds no permission |
| `role` outside the enum (`"member"`, `"root"`, `""`) | Denied |
| `role` is not a string | Denied |
| Permission not in the catalog | Denied, even for `owner` |
| No authentication | 401 before any authorization runs |

`resolve_trusted_role` normalizes surrounding whitespace and letter case, because
the column is free-form; `"  Admin "` is the same stored intent as `"admin"`.

## Immutability

`ROLE_PERMISSIONS` is a `MappingProxyType` whose every value is a `frozenset`.
Neither the policy nor an individual permission set can be mutated after import,
whether by accident or by a compromised code path. Both properties are tested.

## RequestContext and logging

`require_permission` layers on `get_current_user`, so correlation-ID creation and
`RequestContext` enrichment keep their existing order and behaviour, and
`ContextVar` isolation is untouched. Denials log at WARNING with only the required
permission and the resolved role name; `correlation_id`, `user_id` and
`organization_id` are already attached to every record by the logging factory in
`app/core/logging.py`. No token, header, credential or request body is logged.

## Response behaviour

| Situation | Status | Envelope |
|---|---|---|
| Missing or invalid token | 401 | Existing `AuthenticationError`, including `WWW-Authenticate: Bearer` |
| Valid identity, missing permission | 403 | Existing `AuthorizationError` |

Both reuse the repository's established `AppError` handler, so CORS headers and
`X-Correlation-ID` are preserved exactly as before. The 403 body is
`{"detail": "You do not have permission to perform this action."}` — deliberately
generic, disclosing neither the required permission nor any role mapping.

## Deferred, explicitly

| Item | Slice |
|---|---|
| Repository and object-level tenant enforcement, cross-tenant enumeration | 3 — Repository-Level Tenant Hardening |
| Evidence lifecycle and verified-only retrieval | 4 |
| Page and passage citation preservation | 5 |
| Full prompt-injection defence for RAG | 6 |
| Human answer approval, and the permission that will gate it | 7 |
| Audit of authorization denials (backlog A-4) | 8 |
| Read-path permission binding | Follow-up, see risks |
| RLS defence-in-depth (backlog A-5) | Gated on M-11 |

Tenant isolation continues to rely on the existing service-layer checks, which
this slice did not move, alter or weaken.
