import { Role } from '@/features/rbac/roles';
import { DEMO_WORKSPACE_ORG_ID } from '@/features/organizations/mockOrgs';
import type { AuthUser } from '../types';

/**
 * The single synthetic identity a Preview build signs in as.
 *
 * There is deliberately no roster of accounts and **no password**. Preview
 * sign-in is a one-click entry into a local session; it accepts no
 * credentials, so there is nothing here that could be mistaken for a real
 * login, reused against a real environment, or leaked as a shared secret.
 *
 * The address uses the reserved `.invalid` TLD (RFC 2606): it is
 * unroutable by construction and cannot correspond to a real mailbox.
 */
export const PREVIEW_USER: AuthUser = {
  id: 'preview-user-administrator',
  name: 'Demo Administrator',
  email: 'demo.administrator@preview.invalid',
  // Admin (not Owner) so the Preview shell exercises the RBAC-gated routes
  // without implying an unrestricted account.
  role: Role.Admin,
  orgIds: [DEMO_WORKSPACE_ORG_ID],
};

export const PREVIEW_ORGANIZATION_ID = DEMO_WORKSPACE_ORG_ID;
