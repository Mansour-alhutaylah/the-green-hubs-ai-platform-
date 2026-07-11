import type { ReactNode } from 'react';
import { LocaleProvider } from '@/lib/i18n/LocaleContext';
import { AuthProvider } from '@/features/auth/AuthContext';
import { TooltipProvider, ToastProvider } from '@/design-system';

/** Composition root for every cross-cutting context the shell needs.
 * Order matters only where one provider's children read another's context
 * — none of these do today, so this order is purely for readability. */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <LocaleProvider>
      <AuthProvider>
        <TooltipProvider>
          <ToastProvider>{children}</ToastProvider>
        </TooltipProvider>
      </AuthProvider>
    </LocaleProvider>
  );
}
