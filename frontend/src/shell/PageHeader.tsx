import type { ReactNode } from 'react';

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  action?: ReactNode;
}

/** §8/§10.1: every page's single `h1`, plus an optional subtitle line and
 * a right-aligned primary action slot. */
export function PageHeader({ title, subtitle, eyebrow, action }: PageHeaderProps) {
  return (
    <header className="page-header-frame panel-enter mb-5 rounded-xl border border-leaf-300/70 px-5 py-5 sm:mb-6 sm:px-6 sm:py-6">
      <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {eyebrow && (
            <p className="type-label mb-2 flex items-center gap-2 text-leaf-700">
              <span className="h-1.5 w-1.5 rounded-full bg-leaf-500" aria-hidden />
              {eyebrow}
            </p>
          )}
          <h1 className="text-display text-forest-900 sm:text-hero">{title}</h1>
          {subtitle && <p className="mt-2 max-w-3xl text-body text-gray-600">{subtitle}</p>}
        </div>
        {action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}
      </div>
    </header>
  );
}
