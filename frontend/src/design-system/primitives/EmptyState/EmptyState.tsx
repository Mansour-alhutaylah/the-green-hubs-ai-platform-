import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';
import { DiamondGlyph } from '../DiamondGlyph/DiamondGlyph';

export interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  /** §17: "one h1 per page." Most EmptyState usages sit inside a page that
   * already has its own PageHeader `<h1>` (a placeholder module, a panel),
   * so this defaults to `<h2>` — but the handful of routes that render
   * *only* an EmptyState (404, no-access, the route error boundary) have
   * no other heading on the page and must pass `headingLevel={1}` or a
   * screen reader gets a heading-less page. */
  headingLevel?: 1 | 2;
}

/** §14.7 anatomy, verbatim: hollow 32px diamond → 16/800 Forest headline →
 * one 13px gray-600 sentence → one optional primary action. Voice is
 * instructive, never apologetic (never "No data found"). */
export function EmptyState({
  title,
  description,
  action,
  className,
  headingLevel = 2,
}: EmptyStateProps) {
  const Heading = headingLevel === 1 ? 'h1' : 'h2';
  return (
    <div className={cn('mx-auto flex max-w-90 flex-col items-center py-12 text-center', className)}>
      <DiamondGlyph variant="hollow" size={32} className="text-gray-400" />
      <Heading className="mt-4 text-panel text-forest-900">{title}</Heading>
      {description && <p className="mt-1.5 text-meta text-gray-600">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
