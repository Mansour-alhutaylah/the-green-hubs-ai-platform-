import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { AuthProvider } from '@/features/auth/AuthContext';
import { WorkspaceProvider } from '../WorkspaceProvider';
import { useWorkspace } from '../WorkspaceContext';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { DEMO_WORKSPACE_ORG_ID } from '@/features/organizations/mockOrgs';
import type { OrganizationListResponse } from '@/lib/api/types';
import { ApiError } from '@/lib/api/errors';

const listOrganizations = vi.fn<() => Promise<OrganizationListResponse>>();

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: (...args: unknown[]) => listOrganizations(...(args as [])),
}));

function Probe() {
  const workspace = useWorkspace();
  return (
    <div>
      <p data-testid="status">{workspace.status}</p>
      <p data-testid="org-name">{workspace.organization?.name ?? ''}</p>
      <p data-testid="error">{workspace.error ?? ''}</p>
      <button type="button" onClick={workspace.retry}>
        retry
      </button>
    </div>
  );
}

function buildDemoSession(): Session {
  return {
    kind: 'preview',
    user: { id: 'user-admin', name: 'Mansour', email: 'admin@demo.greenhubs.sa', role: Role.Admin, orgIds: [DEMO_WORKSPACE_ORG_ID] },
    token: 'local-development-demo-session',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId: DEMO_WORKSPACE_ORG_ID,
  };
}

function buildLiveAuthService(activeOrgId: string | null): AuthService {
  const session: Session = {
    kind: 'live',
    user: { id: 'user-1', name: 'Reem', email: 'reem@example.com', role: Role.Admin, orgIds: activeOrgId ? [activeOrgId] : [] },
    token: 'supabase-session',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId,
  };
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused');
    },
    async logout(): Promise<void> {},
    getSession: () => null,
    setActiveOrg: () => null,
    restoreSession: async () => session,
  };
}

function renderProbe(service: AuthService) {
  return render(
    <MemoryRouter>
      <LocaleProvider>
        <AuthProvider service={service}>
          <WorkspaceProvider>
            <Probe />
          </WorkspaceProvider>
        </AuthProvider>
      </LocaleProvider>
    </MemoryRouter>,
  );
}

function buildDemoAuthService(): AuthService {
  const session = buildDemoSession();
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused');
    },
    async logout(): Promise<void> {},
    getSession: () => session,
    setActiveOrg: () => null,
  };
}

describe('WorkspaceProvider', () => {
  beforeEach(() => {
    listOrganizations.mockReset();
  });

  it('resolves the demo organization synchronously, with no backend request', async () => {
    renderProbe(buildDemoAuthService());

    expect(await screen.findByText('ready', {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByTestId('org-name')).toHaveTextContent('The Green Hubs Demo Workspace');
    expect(listOrganizations).not.toHaveBeenCalled();
  });

  it('loads the real organization for a live session', async () => {
    listOrganizations.mockResolvedValue({ items: [{ id: 'org-1', name: 'Al-Riyadh Industrial Group', created_at: null }], page: 1, page_size: 1, total: 1 });

    renderProbe(buildLiveAuthService('org-1'));

    expect(await screen.findByText('ready', {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByTestId('org-name')).toHaveTextContent('Al-Riyadh Industrial Group');
  });

  it('resolves "no-organization" for a live user with no organization_id, without calling the backend', async () => {
    renderProbe(buildLiveAuthService(null));

    expect(await screen.findByText('no-organization', {}, { timeout: 5000 })).toBeInTheDocument();
    expect(listOrganizations).not.toHaveBeenCalled();
  });

  it('surfaces a retry-able error on a backend failure', async () => {
    listOrganizations.mockRejectedValueOnce(new ApiError(500, 'Something went wrong on our end. Try again.'));
    listOrganizations.mockResolvedValueOnce({ items: [{ id: 'org-1', name: 'Al-Riyadh Industrial Group', created_at: null }], page: 1, page_size: 1, total: 1 });

    renderProbe(buildLiveAuthService('org-1'));

    expect(await screen.findByText('error', {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByTestId('error')).toHaveTextContent(/something went wrong/i);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'retry' }));

    expect(await screen.findByText('ready', {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByTestId('org-name')).toHaveTextContent('Al-Riyadh Industrial Group');
  });
});
