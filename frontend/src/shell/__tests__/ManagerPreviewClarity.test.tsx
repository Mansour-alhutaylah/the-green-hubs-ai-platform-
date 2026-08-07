import { beforeEach, describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { AppRoutes } from '@/app/router/routes';
import { Role } from '@/features/rbac/roles';
import { DEMO_USERS } from '@/features/auth/services/demoUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { en } from '@/lib/i18n/strings/en';

/**
 * Guards the controlled-internal-preview disclosures: a reviewer must be
 * able to tell sample content from live capability, and every
 * not-yet-available module must say so in the same words. These are
 * truthfulness assertions, not styling ones.
 */
describe('manager preview clarity', () => {
  const admin = DEMO_USERS.find((user) => user.role === Role.Admin);
  if (!admin) throw new Error('No Admin demo user seeded');

  beforeEach(() => {
    window.sessionStorage.setItem('ghp:dashboard-visited', '1');
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  it('discloses the internal MVP preview and sample data on the Dashboard', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();

    const notice = screen.getByRole('complementary', { name: en['preview.label'] });
    expect(notice).toBeVisible();
    expect(notice).toHaveTextContent(en['preview.notice']);

    // The pre-existing sample-data indication must survive alongside it.
    expect(screen.getByText(en['dashboard.sampleData'])).toBeVisible();
  });

  it.each([
    ['/reports', /^reports$/i],
    ['/organizations', /^organizations$/i],
    ['/users', /users & roles/i],
    ['/notifications', /^notifications$/i],
  ])('gives %s the same Coming Soon treatment as the placeholder hubs', async (path, heading) => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: [path],
      session: buildTestSession(admin),
    });

    expect(await screen.findByRole('heading', { name: heading }, { timeout: 5000 })).toBeVisible();
    expect(screen.getAllByText(/^soon$/i).length).toBeGreaterThan(0);
    expect(screen.getByText(en['stub.laterPhase'])).toBeVisible();
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  });

  it('renders the not-yet-implemented Settings sections without throwing', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/settings'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^settings$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(screen.getAllByText(en['stub.laterPhase']).length).toBeGreaterThan(0);
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
        initialEntries: ['/reports'],
        session: buildTestSession(admin),
      });

      expect(
        await screen.findByRole('heading', { name: /^reports$/i }, { timeout: 5000 }),
      ).toBeVisible();
      expect(screen.getByText(en['stub.laterPhase'])).toBeVisible();
      expect(screen.getAllByText(/^soon$/i).length).toBeGreaterThan(0);
    },
  );

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
