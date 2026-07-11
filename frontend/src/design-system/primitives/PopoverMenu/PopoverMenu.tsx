import type { ReactNode } from 'react';
import * as PopoverPrimitive from '@radix-ui/react-popover';
import { cn } from '@/lib/utils/cn';

export interface PopoverMenuProps {
  trigger: ReactNode;
  children: ReactNode;
  align?: 'start' | 'center' | 'end';
  sideOffset?: number;
  /** Uncontrolled by default (Radix manages its own open state) — pass
   * both to control it, e.g. so a selection can close the menu itself
   * (OrgSwitcher). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  contentClassName?: string;
}

/**
 * Shared "overlay card anchored to a trigger" shell behind the Context
 * Bar's org switcher, notifications bell, and profile menu (§3.2) — those
 * three previously hand-rolled the same Radix Popover + card styling
 * independently. One definition of the overlay's chrome (radius, hairline,
 * shadow, z-index) instead of three.
 */
export function PopoverMenu({
  trigger,
  children,
  align = 'end',
  sideOffset = 8,
  open,
  onOpenChange,
  contentClassName,
}: PopoverMenuProps) {
  return (
    <PopoverPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align={align}
          sideOffset={sideOffset}
          className={cn(
            'z-[var(--z-overlay)] rounded-m border border-line-200 bg-surface-0 shadow-float',
            contentClassName,
          )}
        >
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
