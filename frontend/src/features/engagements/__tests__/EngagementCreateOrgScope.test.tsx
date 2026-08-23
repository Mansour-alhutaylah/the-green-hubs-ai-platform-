import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import { buildLiveAuthService, LIVE_ORGANIZATION_ID } from '@/test/liveSession';
import { en } from '@/lib/i18n/strings/en';
import type { EngagementListResponse, EngagementResponse } from '@/lib/api/types';
import { EngagementsListPage } from '../pages/EngagementsListPage';

/**
 * Where the create request's `organization_id` comes from.
 *
 * `EngagementCreateRequest` requires the field, which makes it the one
 * place the Frontend sends an organization id at all — and therefore the
 * one place worth proving cannot be steered. The service does compare it
 * against the caller's own organization and answers 403 on a mismatch, but
 * relying on that alone would leave a UI that invites people to try, and
 * would break the moment a future endpoint is less strict.
 *
 * So this test drives the real page with hostile inputs in every
 * client-controlled channel at once — query string, route parameter, and
 * `localStorage` — and asserts the value that reaches the wire is the one
 * from the authenticated session and nothing else.
 */

type CreatePayload = { organization_id: string; title: string; status?: string };
const createEngagement = vi.fn<(payload: CreatePayload) => Promise<EngagementResponse>>();
const listEngagements = vi.fn<() => Promise<EngagementListResponse>>();

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: (...args: unknown[]) => listEngagements(...(args as [])),
  createEngagement: (...args: unknown[]) => createEngagement(...(args as [CreatePayload])),
  getEngagement: async () => {
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
}));

const ATTACKER_ORG_ID = 'org-belonging-to-someone-else';

describe('engagement creation uses only authenticated organization context', () => {
  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('sends the session organization, ignoring query, route, and stored values', async () => {
    const user = userEvent.setup();

    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });
    createEngagement.mockResolvedValue({
      id: 'eng-new',
      organization_id: LIVE_ORGANIZATION_ID,
      title: 'Annual disclosure',
      status: 'planning',
      created_at: null,
    });

    // Every client-controlled channel, poisoned at once.
    window.localStorage.setItem('ghp:activeOrg', ATTACKER_ORG_ID);
    window.localStorage.setItem('organization_id', ATTACKER_ORG_ID);

    renderWithProviders(<EngagementsListPage />, {
      authService: buildLiveAuthService(),
      initialEntries: [
        `/engagements?organization_id=${ATTACKER_ORG_ID}&org=${ATTACKER_ORG_ID}`,
      ],
    });

    await user.click(
      await screen.findByRole('button', { name: en['engagements.create.action'] }),
    );

    await user.type(
      await screen.findByLabelText(en['engagements.create.field.title']),
      'Annual disclosure',
    );
    await user.click(screen.getByRole('button', { name: en['engagements.create.submit'] }));

    await waitFor(() => expect(createEngagement).toHaveBeenCalledTimes(1));

    const payload = createEngagement.mock.calls[0]?.[0];
    expect(payload).toBeDefined();
    expect(payload?.organization_id).toBe(LIVE_ORGANIZATION_ID);
    expect(payload?.organization_id).not.toBe(ATTACKER_ORG_ID);
    expect(payload?.title).toBe('Annual disclosure');
  });

  it('offers no editable organization field for a person to point elsewhere', async () => {
    const user = userEvent.setup();
    listEngagements.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 });

    renderWithProviders(<EngagementsListPage />, {
      authService: buildLiveAuthService(),
      initialEntries: ['/engagements'],
    });

    await user.click(
      await screen.findByRole('button', { name: en['engagements.create.action'] }),
    );

    // The organization is read-only context, stated with its provenance.
    expect(
      await screen.findByText(en['engagements.create.organization.hint']),
    ).toBeVisible();

    // No control of any kind is bound to the organization.
    expect(
      screen.queryByLabelText(en['engagements.create.organization.label']),
    ).toBeNull();
    expect(screen.queryByRole('combobox', { name: /organization/i })).toBeNull();
    expect(screen.queryByRole('textbox', { name: /organization/i })).toBeNull();
  });
});
