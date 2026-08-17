import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { AppRoutes } from '../routes';
import { ROUTES } from '@/app/navigation/routePaths';
import {
  isKnownProtectedPath,
  PROTECTED_ROUTE_KEYS,
  PROTECTED_ROUTE_PATHS,
  PUBLIC_ONLY_ROUTE_KEYS,
  UNGUARDED_ROUTE_KEYS,
} from '../routeRegistry';
import { activeNavItemId, findNavItem } from '@/app/navigation/navConfig';
import { Role } from '@/features/rbac/roles';
import { renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService, LIVE_ORGANIZATION_ID } from '@/test/liveSession';
import { en } from '@/lib/i18n/strings/en';

/**
 * The two routes F2A added, and the drift they could have introduced.
 *
 * `routeRegistry.test.tsx` already proves the *rule* — protected is the
 * derived default, and the router's declared tree matches the registry.
 * This file pins the two concrete routes to that rule and then checks the
 * thing a registry test cannot: that a deep link to
 * `/engagements/:id` actually renders the engagement rather than a 404 or a
 * bounce to the dashboard.
 */

const ENGAGEMENT_ID = 'eng-deep-link-1';
const ENGAGEMENT_TITLE = 'Deep Linked Engagement';

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: async () => ({ items: [], page: 1, page_size: 20, total: 0 }),
  getEngagement: async (id: string) => ({
    id,
    organization_id: LIVE_ORGANIZATION_ID,
    title: ENGAGEMENT_TITLE,
    status: 'active',
    created_at: '2026-04-01T09:00:00.000Z',
  }),
  createEngagement: async () => {
    throw new Error('unused in this test');
  },
  updateEngagement: async () => {
    throw new Error('unused in this test');
  },
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: LIVE_ORGANIZATION_ID, name: 'Authenticated Live Organization', created_at: null }],
    page: 1,
    page_size: 20,
    total: 1,
  }),
  getOrganization: async () => {
    throw new Error('unused in this test');
  },
  updateOrganization: async () => {
    throw new Error('unused in this test');
  },
}));

describe('engagement route classification', () => {
  it('classifies both engagement routes as protected, by derivation not by listing', () => {
    expect(PROTECTED_ROUTE_KEYS).toContain('engagements');
    expect(PROTECTED_ROUTE_KEYS).toContain('engagementDetail');
    expect(PUBLIC_ONLY_ROUTE_KEYS).not.toContain('engagements');
    expect(UNGUARDED_ROUTE_KEYS).not.toContain('engagements');

    expect(PROTECTED_ROUTE_PATHS).toContain(ROUTES.engagements);
    expect(PROTECTED_ROUTE_PATHS).toContain(ROUTES.engagementDetail);
  });

  it('recognizes both concrete URLs, so a deep link is not answered with a 404', () => {
    expect(isKnownProtectedPath('/engagements')).toBe(true);
    expect(isKnownProtectedPath(`/engagements/${ENGAGEMENT_ID}`)).toBe(true);
    // Still not a wildcard: an extra segment matches no route.
    expect(isKnownProtectedPath('/engagements/eng-1/extra')).toBe(false);
  });

  it('applies the minimum tier the backend actually enforces', () => {
    // Reading engagements requires only `get_current_user`, so the route is
    // Viewer-visible; `engagement.manage` (editor and above) gates the
    // create/update actions inside the page instead.
    expect(findNavItem('engagements').minTier).toBe(Role.Viewer);
  });

  it('lights the Engagements nav item for both routes, and nothing else', () => {
    expect(activeNavItemId('/engagements')).toBe('engagements');
    expect(activeNavItemId(`/engagements/${ENGAGEMENT_ID}`)).toBe('engagements');
    expect(activeNavItemId('/documents')).toBe('documents');
  });
});

describe('engagement deep links', () => {
  it('renders the list route directly', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/engagements'],
      authService: buildLiveAuthService(),
    });

    expect(
      await screen.findByRole('heading', { name: /^engagements$/i }),
    ).toBeVisible();
  });

  it('renders the detail route directly from its URL', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: [`/engagements/${ENGAGEMENT_ID}`],
      authService: buildLiveAuthService(),
    });

    expect(
      await screen.findByRole('heading', { name: ENGAGEMENT_TITLE }),
    ).toBeVisible();
    expect(screen.getByText(en['engagements.detail.profile.title'])).toBeVisible();
  });

  it('still answers an unknown URL under the same prefix with the 404 page', async () => {
    renderWithProviders(<AppRoutes />, {
      initialEntries: ['/engagements/eng-1/not-a-page'],
      authService: buildLiveAuthService(),
    });

    expect(await screen.findByText(en['errors.notFound.title'], undefined)).toBeVisible();
  });
});
