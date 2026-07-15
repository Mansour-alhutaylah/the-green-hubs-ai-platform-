import type { ReactElement, ReactNode } from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { AuthProvider } from '@/features/auth/AuthContext';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { DemoUser, Session } from '@/features/auth/types';
import { WorkspaceProvider } from '@/features/organizations/workspace/WorkspaceProvider';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { TooltipProvider, ToastProvider } from '@/design-system';

/** A no-real-login AuthService stub that just returns a pre-seeded session
 * — used by tests that want to render already-authenticated as a specific
 * demo user without driving the real login/OTP UI. */
function createSeededAuthService(session: Session | null): AuthService {
  let current = session;
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('not implemented in test stub');
    },
    async verifyOtp(): Promise<Session> {
      throw new Error('not implemented in test stub');
    },
    async resendOtp(): Promise<void> {},
    async logout(): Promise<void> {
      current = null;
    },
    getSession: () => current,
    setActiveOrg: (orgId: string) => {
      if (!current) return null;
      current = { ...current, activeOrgId: orgId };
      return current;
    },
  };
}

export function buildTestSession(user: DemoUser): Session {
  return {
    kind: 'demo',
    user,
    token: 'test-token',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId: user.orgIds[0] ?? '',
  };
}

export interface RenderWithProvidersOptions {
  initialEntries?: string[];
  /** Pre-seeded session — renders already-authenticated as this user. */
  session?: Session | null;
  /** Escape hatch for tests that need the real mockAuthService (e.g. the
   * login/OTP flow test) instead of the seeded stub. */
  authService?: AuthService;
}

export function renderWithProviders(ui: ReactElement, options: RenderWithProvidersOptions = {}) {
  const { initialEntries = ['/'], session, authService } = options;
  const service = authService ?? createSeededAuthService(session ?? null);

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
        <LocaleProvider>
          <AuthProvider service={service}>
            <WorkspaceProvider>
              <TooltipProvider>
                <ToastProvider>{children}</ToastProvider>
              </TooltipProvider>
            </WorkspaceProvider>
          </AuthProvider>
        </LocaleProvider>
      </MemoryRouter>
    );
  }

  return render(ui, { wrapper: Wrapper });
}
