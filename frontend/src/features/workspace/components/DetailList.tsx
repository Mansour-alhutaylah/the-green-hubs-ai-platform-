import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

export interface DetailItem {
  /** Stable key — never the translated label, which changes with locale. */
  id: string;
  label: string;
  value: ReactNode;
}

/**
 * The shared label/value block for a detail page.
 *
 * A real `<dl>`, so each label is programmatically associated with its
 * value rather than merely sitting above it — a screen reader announces
 * "Created, 12 January 2026", not two unrelated strings.
 *
 * Stacked on a phone and two-column from `sm` up. The value column is
 * `min-w-0` with `break-words`, because the things that land here (an
 * organization name, an engagement title, an email address) are
 * user-supplied and arbitrarily long; without it a single long token
 * pushes the whole page sideways at 360px.
 */
export function DetailList({ items, className }: { items: readonly DetailItem[]; className?: string }) {
  return (
    <dl className={cn('grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-[12rem_minmax(0,1fr)]', className)}>
      {items.map((item) => (
        <div key={item.id} className="contents">
          <dt className="text-meta font-bold text-ink-900">{item.label}</dt>
          <dd className="min-w-0 break-words text-body text-gray-600">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
