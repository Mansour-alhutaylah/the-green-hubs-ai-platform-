import { beforeEach, describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { AppRoutes } from '../routes';
import { Role } from '@/features/rbac/roles';
import { DEMO_USERS } from '@/features/auth/services/demoUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';

describe('routed page content', () => {
  const admin = DEMO_USERS.find((user) => user.role === Role.Admin);

  beforeEach(() => {
    window.sessionStorage.setItem('ghp:dashboard-visited', '1');
  });

  if (!admin) throw new Error('No Admin demo user seeded');

  it('renders the complete Dashboard experience inside the app shell', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/dashboard'],
      session: buildTestSession(admin),
    });

    expect(
      await screen.findByRole('heading', { name: /^dashboard$/i }, { timeout: 5000 }),
    ).toBeVisible();
    expect(screen.getByText(/documents analyzed/i)).toBeVisible();
    expect(screen.getByText(/active reports/i)).toBeVisible();
    expect(screen.getByText(/compliance score/i)).toBeVisible();
    expect(screen.getByText(/pending approvals/i)).toBeVisible();
    expect(screen.getByRole('heading', { name: /recent documents/i })).toBeVisible();
    expect(screen.getByRole('heading', { name: /recent activity/i })).toBeVisible();
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  });

  it.each([
    ['/documents', /^documents$/i],
    ['/documents/upload', /^upload$/i],
    ['/analysis', /^analysis$/i],
  ])('renders completed route content for %s', async (path, heading) => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: [path],
      session: buildTestSession(admin),
    });

    expect(await screen.findByRole('heading', { name: heading }, { timeout: 5000 })).toBeVisible();
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  });

  it.each([
    ['/hub-zero', /hub zero/i],
    ['/carbon', /carbon intelligence/i],
    ['/telemetry', /telemetry/i],
    ['/frameworks', /frameworks & compliance/i],
    ['/audit', /audit log/i],
  ])('renders an explained coming-soon state for %s', async (path, heading) => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: [path],
      session: buildTestSession(admin),
    });

    expect(await screen.findByRole('heading', { name: heading }, { timeout: 5000 })).toBeVisible();
    expect(screen.getAllByText(/^soon$/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute(
      'href',
      '/dashboard',
    );
    expect(screen.getByRole('main')).not.toBeEmptyDOMElement();
  });
});
