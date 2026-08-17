import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService, LIVE_USER_EMAIL, LIVE_USER_NAME } from '@/test/liveSession';
import { buildTestSession } from '@/test/renderWithProviders';
import { TEST_USERS } from '@/test/testUsers';
import { Role } from '@/features/rbac/roles';
import { en } from '@/lib/i18n/strings/en';
import type { UserProfileResponse } from '@/lib/api/types';
import { PREVIEW_TEAM_MEMBERS } from '@/lib/data/fixtures/previewWorkspace';
import { UsersPage } from '../pages/UsersPage';

/**
 * Users & Roles is the page most likely to be quietly filled in with
 * invention, because a team directory is what everyone expects to find
 * here and the backend has no endpoint for one.
 *
 * Live must therefore show exactly one person — the caller, from
 * `GET /api/v1/auth/me` — and say why. Preview may show a full directory,
 * provided every identity in it is obviously synthetic.
 */

const getMe = vi.fn<() => Promise<UserProfileResponse>>();

vi.mock('@/lib/api/endpoints/auth', () => ({
  getMe: (...args: unknown[]) => getMe(...(args as [])),
}));

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: 'org-1', name: 'Authenticated Live Organization', created_at: null }],
    page: 1,
    page_size: 20,
    total: 1,
  }),
}));

describe('Users & Roles — Live', () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  it('shows only the authenticated identity the backend actually returns', async () => {
    getMe.mockResolvedValue({
      id: 'user-live-1',
      organization_id: 'org-1',
      full_name: LIVE_USER_NAME,
      email: LIVE_USER_EMAIL,
      role: 'admin',
    });

    renderWithProviders(<UsersPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByText(LIVE_USER_NAME, undefined)).toBeVisible();
    expect(screen.getByText(LIVE_USER_EMAIL)).toBeVisible();
    expect(screen.getByText(en['users.you'])).toBeVisible();

    // Exactly one person. A second row would be an invention.
    const rows = screen.getAllByRole('row');
    // One header row plus one body row.
    expect(rows).toHaveLength(2);
  });

  it('states that this is an account, not a directory, and why', async () => {
    getMe.mockResolvedValue({
      id: 'user-live-1',
      organization_id: 'org-1',
      full_name: LIVE_USER_NAME,
      email: LIVE_USER_EMAIL,
      role: 'admin',
    });

    renderWithProviders(<UsersPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByText(en['users.live.disclosure.title'])).toBeVisible();
    expect(screen.getByText(en['users.live.disclosure.description'])).toBeVisible();
  });

  it('offers no invitation, role-change, or removal control', async () => {
    getMe.mockResolvedValue({
      id: 'user-live-1',
      organization_id: 'org-1',
      full_name: LIVE_USER_NAME,
      email: LIVE_USER_EMAIL,
      role: 'admin',
    });

    renderWithProviders(<UsersPage />, { authService: buildLiveAuthService() });
    await screen.findByText(LIVE_USER_NAME);

    for (const pattern of [/invite/i, /add user/i, /change role/i, /remove/i, /delete/i, /resend/i]) {
      expect(screen.queryByRole('button', { name: pattern })).toBeNull();
      expect(screen.queryByRole('link', { name: pattern })).toBeNull();
    }
  });

  it('names an unrecognized stored role instead of defaulting it to a tier', async () => {
    getMe.mockResolvedValue({
      id: 'user-live-1',
      organization_id: 'org-1',
      full_name: LIVE_USER_NAME,
      email: LIVE_USER_EMAIL,
      // `users.role` is a free-form nullable column; the backend denies
      // every permission for a value outside its enum.
      role: 'super-duper-admin',
    });

    renderWithProviders(<UsersPage />, { authService: buildLiveAuthService() });

    expect(await screen.findByText(en['users.role.unrecognized'])).toBeVisible();
  });

  it('renders no Preview fixture identity', async () => {
    getMe.mockResolvedValue({
      id: 'user-live-1',
      organization_id: 'org-1',
      full_name: LIVE_USER_NAME,
      email: LIVE_USER_EMAIL,
      role: 'admin',
    });

    renderWithProviders(<UsersPage />, { authService: buildLiveAuthService() });
    await screen.findByText(LIVE_USER_NAME);

    for (const member of PREVIEW_TEAM_MEMBERS) {
      expect(
        screen.queryByText(member.email),
        `Live mode must not render the Preview identity "${member.email}"`,
      ).toBeNull();
    }
  });
});

describe('Users & Roles — Preview', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  function renderPreview() {
    vi.stubEnv('VITE_APP_MODE', 'preview');
    vi.stubEnv('VITE_APP_ENVIRONMENT', 'preview');
    const admin = TEST_USERS.find((user) => user.role === Role.Admin)!;
    return renderWithProviders(<UsersPage />, { session: buildTestSession(admin) });
  }

  it('shows every canonical role tier', async () => {
    renderPreview();

    for (const member of PREVIEW_TEAM_MEMBERS) {
      expect(await screen.findByText(member.fullName)).toBeVisible();
    }

    const roles = new Set(PREVIEW_TEAM_MEMBERS.map((member) => member.role));
    for (const role of [Role.Owner, Role.Admin, Role.Approver, Role.Editor, Role.Viewer]) {
      expect(roles.has(role)).toBe(true);
    }
  });

  it('uses only obviously synthetic identities on a reserved, unroutable domain', () => {
    renderPreview();

    for (const member of PREVIEW_TEAM_MEMBERS) {
      // RFC 2606 reserves `.invalid`: none of these can ever be delivered
      // to, and none can be mistaken for a real person's address.
      expect(member.email.endsWith('@preview.invalid')).toBe(true);
      expect(member.source).toBe('preview-fixture');
    }
  });

  it('labels the directory as synthetic and offers no management control', async () => {
    renderPreview();

    expect(await screen.findByText(en['users.preview.disclosure.title'])).toBeVisible();
    expect(screen.getByText(en['users.preview.disclosure.description'])).toBeVisible();

    for (const pattern of [/invite/i, /change role/i, /remove/i]) {
      expect(screen.queryByRole('button', { name: pattern })).toBeNull();
    }
  });

  it('makes no network call of any kind', () => {
    const fetchSpy = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchSpy);

    renderPreview();

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(getMe).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
