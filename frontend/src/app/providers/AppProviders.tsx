import type { ReactNode } from 'react';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { AuthProvider } from '@/features/auth/AuthContext';
import { WorkspaceProvider } from '@/features/organizations/workspace/WorkspaceProvider';
import { TooltipProvider, ToastProvider } from '@/design-system';

/** Composition root for every cross-cutting context the shell needs.
 * `WorkspaceProvider` sits inside `AuthProvider` because it reads
 * `useAuth()` (session kind, active org). */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <LocaleProvider>
      <AuthProvider>
        <WorkspaceProvider>
          <TooltipProvider>
            <ToastProvider>{children}</ToastProvider>
          </TooltipProvider>
        </WorkspaceProvider>
      </AuthProvider>
    </LocaleProvider>
  );
}
