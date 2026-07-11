import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';
import { DiamondGlyph, type DiamondVariant } from '../DiamondGlyph/DiamondGlyph';

export type ToastKind = 'default' | 'success' | 'warning';

export interface ToastItem {
  id: string;
  kind: ToastKind;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

const GLYPH_BY_KIND: Record<ToastKind, DiamondVariant> = {
  default: 'hollow',
  success: 'filled',
  warning: 'warning',
};

const COLOR_BY_KIND: Record<ToastKind, string> = {
  default: 'text-white',
  success: 'text-leaf-500',
  warning: 'text-amber-100',
};

/** §15: "Forest bg, white text 13px, radius 6, diamond glyph by kind,
 * optional action link (Leaf-300), autodismiss 6s (paused on hover)." */
export function Toast({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}): ReactNode {
  return (
    <output className="flex w-90 items-start gap-3 rounded-m bg-forest-900 p-4 text-meta text-white shadow-float [animation:toast-in_var(--motion-base)_var(--ease-out)]">
      <DiamondGlyph
        variant={GLYPH_BY_KIND[toast.kind]}
        size={10}
        className={cn('mt-0.5', COLOR_BY_KIND[toast.kind])}
      />
      <div className="flex-1">
        <p>{toast.message}</p>
        {toast.actionLabel && (
          <button
            type="button"
            onClick={toast.onAction}
            className="mt-1 text-leaf-300 underline underline-offset-2"
          >
            {toast.actionLabel}
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="text-rail-text hover:text-white"
      >
        ×
      </button>
    </output>
  );
}
