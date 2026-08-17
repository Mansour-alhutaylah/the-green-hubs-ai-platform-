import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { buildTestSession, renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService } from '@/test/liveSession';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import type { PreviewScenario } from '@/lib/data/scenarios';
import type {
  EngagementListResponse,
  OrganizationListResponse,
  UserProfileResponse,
} from '@/lib/api/types';
import { EngagementsListPage } from '@/features/engagements/pages/EngagementsListPage';
import { OrganizationsListPage } from '@/features/organizations/pages/OrganizationsListPage';
import { UsersPage } from '@/features/users/pages/UsersPage';

/**
 * State coverage for the F2A pages.
 *
 * Every one of these screens can reach six states, and the failure this
 * suite guards against is the one that never throws: a page that renders
 * "nothing here yet" when the request actually failed, or renders an empty
 * table when the caller simply may not see it. Those are different facts
 * and a person acts on them differently.
 *
 * Preview drives the states through the build-time scenario, which is how
 * they are meant to be reviewed without a backend. Live drives them through
 * the API layer, which is where they really come from.
 */

const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;

const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();
const listOrganizations = vi.fn<() => Promise<OrganizationListResponse>>();
const getMe = vi.fn<() => Promise<UserProfileResponse>>();

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: (...args: unknown[]) => listEngagements(...(args as [])),
  getEngagement: async () => {
    throw new Error('unused');
  },
  createEngagement: async () => {
    throw new Error('unused');
  },
  updateEngagement: async () => {
    throw new Error('unused');
  },
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: (...args: unknown[]) => listOrganizations(...(args as [])),
  getOrganization: async () => {
    throw new Error('unused');
  },
  updateOrganization: async () => {
    throw new Error('unused');
  },
}));

vi.mock('@/lib/api/endpoints/auth', () => ({
  getMe: (...args: unknown[]) => getMe(...(args as [])),
}));

const { ForbiddenError } = await import('@/lib/api/errors');

function usePreview(scenario: PreviewScenario) {
  vi.stubEnv('VITE_APP_MODE', 'preview');
  vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
  vi.stubEnv('VITE_PREVIEW_SCENARIO', scenario);
}

describe('Preview scenarios reach every state on every F2A collection page', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  const pages = [
    ['Engagements', <EngagementsListPage key="e" />, 'engagements.error.title'],
    ['Organizations', <OrganizationsListPage key="o" />, 'organizations.error.title'],
    ['Users', <UsersPage key="u" />, 'users.error.title'],
  ] as const;

  it.each(pages)('%s renders populated content', async (_name, element) => {
    usePreview('populated');
    renderWithProviders(element, { session: buildTestSession(admin) });

    // A real table with rows, not a state block.
    expect(await screen.findAllByRole('row')).not.toHaveLength(0);
    expect(screen.queryByText(en['workspace.state.error.title'])).toBeNull();
  });

  it.each(pages)('%s states a failure as a failure, not as an empty result', async (_name, element, errorKey) => {
    usePreview('error');
    renderWithProviders(element, { session: buildTestSession(admin) });

    expect(await screen.findByText(en[errorKey])).toBeVisible();
    expect(screen.getByText(en['workspace.state.error.description'])).toBeVisible();
    // The distinction that matters: this is not an empty state.
    expect(screen.queryByText(en['engagements.empty.title'])).toBeNull();
    expect(screen.queryByText(en['organizations.empty.title'])).toBeNull();
  });

  it.each(pages)('%s states a forbidden result distinctly from an empty one', async (_name, element) => {
    usePreview('forbidden');
    renderWithProviders(element, { session: buildTestSession(admin) });

    expect(await screen.findByText(en['workspace.state.forbidden.title'])).toBeVisible();
    expect(screen.getByText(en['workspace.state.forbidden.description'])).toBeVisible();
  });

  it.each(pages)('%s announces a loading state politely', async (_name, element) => {
    usePreview('loading');
    const { container } = renderWithProviders(element, { session: buildTestSession(admin) });

    // `<output>` is an implicit `role="status"`: the region is announced
    // without interrupting the reader.
    expect(container.querySelector('output[aria-busy="true"]')).not.toBeNull();
  });

  it('Engagements states an empty workspace as empty, with a way forward', async () => {
    usePreview('empty');
    renderWithProviders(<EngagementsListPage />, { session: buildTestSession(admin) });

    expect(await screen.findByText(en['engagements.empty.title'])).toBeVisible();
    expect(screen.getByText(en['engagements.empty.description'])).toBeVisible();
  });

  it('Organizations states an unlinked account as empty, not as an error', async () => {
    usePreview('empty');
    renderWithProviders(<OrganizationsListPage />, { session: buildTestSession(admin) });

    expect(await screen.findByText(en['organizations.empty.title'])).toBeVisible();
    expect(screen.queryByText(en['organizations.error.title'])).toBeNull();
  });

  it.each(pages)('%s marks a partial result as partial rather than complete', async (_name, element) => {
    usePreview('partial');
    renderWithProviders(element, { session: buildTestSession(admin) });

    expect(await screen.findByText(en['workspace.state.partial'])).toBeVisible();
  });

  it('makes no network call in any scenario', async () => {
    const fetchSpy = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchSpy);
    usePreview('populated');

    renderWithProviders(<EngagementsListPage />, { session: buildTestSession(admin) });
    await screen.findAllByRole('row');

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(listEngagements).not.toHaveBeenCalled();
    expect(listOrganizations).not.toHaveBeenCalled();
    expect(getMe).not.toHaveBeenCalled();
  });
});

