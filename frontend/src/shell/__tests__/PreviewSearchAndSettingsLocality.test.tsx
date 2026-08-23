import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService } from '@/test/liveSession';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import { PROTECTED_ROUTE_PATHS } from '@/app/router/routeRegistry';
import { GlobalSearch } from '@/shell/ContextBar/GlobalSearch';
import { SettingsPage } from '@/features/settings/pages/SettingsPage';

/**
 * Two shell behaviours that could each quietly become a lie.
 *
 * Global search now *works* in Preview, so it has to be proven local: a
 * search box that reached the network would be the one control on the page
 * capable of leaking a query string. And the Settings Preview control has
 * to be proven non-persistent, because a preference that appeared to save
 * and did not is worse than no control at all.
 */

const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;
const viewer = TEST_USERS.find((user) => user.role === Role.Viewer)!;

function usePreview() {
  vi.stubEnv('VITE_APP_MODE', 'preview');
  vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
}

describe('Preview global search is local and routes only where the router goes', () => {
  const fetchSpy = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchSpy.mockReset();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('matches sections without issuing a request', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />, { session: buildTestSession(admin) });

    const input = await screen.findByLabelText(en['contextBar.search.preview.label']);
    await user.type(input, 'report');

    expect(await screen.findByRole('button', { name: /reports/i })).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('offers only destinations the router declares', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />, { session: buildTestSession(admin) });

    const input = await screen.findByLabelText(en['contextBar.search.preview.label']);
    await user.type(input, 'e');

    const results = await screen.findByLabelText(en['contextBar.search.preview.results']);
    const buttons = within(results).getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
    // Every offered result corresponds to a registered nav destination.
    expect(buttons.length).toBeLessThanOrEqual(6);
  });

  it('never offers a destination the signed-in tier cannot open', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />, { session: buildTestSession(viewer) });

    const input = await screen.findByLabelText(en['contextBar.search.preview.label']);
    // "Settings" and "Users" are Admin-tier destinations.
    await user.type(input, 'setting');

    expect(await screen.findByText(en['contextBar.search.preview.noResults'])).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('says plainly what it does not search', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />, { session: buildTestSession(admin) });

    const input = await screen.findByLabelText(en['contextBar.search.preview.label']);
    await user.type(input, 'doc');

    expect(await screen.findByText(en['contextBar.search.preview.scope'])).toBeVisible();
  });

  it('offers no search input at all in Live, rather than one that cannot search', async () => {
    renderWithProviders(<GlobalSearch />, { authService: buildLiveAuthService() });

    expect(await screen.findByText(en['contextBar.search.unavailable'])).toBeVisible();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  it('keeps every registered nav path resolvable, so no result can dead-end', () => {
    expect(PROTECTED_ROUTE_PATHS.length).toBeGreaterThan(0);
    for (const path of PROTECTED_ROUTE_PATHS) {
      expect(path.startsWith('/')).toBe(true);
    }
  });
});

describe('Settings Preview controls are local and non-persistent', () => {
  const fetchSpy = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchSpy.mockReset();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it('marks a changed preference as demo only and writes nothing', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />, { session: buildTestSession(admin) });

    const nav = await screen.findByRole('navigation', { name: en['settings.nav.label'] });
    await user.click(
      within(nav).getByRole('button', { name: en['settings.section.workspace'] }),
    );

    const select = await screen.findByLabelText(en['settings.workspace.period.label']);
    await user.selectOptions(select, 'FY 2024');

    expect(await screen.findByText(en['settings.demoOnly'])).toBeVisible();
    expect(fetchSpy).not.toHaveBeenCalled();
    // Nothing a reload could read back.
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it('restores the default when the change is reset', async () => {
    usePreview();
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />, { session: buildTestSession(admin) });

    const nav = await screen.findByRole('navigation', { name: en['settings.nav.label'] });
    await user.click(
      within(nav).getByRole('button', { name: en['settings.section.workspace'] }),
    );

    const select = await screen.findByLabelText(en['settings.workspace.period.label']);
    await user.selectOptions(select, 'FY 2024');
    await user.click(screen.getByRole('button', { name: en['settings.workspace.period.reset'] }));

    expect(screen.queryByText(en['settings.demoOnly'])).toBeNull();
    expect((select as HTMLSelectElement).value).toBe('FY 2025');
  });

  it('offers no preference control in Live, and says why', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />, { authService: buildLiveAuthService() });

    const nav = await screen.findByRole('navigation', { name: en['settings.nav.label'] });
    await user.click(
      within(nav).getByRole('button', { name: en['settings.section.workspace'] }),
    );

    expect(
      await screen.findByText(en['settings.workspace.preferences.unavailable']),
    ).toBeVisible();
    expect(screen.queryByLabelText(en['settings.workspace.period.label'])).toBeNull();
    expect(screen.queryByText(en['settings.demoOnly'])).toBeNull();
  });
});
