import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRoutes } from '@/app/router/routes';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { en } from '@/lib/i18n/strings/en';
import { ar } from '@/lib/i18n/strings/ar';

const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;

/**
 * The global search control was a stub: a real input with a real "/"
 * shortcut and no search behind it. F1 makes the absence visible rather
 * than dressing it up.
 */
describe('global search is presented as unavailable', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  it('shows a coming-later label in the Context Bar', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    const contextBar = await screen.findByTestId('context-bar');
    expect(contextBar).toHaveTextContent(en['contextBar.search.unavailable']);
  });

  it('offers no search input to type into', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    const contextBar = await screen.findByTestId('context-bar');
    expect(contextBar.querySelectorAll('input')).toHaveLength(0);
    expect(screen.queryByRole('searchbox')).toBeNull();
  });

  it('no longer focuses anything on the "/" shortcut', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    await screen.findByTestId('context-bar');
    const before = document.activeElement;
    await user.keyboard('/');
    expect(document.activeElement).toBe(before);
  });

  it('emits no request when the shell renders or the shortcut is pressed', async () => {
    const fetchSpy = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchSpy);
    const user = userEvent.setup();

    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    await screen.findByTestId('context-bar');
    await user.keyboard('/search term{Enter}');

    expect(fetchSpy).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it('has translated copy in both languages', () => {
    expect(en['contextBar.search.unavailable'].length).toBeGreaterThan(0);
    expect(ar['contextBar.search.unavailable'].length).toBeGreaterThan(0);
    expect(ar['contextBar.search.unavailable']).not.toBe(en['contextBar.search.unavailable']);
  });
});
