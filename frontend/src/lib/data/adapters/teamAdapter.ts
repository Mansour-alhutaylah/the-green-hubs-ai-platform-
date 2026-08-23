import type { UserProfileResponse } from '@/lib/api/types';
import { Role } from '@/features/rbac/roles';
import { organizationId, userId } from '../contracts/ids';
import type { TeamMember } from '../contracts/team';

const KNOWN_ROLES: readonly Role[] = [
  Role.Viewer,
  Role.Editor,
  Role.Approver,
  Role.Admin,
  Role.Owner,
];

/**
 * Normalizes the backend's free-form nullable `users.role` column.
 *
 * Mirrors `resolve_trusted_role` in
 * `backend/app/domain/security/permissions.py`: trim, lowercase, and
 * require membership in the five-role enum. Anything else is `null` —
 * **not** a defaulted Viewer. The backend denies every permission for an
 * unrecognized role, and the UI must say "unrecognized", not quietly
 * present a tier the server does not actually grant.
 */
export function recognizeRole(raw: string | null): Role | null {
  if (typeof raw !== 'string') return null;
  const normalized = raw.trim().toLowerCase();
  return KNOWN_ROLES.find((role) => role === normalized) ?? null;
}

/** The caller's own profile, the only real identity any existing contract
 * exposes. Marked as `authenticated-user` so the page can state its
 * provenance rather than implying a directory lookup. */
export function toCurrentTeamMember(wire: UserProfileResponse): TeamMember {
  return {
    id: userId(wire.id),
    fullName: wire.full_name,
    email: wire.email,
    role: recognizeRole(wire.role),
    organizationId: wire.organization_id == null ? null : organizationId(wire.organization_id),
    source: 'authenticated-user',
    isCurrentUser: true,
  };
}
