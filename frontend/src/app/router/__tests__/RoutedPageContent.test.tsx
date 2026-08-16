import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRoutes } from '../routes';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';

describe('routed page content', () => {
  const admin = TEST_USERS.find((user) => user.role === Role.Admin);

  beforeEach(() => {
    vi.mocked(window.scrollTo).mockClear();
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  if (!admin) throw new Error('No Admin demo user seeded');

  it('renders the Dashboard route inside the app shell', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
    // This is a Live session, and no dashboard endpoint exists yet, so the
    // page states that rather than rendering metric cards — see
    // DashboardTruthfulness.test.tsx for the full rule.
    expect(screen.getByText(/dashboard metrics are not connected yet/i)).toBeVisible();
    expect(screen.queryByText(/documents analyzed/i)).toBeNull();
    const main = screen.getByRole('main');
    expect(main).not.toBeEmptyDOMElement();
    expect(main).toHaveClass('py-4', 'md:py-5', 'xl:py-6');
    expect(
      screen.getByRole('heading', { name: /^dashboard$/i }).closest('section'),
    ).not.toHaveClass('panel-enter');
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'auto' });
    expect(window.history.scrollRestoration).toBe('manual');
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
