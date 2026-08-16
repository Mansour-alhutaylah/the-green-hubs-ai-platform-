import { act } from 'react';
import { beforeEach, describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRoutes } from '@/app/router/routes';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS, testUserByRole } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { emitUnauthorizedResponse } from '@/lib/api/sessionEvents';
import { en } from '@/lib/i18n/strings/en';
import { DEFAULT_POST_LOGIN_PATH, resolveReturnPath } from '../returnPath';

const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;

/** A service that starts signed out and authenticates on the first
 * credential submission — enough to drive the real login form. */
function createSignInService(session: Session): AuthService {
  let current: Session | null = null;
  return {
    async requestLogin(): Promise<LoginResult> {
      current = session;
      return { kind: 'authenticated', session };
    },
    async logout() {
      current = null;
    },
    getSession: () => current,
    setActiveOrg: () => current,
  };
}

describe('routing and deep links', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  it('renders an authenticated deep link instead of bouncing it to the dashboard', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/profile'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^profile$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(screen.queryByRole('heading', { name: /^dashboard$/i })).toBeNull();
  });

  it('sends an unauthenticated visitor on a protected deep link to sign in', async () => {
    renderWithProviders(<AppRoutes />, { initialEntries: ['/documents'], session: null });

    expect(await screen.findByText(en['auth.signin.title'])).toBeVisible();
  });

  it('returns to the originally requested route after signing in', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/profile'],
      authService: createSignInService(buildTestSession(admin)),
    });

    await screen.findByText(en['auth.signin.title']);
    await user.type(screen.getByLabelText(en['auth.signin.emailLabel']), 'someone@example.test');
    await user.type(screen.getByLabelText(en['auth.signin.passwordLabel']), 'irrelevant');
    await user.click(screen.getByRole('button', { name: en['auth.signin.submit'] }));

    expect(
      await screen.findByRole('heading', { name: /^profile$/i }, { timeout: 5000 }),
    ).toBeVisible();
  });

  it('answers an unknown public URL with a 404, not the sign-in screen', async () => {
    renderWithProviders(<AppRoutes />, { initialEntries: ['/no-such-page'], session: null });

    expect(await screen.findByText(en['errors.notFound.title'])).toBeVisible();
    expect(screen.queryByText(en['auth.signin.title'])).toBeNull();
  });

  it('answers an unknown authenticated URL with a 404 inside the shell', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/no-such-page'],
      session: buildTestSession(admin),
    });

    expect(await screen.findByText(en['errors.notFound.title'])).toBeVisible();
    expect(screen.getByTestId('context-bar')).toBeVisible();
  });

  it('keeps a route above the caller tier behind the access-denied state', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/users'],
      session: buildTestSession(testUserByRole(Role.Viewer)),
    });

    expect(await screen.findByText(en['errors.noAccess.title'])).toBeVisible();
    expect(screen.queryByRole('heading', { name: /users & roles/i })).toBeNull();
  });

  it('routes an out-of-band session loss to the session-expired page', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/documents'],
      session: buildTestSession(admin),
    });

    await screen.findByTestId('context-bar');
    act(() => {
      emitUnauthorizedResponse();
    });

    expect(await screen.findByText(en['auth.sessionExpired.heading'])).toBeVisible();
  });
});

describe('post-login return path validation', () => {
  it('accepts a known protected route', () => {
    expect(resolveReturnPath({ from: { pathname: '/documents', search: '', hash: '' } })).toBe(
      '/documents',
    );
    expect(resolveReturnPath({ from: { pathname: '/documents/abc', search: '?q=1', hash: '' } })).toBe(
      '/documents/abc?q=1',
    );
  });

  it.each([
    ['no state', undefined],
    ['empty state', {}],
    ['absolute URL', { from: { pathname: 'https://evil.example/steal' } }],
    ['protocol relative', { from: { pathname: '//evil.example' } }],
    ['backslash', { from: { pathname: '/\\evil.example' } }],
    ['public auth route', { from: { pathname: '/login' } }],
    ['unknown route', { from: { pathname: '/not-a-route' } }],
    ['non-string pathname', { from: { pathname: 42 } }],
  ])('falls back to the dashboard for %s', (_case, state) => {
    expect(resolveReturnPath(state)).toBe(DEFAULT_POST_LOGIN_PATH);
  });
});
