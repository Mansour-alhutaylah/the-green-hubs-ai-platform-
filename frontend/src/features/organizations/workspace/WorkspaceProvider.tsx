import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useAuth } from '@/features/auth/useAuth';
import { useLocale } from '@/lib/i18n/useLocale';
import { listOrganizations } from '@/lib/api/endpoints/organizations';
import { ApiError, RequestAbortedError } from '@/lib/api/errors';
import { findOrganization, localizedOrgName } from '../mockOrgs';
import { WorkspaceContext, type Workspace, type WorkspaceContextValue, type WorkspaceStatus } from './WorkspaceContext';

interface InternalState {
  status: WorkspaceStatus;
  organization: Workspace | null;
  error: string | null;
}

const IDLE_STATE: InternalState = { status: 'loading', organization: null, error: null };

/**
 * Resolves the active workspace: in demo mode, the seeded mock
 * organization for `activeOrgId` (unchanged local lookup, no network); in
 * live mode, the caller's single real organization via
 * `GET /api/v1/organizations` — never a client-invented multi-org list.
 * Only `'live'` ever fetches; every other session kind (including no
 * session) resolves synchronously from local data, so this never issues a
 * request in demo mode.
 */
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { status: authStatus, sessionKind, activeOrgId } = useAuth();
  const { locale } = useLocale();
  const [state, setState] = useState<InternalState>(IDLE_STATE);
  const [retryToken, setRetryToken] = useState(0);
  const isLive = sessionKind === 'live';

  useEffect(() => {
    if (authStatus !== 'authenticated') {
      setState(IDLE_STATE);
      return;
    }

    if (!isLive) {
      const org = activeOrgId ? findOrganization(activeOrgId) : undefined;
      setState({
        status: org ? 'ready' : 'no-organization',
        organization: org ? { id: org.id, name: localizedOrgName(org, locale) } : null,
        error: null,
      });
      return;
    }

    if (!activeOrgId) {
      setState({ status: 'no-organization', organization: null, error: null });
      return;
    }

    const controller = new AbortController();
    setState({ status: 'loading', organization: null, error: null });

    listOrganizations(controller.signal)
      .then((response) => {
        const org = response.items[0];
        setState(
          org
            ? { status: 'ready', organization: { id: org.id, name: org.name }, error: null }
            : { status: 'no-organization', organization: null, error: null },
        );
      })
      .catch((error: unknown) => {
        if (error instanceof RequestAbortedError) return;
        setState({
          status: 'error',
          organization: null,
          error: error instanceof ApiError || error instanceof Error
            ? error.message
            : 'Unable to load your workspace.',
        });
      });

    return () => controller.abort();
  }, [authStatus, isLive, activeOrgId, locale, retryToken]);

  const retry = useCallback(() => setRetryToken((token) => token + 1), []);

  const value = useMemo<WorkspaceContextValue>(() => ({ ...state, retry }), [state, retry]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}
