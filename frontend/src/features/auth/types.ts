import type { Role } from '@/features/rbac/roles';

export interface DemoUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  /** Organization ids this user belongs to — §0.5: a user may belong to several. */
  orgIds: string[];
}

export interface Session {
  user: DemoUser;
  token: string;
  /** Epoch millis. */
  expiresAt: number;
  /** Active organization for this session — the "ambient" org scope (§2.1). */
  activeOrgId: string;
}

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';
