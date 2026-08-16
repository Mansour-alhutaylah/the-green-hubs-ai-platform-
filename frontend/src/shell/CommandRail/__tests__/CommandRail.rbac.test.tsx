import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders, buildTestSession } from '@/test/renderWithProviders';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
import { CommandRail } from '../CommandRail';

function userWithRole(role: Role) {
  const user = TEST_USERS.find((demoUser) => demoUser.role === role);
  if (!user) throw new Error(`No demo user seeded for role ${role}`);
  return user;
}

describe('CommandRail RBAC gating', () => {
  it('hides the Upload nav item for a Viewer-tier session', async () => {
    renderWithProviders(<CommandRail isCollapsed={false} onToggle={() => {}} />, {
      session: buildTestSession(userWithRole(Role.Viewer)),
    });

    // Wait for the auth session to finish restoring before asserting absence.
    await screen.findByText('Dashboard');
    expect(screen.queryByText('Upload')).not.toBeInTheDocument();
  });

  it('shows the Upload nav item for an Editor-tier session', async () => {
    renderWithProviders(<CommandRail isCollapsed={false} onToggle={() => {}} />, {
      session: buildTestSession(userWithRole(Role.Editor)),
    });

    expect(await screen.findByText('Upload')).toBeInTheDocument();
  });
});
