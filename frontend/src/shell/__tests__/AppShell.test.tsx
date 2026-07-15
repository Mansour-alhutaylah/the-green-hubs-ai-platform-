import { describe, expect, it, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { renderWithProviders, buildTestSession } from '@/test/renderWithProviders';
import { DEMO_USERS } from '@/features/auth/services/demoUsers';
import { Role } from '@/features/rbac/roles';
import { AppShell } from '../AppShell';

describe('AppShell', () => {
  beforeEach(() => {
    // Force desktop nav mode (>=1280px) so the Command Rail renders
    // expanded by default, rather than tablet's icon-only collapse.
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
  });

  it('renders the Command Rail, Context Bar, and sovereignty seal for an authenticated user', async () => {
    const owner = DEMO_USERS.find((user) => user.role === Role.Owner);
    if (!owner) throw new Error('No Owner demo user seeded');

    renderWithProviders(
      <Routes>
        <Route path="/dashboard" element={<AppShell />}>
          <Route index element={<div>dashboard content</div>} />
        </Route>
      </Routes>,
      { initialEntries: ['/dashboard'], session: buildTestSession(owner) },
    );

    expect(await screen.findByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'The Green Hubs' })).toHaveAttribute(
      'src',
      '/brand/logo-lockup-white-on-forest.png',
    );
    expect(screen.getByTestId('context-bar')).toBeInTheDocument();
    expect(screen.getByText('Secure sustainability workspace')).toBeInTheDocument();
  });
});
