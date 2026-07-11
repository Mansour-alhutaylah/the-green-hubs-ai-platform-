import { createContext, useContext } from 'react';
import type { ToastKind } from './Toast';

export interface ShowToastOptions {
  kind?: ToastKind;
  actionLabel?: string;
  onAction?: () => void;
}

export interface ToastContextValue {
  showToast: (message: string, options?: ShowToastOptions) => void;
}

/**
 * Kept in its own module (not alongside ToastProvider) so
 * ToastProvider.tsx only ever exports the component — mixing a plain
 * `createContext()` value or a hook into a component file breaks React
 * Fast Refresh.
 */
export const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within a ToastProvider');
  return context;
}
