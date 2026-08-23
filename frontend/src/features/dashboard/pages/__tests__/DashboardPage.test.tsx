import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders, buildTestSession } from '@/test/renderWithProviders';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import { DashboardPage } from '../DashboardPage';

function userWithRole(role: Role) {
  const user = TEST_USERS.find((candidate) => candidate.role === role);
  if (!user) throw new Error(`No test user seeded for role ${role}`);
  return user;
}

/** The charts only have data to draw in Preview mode — Live has no
 * dashboard source yet (see DashboardTruthfulness.test.tsx). */
function usePreviewMode() {
  vi.stubEnv('VITE_APP_MODE', 'preview');
  vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
}

describe('DashboardPage — analysis chart, donut, and quick actions', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('renders the Analysis Activity chart and Analysis Summary donut with the snapshot totals', () => {
    usePreviewMode();
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Admin)) });

    expect(screen.getByRole('heading', { name: /analysis activity/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /analysis summary/i })).toBeInTheDocument();
    // 18 + 4 + 2 + 3 analysis outcomes in the Preview fixture.
    expect(screen.getAllByText('27').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Completed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Processing').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Insufficient evidence').length).toBeGreaterThan(0);
  });

  it('switches the chart between Monthly and Quarterly views', async () => {
    usePreviewMode();
    const user = userEvent.setup();
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Admin)) });

    const quarterlyTab = screen.getByRole('tab', { name: /quarterly/i });
    expect(quarterlyTab).toHaveAttribute('aria-selected', 'false');

    await user.click(quarterlyTab);
    expect(quarterlyTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /monthly/i })).toHaveAttribute('aria-selected', 'false');
  });

  /* The executive header replaced the marketing hero, so the three primary
     actions are now Review evidence / Open reports / Upload source. The
     tier rule they enforce is unchanged: Upload is the only gated one, and
     a Viewer must not see it. */
  it('shows the Upload quick action only for Editor-tier and above', async () => {
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Viewer)) });
    // Wait for the seeded auth session to finish restoring before asserting
    // absence, same pattern as CommandRail.rbac.test.tsx.
    await screen.findByRole('link', { name: /review evidence/i });
    expect(screen.queryByRole('link', { name: /upload source/i })).not.toBeInTheDocument();
  });

  it('shows Review evidence, Open reports, and Upload source for an Editor-tier session', async () => {
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Editor)) });
    expect(await screen.findByRole('link', { name: /upload source/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /review evidence/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open reports/i })).toBeInTheDocument();
  });

  it('leads with the four evidence KPIs, and never labels one a compliance score', async () => {
    usePreviewMode();
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Editor)) });

    expect(await screen.findByText(en['dashboard.kpi.evidenceReadiness'])).toBeVisible();
    expect(screen.getByText(en['dashboard.kpi.sourceDocuments'])).toBeVisible();
    expect(screen.getByText(en['dashboard.kpi.awaitingReview'])).toBeVisible();
    expect(screen.getByText(en['dashboard.kpi.processingHealth'])).toBeVisible();

    // The label this replaced. A regulatory judgement no backend computes
    // must not reappear under any casing.
    expect(screen.queryByText(/compliance score/i)).not.toBeInTheDocument();
  });

  it('gives the throughput chart an accessible textual equivalent, not just an image', async () => {
    usePreviewMode();
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Editor)) });

    // The sentence a screen reader gets instead of the polylines.
    expect(
      await screen.findByText(/documents were verified and .* reached report-ready/i),
    ).toBeInTheDocument();
    // And the same figures as a real table.
    expect(
      screen.getByRole('table', { name: en['dashboard.throughput.title'] }),
    ).toBeInTheDocument();
  });
});
