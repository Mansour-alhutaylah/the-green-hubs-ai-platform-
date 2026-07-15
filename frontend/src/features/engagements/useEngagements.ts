import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/features/auth/useAuth';
import { listEngagements } from '@/lib/api/endpoints/engagements';
import { ApiError, RequestAbortedError } from '@/lib/api/errors';
import { MOCK_DOCUMENTS } from '@/features/documents/mockDocuments';

export interface EngagementOption {
  id: string;
  title: string;
}

export type EngagementsStatus = 'loading' | 'ready' | 'error';

export interface EngagementsState {
  status: EngagementsStatus;
  engagements: EngagementOption[];
  error: string | null;
  retry: () => void;
}

/** Demo has no dedicated engagement entity — every seeded document already
 * carries a plain-string `engagement` name (see mockDocuments.ts), so this
 * reuses those distinct names as the demo engagement list rather than
 * inventing a second, parallel fixture module. */
const DEMO_ENGAGEMENTS: EngagementOption[] = Array.from(
  new Set(MOCK_DOCUMENTS.map((document) => document.engagement)),
).map((name) => ({ id: name, title: name }));

type InternalState = Omit<EngagementsState, 'retry'>;

const IDLE_STATE: InternalState = { status: 'loading', engagements: [], error: null };

/** Loads the caller's Engagements — demo mode reuses the local fixture
 * list above with no network call; live mode calls
 * `GET /api/v1/engagements`, never sending a client-supplied
 * `organization_id` (tenant scope is derived server-side). */
export function useEngagements(): EngagementsState {
  const { status: authStatus, sessionKind, activeOrgId } = useAuth();
  const [state, setState] = useState<InternalState>(IDLE_STATE);
  const [retryToken, setRetryToken] = useState(0);
  const isLive = sessionKind === 'live';

  useEffect(() => {
    if (authStatus !== 'authenticated') {
      setState(IDLE_STATE);
      return;
    }

    if (!isLive) {
      setState({ status: 'ready', engagements: DEMO_ENGAGEMENTS, error: null });
      return;
    }

    if (!activeOrgId) {
      setState({ status: 'ready', engagements: [], error: null });
      return;
    }

    const controller = new AbortController();
    setState({ status: 'loading', engagements: [], error: null });

    listEngagements({ page_size: 100 }, controller.signal)
      .then((response) => {
        setState({
          status: 'ready',
          engagements: response.items.map((item) => ({ id: item.id, title: item.title })),
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (error instanceof RequestAbortedError) return;
        setState({
          status: 'error',
          engagements: [],
          error: error instanceof ApiError || error instanceof Error
            ? error.message
            : 'Unable to load engagements.',
        });
      });

    return () => controller.abort();
  }, [authStatus, isLive, activeOrgId, retryToken]);

  const retry = useCallback(() => setRetryToken((token) => token + 1), []);

  return { ...state, retry };
}
