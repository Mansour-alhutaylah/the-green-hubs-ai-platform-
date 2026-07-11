import { useCallback, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';
import { Toast, type ToastItem } from './Toast';
import { ToastContext, type ToastContextValue, type ShowToastOptions } from './context';

const AUTO_DISMISS_MS = 6000;
const MAX_VISIBLE = 3;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const { dir } = useLocale();
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const scheduleDismiss = useCallback(
    (id: string) => {
      const timer = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
      timers.current.set(id, timer);
    },
    [dismiss],
  );

  const pause = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) clearTimeout(timer);
  }, []);

  const resume = useCallback(
    (id: string) => {
      scheduleDismiss(id);
    },
    [scheduleDismiss],
  );

  const showToast = useCallback(
    (message: string, options?: ShowToastOptions) => {
      const id = crypto.randomUUID();
      const toast: ToastItem = {
        id,
        message,
        kind: options?.kind ?? 'default',
        actionLabel: options?.actionLabel,
        onAction: options?.onAction,
      };
      setToasts((prev) => [...prev, toast].slice(-MAX_VISIBLE));
      scheduleDismiss(id);
    },
    [scheduleDismiss],
  );

  const value = useMemo<ToastContextValue>(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div
          className={cn(
            'fixed bottom-6 z-[var(--z-toast)] flex flex-col gap-3',
            dir === 'rtl' ? 'left-6' : 'right-6',
          )}
        >
          {toasts.map((toast) => (
            <div
              key={toast.id}
              onMouseEnter={() => pause(toast.id)}
              onMouseLeave={() => resume(toast.id)}
            >
              <Toast toast={toast} onDismiss={dismiss} />
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}
