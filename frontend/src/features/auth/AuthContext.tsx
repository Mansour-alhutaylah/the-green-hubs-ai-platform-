import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthService } from './services/AuthService';
import { mockAuthService } from './services/mockAuthService';
import type { AuthStatus, Session } from './types';
import { AuthContext, type AuthContextValue } from './context';
import { getDevBypassSession } from './devAuthBypass';

/** Injected so tests can seed a session without going through the mock
 * service's localStorage side effects. */
export function AuthProvider({
  children,
  service = mockAuthService,
}: {
  children: ReactNode;
  service?: AuthService;
}) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    // A microtask hop so `status: 'loading'` is genuinely observable for a
    // tick (ProtectedRoute renders a LoadingDiamond during it) rather than
    // synchronously resolving before first paint.
    Promise.resolve().then(() => {
      const bypassSession = getDevBypassSession();
      const restored = bypassSession ?? service.getSession();
      setSession(restored);
      setStatus(restored ? 'authenticated' : 'unauthenticated');
    });
  }, [service]);

  const requestLogin = useCallback(
    (email: string, password: string) => service.requestLogin(email, password),
    [service],
  );

  const verifyOtp = useCallback(
    async (challengeId: string, code: string) => {
      const nextSession = await service.verifyOtp(challengeId, code);
      setSession(nextSession);
      setStatus('authenticated');
    },
    [service],
  );

  const resendOtp = useCallback((challengeId: string) => service.resendOtp(challengeId), [service]);

  const logout = useCallback(async () => {
    await service.logout();
    setSession(null);
    setStatus('unauthenticated');
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
      requestLogin,
      verifyOtp,
      resendOtp,
      logout,
      setActiveOrg,
      devOtpHint: service.getDevOtpHint?.() ?? null,
      checkDevOtpCode,
    }),
    [
      status,
      session,
      requestLogin,
      verifyOtp,
      resendOtp,
      logout,
      setActiveOrg,
      service,
      checkDevOtpCode,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
