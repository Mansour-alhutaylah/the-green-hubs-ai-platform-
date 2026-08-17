import type { Role } from '@/features/rbac/roles';
import type { OrganizationId, UserId } from './ids';

/**
 * Normalized Frontend view of a person in the workspace.
 *
 * There is **no organization-wide user endpoint on the backend today** —
 * `app/domain/security/permissions.py` states it outright ("There is no
 * `user.manage` permission because no user-management route exists yet").
 * The only real identity the product can obtain is the caller's own, from
 * `GET /api/v1/auth/me`.
 *
 * So this contract is honest about provenance: `source` records whether a
 * member came from a real authenticated response or from Preview
 * fixtures, and the Live team page renders exactly one member — the signed-in
 * user — rather than implying a directory it cannot fetch.
 *
 * `role` is nullable because `users.role` is a free-form nullable column;
 * an unrecognized value normalizes to `null`, which the UI renders as an
 * explicit "unrecognized role" rather than guessing a tier.
 */
export type TeamMemberSource = 'authenticated-user' | 'preview-fixture';

export interface TeamMember {
  readonly id: UserId;
  readonly fullName: string;
  readonly email: string;
  readonly role: Role | null;
  readonly organizationId: OrganizationId | null;
  readonly source: TeamMemberSource;
  /** True for the row representing the currently signed-in account. */
  readonly isCurrentUser: boolean;
}

export interface TeamDirectory {
  readonly members: readonly TeamMember[];
  /** `false` whenever the list is only the caller — i.e. always, in Live,
   * until a real team endpoint exists. Drives the disclosure copy so the
   * page never implies it is showing everyone. */
  readonly isCompleteDirectory: boolean;
}
