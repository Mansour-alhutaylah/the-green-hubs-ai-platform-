import { createContext, useContext } from 'react';

export interface Workspace {
  id: string;
  name: string;
}

export type WorkspaceStatus = 'loading' | 'ready' | 'no-organization' | 'error';

export interface WorkspaceContextValue {
  status: WorkspaceStatus;
  organization: Workspace | null;
  error: string | null;
  retry: () => void;
}

/**
 * Kept in its own module (not alongside WorkspaceProvider) so
 * WorkspaceProvider.tsx only ever exports the component — mixing a plain
 * `createContext()` value or a hook into a component file breaks React
 * Fast Refresh.
 */
export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspace(): WorkspaceContextValue {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('useWorkspace must be used within a WorkspaceProvider');
  return context;
}
