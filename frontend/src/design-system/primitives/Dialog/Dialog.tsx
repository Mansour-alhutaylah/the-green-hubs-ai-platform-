import type { ReactNode } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { cn } from '@/lib/utils/cn';

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  /** Blocks Esc/overlay-click dismissal — spec §15: "Esc + overlay-click
   * close (blocked while submitting)". */
  preventClose?: boolean;
  /** 480px default, 560px for form dialogs (§15). */
  variant?: 'default' | 'form';
}

/** §15/§18: overlay rgba(18,38,24,.4), card radius-l, 28px padding,
 * shadow-float; fade + translateY(8→0) 200ms entrance; focus trapped by
 * Radix, restored to the trigger on close automatically. */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  preventClose,
  variant = 'default',
}: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[var(--z-overlay)] bg-overlay [animation:overlay-fade-in_var(--motion-base)_var(--ease-out)]" />
        <DialogPrimitive.Content
          onEscapeKeyDown={(event) => preventClose && event.preventDefault()}
          onPointerDownOutside={(event) => preventClose && event.preventDefault()}
          className={cn(
            'fixed left-1/2 top-1/2 z-[var(--z-dialog)] w-full -translate-x-1/2 -translate-y-1/2 rounded-l bg-surface-0 p-7 shadow-float',
            '[animation:dialog-content-in_var(--motion-base)_var(--ease-out)]',
            variant === 'form' ? 'max-w-140' : 'max-w-120',
          )}
        >
          <DialogPrimitive.Title className="text-title text-forest-900">
            {title}
          </DialogPrimitive.Title>
          {description && (
            <DialogPrimitive.Description className="mt-2 text-body text-gray-600">
              {description}
            </DialogPrimitive.Description>
          )}
          {children && <div className="mt-4">{children}</div>}
          {footer && <div className="mt-6 flex justify-end gap-3">{footer}</div>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
