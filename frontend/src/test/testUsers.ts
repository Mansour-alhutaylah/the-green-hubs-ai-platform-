import { Role } from '@/features/rbac/roles';
import { MOCK_ORGANIZATIONS } from '@/features/organizations/mockOrgs';
import type { AuthUser } from '@/features/auth/types';

/**
 * Test-only user fixtures, one per role tier, so RBAC-dependent rendering
 * can be exercised without a real session.
 *
 * This lives under `src/test/` deliberately: it is not shipped, not
 * importable from a page, and carries **no password** — the application no
 * longer has a credential-checking mock to hold one. Identities are
 * obviously synthetic.
 */
const ALL_ORG_IDS = MOCK_ORGANIZATIONS.map((org) => org.id);

export const TEST_USERS: AuthUser[] = [
  {
    id: 'test-user-owner',
    name: 'Demo Owner',
    email: 'demo.owner@preview.invalid',
    role: Role.Owner,
    orgIds: ALL_ORG_IDS,
  },
  {
    id: 'test-user-admin',
    name: 'Demo Administrator',
    email: 'demo.administrator@preview.invalid',
    role: Role.Admin,
    orgIds: ALL_ORG_IDS,
  },
  {
    id: 'test-user-approver',
    name: 'Reviewer A',
    email: 'reviewer.a@preview.invalid',
    role: Role.Approver,
    orgIds: [ALL_ORG_IDS[0]!],
  },
  {
    id: 'test-user-editor',
    name: 'Editor A',
    email: 'editor.a@preview.invalid',
    role: Role.Editor,
    orgIds: [ALL_ORG_IDS[0]!],
  },
  {
    id: 'test-user-viewer',
    name: 'Viewer A',
    email: 'viewer.a@preview.invalid',
    role: Role.Viewer,
    orgIds: [ALL_ORG_IDS[0]!],
  },
];

export function testUserByRole(role: Role): AuthUser {
  const user = TEST_USERS.find((candidate) => candidate.role === role);
  if (!user) throw new Error(`No test user seeded for role ${role}`);
  return user;
}
