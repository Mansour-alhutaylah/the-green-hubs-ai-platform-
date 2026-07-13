import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

export interface SectionCardProps {
  children: ReactNode;
  title?: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  contentClassName?: string;
}

/** Shared enterprise surface for feature-level panels and state previews. */
export function SectionCard({
  children,
  title,
  description,
  action,
  className,
  contentClassName,
}: SectionCardProps) {
  return (
    <section
      className={cn(
        'overflow-hidden rounded-l border border-line-200 bg-surface-0 shadow-card',
        className,
      )}
    >
      {(title || description || action) && (
        <div className="flex flex-col gap-3 border-b border-line-200 px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-5">
          <div className="min-w-0">
            {title && <h2 className="text-panel text-forest-900">{title}</h2>}
            {description && <p className="mt-1 text-meta text-gray-600">{description}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={cn('p-4 sm:p-5', contentClassName)}>{children}</div>
    </section>
  );
}
