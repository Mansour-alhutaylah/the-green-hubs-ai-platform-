import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthService } from './services/AuthService';
import { resolvedAuthService } from './services/resolvedAuthService';
import type { AuthStatus, Session } from './types';
import { AuthContext, type AuthContextValue } from './context';
import { isDevAuthBypassEnabled } from './devAuthBypass';
import { onUnauthorizedResponse } from '@/lib/api/sessionEvents';

/** Injected so tests can seed a session without going through the mock
 * service's localStorage side effects. Production (`AppProviders.tsx`,
 * no override) uses `resolvedAuthService` — demo-aware and live-aware at
 * once, see its own docstring. */
export function AuthProvider({
  children,
  service = resolvedAuthService,
}: {
  children: ReactNode;
  service?: AuthService;
}) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [session, setSession] = useState<Session | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;

    async function bootstrap() {
      // A microtask hop so `status: 'loading'` is genuinely observable for
      // a tick (ProtectedRoute renders a LoadingDiamond during it) rather
      // than synchronously resolving before first paint, for every
      // restoration path below (sync demo lookup included).
      await Promise.resolve();
      if (cancelled) return;

      const demoSession = service.getSession();
      if (demoSession) {
        setSession(demoSession);
        setStatus('authenticated');
        return;
      }

      if (service.restoreSession) {
        try {
          const restored = await service.restoreSession();
          if (cancelled) return;
          setSession(restored);
          setStatus(restored ? 'authenticated' : 'unauthenticated');
        } catch {
          if (!cancelled) {
            setSession(null);
            setStatus('unauthenticated');
          }
        }
      } else if (!cancelled) {
        setStatus('unauthenticated');
      }

      if (service.subscribe && !cancelled) {
        unsubscribe = service.subscribe((next) => {
          if (cancelled) return;
          setSession(next);
          setStatus(next ? 'authenticated' : 'unauthenticated');
        });
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, [service]);

  // A live session an authenticated API call just discovered is invalid
  // (401 while we believed it was current) — never fired by an explicit
  // logout, which clears state through `logout()` below instead.
  useEffect(
    () =>
      onUnauthorizedResponse(() => {
        setSession(null);
        setStatus((prev) => (prev === 'authenticated' ? 'unauthenticated' : prev));
        setSessionExpired(true);
      }),
    [],
  );

  const requestLogin = useCallback(
    async (email: string, password: string) => {
      const result = await service.requestLogin(email, password);
      if (result.kind === 'authenticated') {
        setSession(result.session);
        setStatus('authenticated');
        setSessionExpired(false);
      }
      return result;
    },
    [service],
  );

  const verifyOtp = useCallback(
    async (challengeId: string, code: string) => {
      const nextSession = await service.verifyOtp(challengeId, code);
      setSession(nextSession);
      setStatus('authenticated');
      setSessionExpired(false);
    },
    [service],
  );

  const resendOtp = useCallback((challengeId: string) => service.resendOtp(challengeId), [service]);

  const enterDemoWorkspace = useMemo(() => {
    if (!isDevAuthBypassEnabled() || !service.enterDemoWorkspace) return null;
    return async () => {
      if (!isDevAuthBypassEnabled() || !service.enterDemoWorkspace) {
        throw new Error('Development authentication bypass is disabled.');
      }
      const nextSession = await service.enterDemoWorkspace();
      setSession(nextSession);
      setStatus('authenticated');
      setSessionExpired(false);
    };
  }, [service]);

  const logout = useCallback(async () => {
    await service.logout();
    setSession(null);
    setStatus('unauthenticated');
    setSessionExpired(false);
  }, [service]);

  const setActiveOrg = useCallback(
    (orgId: string) => {
      const updated = service.setActiveOrg(orgId);
      if (updated) setSession(updated);
    },
    [service],
  );

  const checkDevOtpCode = useCallback(
    (code: string) => service.checkDevOtpCode?.(code) ?? false,
    [service],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session?.user ?? null,
      activeOrgId: session?.activeOrgId ?? null,
      sessionKind: session?.kind ?? null,
      requestLogin,
      verifyOtp,
      resendOtp,
      enterDemoWorkspace,
      logout,
      setActiveOrg,
      devOtpHint: service.getDevOtpHint?.() ?? null,
      checkDevOtpCode,
      sessionExpired,
    }),
    [
      status,
      session,
      requestLogin,
      verifyOtp,
      resendOtp,
      enterDemoWorkspace,
      logout,
      setActiveOrg,
      service,
      checkDevOtpCode,
      sessionExpired,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
