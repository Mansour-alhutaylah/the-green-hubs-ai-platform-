import { Role } from '@/features/rbac/roles';
import { MOCK_ORGANIZATIONS } from '@/features/organizations/mockOrgs';
import type { DemoUser } from '../types';

const ALL_ORG_IDS = MOCK_ORGANIZATIONS.map((org) => org.id);

/**
 * Seeded demo users, one per role tier, so RBAC can be exercised end to end
 * without a real backend. Shared demo password documented in README.md.
 * The real Supabase-backed AuthService that replaces mockAuthService later
 * will look these up server-side instead — this list is Phase 1 fixture
 * data only, not a security boundary.
 */
export const DEMO_PASSWORD = 'Demo1234!';

export const DEMO_USERS: DemoUser[] = [
  {
    id: 'user-owner',
    name: 'Adel Al-Qahtani',
    email: 'owner@demo.greenhubs.sa',
    role: Role.Owner,
    orgIds: ALL_ORG_IDS,
  },
  {
    id: 'user-admin',
    name: 'Mansour Ali Al-Hutaylah',
    email: 'admin@demo.greenhubs.sa',
    role: Role.Admin,
    orgIds: ALL_ORG_IDS,
  },
  {
    id: 'user-approver',
    name: 'Reem Al-Harbi',
    email: 'approver@demo.greenhubs.sa',
    role: Role.Approver,
    orgIds: [ALL_ORG_IDS[0]!],
  },
  {
    id: 'user-editor',
    name: 'Faisal Al-Dossary',
    email: 'editor@demo.greenhubs.sa',
    role: Role.Editor,
    orgIds: [ALL_ORG_IDS[0]!],
  },
  {
    id: 'user-viewer',
    name: 'Noura Al-Zahrani',
    email: 'viewer@demo.greenhubs.sa',
    role: Role.Viewer,
    orgIds: [ALL_ORG_IDS[0]!],
  },
];

export function findDemoUserByEmail(email: string): DemoUser | undefined {
  const normalized = email.trim().toLowerCase();
  return DEMO_USERS.find((user) => user.email.toLowerCase() === normalized);
}
