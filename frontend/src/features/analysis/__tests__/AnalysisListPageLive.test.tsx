import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AuthProvider } from '@/features/auth/AuthContext';
import { WorkspaceProvider } from '@/features/organizations/workspace/WorkspaceProvider';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { TooltipProvider, ToastProvider } from '@/design-system';
import type { AuthService, LoginResult } from '@/features/auth/services/AuthService';
import type { Session } from '@/features/auth/types';
import { Role } from '@/features/rbac/roles';
import { AnalysisListPage } from '../pages/AnalysisListPage';
import { MOCK_ANALYSIS_RUNS } from '../mockAnalysisData';

vi.mock('@/lib/api/endpoints/organizations', () => ({
  listOrganizations: async () => ({
    items: [{ id: 'org-1', name: 'Al-Riyadh Industrial Group', created_at: null }],
    page: 1,
    page_size: 1,
    total: 1,
  }),
}));

vi.mock('@/lib/api/endpoints/engagements', () => ({
  listEngagements: async () => ({ items: [], page: 1, page_size: 100, total: 0 }),
}));

function buildLiveSession(): Session {
  return {
    kind: 'live',
    user: { id: 'user-1', name: 'Reem Al-Harbi', email: 'reem@example.com', role: Role.Admin, orgIds: ['org-1'] },
    token: 'supabase-session',
    expiresAt: Date.now() + 60 * 60 * 1000,
    activeOrgId: 'org-1',
  };
}

function buildLiveAuthService(): AuthService {
  return {
    async requestLogin(): Promise<LoginResult> {
      throw new Error('unused');
    },
    async verifyOtp(): Promise<Session> {
      throw new Error('unused');
    },
    async resendOtp(): Promise<void> {},
    async logout(): Promise<void> {},
    getSession: () => null,
    setActiveOrg: () => null,
    restoreSession: async () => buildLiveSession(),
  };
}

function renderList() {
  return render(
    <MemoryRouter initialEntries={['/analysis']}>
      <LocaleProvider>
        <AuthProvider service={buildLiveAuthService()}>
          <WorkspaceProvider>
            <TooltipProvider>
              <ToastProvider>
                <Routes>
                  <Route path="/analysis" element={<AnalysisListPage />} />
                </Routes>
              </ToastProvider>
            </TooltipProvider>
          </WorkspaceProvider>
        </AuthProvider>
      </LocaleProvider>
    </MemoryRouter>,
  );
}

describe('AnalysisListPage — live mode', () => {
  it('shows a truthful limited state instead of fabricating an analysis history', async () => {
    renderList();

    expect(
      await screen.findByText('Analysis history is not available yet', {}, { timeout: 5000 }),
    ).toBeVisible();
    expect(screen.getByRole('link', { name: /go to documents/i })).toHaveAttribute('href', '/documents');
  });

  it('never shows demo analysis rows or sample badges in live mode', async () => {
    renderList();

    await screen.findByText('Analysis history is not available yet', {}, { timeout: 5000 });
    for (const run of MOCK_ANALYSIS_RUNS) {
      expect(screen.queryByText(run.documentName)).not.toBeInTheDocument();
      expect(screen.queryByText(run.analysisName)).not.toBeInTheDocument();
    }
    expect(screen.queryByText(/sample data/i)).not.toBeInTheDocument();
  });
});
