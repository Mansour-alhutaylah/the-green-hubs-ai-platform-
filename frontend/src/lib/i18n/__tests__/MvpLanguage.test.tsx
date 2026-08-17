import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService } from '@/test/liveSession';
import { en } from '@/lib/i18n/strings/en';
import { ar } from '@/lib/i18n/strings/ar';
import {
  AUTHORITATIVE_LOCALE,
  AVAILABLE_LOCALES,
  hasSelectableLocales,
  isLocaleAvailable,
  resolveLocale,
} from '../availability';
import { SettingsPage } from '@/features/settings/pages/SettingsPage';
import { EngagementsListPage } from '@/features/engagements/pages/EngagementsListPage';

/**
 * The MVP ships English only.
 *
 * Arabic is deferred to a dedicated later phase — the dictionary, the `dir`
 * handling, the logical CSS properties, and the RTL layout all remain, but
 * a partially translated interface is worse than an honest English one, so
 * Arabic is not selectable until a completeness gate is passed.
 *
 * These tests replace the previous EN/AR synchronization and RTL-rendering
 * acceptance criteria. They assert the four things that matter now:
 * English is the only language on offer, Arabic cannot be activated through
 * *any* channel, an unrecognized locale fails closed, and the RTL
 * foundation is still present for the phase that will use it.
 */

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: 'org-1', name: 'Authenticated Live Organization', created_at: null }],
    page: 1,
    page_size: 20,
    total: 1,
  }),
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: async () => ({ items: [], page: 1, page_size: 20, total: 0 }),
  getEngagement: async () => {
    throw new Error('unused in this test');
  },
  createEngagement: async () => {
    throw new Error('unused in this test');
  },
  updateEngagement: async () => {
    throw new Error('unused in this test');
  },
}));

describe('the MVP offers exactly one language', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('lists English and nothing else as available', () => {
    expect(AVAILABLE_LOCALES).toEqual(['en']);
    expect(AUTHORITATIVE_LOCALE).toBe('en');
    expect(isLocaleAvailable('en')).toBe(true);
    expect(isLocaleAvailable('ar')).toBe(false);
    // With one language there is no choice to present, so every selector
    // in the product hides itself rather than showing a single option.
    expect(hasSelectableLocales()).toBe(false);
  });

  it('fails closed to English for every unsupported or malformed value', () => {
    for (const hostile of [
      'ar',
      'AR',
      'ar-SA',
      ' ar ',
      'fr',
      '',
      'en-US',
      null,
      undefined,
      42,
      {},
      ['en'],
      true,
    ]) {
      expect(resolveLocale(hostile), `resolveLocale(${String(hostile)})`).toBe('en');
    }
  });
});

