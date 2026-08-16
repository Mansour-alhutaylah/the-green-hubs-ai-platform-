import { describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/react';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { DocumentTitle } from '../DocumentTitle';
import { AppRoutes } from '../routes';

function titleAt(pathname: string): string {
  renderWithProviders(<DocumentTitle />, { initialEntries: [pathname] });
  return document.title;
}

describe('DocumentTitle', () => {
  it.each([
    ['/dashboard', 'Dashboard | The Green Hubs'],
    ['/documents', 'Documents | The Green Hubs'],
    ['/documents/upload', 'Upload | The Green Hubs'],
    ['/analysis', 'Analysis | The Green Hubs'],
    ['/reports', 'Reports | The Green Hubs'],
    ['/settings', 'Settings | The Green Hubs'],
    ['/login', 'Sign in | The Green Hubs'],
  ])('titles %s as "%s"', (pathname, expected) => {
    expect(titleAt(pathname)).toBe(expected);
  });

  it('gives every Coming Soon module its own module name', () => {
    expect(titleAt('/carbon')).toBe('Carbon Intelligence | The Green Hubs');
    expect(titleAt('/audit')).toBe('Audit Log | The Green Hubs');
  });

  it('keeps record identifiers out of detail-route titles', () => {
    // A browser title outlives the page — history, session restore, task
    // switchers, a shared screen. Nothing route-specific may leak into it.
    expect(titleAt('/documents/q3-emissions-invoice-8871')).toBe('Document | The Green Hubs');
    expect(titleAt('/reports/2f9c1b7e')).toBe('Report | The Green Hubs');
    expect(titleAt('/analysis/2f9c1b7e')).toBe('Analysis run | The Green Hubs');
    expect(titleAt('/organizations/acme-holding')).toBe('Organization | The Green Hubs');
  });

  it('prefers the literal upload path over the document-detail pattern', () => {
    // /documents/upload matches /documents/:id too — order decides.
    expect(titleAt('/documents/upload')).not.toContain('Document |');
  });

  it('titles an unknown path as not found, but the root redirect as the brand alone', () => {
    expect(titleAt('/nope')).toBe('Page not found | The Green Hubs');
    expect(titleAt('/')).toBe('The Green Hubs');
  });

  it('follows the active locale', () => {
    window.localStorage.setItem('ghp:locale', 'ar');
    expect(titleAt('/dashboard')).toBe('لوحة القيادة | ذا جرين هبز');
  });

  it('is mounted by the router, so a real navigation sets the title', async () => {
    const admin = TEST_USERS.find((user) => user.role === Role.Admin);
    if (!admin) throw new Error('No Admin demo user seeded');

    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/documents'],
      session: buildTestSession(admin),
    });

    await waitFor(() => expect(document.title).toBe('Documents | The Green Hubs'));
  });
});
