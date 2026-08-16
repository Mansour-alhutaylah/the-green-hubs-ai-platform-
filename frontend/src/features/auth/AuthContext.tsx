import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthService } from './services/AuthService';
import { resolvedAuthService } from './services/resolvedAuthService';
import type { AuthStatus, Session } from './types';
import { AuthContext, type AuthContextValue } from './context';
import { onUnauthorizedResponse } from '@/lib/api/sessionEvents';

/** Injected so tests can seed a session without going through a real
 * service's storage side effects. The app (`AppProviders.tsx`, no override)
 * uses `resolvedAuthService`, which is the live service in a Live build and
 * the Preview service in a Preview build — never both. */
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

      const synchronousSession = service.getSession();
      if (synchronousSession) {
        setSession(synchronousSession);
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
      setSession(result.session);
      setStatus('authenticated');
      setSessionExpired(false);
      return result;
    },
    [service],
  );

  // Present only when the active service implements it — i.e. only in a
  // Preview build. In a Live build `resolvedAuthService` is the Supabase
  // service, which has no such method, so this stays `null` and the entry
  // point never renders.
  const enterPreviewWorkspace = useMemo(() => {
    const enter = service.enterPreviewWorkspace?.bind(service);
    if (!enter) return null;
    return async () => {
      const nextSession = await enter();
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

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session?.user ?? null,
      activeOrgId: session?.activeOrgId ?? null,
      sessionKind: session?.kind ?? null,
      requestLogin,
      enterPreviewWorkspace,
      logout,
      setActiveOrg,
      sessionExpired,
    }),
    [
      status,
      session,
      requestLogin,
      enterPreviewWorkspace,
      logout,
      setActiveOrg,
      sessionExpired,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
