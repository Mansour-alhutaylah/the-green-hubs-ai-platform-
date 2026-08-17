import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService } from '@/test/liveSession';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import { PREVIEW_REPORTS } from '@/lib/data/fixtures/previewReports';
import { AppRoutes } from '@/app/router/routes';
import { ReportsListPage } from '../pages/ReportsListPage';

/**
 * Reports is the newest surface and the one with the least behind it: the
 * backend exposes no reporting endpoint at all. That makes two properties
 * load-bearing, and this file exists to pin both.
 *
 * 1. **Preview is a complete demonstration and touches nothing.** No
 *    `fetch`, no `apiRequest`, no Supabase call, and the two demonstration
 *    actions state that they created nothing rather than implying a save.
 * 2. **Live shows no report at all.** Not an empty table, which would
 *    claim the workspace has none, but a stated unavailable surface. And
 *    not one character of the Preview fixtures.
 */

const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;

function usePreview() {
  vi.stubEnv('VITE_APP_MODE', 'preview');
  vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
}

describe('Preview reports are complete, local, and non-persistent', () => {
  const fetchSpy = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchSpy.mockReset();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('renders the sample reports without issuing a single network call', async () => {
    usePreview();
    renderWithProviders(<ReportsListPage />, { session: buildTestSession(admin) });

    expect(
      await screen.findByRole('link', { name: /GRI Sustainability Statement 2025/i }),
    ).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('reports the authored totals, never the number of rows in hand', async () => {
    usePreview();
    renderWithProviders(<ReportsListPage />, { session: buildTestSession(admin) });

    await screen.findByRole('link', { name: /GRI Sustainability Statement 2025/i });

    // The fixture deliberately carries authored totals. If the page ever
    // computed them from `reports.length` this would still pass by
    // coincidence today, so the fixture keeps them explicit and this
    // asserts the contract's value rather than the array's length.
    expect(PREVIEW_REPORTS.totals.all).toBe(6);
    expect(screen.getByText(String(PREVIEW_REPORTS.totals.all))).toBeVisible();
    expect(
      screen.getByText(`${PREVIEW_REPORTS.totals.averageReadinessPercent}%`),
    ).toBeVisible();
  });

  it('filters locally, and says so when nothing matches', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<ReportsListPage />, { session: buildTestSession(admin) });

    await screen.findByRole('link', { name: /GRI Sustainability Statement 2025/i });

    await user.type(
      screen.getByLabelText(en['reports.search.label']),
      'no-such-report-anywhere',
    );

    expect(await screen.findByText(en['reports.empty.noMatches'])).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('states that Generate preview created nothing, and persists no result', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<ReportsListPage />, { session: buildTestSession(admin) });

    await screen.findByRole('link', { name: /GRI Sustainability Statement 2025/i });

    await user.click(screen.getAllByRole('button', { name: en['reports.generate.action'] })[0]!);

    expect(await screen.findByText(en['reports.generate.notice'])).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
    // Nothing was written anywhere a reload could read back.
    expect(window.localStorage.getItem('ghp:reports')).toBeNull();
    expect(window.sessionStorage.length).toBe(0);
  });

  it('states that Export produced no file', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<ReportsListPage />, { session: buildTestSession(admin) });

    await screen.findByRole('link', { name: /GRI Sustainability Statement 2025/i });
    await user.click(screen.getAllByRole('button', { name: en['reports.export.action'] })[0]!);

    expect(await screen.findByText(en['reports.export.notice'])).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('opens a report detail through its own registered route', async () => {
    usePreview();
    // Through the real router, so the detail route's params resolve the
    // way a deep link would rather than being hand-fed.
    renderWithProviders(<AppRoutes />, {
      session: buildTestSession(admin),
      initialEntries: ['/reports/rep-gri-annual-2025'],
    });

    expect(
      await screen.findByRole('heading', { name: /GRI Sustainability Statement 2025/i }),
    ).toBeVisible();
    expect(screen.getByText(en['reports.detail.sections.title'])).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('answers an unknown report id with not-found rather than an invented report', async () => {
    usePreview();
    renderWithProviders(<AppRoutes />, {
      session: buildTestSession(admin),
      initialEntries: ['/reports/rep-does-not-exist'],
    });

    expect(await screen.findByText(en['workspace.state.notFound.title'])).toBeVisible();
  });
});

describe('Live reports renders no synthetic report', () => {
  const fetchSpy = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchSpy.mockReset();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('states that reporting is not connected instead of listing zero reports', async () => {
    renderWithProviders(<ReportsListPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByText(en['reports.unavailable.title'])).toBeVisible();
    expect(screen.getByText(en['reports.unavailable.description'])).toBeVisible();

    // Not an empty table: "0 reports" would claim the workspace has none.
    expect(screen.queryByRole('table')).toBeNull();
    // The summary tiles are absent too. Asserted on the average-readiness
    // label rather than on "Reports", which is also the page heading.
    expect(screen.queryByText(en['reports.total.averageReadiness'])).toBeNull();
    expect(screen.queryByText(en['reports.total.readyToPublish'])).toBeNull();
  });

  it('leaks no fixture report, owner, or template into a real session', async () => {
    const { container } = renderWithProviders(<ReportsListPage />, {
      authService: buildLiveAuthService(),
    });

    await screen.findByText(en['reports.unavailable.title']);

    const markup = container.textContent ?? '';
    for (const report of PREVIEW_REPORTS.reports) {
      expect(markup).not.toContain(report.name);
      expect(markup).not.toContain(report.owner);
    }
  });

  it('offers no generate or export action in Live', async () => {
    renderWithProviders(<ReportsListPage />, { authService: buildLiveAuthService() });

    await screen.findByText(en['reports.unavailable.title']);
    expect(screen.queryByRole('button', { name: en['reports.generate.action'] })).toBeNull();
    expect(screen.queryByRole('button', { name: en['reports.export.action'] })).toBeNull();
  });

  it('answers a Live report detail deep link with the same stated absence', async () => {
    renderWithProviders(<AppRoutes />, {
      authService: buildLiveAuthService(),
      initialEntries: ['/reports/rep-gri-annual-2025'],
    });

    expect(await screen.findByText(en['reports.unavailable.title'])).toBeVisible();
    expect(screen.queryByText(/GRI Sustainability Statement/i)).toBeNull();
  });
});

describe('the Action Centre only links to registered routes', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('gives every action a href the router declares', async () => {
    usePreview();
    const { DashboardPage } = await import('@/features/dashboard/pages/DashboardPage');
    const { PROTECTED_ROUTE_PATHS } = await import('@/app/router/routeRegistry');

    renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });

    const heading = await screen.findByRole('heading', { name: en['dashboard.action.title'] });
    const panel = heading.closest('section') ?? heading.parentElement!;
    const links = within(panel as HTMLElement).getAllByRole('link');

    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      const href = link.getAttribute('href') ?? '';
      expect(href.startsWith('/'), `"${href}" must be an in-app path`).toBe(true);
      expect(href).not.toBe('#');
      // The path the action points at is one the router actually declares.
      expect(
        PROTECTED_ROUTE_PATHS.includes(href),
        `"${href}" is not a registered protected route`,
      ).toBe(true);
    }
  });
});
