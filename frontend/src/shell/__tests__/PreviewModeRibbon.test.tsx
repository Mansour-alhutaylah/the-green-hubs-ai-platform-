import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { AppRoutes } from '@/app/router/routes';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { en } from '@/lib/i18n/strings/en';
import { ar } from '@/lib/i18n/strings/ar';
import { PREVIEW_RIBBON_TEST_ID } from '../PreviewModeRibbon';

const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;

const PROTECTED_ROUTES = [
  '/dashboard',
  '/documents',
  '/analysis',
  '/reports',
  '/organizations',
  '/notifications',
  '/profile',
  '/settings',
];

describe('Preview disclosure ribbon', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe('Preview mode', () => {
    beforeEach(() => {
      vi.stubEnv('VITE_APP_MODE', 'preview');
      vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
    });

    it.each(PROTECTED_ROUTES)('is present on %s', async (path) => {
      renderWithProviders(<AppRoutes />, {
        initialEntries: [path],
        session: buildTestSession(admin),
      });

      const ribbon = await screen.findByTestId(PREVIEW_RIBBON_TEST_ID);
      expect(ribbon).toBeVisible();
    });

    it('states that the data and actions are demonstrations and that Production is not connected', async () => {
      renderWithProviders(<AppRoutes />, {
        initialEntries: ['/dashboard'],
        session: buildTestSession(admin),
      });

      const ribbon = await screen.findByTestId(PREVIEW_RIBBON_TEST_ID);
      expect(ribbon).toHaveTextContent(en['preview.ribbon.demonstration']);
      expect(ribbon).toHaveTextContent(en['preview.ribbon.notProduction']);
    });

    it('offers no way to dismiss it', async () => {
      renderWithProviders(<AppRoutes />, {
        initialEntries: ['/dashboard'],
        session: buildTestSession(admin),
      });

      const ribbon = await screen.findByTestId(PREVIEW_RIBBON_TEST_ID);
      expect(ribbon.querySelectorAll('button, a, input')).toHaveLength(0);
    });

    it('has translated copy in both languages', () => {
      for (const key of [
        'preview.ribbon.label',
        'preview.ribbon.demonstration',
        'preview.ribbon.notProduction',
      ] as const) {
        expect(en[key].length).toBeGreaterThan(0);
        expect(ar[key].length).toBeGreaterThan(0);
        expect(ar[key]).not.toBe(en[key]);
      }
    });
  });

  describe('Live mode', () => {
    it.each(PROTECTED_ROUTES)('is absent from %s', async (path) => {
      renderWithProviders(<AppRoutes />, {
        initialEntries: [path],
        session: buildTestSession(admin),
      });

      // Wait for the routed page to settle before asserting an absence.
      await screen.findByTestId('context-bar');
      expect(screen.queryByTestId(PREVIEW_RIBBON_TEST_ID)).toBeNull();
    });
  });
});
