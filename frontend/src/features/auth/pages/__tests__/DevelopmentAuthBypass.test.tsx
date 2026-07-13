import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRoutes } from '@/app/router/routes';
import { Role } from '@/features/rbac/roles';
import { DEMO_WORKSPACE_ORG_ID } from '@/features/organizations/mockOrgs';
import { mockAuthService } from '@/features/auth/services/mockAuthService';
import { renderWithProviders } from '@/test/renderWithProviders';

const SESSION_KEY = 'ghp:session';

describe('development authentication bypass', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it('shows explicit demo access only when enabled and enters without credentials or OTP', async () => {
    vi.stubEnv('VITE_DEV_AUTH_BYPASS', 'true');
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const user = userEvent.setup();

    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/login'],
      authService: mockAuthService,
    });

    expect(await screen.findByText('Development demo access')).toBeVisible();
    expect(
      screen.getByText('No account or verification is required in development mode.'),
    ).toBeVisible();
    expect(screen.getByLabelText(/work email/i)).toHaveValue('');
    expect(screen.getByLabelText(/^password$/i)).toHaveValue('');

    vi.mocked(window.scrollTo).mockClear();
    await user.click(screen.getByRole('button', { name: 'Enter Demo Workspace' }));

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(
      screen.queryByRole('heading', { name: /verify your identity/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText('Mansour Ali Al-Hutaylah')).toBeVisible();
    expect(screen.getAllByText('The Green Hubs Demo Workspace').length).toBeGreaterThan(0);
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'auto' });

    const persisted = JSON.parse(window.localStorage.getItem(SESSION_KEY) ?? 'null');
    expect(persisted).toMatchObject({
      user: { name: 'Mansour Ali Al-Hutaylah', role: Role.Admin },
      activeOrgId: DEMO_WORKSPACE_ORG_ID,
      token: 'local-development-demo-session',
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  }, 10_000);

  it('hides and rejects the bypass when the flag is disabled', async () => {
    vi.stubEnv('VITE_DEV_AUTH_BYPASS', 'false');

    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/login'],
      authService: mockAuthService,
    });

    expect(await screen.findByRole('heading', { name: /sign in to your hub/i })).toBeVisible();
    expect(screen.queryByRole('button', { name: /enter demo workspace/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/development demo access/i)).not.toBeInTheDocument();
    await expect(mockAuthService.enterDemoWorkspace?.()).rejects.toThrow(
      'Development authentication bypass is disabled.',
    );
    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it('restores the local session and naturally passes protected route guards', async () => {
    vi.stubEnv('VITE_DEV_AUTH_BYPASS', 'true');
    await mockAuthService.enterDemoWorkspace?.();
    window.sessionStorage.setItem('ghp:dashboard-visited', '1');

    const routes: Array<[string, RegExp]> = [
      ['/documents', /^documents$/i],
      ['/documents/doc-1', /q3 2025 sustainability report/i],
      ['/documents/upload', /^upload$/i],
      ['/analysis', /^analysis$/i],
      ['/analysis/run-1', /q3 2025 sustainability report/i],
    ];

    for (const [path, heading] of routes) {
      const view = renderWithProviders(<AppRoutes />, {
        initialEntries: [path],
        authService: mockAuthService,
      });
      expect(
        await screen.findByRole('heading', { name: heading }, { timeout: 5000 }),
      ).toBeVisible();
      expect(
        screen.queryByRole('heading', { name: /sign in to your hub/i }),
      ).not.toBeInTheDocument();
      view.unmount();
    }
  }, 20_000);

  it('clears the restored demo session on logout and protects routes again', async () => {
    vi.stubEnv('VITE_DEV_AUTH_BYPASS', 'true');
    await mockAuthService.enterDemoWorkspace?.();
    const user = userEvent.setup();

    const view = renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      authService: mockAuthService,
    });

    await user.click(
      await screen.findByRole('button', { name: /mansour ali al-hutaylah, account menu/i }),
    );
    await user.click(await screen.findByRole('button', { name: /sign out/i }));

    expect(await screen.findByRole('heading', { name: /sign in to your hub/i })).toBeVisible();
    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull();
    view.unmount();

    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/documents'],
      authService: mockAuthService,
    });
    expect(await screen.findByRole('heading', { name: /sign in to your hub/i })).toBeVisible();
  }, 10_000);

  it('renders the enabled demo action in Arabic with its explanatory copy', async () => {
    vi.stubEnv('VITE_DEV_AUTH_BYPASS', 'true');
    window.localStorage.setItem('ghp:locale', 'ar');

    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/login'],
      authService: mockAuthService,
    });

    expect(await screen.findByRole('button', { name: 'دخول النسخة التجريبية' })).toBeVisible();
    expect(screen.getByText('دخول تجريبي لبيئة التطوير')).toBeVisible();
    expect(screen.getByText('لا يتطلب حسابًا أو تحققًا في وضع التطوير.')).toBeVisible();
    expect(document.documentElement).toHaveAttribute('dir', 'rtl');
  });
});
