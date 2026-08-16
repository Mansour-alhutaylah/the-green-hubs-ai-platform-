import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { AppRoutes } from '@/app/router/routes';
import { Role } from '@/features/rbac/roles';
import { TEST_USERS } from '@/test/testUsers';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { PREVIEW_RIBBON_TEST_ID } from '@/shell/PreviewModeRibbon';

vi.mock('@/lib/api/client', () => ({
  apiRequest: vi.fn<() => Promise<never>>(async () => {
    throw new Error('apiRequest must not be called in Preview mode');
  }),
}));

vi.mock('@/lib/supabase/client', () => ({
  getSupabaseClient: vi.fn<() => never>(() => {
    throw new Error('Supabase must not be reached in Preview mode');
  }),
  isSupabaseConfigured: vi.fn<() => boolean>(() => false),
}));

const { apiRequest } = await import('@/lib/api/client');
const { getSupabaseClient } = await import('@/lib/supabase/client');

/**
 * The Preview zero-network boundary.
 *
 * A Preview build exists so that screens can be reviewed without any
 * infrastructure — which is only true if it genuinely reaches nothing. This
 * drives the real router through the protected shell in Preview mode and
 * asserts that no request of any kind leaves the app.
 */
describe('Preview mode network isolation', () => {
  const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.stubEnv('VITE_APP_MODE', 'preview');
    vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
    vi.mocked(apiRequest).mockClear();
    vi.mocked(getSupabaseClient).mockClear();
    fetchSpy = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchSpy);
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    window.dispatchEvent(new Event('resize'));
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it.each(['/dashboard', '/documents', '/analysis', '/profile'])(
    'renders %s without calling fetch, Supabase, or apiRequest',
    async (path) => {
      renderWithProviders(<AppRoutes />, {
        initialEntries: [path],
        session: buildTestSession(admin),
      });

      expect(await screen.findByTestId(PREVIEW_RIBBON_TEST_ID)).toBeVisible();

      expect(fetchSpy).not.toHaveBeenCalled();
      expect(apiRequest).not.toHaveBeenCalled();
      expect(getSupabaseClient).not.toHaveBeenCalled();
    },
  );
});
