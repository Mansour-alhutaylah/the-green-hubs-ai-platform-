/**
 * Single source of truth for the explicit development authentication bypass.
 * No session is created merely by importing this module or mounting the auth
 * provider. The flag must be enabled when the action is offered and invoked.
 *
 * Vite replaces `import.meta.env.DEV` with `false` in production builds, so
 * the bypass stays unavailable there even if the public flag is supplied.
 */
export function isDevAuthBypassEnabled(): boolean {
  return import.meta.env.DEV && import.meta.env.VITE_DEV_AUTH_BYPASS === 'true';
}
