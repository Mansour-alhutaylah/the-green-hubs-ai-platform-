import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

export interface BadgeProps {
  children: ReactNode;
  className?: string;
}

/** Generic hairline-bordered label chip (§15 Badge/RoleBadge family). */
export function Badge({ children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'type-label inline-flex items-center gap-1 rounded-s border border-line-200 px-2 py-0.5 text-ink-900',
        className,
      )}
    >
      {children}
    </span>
  );
}
