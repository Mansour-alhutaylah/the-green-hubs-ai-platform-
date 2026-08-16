import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders, buildTestSession } from '@/test/renderWithProviders';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
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

  it('shows the Upload quick action only for Editor-tier and above', async () => {
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Viewer)) });
    // Wait for the seeded auth session to finish restoring before asserting
    // absence, same pattern as CommandRail.rbac.test.tsx.
    await screen.findByRole('link', { name: /review documents/i });
    expect(screen.queryByRole('link', { name: /upload document/i })).not.toBeInTheDocument();
  });

  it('shows Documents, Analysis, and Upload quick actions for an Editor-tier session', async () => {
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Editor)) });
    expect(await screen.findByRole('link', { name: /upload document/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /review documents/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /explore analysis/i })).toBeInTheDocument();
  });
});
