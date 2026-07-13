import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRoutes } from '../routes';
import { Role } from '@/features/rbac/roles';
import { DEMO_USERS } from '@/features/auth/services/demoUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';

describe('routed page content', () => {
  const admin = DEMO_USERS.find((user) => user.role === Role.Admin);

  beforeEach(() => {
    vi.mocked(window.scrollTo).mockClear();
    window.sessionStorage.setItem('ghp:dashboard-visited', '1');
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  if (!admin) throw new Error('No Admin demo user seeded');

  it('renders the complete Dashboard experience inside the app shell', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(screen.getByText(/documents analyzed/i)).toBeVisible();
    expect(screen.getByText(/active reports/i)).toBeVisible();
    expect(screen.getByText(/compliance score/i)).toBeVisible();
    expect(screen.getByText(/pending approvals/i)).toBeVisible();
    expect(screen.getByRole('heading', { name: /recent documents/i })).toBeVisible();
    expect(screen.getByRole('heading', { name: /recent activity/i })).toBeVisible();
    const main = screen.getByRole('main');
    expect(main).not.toBeEmptyDOMElement();
    expect(main).toHaveClass('py-4', 'md:py-5', 'xl:py-6');
    expect(
      screen.getByRole('heading', { name: /^dashboard$/i }).closest('section'),
    ).not.toHaveClass('panel-enter');
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'auto' });
  });

  it('renders Dashboard after refresh-style remount and away/back navigation', async () => {
    const firstView = renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });
    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
    firstView.unmount();

    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });
    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(window.scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: 'auto' });

    const user = userEvent.setup();
    vi.mocked(window.scrollTo).mockClear();
    await user.click(screen.getByRole('link', { name: /review documents/i }));
    expect(
      await screen.findByRole('heading', { name: /^documents$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'auto' });
    vi.mocked(window.scrollTo).mockClear();
    await user.click(screen.getByRole('link', { name: /^dashboard$/i }));
    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'auto' });
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  }, 15_000);

  it('leaves in-page hash navigation to the browser', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard#workspace-overview-heading'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(window.scrollTo).not.toHaveBeenCalled();
  });

  it.each([1440, 1280, 1024, 768, 390, 360])(
    'renders non-empty Dashboard content at %ipx',
    async (width) => {
      Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
      window.dispatchEvent(new Event('resize'));

      renderWithProviders(<AppRoutes />, {
        initialEntries: ['/dashboard'],
        session: buildTestSession(admin),
      });

      expect(
        await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
      ).toBeVisible();
      expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
      expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(
        document.documentElement.clientWidth,
      );
    },
  );

  it.each([
    ['/documents', /^documents$/i],
    ['/documents/upload', /^upload$/i],
    ['/analysis', /^analysis$/i],
  ])('renders completed route content for %s', async (path, heading) => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: [path],
      session: buildTestSession(admin),
    });

    expect(await screen.findByRole('heading', { name: heading }, { timeout: 5000 })).toBeVisible();
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  });

  it.each([
    ['/hub-zero', /hub zero/i],
    ['/carbon', /carbon intelligence/i],
    ['/telemetry', /telemetry/i],
    ['/frameworks', /frameworks & compliance/i],
    ['/audit', /audit log/i],
  ])('renders an explained coming-soon state for %s', async (path, heading) => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: [path],
      session: buildTestSession(admin),
    });

    expect(await screen.findByRole('heading', { name: heading }, { timeout: 5000 })).toBeVisible();
    expect(screen.getAllByText(/^soon$/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute(
      'href',
      '/dashboard',
    );
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  });
});
