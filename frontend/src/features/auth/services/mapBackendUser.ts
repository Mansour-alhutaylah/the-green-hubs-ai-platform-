import { Role } from '@/features/rbac/roles';
import type { UserProfileResponse } from '@/lib/api/types';
import type { DemoUser } from '../types';

const KNOWN_ROLES: readonly Role[] = [Role.Viewer, Role.Editor, Role.Approver, Role.Admin, Role.Owner];

/** Backend `role` is a nullable, un-enumerated `str` column (see
 * backend/app/domain/entities/user.py) — this normalizes it to the
 * frontend's closed `Role` tier set. An unrecognized or missing role maps
 * to `Viewer`, the least-privileged tier, rather than guessing upward:
 * server-side authorization is still the real enforcement boundary, so
 * this only affects which nav items/routes render client-side. */
export function mapBackendRole(role: string | null): Role {
  const normalized = role?.trim().toLowerCase();
  const match = KNOWN_ROLES.find((candidate) => candidate === normalized);
  return match ?? Role.Viewer;
}

/** Maps the backend's `UserProfileResponse` to the shared `DemoUser` shape
 * every existing UI (ProfileMenu, RoleGuard, useHasMinTier, the dashboard
 * greeting) already reads — this is purely a display/authorization-UX
 * mapping, not a re-derivation of tenant scope: `organization_id` /
 * `orgIds` here is used for display only, never sent back to the backend
 * as an authority. */
export function mapBackendUser(profile: UserProfileResponse): DemoUser {
  return {
    id: profile.id,
    name: profile.full_name,
    email: profile.email,
    role: mapBackendRole(profile.role),
    orgIds: profile.organization_id ? [profile.organization_id] : [],
  };
}
