import { beforeEach, describe, expect, it } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AppRoutes } from '@/app/router/routes';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { en } from '@/lib/i18n/strings/en';

/**
 * Guards the controlled-internal-preview disclosures: a reviewer must be
 * able to tell sample content from live capability, and every
 * not-yet-available module must say so in the same words. These are
 * truthfulness assertions, not styling ones.
 */
describe('manager preview clarity', () => {
  const admin = TEST_USERS.find((user) => user.role === Role.Admin);
  if (!admin) throw new Error('No Admin test user seeded');

  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  /* F2A replaced the Dashboard placeholder with real cards. What a Live
     user must still never see is an invented figure; what they must see is
     each unbacked capability named. Both are asserted here, and in full in
     `DashboardTruthfulness.test.tsx`. */
  it('names the Live dashboard capabilities that have no service, instead of inventing figures', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }),
    ).toBeVisible();

    expect(screen.getByText(en['dashboard.live.section.notConnected'])).toBeVisible();
    expect(screen.getByText(en['dashboard.live.unavailable.evidenceReview'])).toBeVisible();
  });

  /* Notifications is still a Phase-2 placeholder and must keep the shared
     Coming Soon treatment. Reports left this list when it was implemented
     as a full Preview surface; it is asserted below on what it now shows.
     Organizations, Users, Settings, and the Dashboard are likewise no
     longer placeholders. */
  it.each([['/notifications', /^notifications$/i]])(
    'gives %s the same Coming Soon treatment as the placeholder hubs',
    async (path, heading) => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: [path],
      session: buildTestSession(admin),
    });

      expect(await screen.findByRole('heading', { name: heading })).toBeVisible();
      expect(screen.getAllByText(/^soon$/i).length).toBeGreaterThan(0);
      expect(screen.getByText(en['stub.laterPhase'])).toBeVisible();
      expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
    },
  );

  it('tells a Live user that organization creation is refused by the product API', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/organizations'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^organizations$/i }),
    ).toBeVisible();
    expect(screen.getByText(en['organizations.create.unavailable.title'])).toBeVisible();
    expect(screen.getByText(en['organizations.create.unavailable.description'])).toBeVisible();
    // A control that could only ever produce a 403 is not offered at all.
    expect(screen.queryByRole('button', { name: /create organization/i })).toBeNull();
  });

  it('tells a Live user that the team directory needs a contract the backend lacks', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/users'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /users & roles/i }),
    ).toBeVisible();
    expect(screen.getByText(en['users.live.disclosure.title'])).toBeVisible();
    expect(screen.getByText(en['users.live.disclosure.description'])).toBeVisible();
    for (const pattern of [/invite/i, /remove user/i, /change role/i]) {
      expect(screen.queryByRole('button', { name: pattern })).toBeNull();
    }
  });

  /* Settings is a section workspace now, so each truthful absence is
     asserted in the section that owns it. The claims themselves are
     unchanged: residency and MFA have no product API and both say so
     precisely, rather than sharing the generic placeholder notice. */
  it('renders the implemented Settings sections with truthful unavailable states', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/settings'],
      session: buildTestSession(admin),
    });

    expect(await screen.findByRole('heading', { name: /^settings$/i })).toBeVisible();

    const nav = await screen.findByRole('navigation', { name: en['settings.nav.label'] });
    const open = (label: string) => user.click(within(nav).getByRole('button', { name: label }));

    await open(en['settings.section.residency']);
    expect(screen.getByText(en['settings.residency.unavailable.title'])).toBeVisible();
    expect(screen.getByText(en['settings.residency.unavailable.description'])).toBeVisible();

    await open(en['settings.section.security']);
    expect(screen.getByText(en['settings.security.mfa.description'])).toBeVisible();

    await open(en['settings.section.about']);
    expect(screen.getByText(en['settings.about.claims'])).toBeVisible();

    expect(screen.queryByText(en['stub.laterPhase'])).toBeNull();
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  });

  // NOTE: jsdom performs no layout — `scrollWidth`/`clientWidth` are both 0
  // here, so an overflow assertion would compare 0 <= 0 and pass no matter
  // what. This asserts only what jsdom can actually observe: the module
  // renders its full content at every width. Real horizontal-overflow
  // checking requires a browser.
  it.each([1440, 1280, 1024, 768, 430, 390, 375, 360])(
    'renders a Coming Soon module completely at %ipx',
    async (width) => {
      Object.defineProperty(window, 'innerWidth', { value: width, configurable: true });
      window.dispatchEvent(new Event('resize'));

      renderWithProviders(<AppRoutes />, {
        initialEntries: ['/notifications'],
        session: buildTestSession(admin),
      });

      expect(
        await screen.findByRole('heading', { name: /^notifications$/i }),
      ).toBeVisible();
      expect(screen.getByText(en['stub.laterPhase'])).toBeVisible();
      expect(screen.getAllByText(/^soon$/i).length).toBeGreaterThan(0);
    },
  );

  /* Reports is no longer a placeholder. In a Live session it must still
     refuse to invent reports: no reporting endpoint exists, so it states
     that rather than rendering an empty table, which would claim the
     workspace has none. */
  it('tells a Live user that reporting is not connected, rather than showing none', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/reports'],
      session: buildTestSession(admin),
    });

    expect(await screen.findByRole('heading', { name: /^reports$/i })).toBeVisible();
    expect(screen.getByText(en['reports.unavailable.title'])).toBeVisible();
    expect(screen.getByText(en['reports.unavailable.description'])).toBeVisible();
    expect(screen.queryByText(en['stub.laterPhase'])).toBeNull();
    // Not a single synthetic report leaks into a real session.
    expect(screen.queryByText(/GRI Sustainability Statement/i)).toBeNull();
  });

  it('states that analysis starts from a processed document, without inventing history', () => {
    // The live-session branch of /analysis is the one a manager sees.
    expect(en['analysis.live.noHistory.title']).toBe('Analysis history is not available yet');
    expect(en['analysis.live.noHistory.description']).toBe(
      'Analysis is currently launched from a processed document. A dedicated analysis history view will be added in a later MVP scope.',
    );
    expect(en['analysis.live.noHistory.action']).toBe('Go to documents');
  });

  it('keeps every not-yet-available module on one identical scope statement', () => {
    const unlockLines = (['hubZero', 'carbon', 'telemetry', 'frameworks', 'audit'] as const).map(
      (module) => en[`placeholder.${module}.unlock`],
    );

    expect(new Set([...unlockLines, en['stub.laterPhase']]).size).toBe(1);
    expect(en['stub.laterPhase']).toBe(
      'This capability is not included in the current MVP scope and will be activated in a later release.',
    );
  });

  it('does not claim a verified-evidence or approval lifecycle that is not built', () => {
    const overstated = /\bverified\b/i;
    const liveSurfaces = [
      'auth.welcome.supporting',
      'analysis.live.subtitle',
      'analysis.run.summary.description',
      'analysis.run.findings.description',
      'analysis.run.citations.title',
      'analysis.run.citations.description',
      'analysis.run.insufficient.title',
      'analysis.run.insufficient.description',
      'coachmarks.insightLedger',
    ] as const;

    for (const key of liveSurfaces) {
      expect(en[key], `${key} must not claim verified evidence`).not.toMatch(overstated);
    }
  });
});
