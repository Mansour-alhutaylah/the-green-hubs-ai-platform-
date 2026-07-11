import { Role } from '@/features/rbac/roles';
import { DEMO_USERS } from './services/demoUsers';
import { writePersistedSession } from './services/sessionStorage';
import type { Session } from './types';

/**
 * Development-only shortcut: when enabled, skips the credentials/OTP steps
 * entirely and signs the visitor in as the Admin demo account. This is the
 * single place `VITE_DEV_AUTH_BYPASS` is read — no UI component checks the
 * flag directly, so removing this module (or flipping the flag off) is the
 * only thing required to fully retire it.
 *
 * `import.meta.env.DEV` is statically `false` in a production build (Vite
 * replaces and dead-code-eliminates it at build time), so this stays
 * inert in production no matter what `VITE_DEV_AUTH_BYPASS` is set to.
 *
 * The `MODE !== 'test'` guard matters separately: Vitest also runs with
 * `DEV: true` (it's a dev-mode Vite instance), so without this a real
 * `.env.local` bypass flag would silently sign every test in as Admin —
 * defeating tests that specifically construct an unauthenticated or
 * different-role session. Vitest's default mode is `'test'` unless a
 * suite overrides it, so this only ever excludes the test runner.
 */
const BYPASS_ENABLED =
  import.meta.env.DEV &&
  import.meta.env.MODE !== 'test' &&
  import.meta.env.VITE_DEV_AUTH_BYPASS === 'true';

const BYPASS_SESSION_TTL_MS = 12 * 60 * 60 * 1000;

function buildBypassSession(): Session {
  const adminUser = DEMO_USERS.find((user) => user.role === Role.Admin);
  if (!adminUser) {
    throw new Error('devAuthBypass: no Admin demo user is seeded in demoUsers.ts');
  }
  return {
    user: adminUser,
    token: 'dev-auth-bypass',
    expiresAt: Date.now() + BYPASS_SESSION_TTL_MS,
    activeOrgId: adminUser.orgIds[0] ?? '',
  };
}

/** Called once from AuthProvider's session-restore effect. Returns `null`
 * (a no-op) whenever the flag isn't both a dev build and explicitly
 * enabled — the normal session-restore path runs unchanged. */
export function getDevBypassSession(): Session | null {
  if (!BYPASS_ENABLED) return null;
  const session = buildBypassSession();
  writePersistedSession(session);
  return session;
}
