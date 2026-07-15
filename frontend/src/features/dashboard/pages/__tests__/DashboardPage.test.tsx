import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders, buildTestSession } from '@/test/renderWithProviders';
import { DEMO_USERS } from '@/features/auth/services/demoUsers';
import { Role } from '@/features/rbac/roles';
import { DashboardPage } from '../DashboardPage';

function userWithRole(role: Role) {
  const user = DEMO_USERS.find((demoUser) => demoUser.role === role);
  if (!user) throw new Error(`No demo user seeded for role ${role}`);
  return user;
}

describe('DashboardPage — analysis chart, donut, and quick actions', () => {
  it('renders the Analysis Activity chart and Analysis Summary donut with real totals', () => {
    renderWithProviders(<DashboardPage />, { session: buildTestSession(userWithRole(Role.Admin)) });

    expect(screen.getByRole('heading', { name: /analysis activity/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /analysis summary/i })).toBeInTheDocument();
    // 9 total mock analysis runs across all statuses (see mockAnalysisData.ts).
    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getAllByText('Completed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Processing').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Insufficient evidence').length).toBeGreaterThan(0);
  });

  it('switches the chart between Monthly and Quarterly views', async () => {
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