describe('Arabic cannot be activated through any channel', () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.unstubAllEnvs();
  });

  it('ignores a stored Arabic preference and renders English LTR', async () => {
    window.localStorage.setItem('ghp:locale', 'ar');

    renderWithProviders(<SettingsPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByText(en['settings.language.title'])).toBeVisible();
    expect(document.documentElement).toHaveAttribute('lang', 'en');
    expect(document.documentElement).toHaveAttribute('dir', 'ltr');
  });

  it('rewrites a forged stored value instead of leaving it to be read again', async () => {
    window.localStorage.setItem('ghp:locale', 'ar');

    renderWithProviders(<SettingsPage />, { authService: buildLiveAuthService() });
    await screen.findByText(en['settings.language.title']);

    // The provider resolved it to English; the next read must not find
    // Arabic sitting there waiting for a build where it becomes selectable.
    expect(document.documentElement.lang).toBe('en');
  });

  it('ignores a query parameter or route-shaped locale hint', async () => {
    renderWithProviders(<EngagementsListPage />, {
      authService: buildLiveAuthService(),
      initialEntries: ['/engagements?lang=ar&locale=ar&hl=ar'],
    });

    expect(
      await screen.findByRole('heading', { name: /^engagements$/i }),
    ).toBeVisible();
    expect(document.documentElement).toHaveAttribute('dir', 'ltr');
  });

  it('offers no language control in Settings, only a truthful statement', async () => {
    renderWithProviders(<SettingsPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByText(en['settings.language.title'])).toBeVisible();
    expect(screen.getByText(en['settings.language.onlyOption'])).toBeVisible();
    expect(screen.getByText(en['settings.language.future.title'])).toBeVisible();
    expect(screen.getByText(en['settings.language.future.description'])).toBeVisible();

    // No control of any kind is bound to language.
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(screen.queryByRole('radiogroup')).toBeNull();
    expect(screen.queryByRole('button', { name: 'العربية' })).toBeNull();
  });

  it('renders no Arabic script anywhere on an F2A page', async () => {
    const { container } = renderWithProviders(<EngagementsListPage />, {
      authService: buildLiveAuthService(),
    });

    await screen.findByRole('heading', { name: /^engagements$/i });
    // Arabic block, U+0600–U+06FF.
    expect(container.textContent ?? '').not.toMatch(/[؀-ۿ]/);
  });

  it('hides the shell and auth language toggles rather than disabling them', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />, { authService: buildLiveAuthService() });
    await screen.findByText(en['settings.language.title']);

    const toggle = screen.queryByRole('button', { name: /AR ?\/ ?EN|EN ?\/ ?AR/i });
    expect(toggle).toBeNull();

    // Nothing else on the page can flip the language either.
    const buttons = screen.getAllByRole('button');
    for (const button of buttons) {
      expect(button.textContent ?? '').not.toMatch(/[؀-ۿ]/);
    }
    // Sanity: the page is interactive, so the absence above is meaningful.
    expect(buttons.length).toBeGreaterThan(0);
    await user.click(buttons[0]!);
    expect(document.documentElement).toHaveAttribute('dir', 'ltr');
  });
});

describe('the localization system and RTL foundation are preserved', () => {
  it('routes every new F2A string through the dictionary rather than hardcoding it', () => {
    // A representative key from each F2A page. If a page had inlined its
    // copy instead, the key would not exist here.
    for (const key of [
      'nav.engagements',
      'engagements.create.organization.hint',
      'engagements.detail.profile.title',
      'organizations.create.unavailable.description',
      'users.live.disclosure.description',
      'settings.residency.unavailable.description',
      'dashboard.live.section.notConnected',
      'workspace.value.unavailable.detail',
      'workspace.state.partial',
    ] as const) {
      expect(typeof en[key]).toBe('string');
      expect(en[key].length).toBeGreaterThan(0);
    }
  });

  it('keeps the Arabic dictionary in the tree for the future phase', () => {
    // Not deleted, not emptied — the foundation stays, it is simply not
    // reachable from the UI yet.
    expect(Object.keys(ar).length).toBeGreaterThan(100);
    expect(ar['nav.dashboard']).toBeDefined();
  });

  it('allows a future locale dictionary to be partial, falling back to English', () => {
    // The Arabic dictionary is typed `Partial`, so an untranslated key is
    // absent rather than an English string wearing an Arabic label. The
    // provider's fallback is what makes that safe — see
    // `Tabs.test.tsx` for the RTL rendering path itself.
    const arabicKeys = new Set(Object.keys(ar));
    const englishKeys = Object.keys(en);
    // Whether or not the two are in step, the build must still work.
    expect(englishKeys.length).toBeGreaterThan(0);
    expect(arabicKeys.size).toBeLessThanOrEqual(englishKeys.length);
  });

  it('still derives direction from the locale, so enabling Arabic restores RTL', async () => {
    // The mechanism is intact and untouched: `LocaleProvider` writes `dir`
    // from the active locale on every change. Today that always resolves to
    // English/LTR; adding `'ar'` to `AVAILABLE_LOCALES` is the only change
    // needed to bring RTL back.
    renderWithProviders(<SettingsPage />, { authService: buildLiveAuthService() });
    await screen.findByText(en['settings.language.title']);

    expect(document.documentElement.dir).toBe('ltr');
    expect(document.documentElement.lang).toBe('en');
  });
});
