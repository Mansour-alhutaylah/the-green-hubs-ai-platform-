import type { ReactNode } from 'react';

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}

/** §8/§10.1: every page's single `h1`, plus an optional subtitle line and
 * a right-aligned primary action slot. */
export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="mb-8 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-display text-forest-900">{title}</h1>
        {subtitle && <p className="mt-1 text-body text-gray-600">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
