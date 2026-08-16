import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { DashboardPage } from '../DashboardPage';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { en } from '@/lib/i18n/strings/en';
import { PREVIEW_DASHBOARD_SOURCE } from '@/lib/data/fixtures/previewDashboard';

/**
 * The dashboard truthfulness correction.
 *
 * Before F1 the page rendered `mockDashboardData` unconditionally, so a
 * real authenticated user saw 128 analyzed documents, an 86% compliance
 * score, and a named activity feed belonging to nobody. The rule this file
 * enforces is simple: those figures may appear in Preview and may never
 * appear in Live.
 */
const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;

/** Every value in the Preview fixture that would be a lie in Live mode. */
const PREVIEW_ONLY_VALUES = [
  ...PREVIEW_DASHBOARD_SOURCE.metrics.map((metric) => String(metric.value)),
  ...PREVIEW_DASHBOARD_SOURCE.documents.map((document) => document.filename),
  ...PREVIEW_DASHBOARD_SOURCE.activity.map((entry) => entry.actorName),
  ...PREVIEW_DASHBOARD_SOURCE.processingQueue.map((item) => item.filename),
  PREVIEW_DASHBOARD_SOURCE.organizationName,
];

describe('Dashboard truthfulness', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe('Live mode', () => {
    it('states that dashboard metrics are not connected', async () => {
      renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });

      expect(await screen.findByText(en['dashboard.unavailable.title'])).toBeVisible();
      expect(screen.getByText(en['dashboard.unavailable.description'])).toBeVisible();
      expect(screen.getByText(en['dashboard.unavailable.detail'])).toBeVisible();
    });

    it('renders no Preview metric, document, actor, or organization', () => {
      renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });

      for (const value of PREVIEW_ONLY_VALUES) {
        expect(
          screen.queryByText(value, { exact: false }),
          `Live mode must not render the Preview value "${value}"`,
        ).toBeNull();
      }
    });

    it('does not render the hero counts strip when no source supplied totals', () => {
      renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });

      expect(screen.queryByText(en['dashboard.hero.documentsTracked'])).toBeNull();
      expect(screen.queryByText(en['dashboard.hero.analysisRuns'])).toBeNull();
    });
  });

  describe('Preview mode', () => {
    it('renders the deterministic Preview snapshot', async () => {
      vi.stubEnv('VITE_APP_MODE', 'preview');
      vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');

      renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });

      expect(await screen.findByText(en['dashboard.kpi.documentsAnalyzed'])).toBeVisible();
      expect(screen.getAllByText('128').length).toBeGreaterThan(0);
      expect(screen.getAllByText('86%').length).toBeGreaterThan(0);
      expect(screen.queryByText(en['dashboard.unavailable.title'])).toBeNull();
    });

    it('is deterministic across renders', () => {
      vi.stubEnv('VITE_APP_MODE', 'preview');
      vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');

      const first = renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });
      const firstHtml = first.container.innerHTML;
      first.unmount();

      const second = renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });
      expect(second.container.innerHTML).toBe(firstHtml);
    });

    it('honours the configured scenario instead of always showing data', async () => {
      vi.stubEnv('VITE_APP_MODE', 'preview');
      vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
      vi.stubEnv('VITE_PREVIEW_SCENARIO', 'forbidden');

      renderWithProviders(<DashboardPage />, { session: buildTestSession(admin) });

      expect(await screen.findByText(en['dashboard.state.forbidden.title'])).toBeVisible();
      expect(screen.queryByText('128')).toBeNull();
    });
  });
});
