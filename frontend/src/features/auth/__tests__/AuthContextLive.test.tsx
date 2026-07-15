import { describe, expect, it, vi } from 'vitest';
import { act, screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { emitUnauthorizedResponse } from '@/lib/api/sessionEvents';
import { AppRoutes } from '@/app/router/routes';

function buildLiveSession(): Session {
  return {
    kind: 'live',
    user: { id: 'user-1', name: 'Reem Al-Harbi', email: 'reem@example.com', role: Role.Admin, orgIds: ['org-1'] },
    token: 'supabase-session',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId: 'org-1',
  };
}

function buildLiveOnlyService(overrides: Partial<AuthService> = {}): AuthService {
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('not used in this test');
    },
    async verifyOtp(): Promise<Session> {
      throw new Error('not used in this test');
    },
    async resendOtp(): Promise<void> {},
    async logout(): Promise<void> {},
    getSession: () => null,
    setActiveOrg: () => null,
    ...overrides,
  };
}

describe('AuthProvider — live session bootstrap and expiry', () => {
  it('restores a live session asynchronously via restoreSession (no synchronous demo session)', async () => {
    const service = buildLiveOnlyService({
      restoreSession: async () => buildLiveSession(),
    });

    renderWithProviders(<AppRoutes />, { initialEntries: ['/dashboard'], authService: service });

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
  });

  it('does not loop on loading when there is no session to restore', async () => {
    const service = buildLiveOnlyService({
      restoreSession: async () => null,
    });

    renderWithProviders(<AppRoutes />, { initialEntries: ['/dashboard'], authService: service });

    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeVisible();
  });

  it('routes through the existing session-expired page after an out-of-band 401, not a bare logout redirect', async () => {
    window.sessionStorage.setItem('ghp:dashboard-visited', '1');
    const service = buildLiveOnlyService({
      restoreSession: async () => buildLiveSession(),
    });

    renderWithProviders(<AppRoutes />, { initialEntries: ['/documents'], authService: service });

    expect(await screen.findByRole('heading', { name: /^documents$/i }, { timeout: 5000 })).toBeVisible();

    act(() => emitUnauthorizedResponse());

    expect(
      await screen.findByRole('heading', { name: /session expired/i }, { timeout: 5000 }),
    ).toBeVisible();
  });

  it('an explicit logout goes to the plain login page, not session-expired', async () => {
    const logout = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
    const service = buildLiveOnlyService({
      getSession: () => buildLiveSession(),
      logout,
    });

    renderWithProviders(<AppRoutes />, { initialEntries: ['/dashboard'], authService: service });
    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();

    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /reem al-harbi, account menu/i }));
    await user.click(await screen.findByRole('button', { name: /sign out/i }));

    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeVisible();
    expect(logout).toHaveBeenCalledTimes(1);
  });
});