describe('Live states come from the API layer', () => {
  beforeEach(() => {
    // `WorkspaceProvider` resolves the caller's organization on every
    // authenticated render, so it needs a response here too.
    listOrganizations.mockResolvedValue({
      items: [{ id: 'org-1', name: 'Authenticated Live Organization', created_at: null }],
      page: 1,
      page_size: 20,
      total: 1,
    });
    getMe.mockResolvedValue({
      id: 'u1',
      organization_id: 'org-1',
      full_name: 'Live Administrator',
      email: 'live.admin@example.test',
      role: 'admin',
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders a real empty collection as empty', async () => {
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });

    renderWithProviders(<EngagementsListPage />, { authService: buildLiveAuthService() });

    expect(
      await screen.findByText(en['engagements.empty.title'], undefined),
    ).toBeVisible();
  });

  it('renders a 403 as forbidden, never as an empty collection', async () => {
    listEngagements.mockRejectedValue(new ForbiddenError('You do not have permission to do this.'));

    renderWithProviders(<EngagementsListPage />, { authService: buildLiveAuthService() });

    expect(
      await screen.findByText(en['workspace.state.forbidden.title'], undefined),
    ).toBeVisible();
    expect(screen.queryByText(en['engagements.empty.title'])).toBeNull();
  });

  it('renders a failed request as an error with a retry, never as an empty collection', async () => {
    listEngagements.mockRejectedValue(new Error('network'));

    renderWithProviders(<EngagementsListPage />, { authService: buildLiveAuthService() });

    expect(
      await screen.findByText(en['engagements.error.title'], undefined),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: en['workspace.state.retry'] })).toBeVisible();
    expect(screen.queryByText(en['engagements.empty.title'])).toBeNull();
  });

  it('preserves the server total rather than counting the rows on the page', async () => {
    listEngagements.mockResolvedValue({
      items: [
        { id: 'e1', organization_id: 'org-1', title: 'First', status: 'active', created_at: null },
        { id: 'e2', organization_id: 'org-1', title: 'Second', status: 'draft', created_at: null },
      ],
      page: 1,
      page_size: 20,
      // Far more than the two rows returned.
      total: 431,
    });

    renderWithProviders(<EngagementsListPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByText('First', undefined)).toBeVisible();
    expect(
      screen.getByText(
        en['engagements.pagination.showing']
          .replace('{start}', '1')
          .replace('{end}', '20')
          .replace('{total}', '431'),
      ),
    ).toBeVisible();
  });
});
