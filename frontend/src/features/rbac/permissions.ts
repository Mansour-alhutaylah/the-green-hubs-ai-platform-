/**
 * The frontend mirror of the backend's centralized permission policy
 * (`backend/app/domain/security/permissions.py`).
 *
 * **This is not the security boundary.** The backend re-derives the
 * caller's role from the database on every request and refuses an
 * unauthorized command with 403 regardless of what the browser believes.
 * What this module decides is only whether a control is *offered*: a
 * reviewer who cannot act should be told so plainly, not handed a button
 * that fails. Hiding a control the server would refuse is user experience;
 * refusing the command is enforcement, and it happens server-side.
 *
 * It exists as a policy table rather than as scattered role comparisons
 * for the same reason the backend's does: `role === 'approver' || ...`
 * repeated across components is a policy nobody can read in one place and
 * that drifts the moment one site is missed. Components ask
 * `hasPermission(role, Permission.EvidenceReview)` and never name a role.
 *
 * The role → permission mapping below is a deliberate, checked copy of the
 * backend's. `backend/tests/domain/security/test_permissions.py` reads
 * this file and fails if the two ever disagree about who may review
 * evidence, so a change on one side cannot silently outlive the other.
 *
 * A const object rather than a TypeScript `enum`, matching `roles.ts`:
 * the project's tsconfig sets `erasableSyntaxOnly`, which forbids `enum`.
 */
import { Role } from './roles';

export const Permission = {
  /** Decide a document's evidence status: verify, reject, restrict or
   * supersede. **M-4** records this as an *approval* authority rather than
   * a write authority — see `EVIDENCE_REVIEW_ROLES` below. */
  EvidenceReview: 'evidence.review',
} as const;

export type Permission = (typeof Permission)[keyof typeof Permission];

/**
 * The recorded **M-4** evidence-review matrix:
 *
 * | role     | evidence review |
 * |----------|-----------------|
 * | viewer   | denied          |
 * | editor   | denied          |
 * | approver | allowed         |
 * | admin    | allowed         |
 * | owner    | allowed         |
 *
 * The editor exclusion is the substance of the decision, not an oversight:
 * producing evidence and approving it are separate duties, and an editor
 * who could approve their own upload would make the review step
 * decorative. An editor keeps every unrelated authority — upload,
 * processing, analysis, engagement management — which is why this is a
 * permission table and not a tier comparison. `meetsMinTier` would give
 * the same answer today by coincidence of ordering; it would give the
 * wrong answer the moment a permission is not tier-shaped.
 */
const EVIDENCE_REVIEW_ROLES: readonly Role[] = [Role.Approver, Role.Admin, Role.Owner];

const ROLE_PERMISSIONS: Readonly<Record<Role, readonly Permission[]>> = {
  [Role.Viewer]: [],
  [Role.Editor]: [],
  [Role.Approver]: [Permission.EvidenceReview],
  [Role.Admin]: [Permission.EvidenceReview],
  [Role.Owner]: [Permission.EvidenceReview],
};

/**
 * Whether `role` may exercise `permission`. Deny by default.
 *
 * Fails closed on every uncertain input, mirroring the backend's
 * `has_permission`: a missing role (no session yet), and any value outside
 * the closed `Role` set, both hold no permissions. That matters because
 * `mapBackendRole` already collapses an unrecognized backend role to
 * `Viewer`, so an unknown role reaches here as the least-privileged tier
 * — but a caller passing `undefined` directly must be denied too, rather
 * than reading a permission list off an absent key.
 */
export function hasPermission(role: Role | null | undefined, permission: Permission): boolean {
  if (role == null) return false;
  const granted = ROLE_PERMISSIONS[role];
  if (granted === undefined) return false;
  return granted.includes(permission);
}

/** The roles that hold evidence-review authority, for the parity guard and
 * for tests that must follow the policy rather than restate it. */
export function evidenceReviewRoles(): readonly Role[] {
  return EVIDENCE_REVIEW_ROLES;
}
