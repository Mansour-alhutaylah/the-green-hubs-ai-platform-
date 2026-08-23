import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import { BREAKPOINTS } from '@/lib/utils/breakpoints';
import { DashboardPage } from '../pages/DashboardPage';

/**
 * The coaching panel used to be shown automatically on every first visit,
 * including on a 360px phone where it is roughly as wide as the screen. It
 * only dismissed on the next interaction, so until then it sat on top of
 * whatever occupied the bottom of the viewport: the header, the primary
 * actions, or a KPI card, depending on scroll position.
 *
 * These tests pin the corrected behaviour at both ends. On a compact
 * viewport nothing is shown until the reader asks for it, and what they
 * open they can close. Above the threshold the original presentation is
 * unchanged, which is the part most at risk of being broken by a mobile
 * fix.
 */

const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;

function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
  window.dispatchEvent(new Event('resize'));
}

function renderDashboard() {
  vi.stubEnv('VITE_APP_MODE', 'preview');
  vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
  return renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });
}

/** Every tip, so "the panel is closed" means no coaching content at all
 * rather than merely no container. */
const TIP_TEXTS = [
  en['coachmarks.orgSwitcher'],
  en['coachmarks.insightLedger'],
  en['coachmarks.uploadEntry'],
] as const;

describe('the coaching panel does not obstruct a compact viewport', () => {
  beforeEach(() => {
    window.localStorage.clear();
    setViewport(360);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    window.localStorage.clear();
    setViewport(1280);
  });

  it('renders no tip until the reader opens it', async () => {
    renderDashboard();

    // The dashboard itself is up.
    expect(await screen.findByRole('heading', { name: /^dashboard$/i })).toBeVisible();

    for (const tip of TIP_TEXTS) {
      expect(screen.queryByText(tip)).toBeNull();
    }
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('offers a named, collapsed trigger', async () => {
    renderDashboard();

    const trigger = await screen.findByRole('button', { name: en['coachmarks.trigger'] });
    expect(trigger).toBeVisible();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('opens on the trigger and shows every tip', async () => {
    const user = userEvent.setup();
    renderDashboard();

    const trigger = await screen.findByRole('button', { name: en['coachmarks.trigger'] });
    await user.click(trigger);

    expect(await screen.findByRole('dialog')).toBeVisible();
    for (const tip of TIP_TEXTS) {
      expect(screen.getByText(tip)).toBeVisible();
    }
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('moves focus into the sheet on open and back to the trigger on close', async () => {
    const user = userEvent.setup();
    renderDashboard();

    const trigger = await screen.findByRole('button', { name: en['coachmarks.trigger'] });
    await user.click(trigger);

    const close = await screen.findByRole('button', { name: en['coachmarks.close'] });
    expect(close).toHaveFocus();

    await user.click(close);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    renderDashboard();

    await user.click(await screen.findByRole('button', { name: en['coachmarks.trigger'] }));
    expect(await screen.findByRole('dialog')).toBeVisible();

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).toBeNull();
    for (const tip of TIP_TEXTS) {
      expect(screen.queryByText(tip)).toBeNull();
    }
  });

  it('keeps the dashboard heading, primary actions, and KPIs reachable while open', async () => {
    const user = userEvent.setup();
    renderDashboard();

    await user.click(await screen.findByRole('button', { name: en['coachmarks.trigger'] }));
    await screen.findByRole('dialog');

    // None of the page's primary content is unmounted or hidden behind the
    // sheet: jsdom cannot measure overlap, but it can prove the content is
    // still present, still visible, and still an accessible target.
    expect(screen.getByRole('heading', { name: /^dashboard$/i })).toBeVisible();
    expect(screen.getByRole('link', { name: /review evidence/i })).toBeVisible();
    expect(screen.getByRole('link', { name: /open reports/i })).toBeVisible();
    expect(screen.getByText(en['dashboard.kpi.evidenceReadiness'])).toBeVisible();
    expect(screen.getByText(en['dashboard.kpi.sourceDocuments'])).toBeVisible();
  });

  it('stays dismissed for good once the reader says so', async () => {
    const user = userEvent.setup();
    const { unmount } = renderDashboard();

    await user.click(await screen.findByRole('button', { name: en['coachmarks.trigger'] }));
    await user.click(await screen.findByRole('button', { name: en['coachmarks.dismiss'] }));

    expect(screen.queryByRole('button', { name: en['coachmarks.trigger'] })).toBeNull();
    unmount();

    // And it does not come back on the next visit.
    renderDashboard();
    await screen.findByRole('heading', { name: /^dashboard$/i });
    expect(screen.queryByRole('button', { name: en['coachmarks.trigger'] })).toBeNull();
  });

  it('treats the breakpoint itself as compact', async () => {
    setViewport(BREAKPOINTS.compact);
    renderDashboard();

    expect(
      await screen.findByRole('button', { name: en['coachmarks.trigger'] }),
    ).toBeVisible();
  });

  /**
   * jsdom performs no layout: `scrollWidth` and `clientWidth` are both `0`,
   * so a real overflow assertion would compare `0 <= 0` and pass whatever
   * the CSS said. Actual horizontal-overflow checking needs a browser.
   *
   * What is checkable here is the mechanism that caused the overflow risk
   * in the first place: a fixed 320px width on an overlay, which cannot fit
   * a 360px screen once insets are added. The compact sheet is anchored to
   * both edges instead, so it derives its width from the viewport rather
   * than asserting one.
   */
  it('sizes the compact sheet from the viewport rather than a fixed width', async () => {
    const user = userEvent.setup();
    renderDashboard();

    await user.click(await screen.findByRole('button', { name: en['coachmarks.trigger'] }));
    const sheet = await screen.findByRole('dialog');

    // Anchored to both edges, so its width is the viewport minus insets.
    expect(sheet.className).toContain('inset-x-3');
    // And never the fixed 320px card that did not fit a phone.
    expect(sheet.className).not.toMatch(/\bw-80\b/);
    // Height is capped so it cannot grow past the screen either.
    expect(sheet.className).toContain('max-h-[60vh]');
  });
});

describe('the coaching panel is unchanged above the compact breakpoint', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    window.localStorage.clear();
    setViewport(1280);
  });

  it.each([BREAKPOINTS.compact + 1, 768, 1280, 1440])(
    'shows the tips on arrival at %ipx, with no trigger to press',
    async (width) => {
      setViewport(width);
      renderDashboard();

      for (const tip of TIP_TEXTS) {
        expect(await screen.findByText(tip)).toBeVisible();
      }
      // The desktop presentation is shown outright, so it has no trigger
      // and no sheet.
      expect(screen.queryByRole('button', { name: en['coachmarks.trigger'] })).toBeNull();
      expect(screen.queryByRole('dialog')).toBeNull();
    },
  );

  it('still dismisses on the first interaction anywhere', async () => {
    const user = userEvent.setup();
    setViewport(1280);
    renderDashboard();

    await screen.findByText(en['coachmarks.orgSwitcher']);
    await user.click(screen.getByRole('heading', { name: /^dashboard$/i }));

    expect(screen.queryByText(en['coachmarks.orgSwitcher'])).toBeNull();
    expect(window.localStorage.getItem('ghp:has-onboarded')).toBe('1');
  });
});
